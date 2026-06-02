"""
harvest.py — Read GitHub Copilot session event files and extract structured activity data.

CLI sessions are stored at ~/.copilot/session-state/<uuid>/events.jsonl
VS Code sessions are stored at <appdata>/Code/User/globalStorage/emptyWindowChatSessions/<uuid>.jsonl
"""
import json
import os as _os
import re as _re
import sys as _sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote as _url_unquote

SESSION_DIR = Path.home() / ".copilot" / "session-state"

_LOGIC_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".cs",
    ".cpp", ".c", ".h", ".hpp", ".sh", ".bash", ".zsh", ".ps1", ".rb",
    ".php", ".r", ".sql", ".kt", ".swift", ".dart", ".scala", ".ex", ".exs",
    ".vue", ".svelte", ".tf", ".hcl",
}

_APPROVALS = {
    "yes", "y", "yep", "yeah", "yup", "no", "n", "nope",
    "ok", "okay", "sure", "fine", "right", "correct",
    "proceed", "go ahead", "go for it", "do it", "do that",
    "looks good", "sounds good", "that's fine", "that works",
    "approved", "continue", "perfect", "great", "good",
    "got it", "understood", "makes sense",
}


def _is_approval(text: str) -> bool:
    """True if the message is purely an approval/permission grant."""
    cleaned = text.strip().rstrip(".!").lower()
    if _re.fullmatch(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', cleaned):
        return True
    if len(cleaned.split()) > 8:
        return False
    return cleaned in _APPROVALS


def _strip_injected_context(text: str) -> str:
    """Remove Copilot-injected XML context blocks from user message content."""
    text = _re.sub(r'<current_datetime>.*?</current_datetime>\s*', '', text, flags=_re.DOTALL)
    text = _re.sub(r'<reminder>.*?</reminder>\s*', '', text, flags=_re.DOTALL)
    text = _re.sub(r'<[a-z_]+>.*?</[a-z_]+>\s*', '', text, flags=_re.DOTALL)
    return text.strip()


def _read_workspace(path: Path) -> dict:
    """Parse workspace.yaml (simple key: value, single-level)."""
    result = {}
    if not path.exists():
        return result
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip()
                if ": " in line and not line.startswith(" "):
                    k, _, v = line.partition(": ")
                    result[k.strip()] = v.strip()
    except Exception:
        pass
    return result


_READ_ONLY_TOOLS = {"view", "grep", "glob", "report_intent",
                    "list_powershell", "list_agents"}

_BURN_PREMIUM_MODELS = {
    "claude-opus-4.5", "claude-opus-4.6", "claude-opus-4.7",
    "claude-opus-4.7-1m-internal", "claude-opus-4.7-high",
    "claude-opus-4.7-xhigh", "claude-opus-4.8",
}


def _burn_extract_path(args) -> str:
    """Return the first concrete file path referenced in a tool's arguments."""
    if not isinstance(args, dict):
        return ""
    p = args.get("path") or args.get("paths") or ""
    if isinstance(p, list):
        p = p[0] if p else ""
    if not isinstance(p, str):
        return ""
    if not p or "Temp" in p or "AppData\\Local\\Temp" in p:
        return ""
    return p


def _analyze_burn_patterns(events: list, target_date: str) -> list:
    """Mine session events for observable cost-saving opportunities.

    Returns a list of "burn findings". Each finding describes a behavioural
    pattern that coincided with credit spend, with the raw output-token
    count attributed via direct observation (never extrapolation):

    - hot_file: file touched 10+ times; observed tokens come from
      assistant.messages immediately adjacent to a tool call referencing
      that file (event-adjacent attribution, not a wide time-window slice).
    - fail_loop: same tool failing 3+ times within 10 minutes; observed
      tokens are asst.messages inside the retry window.
    - compaction_storm: 3+ compactions in the session; no token attribution
      (the overhead is contextual — every subsequent turn pays for the
      summary).
    - output_spike: a single assistant.message above 8K outputTokens on a
      premium model.
    - exploration_premium: 5+ consecutive read-only tool calls on a premium
      model; observed tokens are asst.messages inside the run.
    - broad_search_repeat: 5+ grep/glob calls in the session over the same
      broad root path; flag only, no token attribution.

    All findings are scoped to events whose timestamp falls on target_date
    (mirrors the date-filter pattern used elsewhere in this file).
    Returns raw observations — credit conversion happens in the renderer.
    """
    # Collect date-scoped, ordered tool starts/completes and assistant messages
    tool_starts: dict[str, dict] = {}      # toolCallId -> {name, args, ts, idx}
    tool_complete: dict[str, dict] = {}    # toolCallId -> {success}
    asst_msgs: list[dict] = []             # in chronological order
    compactions: list[dict] = []
    user_msgs: list[dict] = []             # post-context-strip user prompts

    for idx, e in enumerate(events):
        ts = e.get("timestamp", "") or ""
        if not ts or ts[:10] != target_date:
            continue
        t = e.get("type", "")
        d = e.get("data", {}) or {}
        if t == "tool.execution_start":
            tid = d.get("toolCallId")
            if tid:
                tool_starts[tid] = {
                    "name": d.get("toolName") or d.get("mcpToolName") or "",
                    "args": d.get("arguments") or {},
                    "ts": ts,
                    "idx": idx,
                }
        elif t == "tool.execution_complete":
            tid = d.get("toolCallId")
            if tid:
                tool_complete[tid] = {"success": d.get("success")}
        elif t == "assistant.message":
            out = d.get("outputTokens") or 0
            if isinstance(out, (int, float)) and out > 0:
                asst_msgs.append({
                    "tokens": int(out),
                    "model": d.get("model") or "",
                    "ts": ts,
                    "idx": idx,
                })
        elif t == "user.message":
            content = d.get("content") or ""
            if isinstance(content, str) and content.strip():
                cleaned = _strip_injected_context(content)
                if cleaned and not _is_approval(cleaned):
                    user_msgs.append({
                        "content": cleaned,
                        "ts": ts,
                        "idx": idx,
                    })
        elif t == "session.compaction_complete":
            # `compactionTokensUsed` carries the directly-observed token bill
            # for the compaction itself (input/output/cache); attribute the
            # finding to that model so credit conversion is grounded.
            ctu = d.get("compactionTokensUsed") or {}
            compactions.append({
                "pre_tokens":     int(d.get("preCompactionTokens", 0) or 0),
                "output_tokens":  int(ctu.get("outputTokens", 0) or 0),
                "model":          ctu.get("model") or "",
                "ts":             ts,
            })

    findings: list[dict] = []

    # Build an idx-ordered ordered list of all events for adjacency lookup
    asst_by_idx = {m["idx"]: m for m in asst_msgs}

    # ── Pattern 1: hot files (event-adjacent token attribution) ────────────
    from collections import Counter, defaultdict
    file_ops = defaultdict(lambda: Counter())  # path -> Counter({tool_name: n})
    file_tool_idxs = defaultdict(list)         # path -> [idx, ...]
    for tid, ts_rec in tool_starts.items():
        name = ts_rec["name"]
        if name not in ("view", "edit", "create", "grep"):
            continue
        path = _burn_extract_path(ts_rec["args"])
        if not path:
            continue
        file_ops[path][name] += 1
        file_tool_idxs[path].append(ts_rec["idx"])

    asst_idxs_sorted = sorted(asst_by_idx.keys())
    for path, ops in file_ops.items():
        total = sum(ops.values())
        if total < 10:
            continue
        # Attribute: sum outputTokens of asst.messages whose idx is the
        # closest assistant message AFTER each tool call on this file.
        # (No double-counting: dedup by message idx.)
        attributed_msg_idxs = set()
        for tool_idx in file_tool_idxs[path]:
            for ai in asst_idxs_sorted:
                if ai > tool_idx:
                    attributed_msg_idxs.add(ai)
                    break
        observed_tokens = sum(asst_by_idx[ai]["tokens"] for ai in attributed_msg_idxs)
        # Primary model = the model that ran most of those attributed messages
        model_votes = Counter(asst_by_idx[ai]["model"] for ai in attributed_msg_idxs)
        model = model_votes.most_common(1)[0][0] if model_votes else ""
        # Representative timestamp = first tool access
        first_idx = min(file_tool_idxs[path])
        first_ts = next((tr["ts"] for tr in tool_starts.values() if tr["idx"] == first_idx), "")
        # Build evidence string from the op counts
        parts = []
        for nm in ("edit", "view", "grep", "create"):
            if ops.get(nm):
                parts.append(f"{ops[nm]} {nm}s" if ops[nm] > 1 else f"1 {nm}")
        short_path = path.replace("\\", "/").rsplit("/", 1)[-1] or path
        findings.append({
            "kind": "hot_file",
            "evidence": f"{short_path} — {', '.join(parts)}",
            "detail": f"During its active turns the session produced {observed_tokens:,} observed output tokens.",
            "model": model,
            "output_tokens": observed_tokens,
            "ts": first_ts,
            "advice": ("Repeated touches on one file often indicate iterative refinement. "
                       "Try sketching the change as a short plan before editing, or batching "
                       "related changes into fewer, larger edits."),
        })

    # ── Pattern 2: failed retry loops ──────────────────────────────────────
    fail_runs: dict[str, list] = defaultdict(list)  # tool_name -> [(ts, idx), ...]
    for tid, comp in tool_complete.items():
        if comp.get("success") is False and tid in tool_starts:
            ts_rec = tool_starts[tid]
            fail_runs[ts_rec["name"]].append((ts_rec["ts"], ts_rec["idx"]))
    for name, run in fail_runs.items():
        if len(run) < 3:
            continue
        run.sort()
        first_ts, first_idx = run[0]
        last_ts, last_idx = run[-1]
        # Attribute observed tokens to asst.messages within idx window
        window_msgs = [m for m in asst_msgs if first_idx <= m["idx"] <= last_idx]
        observed_tokens = sum(m["tokens"] for m in window_msgs)
        model_votes = Counter(m["model"] for m in window_msgs)
        model = model_votes.most_common(1)[0][0] if model_votes else ""
        findings.append({
            "kind": "fail_loop",
            "evidence": f"{name} failed {len(run)} times in this session",
            "detail": (f"Observed {observed_tokens:,} output tokens across the retry window "
                       f"({first_ts[11:16]}–{last_ts[11:16]})."),
            "model": model,
            "output_tokens": observed_tokens,
            "ts": first_ts,
            "advice": ("Each retry re-prompts the full context. Sanity-check inputs "
                       "(URL, path, schema) once before the first call, or paste the "
                       "needed excerpt directly when a fetch is the problem."),
        })

    # ── Pattern 3: compaction storms ───────────────────────────────────────
    if len(compactions) >= 3:
        total_pre = sum(c["pre_tokens"] for c in compactions)
        # Direct measurement: sum the output tokens the compaction events
        # themselves emitted (their own self-summary cost). Attribute to
        # the model that ran the most compactions in this session.
        direct_output = sum(c["output_tokens"] for c in compactions)
        from collections import Counter as _Counter
        model_votes = _Counter(c["model"] for c in compactions if c["model"])
        primary_model = model_votes.most_common(1)[0][0] if model_votes else ""
        findings.append({
            "kind": "compaction_storm",
            "evidence": f"{len(compactions)} compactions in this session",
            "detail": (f"Cumulative {total_pre:,} pre-compaction tokens summarised. "
                       f"Each summary is carried forward, so every subsequent turn "
                       f"pays for it on input."),
            "model": primary_model,
            "output_tokens": direct_output,
            "ts": compactions[0]["ts"],
            "advice": ("Long sessions overflow context. When a topic changes or work "
                       "feels stuck, start a fresh session rather than continuing — "
                       "this stops unrelated context from being summarised and re-paid."),
        })

    # ── Pattern 4: large output spikes on premium models ───────────────────
    for m in asst_msgs:
        if m["tokens"] >= 8000 and m["model"] in _BURN_PREMIUM_MODELS:
            findings.append({
                "kind": "output_spike",
                "evidence": f"{m['tokens']:,}-token assistant response on {m['model']}",
                "detail": f"Single message at {m['ts'][11:16]} on {m['ts'][:10]}.",
                "model": m["model"],
                "output_tokens": m["tokens"],
                "ts": m["ts"],
                "advice": ("Large code generation scales linearly with model price. "
                           "For scaffolding-heavy turns, ask for the change in smaller "
                           "patches, or start the session on a lighter model and "
                           "reserve premium models for reasoning."),
            })

    # ── Pattern 5: exploration runs on premium models ──────────────────────
    # Walk tool starts in chronological order; track runs of read-only tools.
    sorted_tools = sorted(tool_starts.values(), key=lambda x: x["idx"])
    run: list = []
    runs_emitted = 0
    for tr in sorted_tools + [None]:
        if tr is not None and tr["name"] in _READ_ONLY_TOOLS:
            run.append(tr)
        else:
            if len(run) >= 5:
                first_idx, last_idx = run[0]["idx"], run[-1]["idx"]
                window_msgs = [m for m in asst_msgs if first_idx <= m["idx"] <= last_idx]
                model_votes = Counter(m["model"] for m in window_msgs)
                primary_model = model_votes.most_common(1)[0][0] if model_votes else ""
                if primary_model in _BURN_PREMIUM_MODELS and runs_emitted < 3:
                    observed_tokens = sum(m["tokens"] for m in window_msgs)
                    findings.append({
                        "kind": "exploration_premium",
                        "evidence": (f"{len(run)} consecutive read-only tool calls "
                                     f"({_summarise_tools(run)}) on {primary_model}"),
                        "detail": (f"Observed {observed_tokens:,} output tokens during "
                                   f"this investigation window ({run[0]['ts'][11:16]}–"
                                   f"{run[-1]['ts'][11:16]})."),
                        "model": primary_model,
                        "output_tokens": observed_tokens,
                        "ts": run[0]["ts"],
                        "advice": ("Investigation-only phases benefit less from advanced "
                                   "reasoning. Next time, start the read-heavy discovery "
                                   "phase on a lighter model, then open a focused session "
                                   "on a stronger model when you're ready to implement."),
                    })
                    runs_emitted += 1
            run = []

    # ── Pattern 6: broad search repetition ─────────────────────────────────
    broad_searches: list[tuple[str, dict]] = []
    for tr in sorted_tools:
        if tr["name"] not in ("grep", "glob"):
            continue
        args = tr.get("args") or {}
        if not isinstance(args, dict):
            continue
        paths = args.get("paths")
        if isinstance(paths, list):
            paths = paths[0] if paths else None
        # Broad = no path narrowing OR path is the repo/cwd-level root
        if paths is None or (isinstance(paths, str) and paths.count("/") + paths.count("\\") <= 4):
            broad_searches.append((tr["ts"], tr))
    if len(broad_searches) >= 5:
        first_ts = broad_searches[0][0]
        sample_patterns = [
            (b[1].get("args") or {}).get("pattern", "")[:30]
            for b in broad_searches[:4]
        ]
        findings.append({
            "kind": "broad_search_repeat",
            "evidence": f"{len(broad_searches)} broad grep/glob calls across the session",
            "detail": ("Sample patterns: " + ", ".join(f'"{p}"' for p in sample_patterns if p)
                       + ". Each broad scan re-loads many candidate files into context."),
            "model": "",
            "output_tokens": 0,  # flag-only finding, no token attribution
            "ts": first_ts,
            "advice": ("Narrow searches to a known sub-directory or use the first hit "
                       "to navigate to a more specific location. Repeated broad scans "
                       "tend to rediscover the same files."),
        })

    # ── Pattern 7: parallel-missed (Anthropic multi-agent / OpenAI BP-05) ──
    # Group tool calls by the asst.message turn they belong to: a turn = the
    # tool calls whose idx falls between this asst.message and the next.
    # Sequential single-tool turns on different read-only paths could have
    # been batched into a parallel tool call.
    if len(asst_msgs) >= 6:
        asst_idxs = sorted(m["idx"] for m in asst_msgs) + [10**12]
        tools_by_turn: list[list] = []
        sorted_tool_list = sorted(tool_starts.values(), key=lambda x: x["idx"])
        ti = 0
        for k in range(len(asst_idxs) - 1):
            lo, hi = asst_idxs[k], asst_idxs[k + 1]
            turn_tools = []
            while ti < len(sorted_tool_list) and sorted_tool_list[ti]["idx"] < hi:
                if sorted_tool_list[ti]["idx"] >= lo:
                    turn_tools.append(sorted_tool_list[ti])
                ti += 1
            tools_by_turn.append(turn_tools)

        # Find runs of consecutive single-read-only-tool turns on distinct paths.
        run_lengths: list[tuple[int, int, int]] = []  # (start_idx, end_idx, length)
        cur_start = None
        cur_paths: set = set()
        cur_len = 0
        for k, turn in enumerate(tools_by_turn):
            single_read = (
                len(turn) == 1
                and turn[0]["name"] in _READ_ONLY_TOOLS
                and turn[0]["name"] not in ("report_intent", "list_powershell", "list_agents")
            )
            if single_read:
                path = _burn_extract_path(turn[0]["args"]) or turn[0]["name"]
                if cur_start is None:
                    cur_start = turn[0]["idx"]
                    cur_paths = {path}
                    cur_len = 1
                else:
                    cur_paths.add(path)
                    cur_len += 1
            else:
                if cur_len >= 4 and len(cur_paths) >= 3:
                    end_idx = tools_by_turn[k - 1][0]["idx"]
                    run_lengths.append((cur_start, end_idx, cur_len))
                cur_start, cur_paths, cur_len = None, set(), 0
        if cur_len >= 4 and len(cur_paths) >= 3:
            end_idx = sorted_tool_list[-1]["idx"] if sorted_tool_list else cur_start
            run_lengths.append((cur_start, end_idx, cur_len))

        # Emit at most one parallel_missed finding (the longest run).
        if run_lengths:
            start_idx, end_idx, run_len = max(run_lengths, key=lambda x: x[2])
            window_msgs = [m for m in asst_msgs if start_idx <= m["idx"] <= end_idx]
            observed_tokens = sum(m["tokens"] for m in window_msgs)
            model_votes = Counter(m["model"] for m in window_msgs)
            primary_model = model_votes.most_common(1)[0][0] if model_votes else ""
            first_ts = next((m["ts"] for m in asst_msgs if m["idx"] == start_idx), "")
            findings.append({
                "kind": "parallel_missed",
                "evidence": (f"{run_len} consecutive single-tool turns reading different "
                             f"locations — each was its own round-trip"),
                "detail": (f"Observed {observed_tokens:,} output tokens across these "
                           f"turns. Read-only tools without data dependencies between "
                           f"them can be issued in a single response."),
                "model": primary_model,
                "output_tokens": observed_tokens,
                "ts": first_ts,
                "advice": ("When several files or queries are independent, request all "
                           "the reads at once. Anthropic reports up to 90% latency "
                           "reduction from parallel tool calls; each extra round-trip "
                           "also re-pays the system prompt."),
            })

    # ── Pattern 8: no-verification at session end (Anthropic harnesses) ────
    # Long edit sessions that never run a test/build/lint command leave
    # "looks done" as the only stopping signal.
    edit_count = sum(1 for tr in tool_starts.values()
                     if tr["name"] in ("edit", "create"))
    if edit_count >= 10:
        sorted_tools = sorted(tool_starts.values(), key=lambda x: x["idx"])
        tail = sorted_tools[-15:]
        verification_markers = (
            "test", "pytest", "jest", "mocha", "npm test", "go test", "cargo test",
            "lint", "ruff", "flake8", "eslint", "mypy", "tsc",
            "build", "compile", "make ", "npm run build", "cargo build",
        )

        def _looks_like_verify(tr) -> bool:
            n = tr["name"].lower()
            if n in ("task",):  # task tool may launch a verify subagent
                return True
            args = tr.get("args") or {}
            if not isinstance(args, dict):
                return False
            blob = " ".join(str(v) for v in args.values()).lower()
            return any(m in blob for m in verification_markers)

        if not any(_looks_like_verify(tr) for tr in tail):
            findings.append({
                "kind": "no_verification",
                "evidence": f"{edit_count} edits but no test/build/lint near session end",
                "detail": ("The session finished without running a check that could "
                           "produce a pass/fail signal — verification falls back to "
                           "the human eye."),
                "model": "",
                "output_tokens": 0,  # flag-only — the cost is downstream rework
                "ts": tail[-1]["ts"] if tail else "",
                "advice": ("Close the loop on every coding session with a runnable "
                           "check — tests, lint, or a build. The agent will catch "
                           "its own mistakes before you do, and false 'task complete' "
                           "claims become measurable."),
            })

    # ── Pattern 9: subagent delegation missed (Anthropic costs guide) ──────
    # Long sessions doing lots of investigation in the main context pay
    # for that exploration on every subsequent turn (compaction summarises
    # it, but the summary keeps being re-paid).  Flag-only — the absence
    # of delegation is the signal; token cost is opaque (it's the marginal
    # context re-pay, not a measurable line item).
    total_tool_calls = len(tool_starts)
    read_only_calls = sum(1 for tr in tool_starts.values()
                          if tr["name"] in _READ_ONLY_TOOLS)
    task_calls = sum(1 for tr in tool_starts.values() if tr["name"] == "task")
    if total_tool_calls >= 60 and read_only_calls >= 30 and task_calls == 0:
        first_ro_ts = next((tr["ts"] for tr in sorted(tool_starts.values(),
                                                      key=lambda x: x["idx"])
                            if tr["name"] in _READ_ONLY_TOOLS), "")
        findings.append({
            "kind": "subagent_missed",
            "evidence": (f"{total_tool_calls} tool calls ({read_only_calls} read-only) "
                         f"in one session with zero delegation"),
            "detail": ("Verbose exploration stayed in the main context and re-loaded "
                       "on every subsequent turn — the marginal cost shows up indirectly "
                       "as compaction overhead and longer input bills."),
            "model": "",
            "output_tokens": 0,  # flag-only — cost is contextual, not measurable
            "ts": first_ro_ts,
            "advice": ("For broad investigation, run a `task` sub-agent: it explores "
                       "in its own context window and returns only a summary. Anthropic "
                       "reports 90.2% quality improvement on complex breadth-first tasks "
                       "with this pattern."),
        })

    # ── Pattern 10: bundled multi-goal user prompt (OpenAI BP-18) ──────────
    # Distinct, separable tasks bundled into one prompt force the model to
    # juggle objectives; peak quality and cost come from one goal per turn.
    bundled_candidates = []
    for um in user_msgs:
        c = um["content"]
        if len(c) < 600:
            continue
        # Count numbered list markers and ordered conjunctions
        numbered = len(_re.findall(r'(?m)^\s*(?:\d+[\.\)]|[-*])\s+\S', c))
        conjunctions = len(_re.findall(
            r'\band (?:then|also|finally|next|after that)\b', c, _re.IGNORECASE))
        question_marks = c.count("?")
        score = numbered + conjunctions + max(0, question_marks - 1)
        if numbered >= 3 or score >= 4:
            bundled_candidates.append((um, numbered, score))
    if bundled_candidates:
        um, numbered, score = max(bundled_candidates, key=lambda x: x[2])
        # Attribute the next 3 asst.messages after this user.message
        following = [m for m in asst_msgs if m["idx"] > um["idx"]][:3]
        observed_tokens = sum(m["tokens"] for m in following)
        model_votes = Counter(m["model"] for m in following)
        primary_model = model_votes.most_common(1)[0][0] if model_votes else ""
        if numbered >= 3:
            sig = f"contained {numbered} numbered items"
        else:
            sig = f"bundled {score} distinct goals"
        findings.append({
            "kind": "bundled_prompt",
            "evidence": f"A user message {sig} in one turn",
            "detail": (f"Observed {observed_tokens:,} output tokens responding to the "
                       f"bundled prompt. Multi-goal turns force the model to interleave "
                       f"plans rather than focus on one."),
            "model": primary_model,
            "output_tokens": observed_tokens,
            "ts": um["ts"],
            "advice": ("Split distinct sub-tasks across separate turns — peak quality "
                       "comes from one focused goal per turn (OpenAI GPT-5 guide). "
                       "Each turn also starts from a stable cached prefix."),
        })

    # ── Pattern 11: model thrashing within a session (GitHub auto-model) ───
    # Switching models mid-session crosses cache boundaries; GitHub's auto
    # selector routes along natural cache boundaries for this reason.
    if len(asst_msgs) >= 8:
        models_in_order = [m["model"] for m in sorted(asst_msgs, key=lambda x: x["idx"])
                           if m["model"]]
        transitions = sum(1 for a, b in zip(models_in_order, models_in_order[1:])
                          if a != b)
        distinct_models = len(set(models_in_order))
        if transitions >= 4 and distinct_models >= 3:
            model_counts = Counter(models_in_order)
            top_three = ", ".join(f"{n}×{c}" for n, c in model_counts.most_common(3))
            findings.append({
                "kind": "model_thrash",
                "evidence": (f"{transitions} model switches across {len(models_in_order)} "
                             f"assistant turns ({top_three})"),
                "detail": ("Every model switch crosses a cache boundary, so the system "
                           "prompt and prior context are re-billed on the next turn."),
                "model": "",
                "output_tokens": 0,  # flag only — cache miss cost is opaque
                "ts": asst_msgs[0]["ts"],
                "advice": ("Pick a model at session start and stay on it; let GitHub's "
                           "auto-selector route across natural cache boundaries instead "
                           "of toggling manually. Manual switches cost more without "
                           "measurable quality gains."),
            })

    return findings


def _summarise_tools(run: list) -> str:
    """Format a Counter-style summary of tool names in a run."""
    from collections import Counter
    c = Counter(t["name"] for t in run)
    return ", ".join(f"{n} ×{c[n]}" if c[n] > 1 else n for n in c)


def get_sessions_for_date(target_date: str) -> list:
    """
    Find all Copilot sessions with activity on target_date (YYYY-MM-DD).
    Returns a list of session dicts compatible with the whatidid schema.
    """
    sessions = []

    if not SESSION_DIR.exists():
        return sessions

    for session_dir in SESSION_DIR.iterdir():
        if not session_dir.is_dir():
            continue

        events_file   = session_dir / "events.jsonl"
        workspace_file = session_dir / "workspace.yaml"

        if not events_file.exists():
            continue

        workspace = _read_workspace(workspace_file)

        # Parse all events
        events = []
        try:
            with open(events_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            continue

        if not events:
            continue

        # Quick check: does this session touch the target date?
        has_target_date = False
        for e in events:
            ts = e.get("timestamp", "")
            if ts and ts[:10] == target_date:
                has_target_date = True
                break

        if not has_target_date:
            continue

        # Pull session context from session.start
        session_ctx = {}
        for e in events:
            if e.get("type") == "session.start":
                session_ctx = e.get("data", {}).get("context", {})
                break

        cwd        = session_ctx.get("cwd", "")        or workspace.get("cwd", "")
        repository = session_ctx.get("repository", "") or workspace.get("repository", "")
        branch     = session_ctx.get("branch", "")     or workspace.get("branch", "")

        project_name = Path(cwd).name if cwd else session_dir.name[:12]

        # Extract user messages and tool summaries
        messages      = []
        session_start = None
        session_end   = None
        git_ops_list  = []
        files_touched = set()  # files from edit/create tool events

        for e in events:
            ts = e.get("timestamp", "")
            if not ts or ts[:10] != target_date:
                continue

            if not session_start:
                session_start = ts
            session_end = ts

            etype = e.get("type", "")

            if etype == "user.message":
                raw = e.get("data", {}).get("content", "")
                if isinstance(raw, str) and raw.strip():
                    text = _strip_injected_context(raw).strip()
                    if text and not _is_approval(text):
                        messages.append({
                            "role":        "user",
                            "text":        text,
                            "timestamp":   ts,
                            "tools_after": [],
                        })

            elif etype == "assistant.message":
                tool_requests = e.get("data", {}).get("toolRequests", [])
                for tr in tool_requests:
                    # intentionSummary is already human-readable (e.g. "Read report.py")
                    summary = tr.get("intentionSummary") or tr.get("name", "")
                    if summary and messages and messages[-1]["role"] == "user":
                        messages[-1]["tools_after"].append(summary)

                    # Track files touched by edit/create tool operations
                    tool_name_lower = (tr.get("name") or "").lower()
                    if tool_name_lower in ("edit", "create"):
                        path_str = (tr.get("input", {}) or {}).get("path", "")
                        if not path_str and summary:
                            pm = _re.search(r'[\\/]([^\\/]+\.\w{1,8})\.?\s*$', summary)
                            if pm:
                                path_str = pm.group(1)
                        if path_str:
                            files_touched.add(path_str.replace("\\", "/"))

            elif etype == "tool.execution_complete":
                tool_name = e.get("data", {}).get("toolName", "")
                if "pull_request" in tool_name.lower() or "pr" in tool_name.lower():
                    if e.get("data", {}).get("success", False):
                        git_ops_list.append("pr")

        # Detect PRs and commits from user messages and tool summaries
        _pr_keywords = {"create the pr", "create a pr", "create pr", "gh pr create",
                        "pull request", "open a pr", "open pr", "submit pr"}
        _commit_keywords = {"commit", "git commit", "push to remote", "push to origin",
                            "push it", "commit and push"}
        for m in messages:
            txt = m["text"].lower().strip()
            tools_text = " ".join(m.get("tools_after", [])).lower()
            if any(k in txt for k in _pr_keywords) or "create pr" in tools_text:
                if "pr" not in git_ops_list[-1:]:  # Avoid consecutive dupes
                    git_ops_list.append("pr")
            if any(k in txt for k in _commit_keywords) or "commit" in tools_text:
                if "commit" not in git_ops_list[-1:]:
                    git_ops_list.append("commit")

        # Two-phase token/credit extraction.
        #
        # Phase 1 always walks every event and accumulates the per-event signals
        # the agent emits directly. Phase 2 reconciles: when `session.shutdown`
        # is present we use its server-rolled-up `modelMetrics` as canonical;
        # otherwise we reconstruct from per-event data (the only way to attribute
        # cost to sessions that crashed, were killed, are still active, or were
        # suspended — i.e. sessions which never write a clean shutdown record).
        #
        # No modeling or estimation: only token counts that the CLI emits in
        # the event stream are used. Anything we don't have direct data for
        # (e.g. per-turn input tokens for non-compaction calls) stays 0 and the
        # session is flagged `session_state="open"` so the report can disclose
        # that costs are a lower bound.
        tokens_by_model = {}  # {model_name: {input, output, cache_read, cache_creation}}
        requests_by_model = {}  # {model_name: api_call_count}
        ai_credits = None  # server-emitted credit total if available
        ai_credits_by_model = {}  # {model_name: credits_used} if present
        premium_requests = 0
        total_api_ms     = 0
        code_changes     = {}
        model_used       = ""
        plan_tier        = ""
        auto_model       = False

        # ── Phase 1: per-event accumulation (always runs) ────────────────────
        #
        # IMPORTANT: every per-event signal is date-filtered to `target_date`.
        # Without this, a single multi-day open session would inflate totals
        # by N× when the report aggregates across the dates it touches (the
        # same session.tokens would be returned N times by N harvest calls).
        per_msg_output_by_model: dict[str, int] = {}
        per_msg_count_by_model:  dict[str, int] = {}
        compaction_blocks:       list[dict]     = []
        last_assistant_model = ""
        shutdown_data: dict | None = None
        shutdown_ts:   str         = ""

        for e in events:
            t = e.get("type")
            d = e.get("data") or {}
            ts = e.get("timestamp", "") or ""
            on_target_day = ts[:10] == target_date

            if t == "assistant.message":
                if not on_target_day:
                    continue
                m = d.get("model") or "unknown"
                out = d.get("outputTokens") or 0
                per_msg_count_by_model[m] = per_msg_count_by_model.get(m, 0) + 1
                if isinstance(out, (int, float)) and out > 0:
                    per_msg_output_by_model[m] = per_msg_output_by_model.get(m, 0) + int(out)
                if m and m != "unknown":
                    last_assistant_model = m
            elif t == "session.compaction_complete":
                if not on_target_day:
                    continue
                ctu = d.get("compactionTokensUsed") or {}
                if ctu:
                    compaction_blocks.append(ctu)
            elif t == "session.shutdown":
                # Capture every shutdown (use the last one if multiple exist).
                # Whether we attribute its rollup to *this* date is decided in
                # Phase 2 based on the shutdown timestamp.
                shutdown_data = d
                shutdown_ts   = ts

        # ── Phase 2: reconcile ───────────────────────────────────────────────
        session_state = "unknown"

        # The shutdown rollup is the *entire* session bill. Only credit it to
        # the date the shutdown actually fired on, otherwise a multi-day
        # session would over-count its tokens on every date it touches.
        shutdown_on_target = (shutdown_data is not None
                              and shutdown_ts[:10] == target_date)

        if shutdown_on_target:
            # Clean shutdown present today — trust the server-rolled-up totals.
            session_state    = "complete"
            premium_requests = shutdown_data.get("totalPremiumRequests", 0)
            total_api_ms     = shutdown_data.get("totalApiDurationMs", 0)
            code_changes     = shutdown_data.get("codeChanges", {})
            model_used       = shutdown_data.get("currentModel", "") or last_assistant_model
            # AI Credits billing fields (June 2026+) — read if present.
            if "totalAiCredits" in shutdown_data:
                ai_credits = shutdown_data.get("totalAiCredits")
            elif "totalAICredits" in shutdown_data:
                ai_credits = shutdown_data.get("totalAICredits")
            elif "totalCredits" in shutdown_data:
                ai_credits = shutdown_data.get("totalCredits")
            plan_tier  = shutdown_data.get("planTier") or shutdown_data.get("plan") or ""
            auto_model = bool(shutdown_data.get("autoModelSelection")
                              or shutdown_data.get("autoModel")
                              or shutdown_data.get("modelSelectionMode") == "auto")
            for model_name, model_data in shutdown_data.get("modelMetrics", {}).items():
                usage = model_data.get("usage", {}) or {}
                tokens_by_model[model_name] = {
                    "input":          usage.get("inputTokens", 0)      or 0,
                    "output":         usage.get("outputTokens", 0)     or 0,
                    "cache_read":     usage.get("cacheReadTokens", 0)  or 0,
                    "cache_creation": usage.get("cacheWriteTokens", 0) or 0,
                }
                requests_meta = model_data.get("requests", {}) or {}
                if requests_meta.get("count"):
                    requests_by_model[model_name] = requests_meta["count"]
                credits_meta = (model_data.get("creditsUsed")
                                or model_data.get("credits"))
                if credits_meta is not None:
                    ai_credits_by_model[model_name] = credits_meta
        else:
            # No shutdown on this date — use the date-filtered per-event totals.
            # This covers: still-open sessions, crashed/killed sessions, and
            # multi-day sessions whose shutdown fired on a different date.
            has_per_event = bool(per_msg_count_by_model or compaction_blocks)
            session_state = "open" if has_per_event else "unknown"
            model_used    = last_assistant_model

            def _bucket(m: str) -> dict:
                if m not in tokens_by_model:
                    tokens_by_model[m] = {"input": 0, "output": 0,
                                          "cache_read": 0, "cache_creation": 0}
                return tokens_by_model[m]

            # Direct fact: per-message output tokens summed by model
            # (already restricted to events on target_date in Phase 1).
            for m, out in per_msg_output_by_model.items():
                _bucket(m)["output"] += out

            # Direct fact: each compaction on target_date emits exact
            # tokenDetails (the same data GitHub uses to bill nano-AIU).
            # Attribute to the model that ran the compaction call.
            for ctu in compaction_blocks:
                m = ctu.get("model") or "unknown"
                b = _bucket(m)
                b["input"]          += int(ctu.get("inputTokens", 0)      or 0)
                b["output"]         += int(ctu.get("outputTokens", 0)     or 0)
                b["cache_read"]     += int(ctu.get("cacheReadTokens", 0)  or 0)
                b["cache_creation"] += int(ctu.get("cacheWriteTokens", 0) or 0)

            # Request count per model — proxy from assistant.message count.
            # We don't claim these are "premium requests" (that distinction is
            # server-side); leave the top-level premium_requests at 0 so
            # downstream effort estimation falls back to other signals.
            for m, c in per_msg_count_by_model.items():
                requests_by_model[m] = c

            # Plan tier may still be supplied via env var below.

        # Derive scalar `tokens` totals from the per-model breakdown so both
        # code paths produce the same canonical shape.
        tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
        for mt in tokens_by_model.values():
            for k in tokens:
                tokens[k] += mt.get(k, 0) or 0
        tokens["total"] = sum(tokens.values())

        # Plan can also be supplied via env var (COPILOT_PLAN=pro|pro+|max|business|enterprise)
        # when the session log doesn't carry it. Useful for individuals on monthly plans.
        if not plan_tier:
            plan_tier = _os.environ.get("COPILOT_PLAN", "").strip()

        # Merge files: shutdown data + tool event extraction
        shutdown_files = set(code_changes.get("filesModified", []))
        all_modified = shutdown_files | files_touched
        if all_modified and not shutdown_files:
            code_changes.setdefault("filesModified", sorted(all_modified))

        # Split lines into logic vs boilerplate by file extension.
        # Copilot sessions don't give per-file line counts, so estimate from
        # the proportion of modified files with logic extensions.
        total_lines = code_changes.get("linesAdded", 0)
        if all_modified:
            import os
            logic_files = sum(1 for f in all_modified
                              if os.path.splitext(f)[1].lower() in _LOGIC_EXTS)
            logic_frac = logic_files / len(all_modified)
        else:
            logic_frac = 1.0  # no file info → assume all logic
        lines_logic = round(total_lines * logic_frac)
        lines_boilerplate = total_lines - lines_logic

        user_messages = [m for m in messages if m["role"] == "user"]
        if not user_messages:
            continue

        git_repos = [repository] if repository else []

        sessions.append({
            "session_id":        session_dir.name,
            "project":           project_name,
            "project_path":      cwd or str(session_dir),
            "repository":        repository,
            "branch":            branch,
            "entrypoint":        "copilot",
            "date":              target_date,
            "messages":          messages,
            "tokens":            tokens,
            "tokens_by_model":   tokens_by_model,
            "premium_requests":  premium_requests,
            "requests_by_model": requests_by_model,
            "ai_credits":        ai_credits,           # None when server didn't emit
            "ai_credits_by_model": ai_credits_by_model,
            "plan":              plan_tier,
            "auto_model_selection": auto_model,
            "session_state":     session_state,        # complete | open | unknown
            "total_api_ms":      total_api_ms,
            "code_changes":      code_changes,
            "model_used":        model_used,
            "session_start":     session_start,
            "session_end":       session_end,
            "git_repos":         git_repos,
            "git_ops":           git_ops_list,
            "workspace_summary": workspace.get("summary", ""),
            "tool_invocations":  sum(len(m.get("tools_after", [])) for m in messages if m["role"] == "user"),
            "files_touched":     sorted(all_modified),
            "lines_logic":       lines_logic,
            "lines_boilerplate": lines_boilerplate,
            # Per-session burn findings (cost-saving opportunities). Token counts
            # are observational only; credit conversion happens in the renderer.
            "burn_findings":     _analyze_burn_patterns(events, target_date),
        })

    # Also harvest VS Code Copilot Chat sessions
    sessions.extend(get_vscode_sessions_for_date(target_date))

    return sessions


# ── VS Code Session Harvesting ───────────────────────────────────────────────

def _get_vscode_chat_dir() -> Path | None:
    """Cross-platform path to VS Code emptyWindowChatSessions directory."""
    if _sys.platform == "win32":
        appdata = _os.environ.get("APPDATA", "")
        if appdata:
            p = Path(appdata) / "Code" / "User" / "globalStorage" / "emptyWindowChatSessions"
            if p.is_dir():
                return p
    elif _sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "emptyWindowChatSessions"
        if p.is_dir():
            return p
    else:  # Linux
        p = Path.home() / ".config" / "Code" / "User" / "globalStorage" / "emptyWindowChatSessions"
        if p.is_dir():
            return p
    return None


def _vscode_epoch_to_iso(epoch_ms: int | float) -> str:
    """Convert JS epoch-millisecond timestamp to ISO 8601 string."""
    try:
        return datetime.fromtimestamp(epoch_ms / 1000).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return ""


def _extract_file_path_from_markdown(text: str) -> str:
    """Extract a local file path from VS Code markdown-link tool messages."""
    m = _re.search(r'file://(/[^\s\)\]]+)', text)
    if m:
        path = _url_unquote(m.group(1))
        # Strip leading slash for Windows drive paths (e.g. /C:/Users/...)
        if _re.match(r'^/[A-Za-z]:/', path):
            path = path[1:]
        return path.replace("/", _os.sep)
    return ""


def _vscode_walk_token_fields(node) -> "tuple[int, int]":
    """Recursively sum inline ``promptTokens`` and ``outputTokens`` in a JSON tree.

    VS Code records per-tool-call token usage inline inside response payloads.
    Each round of a multi-turn chat re-sends the full conversation context,
    so summing every ``promptTokens`` value across all rounds matches what
    the underlying API actually bills.

    Returns ``(prompt_total, output_total)``.
    """
    prompt = output = 0
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, int):
                if k == "promptTokens":
                    prompt += v
                elif k == "outputTokens":
                    output += v
            else:
                pp, oo = _vscode_walk_token_fields(v)
                prompt += pp; output += oo
    elif isinstance(node, list):
        for x in node:
            pp, oo = _vscode_walk_token_fields(x)
            prompt += pp; output += oo
    return prompt, output


def _vscode_collect_inline_pricing(node, out: dict) -> None:
    """Walk a JSON tree and collect any inline per-model pricing metadata.

    VS Code Copilot Chat session JSONL embeds authoritative per-model rates
    inside ``inputState.selectedModel.metadata`` blocks. Each such block
    carries:

      * ``id``             model identifier (e.g. ``claude-opus-4.6``)
      * ``inputCost``      AI Credits per 1M input tokens
      * ``outputCost``     AI Credits per 1M output tokens
      * ``cacheCost``      AI Credits per 1M cached tokens
      * ``multiplier``     premium-request multiplier string (e.g. ``"3x"``)
      * ``multiplierNumeric`` premium-request multiplier number (e.g. ``3``)

    The ``pricing`` field's literal string is ``"In: 500 \u00b7 Out: 2500 AICs/1M tokens"``
    confirming the unit. Since 1 AIC = $0.01 USD, we convert AICs/M to USD/M
    by dividing by 100 so the result is directly comparable to entries in
    ``report._MODEL_PRICING``.

    Multiple blocks can appear in one session (e.g. mid-session model
    switch). We keep the most recent rates for each ``id`` we see.

    Mutates ``out`` in place: ``{model_id: {input, output, cache_read,
    cache_creation, multiplier, _source}}``.
    """
    if isinstance(node, dict):
        # Detect a pricing block. ``id`` is required for keying; rates are
        # required to be useful. Multiplier-only blocks (e.g. GPT-5.2-Codex
        # carries ``multiplier`` without per-token costs) are recorded so
        # downstream consumers can still see the premium-request rate.
        mid = _normalize_vscode_model(node.get("id", ""))
        has_rates = isinstance(node.get("inputCost"), (int, float)) and \
                    isinstance(node.get("outputCost"), (int, float))
        has_multiplier = isinstance(node.get("multiplierNumeric"), (int, float))
        if mid and (has_rates or has_multiplier):
                cache_aic = node.get("cacheCost", 0) or 0
                entry.update({
                    "input":  node["inputCost"]  / 100.0,
                    "output": node["outputCost"] / 100.0,
                    "cache_read":     cache_aic / 100.0,
                    "cache_creation": cache_aic / 100.0,
                })
            if has_multiplier:
                entry["multiplier"] = node["multiplierNumeric"]
            entry["_source"] = "vscode_inline"
        for v in node.values():
            _vscode_collect_inline_pricing(v, out)
    elif isinstance(node, list):
        for item in node:
            _vscode_collect_inline_pricing(item, out)


def _normalize_vscode_model(model_id: str) -> str:
    """Strip the ``copilot/`` prefix VS Code adds so model names match
    the CLI naming convention used by ``report._MODEL_PRICING``."""
    if not model_id:
        return ""
    if model_id.startswith("copilot/"):
        return model_id[len("copilot/"):]
    return model_id


def get_vscode_sessions_for_date(target_date: str) -> list:
    """Parse VS Code Copilot Chat sessions for a given date.

    VS Code sessions use a different schema than CLI sessions:
      kind=0 → session header (creationDate, sessionId)
      kind=1 → metadata updates (workspace context, timings, model info)
      kind=2 → chat turns (requests with messages, tool invocations, etc.)

    Uses a fast first-line pre-filter: skips files created after the target
    date (they can't have earlier activity). Files created before are always
    parsed; the inner loop filters events by date so non-matching turns are
    skipped cheaply even in large files.
    """
    chat_dir = _get_vscode_chat_dir()
    if not chat_dir:
        return []

    sessions = []

    for jsonl_file in chat_dir.glob("*.jsonl"):
        # ── Fast date pre-filter: read only first line (kind=0 header) ────
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                first_line = f.readline().strip()
            if not first_line:
                continue
            header = json.loads(first_line)
            if header.get("kind") != 0:
                continue
            hv = header.get("v", {})
            creation_ms = hv.get("creationDate", 0)
            if not creation_ms:
                continue
            creation_date = datetime.fromtimestamp(creation_ms / 1000).strftime("%Y-%m-%d")
        except Exception:
            continue

        # Skip files created after the target date — they can't have activity
        # on a date before they existed.  Files created *before* target_date
        # are always parsed because long-lived sessions can span weeks.
        # The inner loop filters individual events by date, so large files
        # that don't match still exit quickly.
        try:
            td = datetime.strptime(target_date, "%Y-%m-%d")
            cd = datetime.strptime(creation_date, "%Y-%m-%d")
            if cd > td:
                continue
        except Exception:
            pass

        # ── Full parse ────────────────────────────────────────────────────
        session_id = hv.get("sessionId", jsonl_file.stem)
        model_used = ""
        input_state = hv.get("inputState", {})
        if isinstance(input_state, dict):
            sel_model = input_state.get("selectedModel", {})
            if isinstance(sel_model, dict):
                model_used = sel_model.get("identifier", "")

        messages = []
        tool_summaries = []  # tools pending attachment to previous request
        files_touched = set()
        cwd = ""
        session_start = None
        session_end = None
        inline_model_pricing: dict = {}

        # Bootstrap inline pricing from the session header itself — the
        # header carries ``selectedModel.metadata`` which is the most
        # reliable signal even when no requests have run yet.
        _vscode_collect_inline_pricing(hv, inline_model_pricing)

        # ── Token & timing accumulators (sparse VS Code JSONL schema) ─────
        # Output tokens: kind=1 patch with key path ["requests", N,
        #   "completionTokens"] — cumulative for the whole turn; latest
        #   value wins per request index.
        # Input tokens : sum of every inline ``promptTokens`` field across
        #   all events (each tool-call round resends the full context, and
        #   the API bills each round, so summing matches actual billing).
        # API time    : kind=1 patch with key ["requests", N, "elapsedMs"]
        #   OR ["requests", N, "result"].timings.totalElapsed.
        # TTFT (bonus): ["requests", N, "result"].timings.firstProgress.
        # Per-request model id : recorded on the kind=2 chat turn event.
        completion_by_req: dict = {}
        elapsed_by_req: dict    = {}
        ttft_by_req: dict       = {}
        prompt_tokens_total     = 0
        output_tokens_inline    = 0  # not used for billing, kept for parity

        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue

                    kind = obj.get("kind")
                    v = obj.get("v")

                    # Sum inline token fields across the whole event tree.
                    pp, oo = _vscode_walk_token_fields(obj)
                    prompt_tokens_total += pp
                    output_tokens_inline += oo

                    # Capture any inline pricing metadata that appears
                    # (e.g. ``inputState`` patches carrying a fresh
                    # ``selectedModel.metadata`` block after a mid-session
                    # model switch).
                    _vscode_collect_inline_pricing(obj, inline_model_pricing)

                    # kind=1 sparse patches: workspace context + per-request
                    # token/timing updates.
                    if kind == 1:
                        # Workspace context (existing behaviour)
                        if isinstance(v, dict):
                            meta = v.get("metadata", {})
                            if isinstance(meta, dict) and not cwd:
                                for rendered in meta.get("renderedUserMessage", []):
                                    if isinstance(rendered, dict):
                                        txt = rendered.get("text", "")
                                        m = _re.search(r'current file is ([^\n]+)', txt)
                                        if m:
                                            fp = m.group(1).strip()
                                            cwd = str(Path(fp).parent)
                                            break

                        # Per-request token/timing patches
                        k = obj.get("k")
                        if (isinstance(k, list) and len(k) >= 3
                                and k[0] == "requests" and isinstance(k[1], int)):
                            req_idx = k[1]
                            field = k[2]
                            if field == "completionTokens" and isinstance(v, int):
                                completion_by_req[req_idx] = v  # latest wins
                            elif field == "elapsedMs" and isinstance(v, (int, float)):
                                elapsed_by_req[req_idx] = int(v)
                            elif field == "result" and isinstance(v, dict):
                                tim = v.get("timings", {})
                                if isinstance(tim, dict):
                                    if "totalElapsed" in tim and req_idx not in elapsed_by_req:
                                        elapsed_by_req[req_idx] = int(tim["totalElapsed"])
                                    if "firstProgress" in tim:
                                        ttft_by_req[req_idx] = int(tim["firstProgress"])

                    # kind=2: chat turns
                    if kind != 2 or not isinstance(v, list):
                        continue

                    for item in v:
                        if not isinstance(item, dict):
                            continue

                        # ── Request (user turn with AI response) ──────────
                        if "requestId" in item and "message" in item:
                            ts_ms = item.get("timestamp", 0)
                            ts_iso = _vscode_epoch_to_iso(ts_ms) if ts_ms else ""
                            if not ts_iso or ts_iso[:10] != target_date:
                                continue

                            if not session_start:
                                session_start = ts_iso
                            session_end = ts_iso

                            msg = item.get("message", {})
                            text = msg.get("text", "") if isinstance(msg, dict) else str(msg)
                            text = _strip_injected_context(text).strip()

                            if not text or _is_approval(text):
                                continue

                            # Attach any pending tool summaries to the previous message
                            if tool_summaries and messages and messages[-1]["role"] == "user":
                                messages[-1]["tools_after"].extend(tool_summaries)
                                tool_summaries = []

                            if not model_used:
                                model_used = item.get("modelId", "")

                            messages.append({
                                "role":        "user",
                                "text":        text,
                                "timestamp":   ts_iso,
                                "tools_after": [],
                            })

                        # ── Tool invocation ───────────────────────────────
                        elif item.get("kind") == "toolInvocationSerialized":
                            tool_id = item.get("toolId", "")
                            ptm = item.get("pastTenseMessage", "")
                            if isinstance(ptm, dict):
                                ptm = ptm.get("value", "")
                            summary = ptm or tool_id
                            tool_summaries.append(summary)

                            # Track files from edit/create tools
                            tool_lower = tool_id.lower()
                            if any(kw in tool_lower for kw in ("edit", "create", "write", "replace")):
                                fp = _extract_file_path_from_markdown(
                                    ptm if isinstance(ptm, str) else str(ptm)
                                )
                                if fp:
                                    files_touched.add(fp.replace("\\", "/"))

        except Exception:
            continue

        # Attach any remaining tool summaries
        if tool_summaries and messages and messages[-1]["role"] == "user":
            messages[-1]["tools_after"].extend(tool_summaries)

        user_messages = [m for m in messages if m["role"] == "user"]
        if not user_messages:
            continue

        project_name = Path(cwd).name if cwd else session_id[:12]
        all_modified = files_touched

        # Line counts not available from VS Code sessions
        total_lines = 0
        if all_modified:
            logic_files = sum(1 for f in all_modified
                              if _os.path.splitext(f)[1].lower() in _LOGIC_EXTS)
            logic_frac = logic_files / len(all_modified) if all_modified else 1.0
        else:
            logic_frac = 1.0
        lines_logic = round(total_lines * logic_frac)
        lines_boilerplate = total_lines - lines_logic

        # Aggregate token + timing extraction from the JSONL.
        out_tokens_total = sum(completion_by_req.values())
        in_tokens_total  = prompt_tokens_total
        total_api_ms     = sum(elapsed_by_req.values())
        request_count    = len(completion_by_req) or len(elapsed_by_req)

        norm_model = _normalize_vscode_model(model_used)
        tokens_by_model: dict = {}
        requests_by_model: dict = {}
        if norm_model and (in_tokens_total or out_tokens_total):
            tokens_by_model[norm_model] = {
                "input":          in_tokens_total,
                "output":         out_tokens_total,
                "cache_read":     0,   # VS Code JSONL does not expose cache breakdown
                "cache_creation": 0,
            }
        if norm_model and request_count:
            requests_by_model[norm_model] = request_count

        sessions.append({
            "session_id":        session_id,
            "project":           project_name,
            "project_path":      cwd or str(jsonl_file),
            "repository":        "",
            "branch":            "",
            "entrypoint":        "vscode",
            "date":              target_date,
            "messages":          messages,
            "tokens":            {"input":          in_tokens_total,
                                  "output":         out_tokens_total,
                                  "cache_read":     0,
                                  "cache_creation": 0,
                                  "total":          in_tokens_total + out_tokens_total},
            "tokens_by_model":   tokens_by_model,
            "premium_requests":  request_count,
            "requests_by_model": requests_by_model,
            "ai_credits":        None,
            "ai_credits_by_model": {},
            "inline_model_pricing": inline_model_pricing,
            "plan":              _os.environ.get("COPILOT_PLAN", "").strip(),
            "auto_model_selection": False,
            "session_state":     "complete",  # VS Code JSONL is read end-to-end so always complete
            "total_api_ms":      total_api_ms,
            "code_changes":      {"filesModified": sorted(all_modified)} if all_modified else {},
            "model_used":        norm_model or model_used,
            "session_start":     session_start,
            "session_end":       session_end,
            "git_repos":         [],
            "git_ops":           [],
            "workspace_summary": "",
            "tool_invocations":  sum(len(m.get("tools_after", [])) for m in messages if m["role"] == "user"),
            "files_touched":     sorted(all_modified),
            "lines_logic":       lines_logic,
            "lines_boilerplate": lines_boilerplate,
        })

    return sessions


def compute_elapsed_minutes(session_start: str, session_end: str) -> float:
    """Return wall-clock minutes between session start and end."""
    if not session_start or not session_end:
        return 0
    try:
        fmt = "%Y-%m-%dT%H:%M:%S"
        t0 = datetime.strptime(session_start[:19], fmt)
        t1 = datetime.strptime(session_end[:19], fmt)
        return max(0, (t1 - t0).total_seconds() / 60)
    except Exception:
        return 0


def compute_active_minutes(messages: list) -> float:
    """Estimate active engagement time from message timestamps.

    Sums intervals between consecutive messages where the gap is under
    5 minutes.  Longer gaps represent idle time (user away or thinking)
    and are excluded from the active total.
    """
    timestamps = []
    for m in messages:
        ts = m.get("timestamp", "")
        if ts:
            try:
                timestamps.append(datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
            except ValueError:
                pass

    if not timestamps:
        return 0.0
    if len(timestamps) == 1:
        return 1.0  # Single message ≈ 1 min engagement

    timestamps.sort()
    ACTIVE_THRESHOLD = 300  # 5 minutes in seconds
    active_s = 0.0

    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
        if gap <= ACTIVE_THRESHOLD:
            active_s += gap

    active_s += 30  # buffer for final message processing
    return round(active_s / 60, 1)


# ── Intent Classification ────────────────────────────────────────────────────

def _load_intent_config() -> tuple:
    """Load intent categories and colors from prompts/intent_classification.txt.
    Icons are hardcoded — they're HTML rendering detail, not classification logic."""
    path = Path(__file__).parent / "prompts" / "intent_classification.txt"
    categories, colors = {}, {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|", 2)]
        if len(parts) != 3:
            continue
        name, color, pattern = parts
        categories[name] = _re.compile(pattern, _re.I)
        colors[name] = color
    return categories, colors


_INTENT_CATEGORIES, _INTENT_COLORS = _load_intent_config()

_INTENT_ICONS = {
    "Building":      "&#128679;",
    "Investigating": "&#128300;",
    "Designing":     "&#127912;",
    "Researching":   "&#128202;",
    "Iterating":     "&#128260;",
    "Shipping":      "&#128640;",
    "Planning":      "&#128203;",
    "Testing":       "&#9989;",
    "Configuring":   "&#9881;",
    "Navigating":    "&#129517;",
}


def classify_message_intent(text: str) -> list[str]:
    """Classify a single user message into one or more intent categories."""
    matched = []
    for cat, rx in _INTENT_CATEGORIES.items():
        if rx.search(text[:300]):
            matched.append(cat)
    return matched or ["Building"]


def classify_session_intents(session: dict) -> dict:
    """Classify all user messages in a session and return aggregated intent data.

    Returns dict with:
      - counts: {category: int} — message count per intent
      - timeline: [(timestamp, category), ...] — ordered intent sequence
      - total: int — total classified messages
    """
    counts: dict = {k: 0 for k in _INTENT_CATEGORIES}
    timeline: list = []

    for m in session.get("messages", []):
        if m.get("role") != "user":
            continue
        intents = classify_message_intent(m.get("text", ""))
        ts = m.get("timestamp", "")
        for cat in intents:
            counts[cat] += 1
        if ts and intents:
            timeline.append((ts, intents[0]))  # primary intent for timeline

    # Auto-collapse: categories < 5% merge into nearest semantic parent
    total = sum(counts.values()) or 1
    _MERGE_MAP = {
        "Navigating":  "Researching",
        "Configuring": "Building",
        "Testing":     "Building",
        "Planning":    "Researching",
    }
    collapsed = dict(counts)
    for small_cat, parent in _MERGE_MAP.items():
        if counts[small_cat] / total < 0.05 and counts[small_cat] > 0:
            collapsed[parent] += collapsed[small_cat]
            collapsed[small_cat] = 0

    # Remove zero-count categories
    collapsed = {k: v for k, v in collapsed.items() if v > 0}

    return {
        "counts": collapsed,
        "counts_raw": {k: v for k, v in counts.items() if v > 0},
        "timeline": timeline,
        "total": sum(counts.values()),
    }


def aggregate_intents(sessions: list) -> dict:
    """Aggregate intent data across multiple sessions.

    Returns dict with:
      - counts: {category: int} — total counts (with auto-collapse)
      - by_project: {project: {category: int}} — per-project breakdown
      - timeline: [(timestamp, category), ...] — merged timeline
      - total: int
    """
    totals: dict = {k: 0 for k in _INTENT_CATEGORIES}
    by_project: dict = {}
    timeline: list = []

    for s in sessions:
        proj = s.get("project", "unknown")
        si = classify_session_intents(s)

        for cat, n in si["counts_raw"].items():
            totals[cat] = totals.get(cat, 0) + n

        if proj not in by_project:
            by_project[proj] = {k: 0 for k in _INTENT_CATEGORIES}
        for cat, n in si["counts_raw"].items():
            by_project[proj][cat] = by_project[proj].get(cat, 0) + n

        timeline.extend(si["timeline"])

    # Auto-collapse at aggregate level
    total = sum(totals.values()) or 1
    _MERGE_MAP = {
        "Navigating":  "Researching",
        "Configuring": "Building",
        "Testing":     "Building",
        "Planning":    "Researching",
    }
    collapsed = dict(totals)
    for small_cat, parent in _MERGE_MAP.items():
        if totals[small_cat] / total < 0.05 and totals[small_cat] > 0:
            collapsed[parent] += collapsed[small_cat]
            collapsed[small_cat] = 0
    collapsed = {k: v for k, v in collapsed.items() if v > 0}

    # Collapse per-project too
    collapsed_by_project = {}
    for proj, pcounts in by_project.items():
        ptotal = sum(pcounts.values()) or 1
        pc = dict(pcounts)
        for small_cat, parent in _MERGE_MAP.items():
            if pcounts[small_cat] / ptotal < 0.05 and pcounts[small_cat] > 0:
                pc[parent] += pc[small_cat]
                pc[small_cat] = 0
        collapsed_by_project[proj] = {k: v for k, v in pc.items() if v > 0}

    timeline.sort(key=lambda x: x[0])

    return {
        "counts": collapsed,
        "by_project": collapsed_by_project,
        "timeline": timeline,
        "total": sum(totals.values()),
    }


def _load_quality_config() -> tuple:
    """Load active time quality classification from prompts/active_time_quality.txt."""
    path = Path(__file__).parent / "prompts" / "active_time_quality.txt"
    user_rx = None
    tool_rx = None
    modes_order = []  # [(name, intents_set, desc)]
    colors = {}
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            section = line.strip("[]")
            continue
        if section == "hand_holding_user_patterns":
            user_rx = _re.compile(line, _re.I)
        elif section == "hand_holding_tool_patterns":
            tool_rx = _re.compile(line, _re.I)
        elif section == "modes":
            parts = [p.strip() for p in line.split("|", 2)]
            if len(parts) == 3:
                name, intents_str, desc = parts
                intents = set(i.strip() for i in intents_str.split(","))
                modes_order.append((name, intents, desc))
        elif section == "mode_colors":
            parts = [p.strip() for p in line.split("|", 1)]
            if len(parts) == 2:
                colors[parts[0]] = parts[1]
    return user_rx, tool_rx, modes_order, colors


_QUALITY_USER_RX, _QUALITY_TOOL_RX, _QUALITY_MODES, _QUALITY_COLORS = _load_quality_config()


def compute_active_time_quality(sessions: list) -> dict:
    """Classify active time into quality modes showing how Copilot contributed.

    Returns dict with mode_name → minutes. Uses two detection layers:
    1. Hand-holding: user correcting Copilot OR error signals in tool output
    2. Mode: based on intent classification of message content
    """
    from datetime import datetime as _dt

    modes = {name: 0.0 for name, _, _ in _QUALITY_MODES}
    modes["Course-correcting"] = 0.0

    for s in sessions:
        user_turns = []
        for m in s.get("messages", []):
            if m.get("role") != "user":
                continue
            ts_str = m.get("timestamp", "")
            try:
                ts = _dt.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                ts = None

            text = m.get("text", "").strip()
            tools = m.get("tools_after", [])
            intents = classify_message_intent(text)
            tools_text = " ".join(tools)

            # Layer 1: hand-holding detection
            user_correcting = bool(_QUALITY_USER_RX and _QUALITY_USER_RX.search(text[:300]))
            tool_errors = bool(_QUALITY_TOOL_RX and _QUALITY_TOOL_RX.search(tools_text))
            needs_handholding = user_correcting or tool_errors

            # Detect trivial turn
            first_line = text.split("\n")[0].strip()
            is_trivial = len(first_line) < 20

            user_turns.append({
                "ts": ts, "intents": intents, "tools": len(tools),
                "needs_handholding": needs_handholding, "is_trivial": is_trivial,
            })

        # Compute time per turn from timestamp gaps (capped at 5 min for idle)
        for i in range(len(user_turns)):
            if i < len(user_turns) - 1 and user_turns[i]["ts"] and user_turns[i + 1]["ts"]:
                gap = (user_turns[i + 1]["ts"] - user_turns[i]["ts"]).total_seconds() / 60
                user_turns[i]["minutes"] = min(gap, 5)
            else:
                user_turns[i]["minutes"] = 1

        # Classify each turn
        for t in user_turns:
            mins = t["minutes"]
            if t["needs_handholding"]:
                # Learning queries can superficially trip the hand-holding
                # patterns — e.g. "I don't understand how X works" matches
                # the broad "don.t" rule, and "what's wrong with my mental
                # model" matches the error vocabulary. When the message
                # *also* carries a Learning intent, the primary goal is
                # knowledge transfer and routing it to Course-correcting
                # would understate genuine learning time. Same logic for
                # Designing — "I don't like this layout, help me redesign"
                # is a design question, not an AI correction.
                if "Learning" in t["intents"]:
                    modes["Learning"] += mins
                elif "Designing" in t["intents"]:
                    modes["Designing"] += mins
                else:
                    modes["Course-correcting"] += mins
                continue
            # Trivial turns → grunt work
            if t["is_trivial"]:
                modes["Delegating"] = modes.get("Delegating", 0) + mins
                continue
            # Match against mode rules (first match wins)
            matched = False
            for mode_name, intent_set, _ in _QUALITY_MODES:
                if any(i in intent_set for i in t["intents"]):
                    modes[mode_name] += mins
                    matched = True
                    break
            if not matched:
                modes["Building"] = modes.get("Building", 0) + mins

    return {k: round(v, 1) for k, v in modes.items() if v > 0}
