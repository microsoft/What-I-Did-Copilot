"""
analyze.py — Semantic analysis of the day's Copilot sessions.

Uses the GitHub Models API (gpt-4o-mini) authenticated with the same GitHub token
that gh CLI already has — no additional credentials needed.
"""
import json
import os
import re
import subprocess
import time
import random
import http.client
import urllib.request
import urllib.error
from pathlib import Path
from typing import Literal
from harvest import compute_active_minutes, compute_elapsed_minutes

# Recursion marker: when we shell out to `copilot` for analysis, we set this
# env var on the child process. If the marker is already set, we refuse to
# re-enter to avoid an infinite (or just expensive) recursion.
_CHILD_MARKER = "WHATIDID_COPILOT_CHILD"
_DISABLE_CLI_VAR = "WHATIDID_DISABLE_COPILOT_CLI"

AnalysisSource = Literal["api", "cli", "heuristic"]

# GitHub Models API — OpenAI-compatible endpoint, authenticated with GitHub token
API_URL = "https://models.github.ai/inference/chat/completions"
MODEL   = "openai/gpt-4o-mini"

# ~3000 tokens, leaving ~5000 for prompt + response
MAX_TRANSCRIPT_CHARS = 25000


def _retry_delay(err, attempt: int) -> float:
    """Seconds to wait before the next retry, with exponential backoff.

    Honors a ``Retry-After`` header (seconds) when the server provides one on a
    429/503; otherwise uses exponential backoff with jitter, capped at 60s.
    """
    if err is not None:
        retry_after = err.headers.get("Retry-After") if getattr(err, "headers", None) else None
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                pass
    return min(2.0 ** attempt + random.uniform(0, 1.0), 60.0)


def _is_context_length_error(code: int, body: str) -> bool:
    """True if an HTTP error indicates the request exceeded the model's context.

    Covers the explicit 413 (Payload Too Large) status as well as the 400/422
    responses GitHub Models returns with a context-length message in the body.
    """
    if code == 413:
        return True
    if code in (400, 422):
        b = (body or "").lower()
        return any(s in b for s in (
            "context length", "context_length", "maximum context",
            "too long", "too large", "tokens_limit", "token limit",
            "maximum number of tokens", "reduce the length",
        ))
    return False


def _load_taxonomy() -> tuple:
    """Load domain and tech skill lists from prompts/skills_taxonomy.txt."""
    path = Path(__file__).parent / "prompts" / "skills_taxonomy.txt"
    domain, tech = [], []
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[domain_skills]":
            section = "domain"
        elif line == "[tech_skills]":
            section = "tech"
        elif section == "domain":
            domain.append(line)
        elif section == "tech":
            tech.append(line)
    return tuple(domain), tuple(tech)


DOMAIN_SKILLS, TECH_SKILLS = _load_taxonomy()


