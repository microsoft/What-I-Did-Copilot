#!/usr/bin/env python3
"""
whatidid.py — Daily GitHub Copilot activity analytics.

Usage:
  python whatidid.py                                      # Today
  python whatidid.py --date 2026-03-30                   # Specific date
  python whatidid.py --from 2026-03-09 --to 2026-03-30   # Date range
  python whatidid.py --from 2026-03-09                   # From date to today
  python whatidid.py --date 7D                           # Last 7 days
  python whatidid.py --date 30D                          # Last 30 days
  python whatidid.py --refresh                           # Force re-analysis
  python whatidid.py --from 2026-03-01 --to 2026-03-31 --lock  # Freeze estimates

Date formats accepted: YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY, DD-Mon-YYYY
Lookback shortcuts: 7D, 14D, 30D, 60D, 90D (days back from today)

Triggered as a Copilot skill via /whatididghcp
"""
import argparse
import io
import json as _json
import os
import re as _re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

# Force UTF-8 output on Windows to avoid cp1252 UnicodeEncodeError on emoji/symbols
def _ensure_utf8_stream(stream):
    encoding = getattr(stream, "encoding", None)
    if encoding and encoding.lower() == "utf-8":
        return stream
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
        return stream
    if hasattr(stream, "buffer"):
        return io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace")
    return stream

sys.stdout = _ensure_utf8_stream(sys.stdout)
sys.stderr = _ensure_utf8_stream(sys.stderr)

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_EMAIL = ""  # Auto-detected from GitHub API or git config

# Per-day AI analyses are independent and I/O-bound (one network round-trip to
# the analysis API each), so they run in a small thread pool. The default of 5
# matches the GitHub Models "Low" tier concurrent-request cap for gpt-4o-mini;
# going higher just triggers 429s and serial self-heal retries (net slower). If
# a day still degrades to the heuristic fallback under load it is re-analysed
# serially so results are identical to a sequential run. Overridable for tuning.
try:
    _ANALYZE_WORKERS = max(1, int(os.environ.get("WHATIDID_ANALYZE_WORKERS", "5")))
except (TypeError, ValueError):
    _ANALYZE_WORKERS = 5

# Lookback pattern: e.g. 7D, 30d, 14D
_LOOKBACK_RE = _re.compile(r'^(\d+)[dD]$')


def _parse_date(s: str) -> str:
    """Parse flexible date formats into YYYY-MM-DD.

    Accepts: YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY, DD-Mon-YYYY, 'today'
    """
    if not s or s.lower() == "today":
        return date.today().isoformat()

    # Lookback shortcut (7D, 30D, etc.)
    m = _LOOKBACK_RE.match(s.strip())
    if m:
        days = int(m.group(1))
        return (date.today() - timedelta(days=days)).isoformat()

    cleaned = s.strip().replace("/", "-")

    # Already YYYY-MM-DD
    if _re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', cleaned):
        parts = cleaned.split("-")
        return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"

    # MM-DD-YYYY
    if _re.match(r'^\d{1,2}-\d{1,2}-\d{4}$', cleaned):
        parts = cleaned.split("-")
        return f"{parts[2]}-{int(parts[0]):02d}-{int(parts[1]):02d}"

    # DD-Mon-YYYY (e.g., 15-Mar-2026)
    m = _re.match(r'^(\d{1,2})-([A-Za-z]{3})-(\d{4})$', cleaned)
    if m:
        from datetime import datetime
        dt = datetime.strptime(cleaned, "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d")

    # Last resort — try fromisoformat
    try:
        return date.fromisoformat(cleaned).isoformat()
    except ValueError:
        print(f"  WARNING: Could not parse date '{s}'. Expected YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY, or 7D/30D.")
        sys.exit(1)


def _date_range(from_str: str, to_str: str) -> list:
    """Return list of YYYY-MM-DD strings for every day in [from, to]."""
    d0 = date.fromisoformat(_parse_date(from_str))
    d1 = date.fromisoformat(_parse_date(to_str))
    days, cur = [], d0
    while cur <= d1:
        days.append(cur.isoformat())
        cur += timedelta(days=1)
    return days


def _normalize_project(name: str) -> str:
    """Normalize project name for grouping (lowercase, strip path separators)."""
    return name.replace("\\", "/").split("/")[-1].lower().strip().replace(" ", "-")


