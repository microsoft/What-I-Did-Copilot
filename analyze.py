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

# GitHub Models API — OpenAI-compatible endpoint, authenticated with GitHub token
API_URL = "https://models.inference.ai.azure.com/chat/completions"
MODEL   = "gpt-4o-mini"

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


def analyze_day(target_date: str, sessions: list, refresh: bool = False) -> dict:
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
    all_files = list(dict.fromkeys(all_files))  # deduplicate, preserve order

    def _attach_metrics(result: dict) -> dict:
        result["tokens"]           = total_tokens
        result["premium_requests"] = total_premium
        result["total_api_ms"]     = total_api_ms
        result["lines_added"]      = total_lines_added
        result["lines_removed"]    = total_lines_removed
        result["files_modified"]   = all_files
        return result

    # Return cached result if available
    cache_file = _cache_path(target_date)
    if not refresh and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            print("  (Using cached analysis — pass --refresh to re-analyse.)")
            return _attach_metrics(cached)
        except Exception:
            pass

    token = _get_github_token()
    if not token:
        print("  (No GitHub token — using heuristic analysis. Run `gh auth login` to enable semantic analysis.)")
        return _attach_metrics(_fallback_analysis(target_date, sessions))

    transcript  = _build_transcript(sessions)
    domain_list = ", ".join(DOMAIN_SKILLS[:6]) + ", ..."
    tech_list   = ", ".join(TECH_SKILLS[:6])   + ", ..."

    prompt = f"""Analyze this day of GitHub Copilot-assisted work and produce a JSON digest.

SESSION TRANSCRIPT:
{transcript}

═══════════════════════════════════════════
RULE 1 — GOAL GROUPING (most important rule)
═══════════════════════════════════════════

Group work into BUSINESS GOALS. A goal = the high-level outcome accomplished, not the technical steps.

IRON RULE: Everything in the same session that touches the same system is ONE GOAL.
Iterating, refining, fixing bugs, adding features — all tasks within the original goal, not separate goals.

DEFAULT RULE: When in doubt, MERGE. Too few goals is better than too many.

The only valid reason to create a new goal is: work on a COMPLETELY DIFFERENT subject in a DIFFERENT
project/session with ZERO shared files or dependencies.

GOOD GOAL TITLES (business outcome, verb-first):
  "Shipped a daily work digest tool from concept to working system"
  "Provided strategic rewrite recommendations for the presentation"
  "Diagnosed and resolved checkout regression in production"

BAD GOAL TITLES (too granular):
  "Set up authentication"        ← part of a larger goal
  "Built report generator"       ← a task within a goal
  "Fixed encoding bug"           ← a task within a goal

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
RULE 3 — EFFORT ESTIMATES
═══════════════════════════════════════════

human_hours = what a skilled senior professional would need starting from scratch.
- Single number, nearest 0.5h. Conservative (lean high, not low).
- goal.human_hours must exactly equal the sum of its task hours.

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
          "human_hours": <single conservative number, nearest 0.5h>
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
        print(f"  API error {e.code}: {body}")
        print("  Falling back to heuristic analysis.")
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        print(f"  API call failed ({e}). Falling back to heuristic analysis.")

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
    return domain[:2], tech[:2]


def _conservative_hours(text: str, tools: list) -> float:
    n, t = len(tools), text.lower()
    if any(_word(w, t) for w in ("fix", "debug", "error", "bug")):
        return 2.0 if n > 10 else 1.0
    if any(_word(w, t) for w in ("implement", "build", "create", "write", "code")) and n > 15:
        return 5.0
    if any(_word(w, t) for w in ("implement", "build", "create", "write", "code")):
        return 3.0
    if any(_word(w, t) for w in ("plan", "design", "architect")):
        return 2.0
    if any(_word(w, t) for w in ("update", "change", "small", "quick")):
        return 0.5
    return 1.5


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
            hours = _conservative_hours(text, tools)
            domain, tech = _infer_skills(text, tools)
            first = text.split("\n")[0].strip()
            title = (first if not first[0].isdigit() else text[:75])[:75]
            tasks.append({
                "title":         title,
                "what_got_done": "Run `gh auth login` for a plain-English description.",
                "domain_skills": domain,
                "tech_skills":   tech,
                "human_hours":   hours,
            })
        goals.append({
            "title":       f"Worked on {proj}",
            "summary":     "Run `gh auth login` for semantic goal analysis.",
            "human_hours": sum(t["human_hours"] for t in tasks),
            "tasks":       tasks,
        })

    projects = list({s["project"] for s in sessions})
    return {
        "headline":       f"Copilot activity on {target_date}",
        "primary_focus":  sessions[0]["project"].split("/")[-1].title() if sessions else "Mixed",
        "day_narrative":  "Heuristic summary — run `gh auth login` for full semantic analysis.",
        "goals":          goals,
        "sessions_count": len(sessions),
        "projects":       projects,
    }