def _get_github_token() -> str:
    """Get GitHub token — from env var or gh CLI."""
    import os
    if key := os.environ.get("GITHUB_TOKEN"):
        return key
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _find_copilot_cli() -> str:
    """Find the copilot CLI binary — checks PATH, gh copilot, and VS Code's bundled copy."""
    import shutil, os, platform

    # 1. Standalone copilot in PATH
    if shutil.which("copilot"):
        return "copilot"

    # 2. gh copilot (wraps the CLI via GitHub CLI extension)
    if shutil.which("gh"):
        try:
            r = subprocess.run(["gh", "copilot", "--", "--version"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return "gh-copilot"
        except Exception:
            pass

    # 3. VS Code's bundled copilot CLI
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            bat = Path(appdata) / "Code" / "User" / "globalStorage" / "github.copilot-chat" / "copilotCli" / "copilot.bat"
            if bat.exists():
                return str(bat)
    else:
        for base in ("~/.vscode/globalStorage", "~/.vscode-server/data/User/globalStorage"):
            cli = Path(base).expanduser() / "github.copilot-chat" / "copilotCli" / "copilot"
            if cli.exists():
                return str(cli)

    return ""


def _extract_json(raw: str) -> str:
    """Extract a JSON object from a string that may contain markdown fences or prose."""
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        raw = raw[start:end]
    return raw


def _analyze_via_copilot_cli(prompt: str) -> dict | None:
    """Run AI analysis by piping the prompt through an authenticated copilot CLI session.

    This uses the user's existing Copilot subscription — no API key needed.
    Works for VS Code users who don't have gh CLI or a GitHub token.

    Prompt is sent on stdin (not via `-p`) to avoid Windows command-line
    length limits (~32K on cmd.exe, ~8K on some shells). A recursion
    marker is set on the child so a nested `copilot whatidid` does not
    re-enter the CLI fallback path.
    """
    if os.environ.get(_DISABLE_CLI_VAR):
        return None
    if os.environ.get(_CHILD_MARKER):
        # We are already running inside a copilot-spawned analysis child —
        # refuse to recurse.
        return None

    cli = _find_copilot_cli()
    if not cli:
        return None

    # Stdin mode: copilot reads the prompt from stdin when -p is omitted
    # and a piped input is supplied. We keep --available-tools= empty so
    # the analyzer doesn't try to call tools (it should just emit JSON).
    if cli == "gh-copilot":
        cmd = ["gh", "copilot", "--", "--output-format", "text", "--available-tools="]
    else:
        cmd = [cli, "--output-format", "text", "--available-tools="]

    env = os.environ.copy()
    env[_CHILD_MARKER] = "1"

    try:
        print("  (Using Copilot CLI for analysis — no API key needed.)")
        result = subprocess.run(
            cmd, input=prompt,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180, env=env,
        )
        if result.returncode != 0:
            return None

        raw = result.stdout.strip()
        raw = _extract_json(raw)

        return json.loads(raw)
    except subprocess.TimeoutExpired:
        print("  WARNING: Copilot CLI timed out after 180s.")
    except (json.JSONDecodeError, Exception) as e:
        print(f"  WARNING: Copilot CLI analysis failed ({type(e).__name__}).")
    return None


# Run-scoped CLI health state. Once we've established the CLI is broken
# during pre-flight (or via the first failed canary), don't pay the
# subprocess + timeout cost on every subsequent day.
_CLI_HEALTH_CHECKED = False
_CLI_HEALTH_STATUS = "broken"


def check_copilot_cli_health() -> tuple:
    """Canary test for the Copilot CLI fallback path.

    Returns (status, message) where status is:
      "ok"      — CLI is present, accepts our flags, and returns parseable JSON
      "missing" — CLI binary not found
      "broken"  — CLI present but the canary failed (auth, flags, JSON parse, timeout)

    Result is cached for the lifetime of the process; subsequent calls
    return the cached verdict.
    """
    global _CLI_HEALTH_CHECKED, _CLI_HEALTH_STATUS
    if _CLI_HEALTH_CHECKED:
        return _CLI_HEALTH_STATUS, "cached"

    if os.environ.get(_DISABLE_CLI_VAR):
        _CLI_HEALTH_CHECKED = True
        _CLI_HEALTH_STATUS = "missing"
        return "missing", f"Disabled via {_DISABLE_CLI_VAR}."
    if os.environ.get(_CHILD_MARKER):
        _CLI_HEALTH_CHECKED = True
        _CLI_HEALTH_STATUS = "missing"
        return "missing", "Already running inside a Copilot CLI child."

    cli = _find_copilot_cli()
    if not cli:
        _CLI_HEALTH_CHECKED = True
        _CLI_HEALTH_STATUS = "missing"
        return "missing", "Copilot CLI not found in PATH, gh extension, or VS Code bundle."

    _CLI_HEALTH_CHECKED = True
    # Canary: a minimal prompt that should produce a one-key JSON object.
    canary_prompt = (
        'Reply with ONLY this exact JSON object, no markdown fences, no prose: '
        '{"ok": true}'
    )
    if cli == "gh-copilot":
        cmd = ["gh", "copilot", "--", "--output-format", "text", "--available-tools="]
    else:
        cmd = [cli, "--output-format", "text", "--available-tools="]

    env = os.environ.copy()
    env[_CHILD_MARKER] = "1"

    try:
        r = subprocess.run(
            cmd, input=canary_prompt,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=45, env=env,
        )
        if r.returncode != 0:
            _CLI_HEALTH_CHECKED = True
            _CLI_HEALTH_STATUS = "broken"
            return "broken", f"Canary exit {r.returncode}: {r.stderr.strip()[:160]}"
        out = _extract_json(r.stdout.strip())
        parsed = json.loads(out)
        if parsed.get("ok") is True:
            _CLI_HEALTH_CHECKED = True
            _CLI_HEALTH_STATUS = "ok"
            return "ok", "Canary succeeded."
        _CLI_HEALTH_CHECKED = True
        _CLI_HEALTH_STATUS = "broken"
        return "broken", "Canary returned unexpected JSON."
    except subprocess.TimeoutExpired:
        _CLI_HEALTH_CHECKED = True
        _CLI_HEALTH_STATUS = "broken"
        return "broken", "Canary timed out after 45s."
    except json.JSONDecodeError:
        _CLI_HEALTH_CHECKED = True
        _CLI_HEALTH_STATUS = "broken"
        return "broken", "Canary output was not valid JSON."
    except Exception as e:
        _CLI_HEALTH_CHECKED = True
        _CLI_HEALTH_STATUS = "broken"
        return "broken", f"Canary failed ({type(e).__name__})."


def check_api_health() -> tuple:
    """Quick connectivity check to the GitHub Models API.

    Returns (status: str, message: str) where status is one of:
      "ok"        — API reachable and authenticated
      "auth"      — reachable but authentication failed (don't retry)
      "down"      — unreachable or server error (retry may help)
    """
    token = _get_github_token()
    if not token:
        return "auth", "No GitHub token found. Run `gh auth login`."

    # Minimal request — cheap and fast
    payload = json.dumps({
        "model": MODEL, "max_tokens": 5, "temperature": 0,
        "messages": [{"role": "user", "content": "ping"}],
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL, data=payload,
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15):
            return "ok", "API reachable."
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return "auth", f"Authentication failed (HTTP {e.code}). Run `gh auth login` to refresh your token."
        if e.code == 429:
            retry_after = e.headers.get("Retry-After") if e.headers else None
            wait = f" Retry after {retry_after}s." if retry_after else ""
            return "down", f"Rate limited (HTTP 429) — too many requests to the GitHub Models API.{wait}"
        reason = (e.reason or "").strip() if hasattr(e, "reason") else ""
        suffix = f" — {reason}" if reason else ""
        return "down", f"API returned HTTP {e.code}{suffix}."
    except urllib.error.URLError as e:
        return "down", f"API unreachable ({e.reason})."
    except Exception as e:
        return "down", f"API check failed ({type(e).__name__}: {e})."


def _build_transcript(sessions: list) -> str:
    lines = []
    for s in sessions:
        proj      = s["project"]
        repo      = s.get("repository", "")
        branch    = s.get("branch", "")
        proj_path = s.get("project_path", "")

        header = f"PROJECT: {proj}"
        if repo:
            header += f" | REPO: {repo}"
        if branch:
            header += f" | BRANCH: {branch}"
        lines.append(f"\n=== {header} | SESSION: {s['session_id'][:8]} ===")

        # Authoritative project identity. This is the real workspace folder /
        # git repository the work happened in — the goal label MUST be built
        # around this name, never around the wording of the first user message.
        anchor = repo or proj
        if anchor:
            anchor_line = f"CANONICAL PROJECT NAME (anchor the goal label on this): {anchor}"
            if proj_path and proj_path not in (anchor, ""):
                anchor_line += f"  [workspace folder: {proj_path}]"
            lines.append(anchor_line)

        if s.get("session_start") and s.get("session_end"):
            lines.append(f"Time: {s['session_start'][11:19]} → {s['session_end'][11:19]} UTC")
        if s.get("workspace_summary"):
            lines.append(f"Copilot session summary: {s['workspace_summary']}")
        cc = s.get("code_changes", {})
        if cc.get("linesAdded") or cc.get("linesRemoved"):
            n_files = len(cc.get("filesModified", []))
            lines.append(
                f"Code impact: +{cc.get('linesAdded', 0)} / -{cc.get('linesRemoved', 0)} lines"
                + (f", {n_files} file(s)" if n_files else "")
            )
        if s.get("premium_requests"):
            lines.append(f"Premium requests (legacy): {s['premium_requests']}")
        if s.get("ai_credits") is not None:
            lines.append(f"AI credits used: {s['ai_credits']} (~${(s['ai_credits'] or 0) * 0.01:.2f})")
        if s.get("plan"):
            lines.append(f"Copilot plan: {s['plan']}")

        # Enriched quantitative signals for effort calibration
        user_msgs = [m for m in s["messages"] if m["role"] == "user"]
        n_tools = sum(len(m.get("tools_after", [])) for m in s["messages"] if m["role"] == "user")
        reads, edits, runs, searches = 0, 0, 0, 0
        edit_targets: dict = {}
        for m in s["messages"]:
            for t in m.get("tools_after", []):
                tl = t.lower()
                if any(w in tl for w in ("grep", "glob", "search", "find")):
                    searches += 1
                elif any(w in tl for w in ("view", "read", "explore")):
                    reads += 1
                elif any(w in tl for w in ("edit", "create", "write", "replace")):
                    edits += 1
                    fname_match = re.search(r'[\\/]([^\\/]+\.\w{1,8})', t)
                    if fname_match:
                        fn = fname_match.group(1)
                        edit_targets[fn] = edit_targets.get(fn, 0) + 1
                elif any(w in tl for w in ("run", "test", "build", "install", "exec", "powershell",
                                           "command", "pip", "npm", "git")):
                    runs += 1
        iter_depth = round(sum(edit_targets.values()) / max(len(edit_targets), 1), 1) if edit_targets else 0.0
        active_min = compute_active_minutes(s["messages"])
        wall_min = compute_elapsed_minutes(s.get("session_start", ""), s.get("session_end", ""))
        engagement = round(active_min / max(wall_min, 1) * 100, 1)
        files_touched = list(set(cc.get("filesModified", []) + s.get("files_touched", [])))

        signals = [f"SIGNALS: {n_tools} tools ({reads} reads, {searches} searches, {edits} edits, {runs} runs)"]
        signals.append(f"  Conversation turns: {len(user_msgs)}")
        if s.get("premium_requests"):
            signals.append(f"  Premium requests (legacy): {s['premium_requests']}")
        if s.get("ai_credits") is not None:
            signals.append(f"  AI credits: {s['ai_credits']} (~${(s['ai_credits'] or 0) * 0.01:.2f})")
        signals.append(f"  Files touched: {len(files_touched)}")
        logic_l = s.get("lines_logic", 0)
        bp_l = s.get("lines_boilerplate", 0)
        if cc.get("linesAdded") or cc.get("linesRemoved"):
            signals.append(f"  Lines: +{cc.get('linesAdded', 0)} / -{cc.get('linesRemoved', 0)}"
                           f" (added lines split: logic {logic_l}, boilerplate {bp_l})")
        signals.append(f"  Active time: {active_min:.0f}m of {wall_min:.0f}m wall clock ({engagement}% engagement)")
        if iter_depth > 1:
            signals.append(f"  Iteration depth: {iter_depth} edits/file avg")
        if s.get("git_ops"):
            ops = s["git_ops"]
            commits = ops.count("commit")
            prs = ops.count("pr")
            parts = []
            if commits: parts.append(f"{commits} commit{'s' if commits != 1 else ''}")
            if prs: parts.append(f"{prs} PR{'s' if prs != 1 else ''}")
            if parts:
                signals.append(f"  Git ops: {', '.join(parts)}")
        lines.append("\n".join(signals))

        for msg in s["messages"]:
            if msg["role"] != "user":
                continue
            lines.append(f"\n[INSTRUCTION] {msg['text']}")
            for t in msg.get("tools_after", []):
                lines.append(f"  • {t}")

    return "\n".join(lines)


_CACHE_DIR = Path(__file__).parent / "cache"


def _cache_path(target_date: str) -> Path:
    return _CACHE_DIR / f"{target_date}.json"


def _build_analysis_prompt(transcript: str, domain_list: str, tech_list: str) -> str:
    """Build the analysis prompt — loads template from prompts/analysis.txt."""
    prompt_path = Path(__file__).parent / "prompts" / "analysis.txt"
    template = prompt_path.read_text(encoding="utf-8")
    return template.format(
        transcript=transcript,
        domain_list=domain_list,
        tech_list=tech_list,
    )


def _prepare_prompt(sessions: list, max_chars: int = MAX_TRANSCRIPT_CHARS) -> str:
    """Build the analysis prompt for a list of sessions.

    Centralises transcript construction, truncation, and domain/tech list
    formatting so every fallback branch uses identical inputs. ``max_chars``
    caps the transcript length and can be lowered to recover from a server-side
    context-length rejection.
    """
    transcript = _build_transcript(sessions)
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n\n[... transcript truncated for length ...]"
    domain_list = ", ".join(DOMAIN_SKILLS[:6]) + ", ..."
    tech_list   = ", ".join(TECH_SKILLS[:6])   + ", ..."
    return _build_analysis_prompt(transcript, domain_list, tech_list)


def analyze_day(target_date: str, sessions: list, refresh: bool = False,
                use_api: bool = True,
                analysis_source: AnalysisSource | None = None) -> dict:
    """Analyse a day's worth of Copilot sessions.

    `analysis_source` (preferred) controls the fallback chain:
      "api"       — Models API → Copilot CLI → heuristic
      "cli"       — Copilot CLI → heuristic (skip Models API)
      "heuristic" — heuristic only (no network, no subprocess)

    `use_api` is kept for backward compatibility: False maps to "heuristic",
    True maps to "api" unless `analysis_source` is also supplied.
    """
    # Resolve effective source
    if analysis_source is None:
        analysis_source = "api" if use_api else "heuristic"
    if analysis_source not in ("api", "cli", "heuristic"):
        analysis_source = "api"
    # Aggregate metrics across all sessions
    total_tokens = {
        "input":          sum(s["tokens"]["input"]          for s in sessions),
        "output":         sum(s["tokens"]["output"]         for s in sessions),
        "cache_read":     sum(s["tokens"]["cache_read"]     for s in sessions),
        "cache_creation": sum(s["tokens"]["cache_creation"] for s in sessions),
    }
    total_tokens["total"] = sum(total_tokens.values())

    # Aggregate per-model token breakdown across sessions
    total_tokens_by_model: dict = {}
    for s in sessions:
        for model, toks in s.get("tokens_by_model", {}).items():
            if model not in total_tokens_by_model:
                total_tokens_by_model[model] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
            for k in ("input", "output", "cache_read", "cache_creation"):
                total_tokens_by_model[model][k] += toks.get(k, 0)
    total_inline_model_pricing: dict = {}
    for s in sessions:
        total_inline_model_pricing.update(s.get("inline_model_pricing") or {})

    # Aggregate per-model request count across sessions. The per-session
    # field is canonical as ``{model: int}`` but an earlier draft of the
    # VS Code parser used ``{model: {count: int}}`` — accept both shapes.
    total_requests_by_model: dict = {}
    for s in sessions:
        for model, v in (s.get("requests_by_model") or {}).items():
            if isinstance(v, dict):
                count = int(v.get("count", 0))
            else:
                try:
                    count = int(v)
                except (TypeError, ValueError):
                    count = 0
            total_requests_by_model[model] = total_requests_by_model.get(model, 0) + count

    total_premium     = sum(s.get("premium_requests", 0)           for s in sessions)
    total_api_ms      = sum(s.get("total_api_ms", 0)               for s in sessions)
    total_lines_added = sum(s.get("code_changes", {}).get("linesAdded", 0)   for s in sessions)
    total_lines_removed = sum(s.get("code_changes", {}).get("linesRemoved", 0) for s in sessions)

    # Session-state census: how many sessions never wrote `session.shutdown`?
    # For those, only directly-emitted per-event signals are captured (output
    # tokens per message + compaction tokenDetails). Non-compaction input
    # tokens are not in the event stream and thus excluded — the report uses
    # this count to disclose that totals are a lower bound for open sessions.
    open_session_count = sum(1 for s in sessions if s.get("session_state") == "open")
    total_session_count = len(sessions)

    # Aggregate per-session burn findings into a single flat list, tagging
    # each finding with its source session so the report can show context.
    all_burn_findings: list = []
    for s in sessions:
        sid = s.get("session_id", "")
        proj = s.get("project", "")
        date = s.get("date", "")
        for f in (s.get("burn_findings") or []):
            tagged = dict(f)
            tagged["session_id"] = sid
            tagged["project"]    = proj
            tagged["date"]       = date
            all_burn_findings.append(tagged)

    # Aggregate inline model pricing metadata from all sessions. Each VS Code
    # session can carry authoritative per-model rates harvested from JSONL;
    # later entries overwrite earlier ones so the most recent rates win.
    inline_model_pricing: dict = {}
    for s in sessions:
        inline_model_pricing.update(s.get("inline_model_pricing") or {})

    # AI Credits aggregation (server-emitted preferred; otherwise None and
    # report.py will compute from tokens × per-model rates).
    has_server_credits = any(s.get("ai_credits") is not None for s in sessions)
    total_ai_credits = (sum((s.get("ai_credits") or 0) for s in sessions)
                        if has_server_credits else None)
    total_ai_credits_by_model: dict = {}
    for s in sessions:
        for model, credits in (s.get("ai_credits_by_model") or {}).items():
            total_ai_credits_by_model[model] = total_ai_credits_by_model.get(model, 0) + credits
    # Plan + auto-model flag: take the first non-empty / any-true value.
    plan = next((s.get("plan") for s in sessions if s.get("plan")), "")
    auto_model = any(s.get("auto_model_selection") for s in sessions)

    all_files = []
    for s in sessions:
        all_files.extend(s.get("code_changes", {}).get("filesModified", []))
        all_files.extend(s.get("files_touched", []))
    all_files = list(dict.fromkeys(all_files))  # deduplicate, preserve order

    # Build per-project session metrics for evidence display
    _session_metrics: dict = {}
    for s in sessions:
        proj = s["project"]
        n_tools = s.get("tool_invocations", 0) or sum(
            len(m.get("tools_after", [])) for m in s["messages"] if m["role"] == "user"
        )
        cc = s.get("code_changes", {})
        active_min = compute_active_minutes(s["messages"])
        wall_min = compute_elapsed_minutes(s.get("session_start", ""), s.get("session_end", ""))

        # New signals: conversation turns, tool types, files, iteration depth
        user_msgs = [m for m in s["messages"] if m["role"] == "user"]
        conv_turns = len(user_msgs)

        # Classify turns: substantive (real instructions) vs trivial (confirmations)
        _trivial_rx = re.compile(
            r'^(yes|no|ok|okay|sure|thanks|thank you|perfect|great|good|looks good|'
            r'go ahead|do it|please|correct|exactly|right|got it|nice|awesome|'
            r'commit|push|open|lgtm|ship it|done|\d)\s*[.!?]*$', re.I)
        substantive = 0
        for um in user_msgs:
            first_line = um["text"].strip().split("\n")[0].strip()
            if len(first_line) >= 20 and not _trivial_rx.match(first_line):
                substantive += 1
        files_touched = list(set(
            cc.get("filesModified", []) + s.get("files_touched", [])
        ))
        files_count = len(files_touched)

        # Classify tool types from tool_after descriptions
        reads, edits, runs, searches = 0, 0, 0, 0
        edit_targets: dict = {}  # filename → edit count for iteration depth
        for m in s["messages"]:
            for t in m.get("tools_after", []):
                tl = t.lower()
                if any(w in tl for w in ("grep", "glob", "search", "find")):
                    searches += 1
                elif any(w in tl for w in ("view", "read", "explore")):
                    reads += 1
                elif any(w in tl for w in ("edit", "create", "write", "replace")):
                    edits += 1
                    # Extract filename for iteration tracking
                    fname_match = re.search(r'[\\/]([^\\/]+\.\w{1,8})', t)
                    if fname_match:
                        fn = fname_match.group(1)
                        edit_targets[fn] = edit_targets.get(fn, 0) + 1
                elif any(w in tl for w in ("run", "test", "build", "install", "exec", "powershell",
                                           "command", "pip", "npm", "git")):
                    runs += 1

        # Iteration depth: avg edits per unique file edited (0 if no edits)
        iter_depth = round(sum(edit_targets.values()) / max(len(edit_targets), 1), 1) if edit_targets else 0.0

        if proj in _session_metrics:
            m = _session_metrics[proj]
            m["tokens"]           += s["tokens"]["total"]
            m["tool_invocations"] += n_tools
            m["premium_requests"] += s.get("premium_requests", 0)
            m["lines_added"]      += cc.get("linesAdded", 0)
            m["lines_removed"]    += cc.get("linesRemoved", 0)
            m["lines_logic"]      += s.get("lines_logic", 0)
            m["lines_boilerplate"] += s.get("lines_boilerplate", 0)
            m["active_minutes"]   += active_min
            m["wall_clock_minutes"] += wall_min
            m["sessions"]         += 1
            m["conversation_turns"] += conv_turns
            m["substantive_turns"] += substantive
            m["reads"]            += reads
            m["edits"]            += edits
            m["runs"]             += runs
            m["searches"]         += searches
            m["files_touched_count"] = len(set(
                files_touched + [f for f in all_files if f in s.get("files_touched", [])]
            )) or m["files_touched_count"]
            # Update iteration depth as weighted average
            prev_edits = m.get("_total_file_edits", 0)
            prev_files = m.get("_total_files_edited", 0)
            curr_edits = sum(edit_targets.values())
            curr_files = len(edit_targets)
            total_e = prev_edits + curr_edits
            total_f = prev_files + curr_files
            m["iteration_depth"] = round(total_e / max(total_f, 1), 1)
            m["_total_file_edits"] = total_e
            m["_total_files_edited"] = total_f
            # Roll up token-by-model and ai_credits so downstream code can
            # compute per-project credits via _ai_credits_for().
            for mdl, toks in (s.get("tokens_by_model") or {}).items():
                bucket = m["tokens_by_model"].setdefault(mdl, {
                    "input": 0, "output": 0, "cache_read": 0, "cache_creation": 0, "total": 0,
                })
                for k, v in toks.items():
                    bucket[k] = bucket.get(k, 0) + int(v or 0)
            if (sc := s.get("ai_credits")) is not None:
                m["ai_credits"] = (m.get("ai_credits") or 0) + int(sc)
            m["auto_model_selection"] = m.get("auto_model_selection") or bool(s.get("auto_model_selection"))
        else:
            _session_metrics[proj] = {
                "tokens":            s["tokens"]["total"],
                "tool_invocations":  n_tools,
                "premium_requests":  s.get("premium_requests", 0),
                "lines_added":       cc.get("linesAdded", 0),
                "lines_removed":     cc.get("linesRemoved", 0),
                "lines_logic":       s.get("lines_logic", 0),
                "lines_boilerplate": s.get("lines_boilerplate", 0),
                "active_minutes":    active_min,
                "wall_clock_minutes": wall_min,
                "sessions":          1,
                "conversation_turns": conv_turns,
                "substantive_turns": substantive,
                "reads":             reads,
                "edits":             edits,
                "runs":              runs,
                "searches":          searches,
                "files_touched_count": files_count,
                "iteration_depth":   iter_depth,
                "_total_file_edits": sum(edit_targets.values()),
                "_total_files_edited": len(edit_targets),
                "tokens_by_model":   {
                    mdl: dict(toks) for mdl, toks in (s.get("tokens_by_model") or {}).items()
                },
                "ai_credits":        s.get("ai_credits"),
                "auto_model_selection": bool(s.get("auto_model_selection")),
            }

    # Also index by last path component for flexible goal→project matching
    for proj in list(_session_metrics.keys()):
        last = proj.replace("\\", "/").split("/")[-1]
        _session_metrics.setdefault(last, _session_metrics[proj])

    def _attach_metrics(result: dict) -> dict:
        result["tokens"]           = total_tokens
        result["tokens_by_model"]  = total_tokens_by_model
        result["inline_model_pricing"] = total_inline_model_pricing
        result["premium_requests"] = total_premium
        result["requests_by_model"] = total_requests_by_model
        result["ai_credits"]       = total_ai_credits
        result["ai_credits_by_model"] = total_ai_credits_by_model
        result["plan"]             = plan
        result["auto_model_selection"] = auto_model
        result["total_api_ms"]     = total_api_ms
        result["lines_added"]      = total_lines_added
        result["lines_removed"]    = total_lines_removed
        result["files_modified"]   = all_files
        result["session_metrics"]  = _session_metrics
        result["open_session_count"]  = open_session_count
        result["total_session_count"] = total_session_count
        result["burn_findings"]       = all_burn_findings
        result["inline_model_pricing"] = inline_model_pricing
        return result

    # Return cached result if available
    cache_file = _cache_path(target_date)
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("locked"):
                if refresh:
                    print("  (Cache is locked — ignoring --refresh. Delete the cache file to unlock.)")
                else:
                    method = cached.get("analysis_method", "ai")
                    if method == "heuristic":
                        print("  WARNING: Using locked HEURISTIC cache — estimates are approximate.")
                    else:
                        print("  (Using locked cache — estimates are frozen.)")
                return _attach_metrics(cached)
            if not refresh:
                method = cached.get("analysis_method", "ai")
                if method == "heuristic":
                    print("  WARNING: Using cached HEURISTIC analysis -- estimates are approximate. Pass --refresh to re-analyse with AI.")
                else:
                    print("  (Using cached analysis — pass --refresh to re-analyse.)")
                return _attach_metrics(cached)
        except Exception:
            pass

    def _finalize_and_cache(result: dict, method: str) -> dict:
        """Stamp common metadata, attach aggregated metrics, and persist to cache."""
        result["sessions_count"]  = len(sessions)
        result["projects"]        = list(dict.fromkeys(s["project"] for s in sessions))
        result["analysis_method"] = method
        _attach_metrics(result)
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        except Exception:
            pass
        return result

    if analysis_source == "heuristic":
        # Respect strict non-AI / non-network mode and use heuristics only.
        result = _fallback_analysis(target_date, sessions)
        _attach_metrics(result)
        # Persist heuristic results too so subsequent runs don't repeatedly
        # incur the (small) cost; --refresh always re-runs.
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            result["sessions_count"] = len(sessions)
            result["projects"] = list(dict.fromkeys(s["project"] for s in sessions))
            cache_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        except Exception:
            pass
        return result

    prompt = _prepare_prompt(sessions)

    # CLI-first path: explicit caller request, OR API path with no token.
    if analysis_source == "cli":
        cli_result = _analyze_via_copilot_cli(prompt)
        if cli_result:
            return _finalize_and_cache(cli_result, "ai-copilot-cli")
        print("  Copilot CLI fallback failed — using heuristic.")
        return _attach_metrics(_fallback_analysis(target_date, sessions))

    # analysis_source == "api"
    token = _get_github_token()
    if not token:
        # No token = Models API impossible. Try CLI before heuristic.
        print("  (No GitHub token — trying Copilot CLI for analysis...)")
        cli_result = _analyze_via_copilot_cli(prompt)
        if cli_result:
            return _finalize_and_cache(cli_result, "ai-copilot-cli")
        print("  (Copilot CLI unavailable — using heuristic analysis. "
              "Run `gh auth login` to enable semantic analysis.)")
        return _attach_metrics(_fallback_analysis(target_date, sessions))

    # Build the request payload inside the loop so an oversized-prompt rejection
    # can rebuild it from a shrunken transcript and retry. ``shrink_caps`` holds
    # progressively smaller transcript budgets to fall back to on a 413/400
    # context-length error.
    current_prompt = prompt
    shrink_caps    = [16000, 8000]

    def _build_req(p: str) -> urllib.request.Request:
        payload = json.dumps({
            "model":       MODEL,
            "max_tokens":  3000,
            "temperature": 0,
            "messages":    [{"role": "user", "content": p}],
        }).encode("utf-8")
        return urllib.request.Request(
            API_URL, data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "content-type":  "application/json",
            },
            method="POST",
        )

    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(_build_req(current_prompt), timeout=120) as resp:
                response = json.loads(resp.read().decode("utf-8"))
            raw = response["choices"][0]["message"]["content"].strip()
            raw = _extract_json(raw)
            analysis = json.loads(raw)
            return _finalize_and_cache(analysis, "ai")

        except urllib.error.HTTPError as e:
            # Reading the error body can itself raise (e.g. IncompleteRead on a
            # truncated 429 response), so guard it — never let cleanup crash.
            try:
                body = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                body = ""
            # Context-length / payload-too-large: shrink the transcript and retry
            # at a smaller budget instead of burning attempts on the same size.
            if _is_context_length_error(e.code, body):
                if shrink_caps:
                    new_cap = shrink_caps.pop(0)
                    current_prompt = _prepare_prompt(sessions, new_cap)
                    print(f"  API {e.code} (prompt too large); "
                          f"shrinking transcript to {new_cap:,} chars and retrying...")
                    continue
                print(f"  WARNING: prompt still too large after shrinking "
                      f"(API {e.code}). Falling back.")
                break
            # 429 (rate limit) and 5xx are transient: back off and retry.
            if e.code == 429 or 500 <= e.code < 600:
                if attempt < max_attempts:
                    delay = _retry_delay(e, attempt)
                    print(f"  API {e.code} (attempt {attempt}/{max_attempts}); "
                          f"retrying in {delay:.0f}s...")
                    time.sleep(delay)
                    continue
            print(f"  WARNING: API error {e.code}: {body}")
            break
        except (urllib.error.URLError, http.client.IncompleteRead,
                ConnectionError, TimeoutError) as e:
            # Network-level hiccup — retry a few times before giving up.
            if attempt < max_attempts:
                delay = _retry_delay(None, attempt)
                print(f"  API connection issue ({type(e).__name__}); "
                      f"retrying in {delay:.0f}s...")
                time.sleep(delay)
                continue
            print(f"  WARNING: API unavailable ({type(e).__name__}).")
            break
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  WARNING: API returned unexpected data ({type(e).__name__}).")
            break

    # API failed — try Copilot CLI before falling back to heuristic
    print("  Trying Copilot CLI as fallback...")
    cli_result = _analyze_via_copilot_cli(prompt)
    if cli_result:
        return _finalize_and_cache(cli_result, "ai-copilot-cli")

    print("  Using heuristic fallback -- estimates will be approximate. Re-run with --refresh when API is available.")
    return _attach_metrics(_fallback_analysis(target_date, sessions))


# ── Heuristic fallback ───────────────────────────────────────────────────────

def _word(w: str, s: str) -> bool:
    return bool(re.search(r'\b' + re.escape(w) + r'\b', s))


def _infer_skills(text: str, tools: list) -> tuple:
    t, ts = text.lower(), " ".join(tools).lower()
    domain, tech = [], []
    if any(_word(w, t) for w in ("plan", "design", "architect", "structure")):
        domain.append("System Architecture")
    if any(_word(w, t) for w in ("research", "find", "look up", "understand")):
        domain.append("Technical Research")
    if any(_word(w, t) for w in ("analyze", "report", "metric", "data")):
        domain.append("Data Analysis")
    if any(_word(w, t) for w in ("write", "draft", "document")):
        domain.append("Technical Writing")
    if any(_word(w, t) for w in ("debug", "fix", "error", "bug")):
        tech.append("Debugging")
    if ".py" in ts or "python" in ts:
        tech.append("Python")
    if ".html" in ts or "html" in ts:
        tech.append("HTML/CSS")
    if any(_word(w, t) for w in ("deploy", "commit", "push")):
        tech.append("DevOps/CI-CD")
    if not domain:
        domain.append("Product Planning")

    # Infer task_type
    task_type = "Development"
    if any(_word(w, t) for w in ("debug", "fix", "error", "bug", "crash", "broken")):
        task_type = "Bug Fix & Debug"
    elif any(_word(w, t) for w in ("analyze", "research", "investigate", "report", "metric", "data")):
        task_type = "Analysis & Research"
    elif any(_word(w, t) for w in ("design", "ui", "ux", "layout", "style", "css", "visual")):
        task_type = "Design & UX"
    elif any(_word(w, t) for w in ("deploy", "release", "pipeline", "ci", "cd", "ops", "config")):
        task_type = "Execution & Ops"

    # Infer professional_roles (heuristic fallback — mirrors the AI prompt taxonomy)
    roles = []
    if task_type == "Bug Fix & Debug":
        roles.append("QA Engineer")
    if task_type == "Design & UX" or ".html" in ts or ".css" in ts:
        roles.append("UX Designer" if "ux" in ts or "wireframe" in ts or "flow" in ts else "Frontend Developer")
    if ".py" in ts or "python" in ts or task_type == "Development":
        roles.append("Software Engineer")
    # Data Analyst = actual data/SQL/metrics work only
    if any(_word(w, t) for w in ("sql", "query", "dashboard", "kpi", "dataset", "dataframe", "pivot", "bi report", "power bi")):
        roles.append("Data Analyst")
    elif any(_word(w, t) for w in ("pipeline", "etl", "schema", "warehouse", "dbt")):
        roles.append("Data Engineer")
    if any(_word(w, t) for w in ("document", "readme", "how-to", "guide", "explainer")):
        roles.append("Technical Writer")
    if any(_word(w, t) for w in ("deploy", "dockerfile", "kubernetes", "terraform", "ci/cd", "github action")):
        roles.append("DevOps Engineer")
    if any(_word(w, t) for w in ("architect", "api design", "integration design")):
        roles.append("Solutions Architect")
    if any(_word(w, t) for w in ("roadmap", "user stor", "prioriti", "backlog", "product requirement")):
        roles.append("Product Manager")
    if any(_word(w, t) for w in ("project plan", "milestone", "delivery", "dependency", "status report", "program")):
        roles.append("Program Manager")
    if any(_word(w, t) for w in ("process map", "gap analysis", "workflow", "business requirement", "stakeholder interview")):
        roles.append("Business Analyst")
    if any(_word(w, t) for w in ("strategy", "recommendation", "framework", "benchmark", "executive", "consulting")):
        roles.append("Management Consultant")
    if any(_word(w, t) for w in ("financial model", "valuation", "forecast", "portfolio", "backtest", "alpha", "pnl", "quant")):
        roles.append("Financial Analyst")
    if any(_word(w, t) for w in ("compliance", "regulation", "audit", "risk assessment", "kyc", "aml", "regulatory")):
        roles.append("Risk & Compliance Analyst")
    if any(_word(w, t) for w in ("experiment", "hypothesis", "literature", "simulation", "scientific", "research paper")):
        roles.append("Research Scientist")
    if not roles:
        # Generic research/investigation — technical vs strategic
        if any(_word(w, t) for w in ("research", "investigate", "evaluate", "explore", "assess", "compare")):
            roles.append("Software Engineer" if any(_word(w, t) for w in ("tool", "library", "api", "sdk", "code", "script")) else "Business Analyst")
        else:
            roles.append("Software Engineer")

    return domain[:2], tech[:2], task_type, roles[:2]


def _conservative_hours(text: str, tools: list, premium_reqs: int = 0, tokens_total: int = 0) -> float:
    """Calibrated effort estimate matching the AI prompt's anchor scale."""
    n, t = len(tools), text.lower()
    # Trivial mechanical tasks — always capped
    if any(_word(w, t) for w in ("install", "deploy", "push", "run", "config", "setup")):
        return 0.5 if n > 5 else 0.25
    if any(_word(w, t) for w in ("update", "change", "small", "quick", "rename", "tweak")):
        return 0.5
    # Very simple interactions
    if n <= 1:
        return 0.25
    if n <= 3:
        return 0.5
    # Bug fix — scales with complexity
    if any(_word(w, t) for w in ("fix", "debug", "error", "bug")):
        if n > 30:   return 3.0
        if n > 10:   return 1.5
        return 1.0
    # Substantial development — scales with tool count
    if any(_word(w, t) for w in ("implement", "build", "create", "write", "code")):
        if n > 50:   return 6.0
        if n > 30:   return 4.0
        if n > 15:   return 2.5
        return 1.5
    # Design / planning
    if any(_word(w, t) for w in ("plan", "design", "architect")):
        if n > 20:   return 3.0
        return 1.5
    # Analysis / research
    if any(_word(w, t) for w in ("analyze", "research", "investigate", "report")):
        if n > 20:   return 3.0
        return 1.5
    # Default — scale with tool count
    if n > 30:   return 2.0
    if n > 10:   return 1.0
    return 0.75


def _summarize_message(text: str, tools: list) -> str:
    """Generate a brief description from user message and tool calls."""
    # Use the first line of the user message, cleaned up
    first_line = text.split("\n")[0].strip()
    # Truncate long messages
    if len(first_line) > 80:
        first_line = first_line[:77] + "..."
    # If tools were used, mention the count
    if tools:
        return f"{first_line} ({len(tools)} tool calls)"
    return first_line


def _fallback_analysis(target_date: str, sessions: list) -> dict:
    goals = []
    for s in sessions:
        user_msgs = [m for m in s["messages"] if m["role"] == "user"]
        if not user_msgs:
            continue
        proj  = s["project"].replace("/", " › ").title()
        tasks = []
        for msg in user_msgs:
            text, tools = msg["text"], msg.get("tools_after", [])
            hours = _conservative_hours(text, tools, s.get("premium_requests", 0), s.get("tokens", {}).get("total", 0))
            domain, tech, task_type, prof_roles = _infer_skills(text, tools)
            first = text.split("\n")[0].strip()
            title = (first if not first[0].isdigit() else text[:75])[:75]
            tasks.append({
                "title":              title,
                "what_got_done":      _summarize_message(text, tools),
                "domain_skills":      domain,
                "tech_skills":        tech,
                "task_type":          task_type,
                "professional_roles": prof_roles,
                "human_hours":        hours,
            })
        goal_hours = sum(t["human_hours"] for t in tasks)
        # Apply complexity multiplier for sessions with high rework or broad scope
        files_touched = s.get("files_touched", [])
        files_count = len(files_touched)
        # Compute iteration depth from tool calls
        edit_targets = {}
        for msg in s["messages"]:
            for t in msg.get("tools_after", []):
                tl = t.lower()
                if any(w in tl for w in ("edit", "create", "write", "replace")):
                    fname_match = re.search(r'[\\/]([^\\/]+\.\w{1,8})', t)
                    if fname_match:
                        fn = fname_match.group(1)
                        edit_targets[fn] = edit_targets.get(fn, 0) + 1
        iter_depth = round(sum(edit_targets.values()) / max(len(edit_targets), 1), 1) if edit_targets else 0.0
        if goal_hours >= 0.50:
            cmult = 1.0
            if iter_depth >= 2.5: cmult += 0.10
            if iter_depth >= 5:   cmult += 0.15
            if iter_depth >= 10:  cmult += 0.10
            if files_count >= 5:  cmult += 0.10
            if files_count >= 10: cmult += 0.15
            cmult = min(cmult, 1.60)
            for task in tasks:
                task["human_hours"] *= cmult
            goal_hours = sum(t["human_hours"] for t in tasks)
        goals.append({
            "title":       f"Worked on {proj}",
            "summary":     f"{len(tasks)} task{'s' if len(tasks) != 1 else ''} completed in {proj}.",
            "human_hours": round(goal_hours * 4) / 4,
            "tasks":       tasks,
        })

    projects = list({s["project"] for s in sessions})
    return {
        "headline":        f"Copilot activity on {target_date}",
        "primary_focus":   sessions[0]["project"].split("/")[-1].title() if sessions else "Mixed",
        "day_narrative":   "Heuristic summary — estimates are approximate. Re-run with --refresh when API is available for accurate analysis.",
        "goals":           goals,
        "sessions_count":  len(sessions),
        "projects":        projects,
        "analysis_method": "heuristic",
    }