def _merge_related_goals(goals: list, project_canonical: dict = None,
                         sessions: list = None) -> list:
    """Group goals from the same project across different days into single entries.

    Goals are considered related when they share the same normalized project name
    (or are linked via shared git repos through project_canonical).
    Merged goals combine all tasks, sum hours, and show the date range.

    EXCEPTION: Goals from home/root folders (ad-hoc work) are only merged if they
    share the same label — the user may be doing unrelated tasks from their home dir.
    """
    from collections import OrderedDict

    if project_canonical is None:
        project_canonical = {}

    # Build set of project names that are actually home folders (check project_path).
    # Use case-insensitive comparison so paths like C:/users/<name> or /USERS/<name>
    # are handled correctly across all OS/path casing conventions.
    home_projects = set()
    for s in (sessions or []):
        pp = s.get("project_path", "").replace("\\", "/").lower()
        if "/users/" in pp or "/home/" in pp:
            parts = pp.split("/")
            for i, p in enumerate(parts):
                if p in ("users", "home") and i + 1 < len(parts):
                    if _normalize_project(s.get("project", "")) == parts[i + 1]:
                        home_projects.add(_normalize_project(s.get("project", "")))

    groups: OrderedDict = OrderedDict()
    for g in goals:
        proj = g.get("project", "")
        norm = _normalize_project(proj) if proj else ""

        # Apply repo-based equivalence (e.g. whatididghcp ↔ what-i-did-copilot)
        canon = project_canonical.get(norm, norm)

        # For home folder projects WITHOUT repo evidence, use label as the grouping
        # key so unrelated ad-hoc tasks stay separate.
        is_home = norm in home_projects
        has_repo_evidence = norm in project_canonical
        if canon and is_home and not has_repo_evidence:
            label = (g.get("label") or g.get("title", "")).strip().lower()
            key = f"_home_{canon}_{label}" if label else f"_unnamed_{id(g)}"
        elif canon:
            key = canon
        else:
            key = f"_unnamed_{id(g)}"

        if key in groups:
            merged = groups[key]
            merged["tasks"].extend(g.get("tasks", []))
            merged["human_hours"] += g.get("human_hours", 0)
            merged["_dates"].add(g.get("date", ""))
            # Keep the longer/better title
            if len(g.get("title", "")) > len(merged.get("title", "")):
                merged["title"] = g["title"]
            # Merge docs
            for d in g.get("docs_referenced", []):
                if d not in merged.get("docs_referenced", []):
                    merged.setdefault("docs_referenced", []).append(d)
        else:
            groups[key] = {
                **g,
                "tasks": list(g.get("tasks", [])),
                "human_hours": g.get("human_hours", 0),
                "_dates": {g.get("date", "")},
            }

    # Finalize: set date field to earliest date, add date range info
    result = []
    for merged in groups.values():
        dates = sorted(merged.pop("_dates", set()))
        merged["_all_dates"] = dates  # Keep all dates for metrics aggregation
        if len(dates) > 1:
            merged["date"] = dates[0]
            d0 = dates[0][5:]   # MM-DD
            d1 = dates[-1][5:]
            merged["summary"] = (merged.get("summary", "") or "") + f" ({len(dates)} days: {d0} to {d1})"
        elif dates:
            merged["date"] = dates[0]
        # Round hours
        merged["human_hours"] = round(merged["human_hours"] * 4) / 4
        result.append(merged)

    return result


