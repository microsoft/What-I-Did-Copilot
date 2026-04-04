"""
analyze.py — Semantic analysis of the day's Copilot sessions.

Uses the GitHub Models API (gpt-4o-mini) authenticated with the same GitHub token
that gh CLI already has — no additional credentials needed.
"""
import json
import re
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from harvest import compute_active_minutes, compute_elapsed_minutes

# GitHub Models API — OpenAI-compatible endpoint, authenticated with GitHub token
API_URL = "https://models.github.ai/inference/chat/completions"
MODEL   = "openai/gpt-4o-mini"

DOMAIN_SKILLS = (
    "System Architecture", "Product Planning", "Requirements Analysis",
    "Technical Research", "Data Analysis", "Statistical Modelling",
    "UX Design", "Product Management", "Project Management",
    "Technical Writing", "Documentation", "Stakeholder Communication",
    "Prompt Engineering", "Security Review", "Code Review",
)
TECH_SKILLS = (
    "Python", "JavaScript", "TypeScript", "Bash/Shell",
    "HTML/CSS", "SQL", "API Integration", "DevOps/CI-CD",
    "Cloud Infrastructure", "Database Design", "Machine Learning",
    "Data Engineering", "Debugging", "Refactoring", "Frontend Development",
)


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


def _analyze_via_copilot_cli(prompt: str) -> dict | None:
    """Run AI analysis by piping the prompt through an authenticated copilot CLI session.

    This uses the user's existing Copilot subscription — no API key needed.
    Works for VS Code users who don't have gh CLI or a GitHub token.
    """
    cli = _find_copilot_cli()
    if not cli:
        return None

    if cli == "gh-copilot":
        cmd = ["gh", "copilot", "--", "-p", prompt, "--output-format", "text",
               "--no-file-access"]
    else:
        cmd = [cli, "-p", prompt, "--output-format", "text",
               "--no-file-access"]

    try:
        print("  (Using Copilot CLI for analysis — no API key needed.)")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            return None

        raw = result.stdout.strip()
        # Extract JSON from response — copilot may wrap it in markdown fences
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
        # Find first { to last }
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]

        return json.loads(raw)
    except subprocess.TimeoutExpired:
        print("  WARNING: Copilot CLI timed out after 180s.")
    except (json.JSONDecodeError, Exception) as e:
        print(f"  WARNING: Copilot CLI analysis failed ({type(e).__name__}).")
    return None


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
        return "down", f"API returned HTTP {e.code}."
    except urllib.error.URLError:
        return "down", "API unreachable (timed out)."
    except Exception as e:
        return "down", f"API check failed ({e})."


def _build_transcript(sessions: list) -> str:
    lines = []
    for s in sessions:
        proj   = s["project"]
        repo   = s.get("repository", "")
        branch = s.get("branch", "")

        header = f"PROJECT: {proj}"
        if repo:
            header += f" | REPO: {repo}"
        if branch:
            header += f" | BRANCH: {branch}"
        lines.append(f"\n=== {header} | SESSION: {s['session_id'][:8]} ===")

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
            lines.append(f"Premium requests: {s['premium_requests']}")

        # Enriched quantitative signals for effort calibration
        user_msgs = [m for m in s["messages"] if m["role"] == "user"]
        n_tools = sum(len(m.get("tools_after", [])) for m in s["messages"] if m["role"] == "user")
        reads, edits, runs = 0, 0, 0
        edit_targets: dict = {}
        for m in s["messages"]:
            for t in m.get("tools_after", []):
                tl = t.lower()
                if any(w in tl for w in ("view", "read", "grep", "glob", "search", "find", "explore")):
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

        signals = [f"SIGNALS: {n_tools} tools ({reads} reads, {edits} edits, {runs} runs)"]
        signals.append(f"  Conversation turns: {len(user_msgs)}")
        if s.get("premium_requests"):
            signals.append(f"  Premium requests: {s['premium_requests']}")
        signals.append(f"  Files touched: {len(files_touched)}")
        if cc.get("linesAdded") or cc.get("linesRemoved"):
            signals.append(f"  Lines: +{cc.get('linesAdded', 0)} / -{cc.get('linesRemoved', 0)}")
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


