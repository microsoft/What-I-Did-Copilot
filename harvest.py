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

_INTENT_CATEGORIES = {
    "Building":      _re.compile(r"\b(create|add|generate|implement|write|make|build|produce|include|set up|initialize|scaffold|install|open it|rerun|run)\b", _re.I),
    "Investigating": _re.compile(r"\b(examine|why does|why is|what.s going on|debug|diagnose|analyze what|look at this|can you examine|what.s wrong|trace|root cause|broken|fails|failing|error|identical.+different)\b", _re.I),
    "Designing":     _re.compile(r"\b(redesign|prominent|visual|layout|style|look like|look more|distinction|spacing|story|compelling|section|appearance|prototype|mockup|wireframe|branding|banner)\b", _re.I),
    "Researching":   _re.compile(r"\b(what.s the|how does|how do|are there|can i do|do they|what can|what would|how come|cost|limit|explain|compare|difference|option)\b", _re.I),
    "Iterating":     _re.compile(r"\b(adjust|simplify|change the|not impressed|didn.t like|better|improve|also like|refine|tweak|move this|swap|resize|reorder|reduce|remove the)\b", _re.I),
    "Shipping":      _re.compile(r"\b(commit|push|pr\b|pull request|merge|deploy|ship|tag|release|check.?in)\b", _re.I),
    "Planning":      _re.compile(r"\b(plan|propose|approach|strategy|stages|phases|priority|before that|options|go ahead|wait for)\b", _re.I),
    "Testing":       _re.compile(r"\b(test|verify|validate|check if|smoke|does it work|try it|confirm)\b", _re.I),
    "Configuring":   _re.compile(r"\b(config|setup|auth|login|permission|access|credential|settings|env|alias|profile)\b", _re.I),
    "Navigating":    _re.compile(r"\b(find|search|where is|show me|list|fetch|locate|get the latest|look for)\b", _re.I),
}

_INTENT_ICONS = {
    "Building":      "&#128679;",  # 🏗
    "Investigating": "&#128300;",  # 🔬
    "Designing":     "&#127912;",  # 🎨
    "Researching":   "&#128202;",  # 📊
    "Iterating":     "&#128260;",  # 🔄
    "Shipping":      "&#128640;",  # 🚀
    "Planning":      "&#128203;",  # 📋
    "Testing":       "&#9989;",    # ✅
    "Configuring":   "&#9881;",    # ⚙
    "Navigating":    "&#129517;",  # 🧭
}

_INTENT_COLORS = {
    "Building":      "#0078d4",
    "Investigating": "#e65100",
    "Designing":     "#7b1fa2",
    "Researching":   "#1a7f37",
    "Iterating":     "#0969da",
    "Shipping":      "#cf222e",
    "Planning":      "#8250df",
    "Testing":       "#1a7f37",
    "Configuring":   "#6a737d",
    "Navigating":    "#bf8700",
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