def _merge_analyses(day_analyses: list) -> dict:
    """Combine per-day analysis dicts into one, tagging each goal with its date."""
    all_goals   = []
    all_sessions = []
    total_tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0, "total": 0}
    total_tokens_by_model = {}  # {model_name: {input, output, cache_read, cache_creation}}
    total_inline_model_pricing: dict = {}
    total_requests_by_model: dict = {}  # {model_name: count}
    total_premium     = 0
    total_ai_credits  = None  # stays None unless at least one day has server credits
    total_ai_credits_by_model: dict = {}
    inline_model_pricing: dict = {}
    plan              = ""
    auto_model        = False
    total_api_ms      = 0
    total_lines_added = 0
    total_lines_removed = 0
    all_files   = []
    all_projects = set()
    merged_session_metrics = {}
    heuristic_dates = []
    cli_dates = []
    open_session_count = 0
    total_session_count = 0
    all_burn_findings: list = []

    for target_date, analysis, sessions in day_analyses:
        for g in analysis.get("goals", []):
            g["date"] = target_date
            all_goals.append(g)
        for k in total_tokens:
            total_tokens[k] += analysis.get("tokens", {}).get(k, 0)
        for model, toks in analysis.get("tokens_by_model", {}).items():
            if model not in total_tokens_by_model:
                total_tokens_by_model[model] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
            for k in ("input", "output", "cache_read", "cache_creation"):
                total_tokens_by_model[model][k] += toks.get(k, 0)
        total_inline_model_pricing.update(analysis.get("inline_model_pricing") or {})
        # Per-model request counts. Tolerate {model: int} and {model: {count: int}}.
        for model, v in (analysis.get("requests_by_model") or {}).items():
            if isinstance(v, dict):
                cnt = int(v.get("count", 0))
            else:
                try:
                    cnt = int(v)
                except (TypeError, ValueError):
                    cnt = 0
            total_requests_by_model[model] = total_requests_by_model.get(model, 0) + cnt
        total_premium       += analysis.get("premium_requests", 0)
        if analysis.get("ai_credits") is not None:
            total_ai_credits = (total_ai_credits or 0) + analysis["ai_credits"]
        for model, credits in (analysis.get("ai_credits_by_model") or {}).items():
            total_ai_credits_by_model[model] = total_ai_credits_by_model.get(model, 0) + credits
        if analysis.get("plan") and not plan:
            plan = analysis["plan"]
        if analysis.get("auto_model_selection"):
            auto_model = True
        total_api_ms        += analysis.get("total_api_ms", 0)
        total_lines_added   += analysis.get("lines_added", 0)
        total_lines_removed += analysis.get("lines_removed", 0)
        open_session_count  += analysis.get("open_session_count", 0)
        total_session_count += analysis.get("total_session_count", 0)
        # Each per-day analysis carries already-tagged findings (project,
        # session_id, date). De-dup of the same session across days is not
        # needed at this layer because burn analysis is scoped per-date.
        all_burn_findings.extend(analysis.get("burn_findings") or [])
        for f in analysis.get("files_modified", []):
            if f not in all_files:
                all_files.append(f)
        all_sessions.extend(sessions)
        all_projects.update(analysis.get("projects", []))
        # Merge inline pricing; later entries overwrite earlier ones so the
        # most recent per-model rates win across days.
        inline_model_pricing.update(analysis.get("inline_model_pricing") or {})
        if analysis.get("analysis_method") == "heuristic":
            heuristic_dates.append(target_date)
        elif analysis.get("analysis_method") == "ai-copilot-cli":
            cli_dates.append(target_date)
        # Merge per-project session metrics across days (keyed by date|project)
        for proj, metrics in analysis.get("session_metrics", {}).items():
            dated_key = target_date + "|" + proj
            merged_session_metrics[dated_key] = dict(metrics)
            # Also store under normalized key for cross-day matching (same object,
            # not a copy, so deduplication by id() works when aggregating totals)
            norm_key = target_date + "|" + _normalize_project(proj)
            if norm_key != dated_key:
                merged_session_metrics.setdefault(norm_key, merged_session_metrics[dated_key])

    active_dates = sorted({d for d, _, _ in day_analyses})

    # Build project equivalence map from git repos: different folder names
    # for the same repo should merge (e.g. "whatididghcp" ↔ "What-I-Did-Copilot")
    _repo_to_projects: dict = {}  # repo_name → set of project names
    for s in all_sessions:
        sp = s.get("project", "")
        for repo in s.get("git_repos", []):
            repo_short = repo.replace("\\", "/").split("/")[-1].lower()
            _repo_to_projects.setdefault(repo_short, set()).add(_normalize_project(sp))
    # Map each project to a canonical name (first seen) via shared repo
    project_canonical: dict = {}
    for repo, projs in _repo_to_projects.items():
        if len(projs) > 1:
            canonical = sorted(projs)[0]  # deterministic: alphabetically first
            for p in projs:
                project_canonical[p] = canonical

    # Merge goals from the same project across days into single entries
    if len(active_dates) > 1:
        all_goals = _merge_related_goals(all_goals, project_canonical, all_sessions)

        # Create aggregated session_metrics for merged goals that span multiple days.
        # IMPORTANT: compute formula per-day then sum (matching AI's per-day approach)
        # rather than aggregating raw metrics then computing once (which inflates
        # multipliers since all thresholds trigger on large cumulative numbers).
        from report import compute_formula_estimate as _cfe
        for g in all_goals:
            all_dates = g.get("_all_dates", [g.get("date", "")])
            if len(all_dates) <= 1:
                continue
            proj = g.get("project", "")
            norm = _normalize_project(proj)
            # Find all project names that are equivalent via repo mapping
            equiv_names = {proj, norm}
            canon = project_canonical.get(norm, norm)
            for p, c in project_canonical.items():
                if c == canon:
                    equiv_names.add(p)

            # Sum raw metrics for display, but compute formula per-day.
            # files_touched_count is a count of unique files per day — use max()
            # across days to avoid overstating scope (and avoid erroneously
            # tripping the >10 files multiplier on aggregated multi-day counts).
            agg = {"tokens": 0, "tool_invocations": 0, "premium_requests": 0,
                   "lines_added": 0, "lines_removed": 0,
                   "lines_logic": 0, "lines_boilerplate": 0,
                   "active_minutes": 0,
                   "wall_clock_minutes": 0, "sessions": 0,
                   "conversation_turns": 0, "substantive_turns": 0,
                   "reads": 0, "edits": 0, "runs": 0, "searches": 0,
                   "files_touched_count": 0, "_total_file_edits": 0, "_total_files_edited": 0,
                   # Credit-bearing fields — must be aggregated alongside other
                   # metrics so per-goal credit attribution works in multi-day
                   # reports. Without these, the multi-day overwrite at the end
                   # of this loop strips credit signal from the entry that the
                   # report's _resolve_metrics looks up.
                   #
                   # ai_credits starts as None (not 0!) because
                   # `_ai_credits_for()` returns the server value when it is
                   # not None, bypassing the token×rate fallback. Setting an
                   # initial 0 here would force every multi-day project to
                   # show 0 credits when no day had a server-emitted value.
                   "tokens_by_model": {}, "ai_credits": None, "auto_model_selection": False}
            per_day_formula_total = 0.0
            per_day_turns_h = 0.0
            per_day_lines_h = 0.0
            per_day_reads_h = 0.0
            per_day_tools_h = 0.0
            per_day_active_h = 0.0
            for d in all_dates:
                found = False
                for pname in equiv_names:
                    for try_key in [d + "|" + pname]:
                        m = merged_session_metrics.get(try_key, {})
                        if m:
                            for k in agg:
                                if k == "files_touched_count":
                                    agg[k] = max(agg[k], m.get(k, 0))
                                elif k == "tokens_by_model":
                                    for mdl, toks in (m.get("tokens_by_model") or {}).items():
                                        if mdl not in agg["tokens_by_model"]:
                                            agg["tokens_by_model"][mdl] = {
                                                "input": 0, "output": 0,
                                                "cache_read": 0, "cache_creation": 0}
                                        for tk in ("input", "output", "cache_read", "cache_creation"):
                                            agg["tokens_by_model"][mdl][tk] += toks.get(tk, 0)
                                elif k == "auto_model_selection":
                                    if m.get("auto_model_selection"):
                                        agg["auto_model_selection"] = True
                                elif k == "ai_credits":
                                    # Only sum when at least one day had real
                                    # server-emitted credits. Otherwise leave
                                    # ai_credits as None so the token×price
                                    # fallback in _ai_credits_for still works.
                                    if m.get("ai_credits") is not None:
                                        if agg["ai_credits"] is None:
                                            agg["ai_credits"] = 0
                                        agg["ai_credits"] += m["ai_credits"]
                                else:
                                    agg[k] += m.get(k, 0)
                            cfe = _cfe(m)
                            per_day_formula_total += cfe["total"]
                            per_day_turns_h += cfe["turns_h"]
                            per_day_lines_h += cfe["lines_h"]
                            per_day_reads_h += cfe["reads_h"]
                            per_day_tools_h += cfe["tools_h"]
                            per_day_active_h += cfe.get("active_h", 0.0)
                            found = True
                            break
                    if found:
                        break
            # Compute aggregate iteration depth from totals
            total_e = agg.pop("_total_file_edits", 0)
            total_f = agg.pop("_total_files_edited", 0)
            agg["iteration_depth"] = round(total_e / max(total_f, 1), 1)
            # Store per-day formula sums so the evidence table components add up correctly
            per_day_formula_total = round(per_day_formula_total * 4) / 4
            per_day_additive = per_day_turns_h + per_day_lines_h + per_day_reads_h + per_day_tools_h
            # Effective complexity mult is total ÷ whichever base dominated
            # (additive or active anchor) — match what compute_formula_estimate
            # would have used per-day to avoid double-counting.
            per_day_base = max(per_day_additive, per_day_active_h)
            per_day_effective_mult = (per_day_formula_total / per_day_base) if per_day_base > 0 else 1.0
            agg["_per_day_formula_total"] = per_day_formula_total
            agg["_per_day_turns_h"] = per_day_turns_h
            agg["_per_day_lines_h"] = per_day_lines_h
            agg["_per_day_reads_h"] = per_day_reads_h
            agg["_per_day_tools_h"] = per_day_tools_h
            agg["_per_day_active_h"] = per_day_active_h
            agg["_per_day_complexity_mult"] = per_day_effective_mult
            # Store aggregated metrics under the earliest date key
            merged_session_metrics[all_dates[0] + "|" + proj] = agg
            merged_session_metrics[all_dates[0] + "|" + norm] = agg

    # Enforce the deterministic formula as a hard floor on every goal's
    # `human_hours`. The methodology calls the formula the "transparency
    # floor" and the LLM prompt asks it to land "AT OR ABOVE" the floor —
    # but the LLM doesn't see the formula number, so this enforcement
    # closes the loop. Without it, the active-time anchor inside the
    # formula has no effect on the displayed Human Effort number.
    from report import compute_formula_estimate as _cfe2
    for g in all_goals:
        proj = g.get("project", "")
        norm = _normalize_project(proj)
        date_key = g.get("date", "")
        m = (merged_session_metrics.get(date_key + "|" + proj)
             or merged_session_metrics.get(date_key + "|" + norm)
             or {})
        if not m:
            continue
        floor = _cfe2(m).get("total", 0)
        if floor > g.get("human_hours", 0):
            # Scale per-task hours proportionally so the breakdown stays consistent
            old_h = g.get("human_hours", 0) or 0.0001
            scale = floor / old_h
            for t in g.get("tasks", []):
                t["human_hours"] = round((t.get("human_hours", 0) or 0) * scale * 4) / 4
            g["human_hours"] = round(floor * 4) / 4

    if len(active_dates) == 1:
        headline  = day_analyses[0][1].get("headline", f"Activity on {active_dates[0]}")
        narrative = day_analyses[0][1].get("day_narrative", "")
    else:
        d0 = active_dates[0][5:]
        d1 = active_dates[-1][5:]
        n  = len(all_goals)
        headline  = (f"{len(active_dates)} active days ({d0} – {d1}): "
                     f"{n} project{'s' if n != 1 else ''} delivered")
        narrative = (f"Across {len(active_dates)} active days from "
                     f"{active_dates[0]} to {active_dates[-1]}, Copilot assisted with "
                     f"{n} distinct project{'s' if n != 1 else ''} across "
                     f"{len(all_projects)} workspace{'s' if len(all_projects) != 1 else ''}. "
                     f"Related work across days has been grouped.")

    return {
        "headline":         headline,
        "primary_focus":    day_analyses[0][1].get("primary_focus", ""),
        "day_narrative":    narrative,
        "goals":            all_goals,
        "tokens":           total_tokens,
        "tokens_by_model":  total_tokens_by_model,
        "inline_model_pricing": total_inline_model_pricing,
        "requests_by_model": total_requests_by_model,
        "premium_requests": total_premium,
        "ai_credits":       total_ai_credits,
        "ai_credits_by_model": total_ai_credits_by_model,
        "inline_model_pricing": inline_model_pricing,
        "plan":             plan,
        "auto_model_selection": auto_model,
        "total_api_ms":     total_api_ms,
        "lines_added":      total_lines_added,
        "lines_removed":    total_lines_removed,
        "files_modified":   all_files,
        "session_metrics":  merged_session_metrics,
        "sessions_count":   len(all_sessions),
        "open_session_count":  open_session_count,
        "total_session_count": total_session_count,
        "burn_findings":    all_burn_findings,
        "projects":         list(all_projects),
        "active_dates":     active_dates,
        "heuristic_dates":  heuristic_dates,
        "cli_dates":        cli_dates,
        "analysis_method":  "heuristic" if heuristic_dates else "ai",
    }


