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
    total_premium     = 0
    total_api_ms      = 0
    total_lines_added = 0
    total_lines_removed = 0
    all_files   = []
    all_projects = set()
    merged_session_metrics = {}
    heuristic_dates = []

    for target_date, analysis, sessions in day_analyses:
        for g in analysis.get("goals", []):
            g["date"] = target_date
            all_goals.append(g)
        for k in total_tokens:
            total_tokens[k] += analysis.get("tokens", {}).get(k, 0)
        total_premium       += analysis.get("premium_requests", 0)
        total_api_ms        += analysis.get("total_api_ms", 0)
        total_lines_added   += analysis.get("lines_added", 0)
        total_lines_removed += analysis.get("lines_removed", 0)
        for f in analysis.get("files_modified", []):
            if f not in all_files:
                all_files.append(f)
        all_sessions.extend(sessions)
        all_projects.update(analysis.get("projects", []))
        if analysis.get("analysis_method") == "heuristic":
            heuristic_dates.append(target_date)
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
                   "files_touched_count": 0, "_total_file_edits": 0, "_total_files_edited": 0}
            per_day_formula_total = 0.0
            per_day_turns_h = 0.0
            per_day_lines_h = 0.0
            per_day_reads_h = 0.0
            for d in all_dates:
                found = False
                for pname in equiv_names:
                    for try_key in [d + "|" + pname]:
                        m = merged_session_metrics.get(try_key, {})
                        if m:
                            for k in agg:
                                if k == "files_touched_count":
                                    agg[k] = max(agg[k], m.get(k, 0))
                                else:
                                    agg[k] += m.get(k, 0)
                            cfe = _cfe(m)
                            per_day_formula_total += cfe["total"]
                            per_day_turns_h += cfe["turns_h"]
                            per_day_lines_h += cfe["lines_h"]
                            per_day_reads_h += cfe["reads_h"]
                            found = True
                            break
                    if found:
                        break
            # Compute aggregate iteration depth from totals
            total_e = agg.pop("_total_file_edits", 0)
            total_f = agg.pop("_total_files_edited", 0)
            agg["iteration_depth"] = round(total_e / max(total_f, 1), 1)
            # Store per-day formula sums so the evidence table components add up correctly
            agg["_per_day_formula_total"] = round(per_day_formula_total * 4) / 4
            agg["_per_day_turns_h"] = per_day_turns_h
            agg["_per_day_lines_h"] = per_day_lines_h
            agg["_per_day_reads_h"] = per_day_reads_h
            # Store aggregated metrics under the earliest date key
            merged_session_metrics[all_dates[0] + "|" + proj] = agg
            merged_session_metrics[all_dates[0] + "|" + norm] = agg

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
        "premium_requests": total_premium,
        "total_api_ms":     total_api_ms,
        "lines_added":      total_lines_added,
        "lines_removed":    total_lines_removed,
        "files_modified":   all_files,
        "session_metrics":  merged_session_metrics,
        "sessions_count":   len(all_sessions),
        "projects":         list(all_projects),
        "active_dates":     active_dates,
        "heuristic_dates":  heuristic_dates,
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
    print(f"  Premium requests:            {analysis.get('premium_requests', 0)}")
    lines_added   = analysis.get("lines_added", 0)
    lines_removed = analysis.get("lines_removed", 0)
    if lines_added or lines_removed:
        print(f"  Code impact:                 +{lines_added} / -{lines_removed} lines")


def _save_and_open(html: str, label: str) -> Path:
    output_path = Path(__file__).parent / f"report_{label}.html"
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


