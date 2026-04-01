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
        if s.get("tokens", {}).get("total"):
            lines.append(f"Tokens consumed: {s['tokens']['total']:,}")
        n_tools = sum(len(m.get("tools_after", [])) for m in s["messages"] if m["role"] == "user")
        if n_tools:
            lines.append(f"Tool invocations: {n_tools}")

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
        print("  (No GitHub token — using heuristic analysis. Run `gh auth login` to enable semantic analysis.)")
        return _attach_metrics(_fallback_analysis(target_date, sessions))

    transcript  = _build_transcript(sessions)

    # Truncate transcript to stay within token limit (~4 chars per token, leave room for prompt)
    MAX_TRANSCRIPT_CHARS = 12000  # ~3000 tokens, leaving ~5000 for prompt + response
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[... transcript truncated for length ...]"

    domain_list = ", ".join(DOMAIN_SKILLS[:6]) + ", ..."
    tech_list   = ", ".join(TECH_SKILLS[:6])   + ", ..."

    prompt = f"""Analyze this day of GitHub Copilot-assisted work and produce a JSON digest.

SESSION TRANSCRIPT:
{transcript}

═══════════════════════════════════════════
RULE 0 — PERSONAL / OFF-TOPIC FILTER
═══════════════════════════════════════════

SKIP any user messages that are clearly personal and unrelated to professional work.
Personal queries include (but are not limited to): health, fitness, nutrition, supplements,
food, recipes, personal finance, relationships, news, general trivia, shopping, entertainment.

If an ENTIRE session contains only personal queries, omit that session from the output entirely.
If personal queries are MIXED with professional work in a session, include only the professional tasks.
Do NOT invent a professional framing for a personal query — just leave it out.

═══════════════════════════════════════════
RULE 1 — GOAL GROUPING (most important rule)
═══════════════════════════════════════════

Group work into BUSINESS GOALS. A goal = the high-level outcome accomplished, not the technical steps.

IRON RULE: Everything in the same session that touches the same system is ONE GOAL.
Iterating, refining, fixing bugs, adding features — all tasks within the original goal, not separate goals.

DEFAULT RULE: When in doubt, MERGE. Too few goals is better than too many.

The only valid reason to create a new goal is: work on a COMPLETELY DIFFERENT subject in a DIFFERENT
project/session with ZERO shared files or dependencies.

GOOD GOAL TITLES (business outcome, verb-first, based on the MOST SUBSTANTIAL work done):
  "Built a daily Copilot activity analytics tool with branded HTML reports"
  "Shipped a daily work digest tool from concept to working system"
  "Provided strategic rewrite recommendations for the presentation"
  "Diagnosed and resolved checkout regression in production"

BAD GOAL TITLES (too granular, based on first message instead of overall outcome):
  "Set up authentication"        ← part of a larger goal
  "Built report generator"       ← a task within a goal
  "Initialized git repository"   ← setup step, not the goal itself
  "Prepared directory for checkin" ← describes first action, not the outcome

TITLE RULE: The goal title must describe the PRIMARY DELIVERABLE, not the first thing done.
If a session starts with "prepare for github" but spends 80% of time building a report tool,
the title should be about the report tool, not the git setup.

═══════════════════════════════════════════
RULE 2 — LANGUAGE
═══════════════════════════════════════════

Write as if briefing a senior executive on what was accomplished.

NEVER write anything that implies the human was unclear, imprecise, or needed to course-correct.
NEVER ASSUME CONTEXT NOT IN THE TRANSCRIPT.
DO use the actual file or document name when it appears in the tool calls.

GOOD framing:
  ✓ "Designed and shipped X" — confident, direct
  ✓ "Built X with Y capability" — outcome-focused
  ✓ "Delivered X that does Y" — value-focused

═══════════════════════════════════════════
RULE 3 — EFFORT ESTIMATES (calibrated)
═══════════════════════════════════════════

human_hours = what a skilled professional would need WITHOUT Copilot assistance.
BE CONSERVATIVE — underestimate rather than overestimate. Credibility matters more than impressive numbers.
Use this calibration scale — match the task to the closest anchor:

  0.25h  — Trivial: install a package, run a CLI command, toggle a config, copy files
  0.5h   — Simple: minor code edit, format/style tweak, rename, small config change, run existing script
  0.75h  — Light: write a helper function, fix a known bug, small template change
  1.0-1.5h — Moderate: implement a small feature, debug an unknown issue, draft a short document
  2-3h   — Substantial: design + implement a feature, write a detailed report, complex analysis
  4-6h   — Major: architect a new system, build a complete tool from scratch, comprehensive research

MOST TASKS SHOULD BE 0.25-1.0h. Only genuinely complex work exceeds 1.5h.

USE THESE QUANTITATIVE SIGNALS to calibrate estimates:
- Premium requests per session indicate complexity: 1-5 = trivial, 5-20 = moderate, 20-50 = substantial, 50+ = major
- Tool invocations: 1-5 = simple task, 5-15 = moderate, 15+ = complex multi-step work
- Code impact: <50 lines = minor, 50-200 = moderate, 200+ = substantial development
- If a session used <10 premium requests total, ALL tasks in that session combined should be ≤1.5h
- If total tokens < 50,000, the work was likely straightforward — cap at 2h total

IMPORTANT RULES:
- Mechanical execution (installing, deploying, running existing code, copying files) → 0.25-0.5h max
- Only tasks involving THINKING, DESIGN, ANALYSIS, or NOVEL CODING deserve estimates above 1h
- "Installing X from GitHub" is 15 minutes (0.25h), not hours — even with troubleshooting
- Each number must be nearest 0.25h (not just 0.5h increments)
- goal.human_hours must exactly equal the sum of its task hours

═══════════════════════════════════════════
OUTPUT SCHEMA
═══════════════════════════════════════════

Return ONLY this JSON (no markdown fences, no explanation before or after):

{{
  "headline": "One punchy sentence — the most significant thing accomplished today",
  "primary_focus": "2-4 words (e.g. 'Productivity tooling', 'Deck strategy')",
  "day_narrative": "Exactly 2 sentences. What was accomplished and why it matters. Confident tone, plain English.",
  "goals": [
    {{
      "title": "Business outcome title (verb-first)",
      "label": "2-5 word noun phrase naming the deliverable (used as bold heading in summary list)",
      "summary": "1 sentence, max 20 words. What exists now that didn't before. Confident tone.",
      "human_hours": <sum of task hours>,
      "project": "exact project name from the SESSION header",
      "docs_referenced": ["filenames of docs actually analyzed or produced — empty list if none"],
      "tasks": [
        {{
          "title": "Implementation step (verb-first)",
          "what_got_done": "One sentence, max 18 words. Outcome only — no tool names.",
          "domain_skills": ["1-2 from: {domain_list}"],
          "tech_skills": ["0-2 from: {tech_list} (omit if none)"],
          "task_type": "one of: Development | Bug Fix & Debug | Analysis & Research | Design & UX | Execution & Ops",
          "professional_roles": ["1-2 roles from the list below. Match to what was ACTUALLY DONE, not the job title of the user. These represent professional services roles — pick the role a billing firm would charge for this work.\n\nTECHNICAL ROLES (code, systems, data):\n  • Software Engineer      — writing/debugging code, implementing features, building tools, scripting in any language\n  • Frontend Developer     — HTML/CSS/JS/TS, web or app UI implementation\n  • Data Analyst           — SQL queries, KPI dashboards, structured data analysis, metrics computation, BI reports. ONLY if actual data/SQL work was done — NOT for general research.\n  • Data Engineer          — data pipelines, ETL, warehouse schema, data infrastructure\n  • DevOps Engineer        — CI/CD, deployment automation, containerisation, infrastructure-as-code\n  • Solutions Architect    — system/API design, architecture decisions, technical integration strategy\n  • Security Engineer      — auth, encryption, vulnerability assessment, security review\n  • QA Engineer            — test writing, debugging, validation, quality assurance\n\nDESIGN & COMMUNICATION ROLES:\n  • UX Designer            — user flows, wireframes, usability, interaction design\n  • Visual Designer        — slide decks, graphics, layouts, branding, visual output\n  • Technical Writer       — documentation, READMEs, how-to guides, technical explainers\n\nBUSINESS & STRATEGY ROLES:\n  • Product Manager        — product roadmap, feature requirements, user stories, prioritisation\n  • Program Manager        — project coordination, delivery planning, cross-team dependencies, status reporting\n  • Business Analyst       — process analysis, gap analysis, requirements gathering, workflow documentation\n  • Management Consultant  — strategic recommendations, frameworks, benchmarking, executive presentations\n\nDOMAIN & INDUSTRY EXPERT ROLES (use when the work requires deep subject-matter knowledge beyond generic software skills):\n  • Research Scientist     — hypothesis-driven investigation, experiments, literature review, scientific modelling\n  • Financial Analyst      — financial modelling, valuation, investment analysis, quantitative finance, forecasting\n  • Risk & Compliance Analyst — regulatory analysis, risk assessment, compliance documentation, audit preparation\n  • Domain Expert          — industry-specific analysis requiring specialist knowledge (engineering, medicine, law, energy, etc.) that does not fit a more specific role above\n\nDECISION RULES:\n  - General web search / reading docs / evaluating tools → Software Engineer (if technical) or Business Analyst (if process/strategy)\n  - Writing a report or presentation → Management Consultant (if strategic) or Visual Designer (if primarily layout/slides) or Technical Writer (if reference documentation)\n  - Any Python/R/Julia for numerical modelling or finance → Financial Analyst if domain is finance/quant, else Software Engineer\n  - Regulatory or policy research → Risk & Compliance Analyst"],
          "human_hours": <single calibrated number per the scale above, nearest 0.25h>
        }}
      ]
    }}
  ]
}}"""

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
    # Keyword checks first so trivial execution tasks aren't over-counted even with few tool calls
    if any(_word(w, t) for w in ("install", "deploy", "push", "run", "config", "setup")):
        return 0.25
    if any(_word(w, t) for w in ("update", "change", "small", "quick", "rename", "tweak")):
        return 0.5
    # If very few tools and no specific keyword matched above, treat as small change
    if n <= 1:
        return 0.25
    if n <= 3:
        return 0.5
    # Bug fix scales with complexity
    if any(_word(w, t) for w in ("fix", "debug", "error", "bug")):
        return 1.5 if n > 10 else 1.0
    # Substantial development
    if any(_word(w, t) for w in ("implement", "build", "create", "write", "code")) and n > 15:
        return 4.0
    if any(_word(w, t) for w in ("implement", "build", "create", "write", "code")):
        return 2.0
    # Design / planning
    if any(_word(w, t) for w in ("plan", "design", "architect")):
        return 1.5
    # Analysis
    if any(_word(w, t) for w in ("analyze", "research", "investigate", "report")):
        return 1.5
    return 1.0


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