def _print_summary(analysis: dict):
    goals   = analysis.get("goals", [])
    total_t = sum(len(g.get("tasks", [])) for g in goals)
    total_h = sum(g.get("human_hours", 0) for g in goals)

    print(f"Identified {len(goals)} goal(s), {total_t} task(s):")
    for g in goals:
        date_tag = f"  [{g['date']}]" if "date" in g else ""
        print(f"  [GOAL]{date_tag} {g.get('title', '')[:65]}  ({g.get('human_hours', 0):.1f}h)")
        for t in g.get("tasks", []):
            domain = ", ".join(t.get("domain_skills", []))
            tech   = ", ".join(t.get("tech_skills", []))
            skills = " | ".join(filter(None, [domain, tech]))
            print(f"    - {t.get('title', '')[:55]}  ({t.get('human_hours', 0):.1f}h | {skills})")

    print(f"\n  Total human effort estimate: {total_h:.1f} hours")
    # AI Credits (computed from tokens × per-model rates if not server-emitted)
    from report import _ai_credits_for, USD_PER_CREDIT
    credits = _ai_credits_for(analysis)
    plan_tag = f" [{analysis.get('plan')}]" if analysis.get("plan") else ""
    auto_tag = " (auto-model −10%)" if analysis.get("auto_model_selection") else ""
    print(f"  AI credits used:             {credits:,} (~${credits * USD_PER_CREDIT:.2f}){plan_tag}{auto_tag}")
    if analysis.get("premium_requests"):
        print(f"  Premium requests (legacy):   {analysis['premium_requests']}")
    lines_added   = analysis.get("lines_added", 0)
    lines_removed = analysis.get("lines_removed", 0)
    if lines_added or lines_removed:
        print(f"  Code impact:                 +{lines_added} / -{lines_removed} lines")