def analyze_day(target_date: str, sessions: list, refresh: bool = False, use_api: bool = True) -> dict:
    # Aggregate metrics across all sessions
    total_tokens = {
        "input":          sum(s["tokens"]["input"]          for s in sessions),
        "output":         sum(s["tokens"]["output"]         for s in sessions),
        "cache_read":     sum(s["tokens"]["cache_read"]     for s in sessions),
        "cache_creation": sum(s["tokens"]["cache_creation"] for s in sessions),
    }
    total_tokens["total"] = sum(total_tokens.values())

    total_premium     = sum(s.get("premium_requests", 0)           for s in sessions)
    total_api_ms      = sum(s.get("total_api_ms", 0)               for s in sessions)
    total_lines_added = sum(s.get("code_changes", {}).get("linesAdded", 0)   for s in sessions)
    total_lines_removed = sum(s.get("code_changes", {}).get("linesRemoved", 0) for s in sessions)

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
        files_touched = list(set(
            cc.get("filesModified", []) + s.get("files_touched", [])
        ))
        files_count = len(files_touched)

        # Classify tool types from tool_after descriptions
        reads, edits, runs = 0, 0, 0
        edit_targets: dict = {}  # filename → edit count for iteration depth
        for m in s["messages"]:
            for t in m.get("tools_after", []):
                tl = t.lower()
                if any(w in tl for w in ("view", "read", "grep", "glob", "search", "find", "explore")):
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
            m["active_minutes"]   += active_min
            m["wall_clock_minutes"] += wall_min
            m["sessions"]         += 1
            m["conversation_turns"] += conv_turns
            m["reads"]            += reads
            m["edits"]            += edits
            m["runs"]             += runs
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
        else:
            _session_metrics[proj] = {
                "tokens":            s["tokens"]["total"],
                "tool_invocations":  n_tools,
                "premium_requests":  s.get("premium_requests", 0),
                "lines_added":       cc.get("linesAdded", 0),
                "lines_removed":     cc.get("linesRemoved", 0),
                "active_minutes":    active_min,
                "wall_clock_minutes": wall_min,
                "sessions":          1,
                "conversation_turns": conv_turns,
                "reads":             reads,
                "edits":             edits,
                "runs":              runs,
                "files_touched_count": files_count,
                "iteration_depth":   iter_depth,
                "_total_file_edits": sum(edit_targets.values()),
                "_total_files_edited": len(edit_targets),
            }

    # Also index by last path component for flexible goal→project matching
    for proj in list(_session_metrics.keys()):
        last = proj.replace("\\", "/").split("/")[-1]
        _session_metrics.setdefault(last, _session_metrics[proj])

    def _attach_metrics(result: dict) -> dict:
        result["tokens"]           = total_tokens
        result["premium_requests"] = total_premium
        result["total_api_ms"]     = total_api_ms
        result["lines_added"]      = total_lines_added
        result["lines_removed"]    = total_lines_removed
        result["files_modified"]   = all_files
        result["session_metrics"]  = _session_metrics
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

    if not use_api:
        return _attach_metrics(_fallback_analysis(target_date, sessions))

    token = _get_github_token()
    if not token:
        # Try copilot CLI fallback (uses Copilot subscription, no API key needed)
        print("  (No GitHub token — trying Copilot CLI for analysis...)")
        transcript = _build_transcript(sessions)
        MAX_TRANSCRIPT_CHARS = 12000
        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[... transcript truncated for length ...]"

        domain_list = ", ".join(DOMAIN_SKILLS[:6]) + ", ..."
        tech_list   = ", ".join(TECH_SKILLS[:6])   + ", ..."

        prompt = _build_analysis_prompt(transcript, domain_list, tech_list)
        cli_result = _analyze_via_copilot_cli(prompt)
        if cli_result:
            cli_result["sessions_count"]  = len(sessions)
            cli_result["projects"]        = list({s["project"] for s in sessions})
            cli_result["analysis_method"] = "ai-copilot-cli"
            _attach_metrics(cli_result)
            try:
                _CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(cli_result, indent=2), encoding="utf-8")
            except Exception:
                pass
            return cli_result

        print("  (Copilot CLI unavailable — using heuristic analysis. Run `gh auth login` to enable semantic analysis.)")
        return _attach_metrics(_fallback_analysis(target_date, sessions))

    transcript  = _build_transcript(sessions)

    # Truncate transcript to stay within token limit (~4 chars per token, leave room for prompt)
    MAX_TRANSCRIPT_CHARS = 12000  # ~3000 tokens, leaving ~5000 for prompt + response
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[... transcript truncated for length ...]"

    domain_list = ", ".join(DOMAIN_SKILLS[:6]) + ", ..."
    tech_list   = ", ".join(TECH_SKILLS[:6])   + ", ..."

    prompt = _build_analysis_prompt(transcript, domain_list, tech_list)

    payload = json.dumps({
        "model":       MODEL,
        "max_tokens":  3000,
        "temperature": 0,
        "messages":    [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL, data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "content-type":  "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            response = json.loads(resp.read().decode("utf-8"))
        raw = response["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        analysis = json.loads(raw)
        analysis["sessions_count"] = len(sessions)
        analysis["projects"]       = list({s["project"] for s in sessions})
        analysis["analysis_method"] = "ai"
        _attach_metrics(analysis)
        # Cache
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        except Exception:
            pass
        return analysis

    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  WARNING: API error {e.code}: {body}")
        print("  Using heuristic fallback -- estimates will be approximate. Re-run with --refresh when API is available.")
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        print(f"  WARNING: API unavailable ({type(e).__name__}). Using heuristic fallback -- estimates will be approximate.")

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
        goals.append({
            "title":       f"Worked on {proj}",
            "summary":     f"{len(tasks)} task{'s' if len(tasks) != 1 else ''} completed in {proj}.",
            "human_hours": sum(t["human_hours"] for t in tasks),
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