def _send_outlook_email(subject: str, html: str, to_email: str) -> bool:
    """Send an email via Outlook COM automation with the full HTML report as the body.
    Returns True on success, False if Outlook is unavailable or the send fails."""
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", encoding="utf-8", delete=False
    )
    try:
        tmp.write(html)
        tmp.close()
        # Single-quoted PowerShell strings are literal — no backslash escaping needed,
        # only single quotes need doubling.
        ps_path = tmp.name.replace("'", "''")
        escaped_subject = subject.replace("'", "''")
        escaped_to = to_email.replace("'", "''")
        ps = (
            f"$html = Get-Content -Path '{ps_path}' -Raw -Encoding UTF8;"
            f"$ol = New-Object -ComObject Outlook.Application;"
            f"$mail = $ol.CreateItem(0);"
            f"$mail.Subject = '{escaped_subject}';"
            f"$mail.To = '{escaped_to}';"
            f"$mail.HTMLBody = $html;"
            f"$mail.Send();"
            f"$ol.Session.SendAndReceive($true);"
            f"Start-Sleep -Seconds 5"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps],
            timeout=60,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"\n  [email error] {result.stderr.strip() or result.stdout.strip()}")
            return False
        return True
    except Exception as exc:
        print(f"\n  [email error] {exc}")
        return False
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


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

    # Pre-flight: check if AI analysis API is reachable
    import time
    MAX_RETRIES = 5
    RETRY_WAIT  = 60  # 1 minute
    api_ok = False
    print("  Checking AI analysis API... ", end="", flush=True)
    status, msg = check_api_health()
    if status == "ok":
        print("[OK] connected.")
        api_ok = True
    elif status == "auth":
        print(f"[FAIL] {msg}")
        print(f"\n  WARNING: This is an authentication issue -- retrying won't help.")
        print(f"  Fix: run `gh auth login` in your terminal, then re-run.\n")
        print(f"  Proceeding with heuristic fallback.\n")
    else:
        print(f"[FAIL] {msg}\n")
        print(f"  The AI analysis API is currently unreachable.")
        print(f"  Without it, estimates will use a less accurate heuristic approach.\n")
        print(f"  Options:")
        print(f"    1. Retry automatically (up to {MAX_RETRIES}× at 1-min intervals)")
        print(f"    2. Continue now with heuristic fallback\n")
        try:
            choice = input("  Enter choice [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "2"

        if choice == "2":
            print("\n  Proceeding with heuristic fallback.\n")
        else:
            for attempt in range(1, MAX_RETRIES + 1):
                print(f"\n  Retry {attempt}/{MAX_RETRIES} — waiting {RETRY_WAIT}s... ", end="", flush=True)
                try:
                    time.sleep(RETRY_WAIT)
                except KeyboardInterrupt:
                    print("\n  Skipped. Proceeding with heuristic fallback.\n")
                    break
                status, msg = check_api_health()
                if status == "ok":
                    print("[OK] connected!")
                    api_ok = True
                    break
                elif status == "auth":
                    print(f"[FAIL] {msg}")
                    print(f"  Authentication issue detected. Run `gh auth login` to fix.\n")
                    break
                else:
                    print(f"[FAIL] {msg}")
            else:
                print(f"\n  WARNING: API unreachable after {MAX_RETRIES} attempts.")
                print(f"  Proceeding with heuristic fallback.\n")

    day_analyses = []
    all_sessions = []

    for d in dates:
        sessions = get_sessions_for_date(d)
        if not sessions:
            continue
        premium = sum(s.get("premium_requests", 0) for s in sessions)
        print(f"  {d}: {len(sessions)} session(s), {premium} premium requests")
        analysis = analyze_day(d, sessions, refresh=args.refresh, use_api=api_ok)
        day_analyses.append((d, analysis, sessions))
        all_sessions.extend(sessions)

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
    if heuristic_dates:
        n = len(heuristic_dates)
        total = len(analysis.get("active_dates", []))
        print(f"\n  WARNING: {n}/{total} day(s) used heuristic fallback (API unavailable).")
        print(f"  Estimates for those days are approximate and likely inflated.")
        print(f"  Re-run with --refresh when the GitHub Models API is available for accurate results.")

    from report import generate_html
    html = generate_html(report_label, analysis, all_sessions, max_width=960)

    _save_and_open(html, report_label)

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
            # Generate a narrower version for email clients (Outlook, Gmail)
            email_html = generate_html(report_label, analysis, all_sessions, max_width=700)
            subject = f"My GitHub Copilot Impact | {report_label.replace('_', ' ')}"
            print(f"  Sending email to: {to_email} ...", end="", flush=True)
            ok = _send_outlook_email(subject, email_html, to_email)
            print(" sent." if ok else " failed.")

    print("\nDone.")
    if today in [d for d in dates]:
        print("  Note: Active sessions (still open) may show incomplete metrics.")
        print("    Close your Copilot session and re-run for full code/token data.")
    print()


if __name__ == "__main__":
    main()