def _save_and_open(html: str, label: str, out_dir: "str | None" = None) -> Path:
    base = Path(out_dir).expanduser() if out_dir else Path(__file__).parent
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path(__file__).parent
    output_path = base / f"report_{label}.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"\nHTML report saved: {output_path}")
    try:
        subprocess.run(["cmd", "/c", "start", "", str(output_path)], check=False)
    except Exception:
        pass
    return output_path


def _detect_email() -> str:
    """Detect the user's email address.

    Priority order:
    1. GitHub API /user/emails (primary verified) via `gh auth token`
    2. git config user.email
    3. DEFAULT_EMAIL constant
    """
    # 1. Try GitHub API
    try:
        token_result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
        )
        token = token_result.stdout.strip()
        if token:
            import urllib.request
            req = urllib.request.Request(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                emails = _json.loads(resp.read().decode())
            # Prefer primary+verified, then primary, then first verified
            for e in emails:
                if e.get("primary") and e.get("verified"):
                    return e["email"]
            for e in emails:
                if e.get("primary"):
                    return e["email"]
            for e in emails:
                if e.get("verified"):
                    return e["email"]
    except Exception:
        pass

    # 2. git config
    try:
        result = subprocess.run(
            ["git", "config", "user.email"], capture_output=True, text=True, timeout=5
        )
        email = result.stdout.strip()
        if email:
            return email
    except Exception:
        pass

    # 3. Fallback
    return DEFAULT_EMAIL


def _normalize_recipients(raw: str) -> str:
    """Turn a comma- and/or semicolon-separated recipient string into the
    RFC-5322 comma-separated form mail clients expect. Either separator (or a
    mix of both) is accepted; surrounding whitespace and empty entries are
    dropped while order is preserved."""
    parts = _re.split(r"[;,]", raw or "")
    seen = []
    for p in parts:
        addr = p.strip()
        if addr and addr not in seen:
            seen.append(addr)
    return ", ".join(seen)


def _build_email_summary_html(analysis: dict, report_label: str) -> str:
    """Build an Outlook-safe HTML summary for the email body.

    Uses only table layout, the ``bgcolor`` attribute, and inline styles — no
    gradients, flexbox, or external CSS — so it renders consistently in the
    Outlook (Word engine) renderer as well as New Outlook, Gmail, and Apple
    Mail. The full interactive report rides separately as an .html attachment.
    """
    import html as _html

    HOURLY_RATE = 72  # keep in step with report.HOURLY_RATE

    headline  = (analysis.get("headline") or "GitHub Copilot Impact Report").strip()
    narrative = (analysis.get("day_narrative") or "").strip()
    goals     = analysis.get("goals") or []
    total_h   = sum(float(g.get("human_hours") or 0) for g in goals)
    value     = total_h * HOURLY_RATE
    n_proj    = len(goals)
    span      = report_label.replace("_", " ")

    esc = _html.escape

    # Project rows
    rows = ""
    for i, g in enumerate(goals):
        title   = esc((g.get("title") or g.get("label") or "Project").strip())
        summary = esc((g.get("summary") or "").strip())
        hours   = float(g.get("human_hours") or 0)
        hours_s = (f"{hours:.1f}h" if hours else "")
        row_bg  = "#ffffff" if i % 2 == 0 else "#f6f8fa"
        rows += (
            f'<tr>'
            f'<td bgcolor="{row_bg}" valign="top" style="padding:10px 14px;border-bottom:1px solid #dde1e7;'
            f'font-family:Segoe UI,Arial,sans-serif">'
            f'<div style="font-size:14px;font-weight:700;color:#1b1f23;line-height:1.35">{title}</div>'
            + (f'<div style="font-size:13px;color:#4a4f54;line-height:1.45;margin-top:3px">{summary}</div>'
               if summary else "")
            + f'</td>'
            f'<td bgcolor="{row_bg}" valign="top" align="right" style="padding:10px 14px;border-bottom:1px solid #dde1e7;'
            f'font-family:Segoe UI,Arial,sans-serif;white-space:nowrap;width:70px">'
            f'<span style="font-size:14px;font-weight:700;color:#0078d4">{hours_s}</span>'
            f'</td>'
            f'</tr>'
        )

    narrative_block = (
        f'<tr><td bgcolor="#ffffff" style="padding:6px 20px 14px;'
        f'font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#3a3f44;line-height:1.5">'
        f'{esc(narrative)}</td></tr>'
        if narrative else ""
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5">
<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f0f2f5" style="background:#f0f2f5">
<tr><td align="center" style="padding:20px 12px">
<table width="640" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff"
       style="width:640px;max-width:640px;background:#ffffff;border:1px solid #dde1e7">

  <tr>
    <td bgcolor="#24292f" style="background:#24292f;padding:18px 20px;font-family:Segoe UI,Arial,sans-serif">
      <div style="font-size:10px;color:#b0b6bd;letter-spacing:1px;text-transform:uppercase;margin-bottom:5px">
        {esc(span)} &nbsp;&middot;&nbsp; GitHub Copilot Impact Report</div>
      <div style="font-size:18px;font-weight:700;color:#ffffff;line-height:1.35">{esc(headline)}</div>
    </td>
  </tr>

  {narrative_block}

  <tr>
    <td bgcolor="#1a7f37" style="background:#1a7f37;padding:14px 20px;text-align:center;
        font-family:Segoe UI,Arial,sans-serif">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:#cdeccd">
        Value Delivered</div>
      <div style="font-size:30px;font-weight:700;color:#ffffff;line-height:1.1;margin-top:4px">
        ${value:,.0f}</div>
      <div style="font-size:12px;color:#d8efd8;margin-top:3px">
        {total_h:.1f}h &times; ${HOURLY_RATE}/hr blended rate
        &nbsp;&middot;&nbsp; {n_proj} project{'s' if n_proj != 1 else ''}</div>
    </td>
  </tr>

  <tr>
    <td bgcolor="#ffffff" style="padding:16px 20px 6px;font-family:Segoe UI,Arial,sans-serif">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#6a737d">
        What Got Delivered</div>
    </td>
  </tr>
  <tr>
    <td style="padding:0 20px 16px">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid #dde1e7;border-collapse:collapse">
        {rows}
      </table>
    </td>
  </tr>

  <tr>
    <td bgcolor="#f6f8fa" style="background:#f6f8fa;padding:12px 20px;border-top:1px solid #dde1e7;
        font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#6a737d;line-height:1.5">
      The full interactive report &mdash; with task-level evidence, skills,
      collaboration patterns, and AI investment &mdash; is attached as an HTML file.
      Open <strong style="color:#1b1f23">report_{esc(report_label)}.html</strong> in any browser.
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _open_email_draft(subject: str, html: str, to_email: str, label: str = "report",
                      body_html: str = "") -> bool:
    """Open a prefilled, sendable email draft in the user's default mail client.

    Writes a standards-compliant .eml file carrying a short summary in the body
    (plain text, plus an optional Outlook-safe HTML summary when ``body_html`` is
    given) and the full HTML report as an .html attachment, with the
    ``X-Unsent: 1`` header that tells mail clients (classic Outlook, New Outlook,
    Windows Mail) to open it as an editable draft the user can review and Send
    through their own account. This works even when no account is configured for
    COM automation. ``to_email`` may list several recipients separated by commas
    and/or semicolons. Returns True if the draft was handed off to the mail
    client, False otherwise.
    """
    import tempfile, os
    from email.message import EmailMessage
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["To"] = _normalize_recipients(to_email)
        msg["X-Unsent"] = "1"
        msg.set_content(
            "Your GitHub Copilot impact report summary is below, and the full "
            "interactive report is attached as an HTML file. Open the attachment "
            "to view it, then click Send."
        )
        if body_html:
            msg.add_alternative(body_html, subtype="html")
        msg.add_attachment(
            html.encode("utf-8"),
            maintype="text",
            subtype="html",
            filename=f"report_{label}.html",
        )

        fd, path = tempfile.mkstemp(suffix=".eml", prefix="copilot_report_")
        with os.fdopen(fd, "wb") as f:
            f.write(bytes(msg))

        # Hand the draft to the default .eml handler (New Outlook on this machine).
        try:
            os.startfile(path)  # type: ignore[attr-defined]  # Windows-only
        except AttributeError:
            subprocess.run(["cmd", "/c", "start", "", path], check=False)
        return True
    except Exception as exc:
        print(f"\n  [email error] {exc}")
        return False


def _preprocess_argv(argv: list) -> list:
    """Rewrite --ND shorthand (e.g. --14D) to --date ND before argparse sees it."""
    out = []
    for arg in argv:
        m = _re.match(r'^--(\d+[dD])$', arg)
        if m:
            out += ["--date", m.group(1).upper()]
        else:
            out.append(arg)
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Generate a digest of what GitHub Copilot helped you accomplish."
    )
    parser.add_argument("--date",    default="7D",
                        help="Single date or lookback: YYYY-MM-DD, MM-DD-YYYY, 7D, 30D, 'today' (default: 7D)")
    parser.add_argument("--from",    dest="date_from", default=None,
                        help="Start of date range (any format)")
    parser.add_argument("--to",      dest="date_to",   default=None,
                        help="End of date range (any format, default: today)")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-run semantic analysis even if cached")
    parser.add_argument("--lock",    action="store_true",
                        help="Freeze estimates after this run — future --refresh calls will be ignored")
    parser.add_argument("--email",   nargs="?", const=True, default=False,
                        help="Send report via Outlook (auto-detects email, or pass an explicit address)")
    parser.add_argument("--non-interactive", dest="non_interactive", action="store_true",
                        help="Never prompt for input; on AI-analysis failure, fall straight back to the "
                             "heuristic estimate. Used when launched from the VS Code extension.")
    parser.add_argument("--out-dir", dest="out_dir", default=None,
                        help="Directory to save the HTML report (default: the folder containing this script)")
    args = parser.parse_args(_preprocess_argv(sys.argv[1:]))

    today = date.today().isoformat()

    if args.date_from:
        from_date = _parse_date(args.date_from)
        to_date   = _parse_date(args.date_to) if args.date_to else today
        dates        = _date_range(from_date, to_date)
        report_label = f"{from_date}_to_{to_date}"
    elif _LOOKBACK_RE.match(args.date.strip()):
        # Lookback shortcut: 7D, 30D, etc. → date range
        from_date    = _parse_date(args.date)
        dates        = _date_range(from_date, today)
        report_label = f"{from_date}_to_{today}"
    else:
        target       = _parse_date(args.date)
        dates        = [target]
        report_label = target

    from harvest import get_sessions_for_date
    from analyze import analyze_day, check_api_health

    print(f"\nwhatididghcp -- {report_label}")
    print("-" * 40)

    # Pre-flight: check if AI analysis is reachable.
    # Chain: GitHub Models API → Copilot CLI → heuristic. We only force
    # heuristic if BOTH options are unavailable.
    import time
    from analyze import check_copilot_cli_health
    MAX_RETRIES = 5
    RETRY_WAIT  = 60  # 1 minute
    api_ok = False
    cli_ok = False
    analysis_source = "api"  # default; downgraded below if api unhealthy
    print("  Checking AI analysis API... ", end="", flush=True)
    status, msg = check_api_health()
    if status == "ok":
        print("[OK] connected.")
        api_ok = True
    elif status == "auth":
        print(f"[FAIL] {msg}")
        print(f"\n  Authentication issue with the GitHub Models API — retrying won't help.")
        print(f"  Fix: run `gh auth login` to refresh your token.")
        # Try CLI as silent fallback
        print(f"  Trying Copilot CLI as a fallback... ", end="", flush=True)
        cli_status, cli_msg = check_copilot_cli_health()
        if cli_status == "ok":
            print("[OK] using Copilot CLI for analysis.")
            cli_ok = True
            analysis_source = "cli"
        else:
            print(f"[FAIL] {cli_msg}")
            print(f"  Proceeding with heuristic fallback.\n")
            analysis_source = "heuristic"
    else:
        print(f"[FAIL] {msg}\n")
        # Try CLI as silent fallback before prompting the user
        print(f"  Trying Copilot CLI as a fallback... ", end="", flush=True)
        cli_status, cli_msg = check_copilot_cli_health()
        if cli_status == "ok":
            print("[OK] using Copilot CLI for analysis.")
            cli_ok = True
            analysis_source = "cli"
        else:
            print(f"[FAIL] {cli_msg}")
            print(f"  The AI analysis API is currently unreachable and the Copilot CLI fallback is unavailable.")
            print(f"  Without either, estimates will use a less accurate heuristic approach.\n")
            if args.non_interactive:
                print(f"  Proceeding with heuristic fallback.")
                print(f"  (Re-run later with the AI analysis available for more accurate estimates.)\n")
                analysis_source = "heuristic"
                choice = "2"
            else:
                print(f"  Options:")
                print(f"    1. Retry the API automatically (up to {MAX_RETRIES}× at 1-min intervals)")
                print(f"    2. Continue now with heuristic fallback\n")
                try:
                    choice = input("  Enter choice [1]: ").strip()
                except (EOFError, KeyboardInterrupt):
                    choice = "2"

            if choice == "2":
                print("\n  Proceeding with heuristic fallback.\n")
                analysis_source = "heuristic"
            else:
                for attempt in range(1, MAX_RETRIES + 1):
                    print(f"\n  Retry {attempt}/{MAX_RETRIES} — waiting {RETRY_WAIT}s... ", end="", flush=True)
                    try:
                        time.sleep(RETRY_WAIT)
                    except KeyboardInterrupt:
                        print("\n  Skipped. Proceeding with heuristic fallback.\n")
                        analysis_source = "heuristic"
                        break
                    status, msg = check_api_health()
                    if status == "ok":
                        print("[OK] connected!")
                        api_ok = True
                        analysis_source = "api"
                        break
                    elif status == "auth":
                        print(f"[FAIL] {msg}")
                        print(f"  Authentication issue detected. Run `gh auth login` to fix.\n")
                        analysis_source = "heuristic"
                        break
                    else:
                        print(f"[FAIL] {msg}")
                else:
                    print(f"\n  WARNING: API unreachable after {MAX_RETRIES} attempts.")
                    print(f"  Proceeding with heuristic fallback.\n")
                    analysis_source = "heuristic"

    day_analyses = []
    all_sessions = []

    from report import _resolve_market_cost as _rmc, _credits as _cred

    # Phase 1 — harvest each day sequentially (cheap, file I/O) and print the
    # per-day line in date order, byte-for-byte identical to the original loop.
    pending = []  # [(date, sessions)] for non-empty days, in date order
    for d in dates:
        sessions = get_sessions_for_date(d)
        if not sessions:
            continue
        premium = sum(s.get("premium_requests", 0) for s in sessions)
        # Compute per-day AI credit total from tokens (server credits aren't
        # always present yet; this matches what the report uses).
        day_credits = sum(_cred(_rmc(s)) for s in sessions)
        leg = f", {premium} legacy reqs" if premium else ""
        print(f"  {d}: {len(sessions)} session(s), {day_credits:,} AI credits{leg}")
        pending.append((d, sessions))
        all_sessions.extend(sessions)

    # Phase 2 — run the per-day AI analysis concurrently. Each call is an
    # independent, I/O-bound network round-trip, so a small thread pool collapses
    # the wall-clock time. Results are keyed by date and reassembled in the
    # original order below, so the merge — and therefore every figure in the
    # report — is identical to the sequential path.
    def _analyze_one(day, sess, force_refresh=None):
        return analyze_day(
            day, sess,
            refresh=args.refresh if force_refresh is None else force_refresh,
            analysis_source=analysis_source,
        )

    results_by_date = {}
    if pending:
        workers = min(_ANALYZE_WORKERS, len(pending))
        if workers <= 1:
            for d, sessions in pending:
                results_by_date[d] = _analyze_one(d, sessions)
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_analyze_one, d, sessions): d
                           for d, sessions in pending}
                for fut in futures:
                    results_by_date[futures[fut]] = fut.result()

        # Safety net: if concurrency caused any day to transiently degrade to the
        # heuristic fallback (e.g. a momentary API rate limit) while the API was
        # healthy, re-analyse those days one at a time so the dataset matches a
        # clean sequential AI run. No-op on the happy path.
        if analysis_source == "api":
            degraded = [(d, s) for d, s in pending
                        if results_by_date[d].get("analysis_method") == "heuristic"]
            for d, sessions in degraded:
                retry = _analyze_one(d, sessions, force_refresh=True)
                if retry.get("analysis_method") != "heuristic":
                    results_by_date[d] = retry

    for d, sessions in pending:
        day_analyses.append((d, results_by_date[d], sessions))

    if not day_analyses:
        print(f"\nNo Copilot sessions found for {report_label}.")
        print("  (Sessions are stored in ~/.copilot/session-state/)")
        sys.exit(0)

    print()
    analysis = _merge_analyses(day_analyses)
    _print_summary(analysis)

    if args.lock:
        from analyze import _cache_path
        locked_count = 0
        for d in dates:
            cf = _cache_path(d)
            if cf.exists():
                try:
                    data = _json.loads(cf.read_text(encoding="utf-8"))
                    if not data.get("locked"):
                        data["locked"] = True
                        cf.write_text(_json.dumps(data, indent=2), encoding="utf-8")
                        locked_count += 1
                except Exception:
                    pass
        if locked_count:
            print(f"\n  Locked {locked_count} cache file(s). These estimates are now frozen.")
            print("  To unlock: delete the cache file(s) in cache/ and re-run.")

    heuristic_dates = analysis.get("heuristic_dates", [])
    cli_dates = analysis.get("cli_dates", [])
    total = len(analysis.get("active_dates", []))
    if cli_dates:
        n = len(cli_dates)
        print(f"\n  NOTE: {n}/{total} day(s) used the Copilot CLI fallback "
              f"(Models API was unavailable).")
        print(f"  CLI results are full AI analysis — no quality degradation.")
    if heuristic_dates:
        n = len(heuristic_dates)
        print(f"\n  WARNING: {n}/{total} day(s) used heuristic fallback "
              f"(neither Models API nor Copilot CLI was available).")
        print(f"  Estimates for those days are approximate and likely inflated.")
        print(f"  Re-run with --refresh when AI analysis is available for accurate results.")

    from report import generate_html
    html = generate_html(report_label, analysis, all_sessions, max_width=960)

    _save_and_open(html, report_label, args.out_dir)

    if args.email is not False:
        # Resolve recipient email
        if args.email is True or args.email is None:
            to_email = _detect_email()
            if to_email:
                print(f"  Detected email: {to_email}")
            else:
                print("  Could not detect email. Use --email you@company.com to specify.")
        else:
            to_email = args.email
        if to_email:
            to_email = _normalize_recipients(to_email)
        if to_email:
            # Generate a narrower version for email clients (Outlook, Gmail)
            email_html = generate_html(report_label, analysis, all_sessions, max_width=700)
            summary_html = _build_email_summary_html(analysis, report_label)
            subject = f"My GitHub Copilot Impact | {report_label.replace('_', ' ')}"
            print(f"  Opening a prefilled draft to {to_email} in your mail app ...", end="", flush=True)
            ok = _open_email_draft(subject, email_html, to_email, report_label, summary_html)
            print(" opened — review and click Send." if ok else " failed.")

    print("\nDone.")
    burn_count = len(analysis.get("burn_findings") or [])
    if burn_count > 0:
        print(f"  Expand any of the top expensive sessions in the HTML report to see")
        print(f"    {burn_count} observed cost-saving opportunities tied to where they occurred.")
    open_cnt = analysis.get("open_session_count", 0)
    total_cnt = analysis.get("total_session_count", 0)
    if open_cnt > 0:
        plural = "s" if total_cnt != 1 else ""
        print(f"  Note: {open_cnt} of {total_cnt} session{plural} did not write a clean shutdown")
        print(f"    record (still active, crashed, or killed). Output tokens and compaction")
        print(f"    costs are captured directly; non-compaction input tokens are not in the")
        print(f"    event stream for those sessions, so credit totals are a lower bound.")
    print()


if __name__ == "__main__":
    main()
