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
  python whatidid.py --email you@company.com             # Send email
  python whatidid.py --html                              # Save HTML only
  python whatidid.py --refresh                           # Force re-analysis

Date formats accepted: YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY, DD-Mon-YYYY
Lookback shortcuts: 7D, 14D, 30D, 60D, 90D (days back from today)

Triggered as a Copilot skill via /whatididghcp
"""
import argparse
import re as _re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_EMAIL = "shahegde@microsoft.com"

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

    active_dates = sorted({d for d, _, _ in day_analyses})

    if len(active_dates) == 1:
        headline  = day_analyses[0][1].get("headline", f"Activity on {active_dates[0]}")
        narrative = day_analyses[0][1].get("day_narrative", "")
    else:
        d0 = active_dates[0][5:]
        d1 = active_dates[-1][5:]
        n  = len(all_goals)
        headline  = (f"{len(active_dates)} active days ({d0} – {d1}): "
                     f"{n} goal{'s' if n != 1 else ''} accomplished")
        narrative = (f"Across {len(active_dates)} active days from "
                     f"{active_dates[0]} to {active_dates[-1]}, Copilot assisted with "
                     f"{n} distinct goal{'s' if n != 1 else ''} across "
                     f"{len(all_projects)} project{'s' if len(all_projects) != 1 else ''}. "
                     f"Each goal below shows the date it was completed.")

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


def main():
    parser = argparse.ArgumentParser(
        description="Generate a digest of what GitHub Copilot helped you accomplish."
    )
    parser.add_argument("--date",    default="today",
                        help="Single date or lookback: YYYY-MM-DD, MM-DD-YYYY, 7D, 30D, 'today'")
    parser.add_argument("--from",    dest="date_from", default=None,
                        help="Start of date range (any format)")
    parser.add_argument("--to",      dest="date_to",   default=None,
                        help="End of date range (any format, default: today)")
    parser.add_argument("--email",   nargs="?", const=DEFAULT_EMAIL, default=None,
                        help=f"Send to this address (default: {DEFAULT_EMAIL})")
    parser.add_argument("--html",    action="store_true",
                        help="Save HTML file (default when --email not used)")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-run semantic analysis even if cached")
    args = parser.parse_args()

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
        analysis = analyze_day(d, sessions, refresh=args.refresh)
        day_analyses.append((d, analysis, sessions))
        all_sessions.extend(sessions)

    if not day_analyses:
        print(f"\nNo Copilot sessions found for {report_label}.")
        print("  (Sessions are stored in ~/.copilot/session-state/)")
        sys.exit(0)

    print()
    analysis = _merge_analyses(day_analyses)
    _print_summary(analysis)

    heuristic_dates = analysis.get("heuristic_dates", [])
    if heuristic_dates:
        n = len(heuristic_dates)
        total = len(analysis.get("active_dates", []))
        print(f"\n  WARNING: {n}/{total} day(s) used heuristic fallback (API unavailable).")
        print(f"  Estimates for those days are approximate and likely inflated.")
        print(f"  Re-run with --refresh when the GitHub Models API is available for accurate results.")

    from report import generate_html
    html = generate_html(report_label, analysis, all_sessions)

    send_email_flag = bool(args.email)
    save_html       = args.html or not send_email_flag

    output_path = None
    if save_html:
        output_path = _save_and_open(html, report_label)

    if send_email_flag:
        from email_send import send_email
        subject = f"What I Did (Copilot) — {report_label}"
        print(f"\nSending to {args.email}...")
        if send_email(args.email, subject, html):
            print("   Sent.")
        else:
            print("   Email failed. Saving HTML as fallback...")
            if not output_path:
                output_path = _save_and_open(html, report_label)

    print("\nDone.")
    if today in [d for d in dates]:
        print("  Note: Active sessions (still open) may show incomplete metrics.")
        print("    Close your Copilot session and re-run for full code/token data.")
    print()


if __name__ == "__main__":
    main()
