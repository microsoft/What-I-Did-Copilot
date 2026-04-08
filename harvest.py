"""
harvest.py — Read GitHub Copilot session event files and extract structured activity data.

Sessions are stored at ~/.copilot/session-state/<uuid>/events.jsonl
Each session directory also contains workspace.yaml with a pre-written summary.
"""
import json
import re as _re
from datetime import datetime
from pathlib import Path

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

        # Pull shutdown metrics (tokens, code changes, premium requests)
        tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
        premium_requests = 0
        total_api_ms     = 0
        code_changes     = {}
        model_used       = ""

        for e in events:
            if e.get("type") == "session.shutdown":
                d = e.get("data", {})
                premium_requests = d.get("totalPremiumRequests", 0)
                total_api_ms     = d.get("totalApiDurationMs", 0)
                code_changes     = d.get("codeChanges", {})
                model_used       = d.get("currentModel", "")
                for model_data in d.get("modelMetrics", {}).values():
                    usage = model_data.get("usage", {})
                    tokens["input"]          += usage.get("inputTokens", 0)
                    tokens["output"]         += usage.get("outputTokens", 0)
                    tokens["cache_read"]     += usage.get("cacheReadTokens", 0)
                    tokens["cache_creation"] += usage.get("cacheWriteTokens", 0)
                break

        tokens["total"] = sum(tokens.values())

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
            "premium_requests":  premium_requests,
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
    modes["Needed hand-holding"] = 0.0

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
                modes["Needed hand-holding"] += mins
                continue
            # Trivial turns → grunt work
            if t["is_trivial"]:
                modes["Grunt work handled"] = modes.get("Grunt work handled", 0) + mins
                continue
            # Match against mode rules (first match wins)
            matched = False
            for mode_name, intent_set, _ in _QUALITY_MODES:
                if any(i in intent_set for i in t["intents"]):
                    modes[mode_name] += mins
                    matched = True
                    break
            if not matched:
                modes["Builder"] = modes.get("Builder", 0) + mins

    return {k: round(v, 1) for k, v in modes.items() if v > 0}
