#!/usr/bin/env python3
"""
whatidid.py — Daily GitHub Copilot activity analytics.

Usage:
  python whatidid.py                                      # Today
  python whatidid.py --date 2026-03-30                   # Specific date
  python whatidid.py --from 2026-03-09 --to 2026-03-30   # Date range
  python whatidid.py --from 2026-03-09                   # From date to today
  python whatidid.py --email you@company.com             # Send email
  python whatidid.py --html                              # Save HTML only
  python whatidid.py --refresh                           # Force re-analysis

Triggered as a Copilot skill via /whatididghcp
"""
import argparse
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_EMAIL = "shahegde@microsoft.com"


def _date_range(from_str: str, to_str: str) -> list:
    """Return list of YYYY-MM-DD strings for every day in [from, to]."""
    d0 = date.fromisoformat(from_str)
    d1 = date.fromisoformat(to_str)
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
        "sessions_count":   len(all_sessions),
        "projects":         list(all_projects),
        "active_dates":     active_dates,
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
                        help="Single date: YYYY-MM-DD or 'today' (default)")
    parser.add_argument("--from",    dest="date_from", default=None,
                        help="Start of date range: YYYY-MM-DD")
    parser.add_argument("--to",      dest="date_to",   default=None,
                        help="End of date range: YYYY-MM-DD (default: today)")
    parser.add_argument("--email",   nargs="?", const=DEFAULT_EMAIL, default=None,
                        help=f"Send to this address (default: {DEFAULT_EMAIL})")
    parser.add_argument("--html",    action="store_true",
                        help="Save HTML file (default when --email not used)")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-run semantic analysis even if cached")
    args = parser.parse_args()

    today = date.today().isoformat()

    if args.date_from:
        dates        = _date_range(args.date_from, args.date_to or today)
        report_label = f"{args.date_from}_to_{args.date_to or today}"
    else:
        target       = today if args.date in ("today", "") else args.date
        dates        = [target]
        report_label = target

    from harvest import get_sessions_for_date
    from analyze import analyze_day

    print(f"\nwhatididghcp -- {report_label}")
    print("-" * 40)

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

    print("\nDone.\n")


if __name__ == "__main__":
    main()
