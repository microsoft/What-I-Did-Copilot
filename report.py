"""
report.py — Daily digest HTML for GitHub Copilot sessions.
Layout: Act 1 (Story) → Act 2 (Journey) → Act 3 (Evidence)
  Act 1: Header → Narrative → KPIs → ROI
  Act 2: How I Collaborated → What Got Built → Skills Augmented → When I Worked
  Act 3: What Got Accomplished → Pricing → Estimation Evidence
"""
from datetime import datetime, timezone
from harvest import compute_elapsed_minutes


def _utc_to_local(ts: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp and convert to the system's local timezone."""
    dt = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone()

C = {
    "bg":        "#f0f2f5",
    "card":      "#ffffff",
    "border":    "#dde1e7",
    "accent":    "#0078d4",
    "accent_dk": "#005a9e",
    "accent_lt": "#e8f2fb",
    "text":      "#1b1f23",
    "muted":     "#6a737d",
    "subtle":    "#f7f9fc",
    "green":     "#1a7f37",
    "green_lt":  "#dff6dd",
    "orange":    "#e65100",
    "orange_lt": "#fff3e0",
}

DOMAIN_PILL = ("background:#fff3e0;color:#e65100;padding:2px 8px;border-radius:9px;"
               "font-size:11px;font-weight:600;display:inline-block;margin:2px 3px 2px 0;"
               "white-space:nowrap")
TECH_PILL   = ("background:#e3f2fd;color:#1565c0;padding:2px 8px;border-radius:9px;"
               "font-size:11px;font-weight:600;display:inline-block;margin:2px 3px 2px 0;"
               "white-space:nowrap")


def _pills(domain: list, tech: list) -> str:
    out = [f'<span style="{DOMAIN_PILL}">{s}</span>' for s in domain]
    out += [f'<span style="{TECH_PILL}">{s}</span>' for s in tech]
    return "".join(out)


def _fmt_h(h: float) -> str:
    if h <= 0:      return "—"
    if h < 1:       return f"{int(round(h * 60))}m"
    if h == int(h): return f"{int(h)}h"
    return f"{h:.1f}h"


def _fmt_ms(ms: int) -> str:
    """Format milliseconds as Xm Ys."""
    if not ms:
        return "—"
    s = ms // 1000
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60}s"


def _cost(tokens: dict) -> str:
    """Calculate API cost using Anthropic token pricing (Copilot sessions use Claude models)."""
    c = (tokens.get("input", 0)          * 3.00
       + tokens.get("output", 0)         * 15.00
       + tokens.get("cache_read", 0)     * 0.30
       + tokens.get("cache_creation", 0) * 3.75) / 1_000_000
    return f"~${c:.2f}"


HOURLY_RATE = 72  # $/hr — blended professional services rate (conservative)
SEAT_COST_PER_MONTH = 39  # Enterprise Copilot seat $/month


def _prorated_seat_cost(analysis: dict) -> "tuple[int, int]":
    """Return (seat_cost, n_months) prorated over the distinct calendar months in active_dates."""
    dates = analysis.get("active_dates", [])
    if not dates:
        return SEAT_COST_PER_MONTH, 1
    months: set = set()
    for d in dates:
        try:
            dt = datetime.strptime(str(d)[:10], "%Y-%m-%d")
            months.add((dt.year, dt.month))
        except ValueError:
            pass
    n_months = max(1, len(months))
    return SEAT_COST_PER_MONTH * n_months, n_months


def _kpi_card(value: str, label: str, sub: str = "") -> str:
    return f"""
    <td style="padding:6px;width:20%;vertical-align:top">
      <div style="background:{C['card']};border:1px solid {C['border']};border-radius:10px;
                  padding:16px 10px;text-align:center;height:80px;
                  box-shadow:0 1px 4px rgba(0,0,0,0.06)">
        <div style="font-size:26px;font-weight:700;color:{C['accent']};line-height:1;
                    letter-spacing:-0.5px">{value}</div>
        <div style="font-size:9px;font-weight:700;color:{C['muted']};text-transform:uppercase;
                    letter-spacing:0.8px;margin-top:6px;line-height:1.3">{label}</div>
        {f'<div style="font-size:10px;color:{C["muted"]};margin-top:3px;line-height:1.3">{sub}</div>' if sub else ""}
      </div>
    </td>"""


def _kpi_section(goals: list, analysis: dict, n_sessions: int, total_prs: int = 0, total_commits: int = 0) -> str:
    total_human_h   = sum(g.get("human_hours", 0) for g in goals)
    n_goals         = len(goals)
    lines_added     = analysis.get("lines_added", 0)
    lines_removed   = analysis.get("lines_removed", 0)
    active_days     = max(1, len(analysis.get("active_dates", ["x"])))

    h_str = _fmt_h(total_human_h)
    days_label = f"{active_days}"

    # Code impact
    if lines_added or lines_removed:
        code_val = f"+{lines_added:,}"
        code_sub = f"{lines_removed:,} removed"
    else:
        code_val = "—"
        code_sub = ""

    # PRs & Commits
    pr_commit_val = f"{total_prs}"
    pr_commit_sub = f"{total_commits} commit{'s' if total_commits != 1 else ''}"

    return f"""
  <tr>
    <td style="background:{C['bg']};padding:12px 24px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {_kpi_card(str(n_goals), "Projects<br>Assisted", f"{n_sessions} sessions")}
          {_kpi_card(h_str, "Human Effort<br>Equivalent", f"@ ${HOURLY_RATE}/hr")}
          {_kpi_card(code_val, "Lines of Code<br>Added", code_sub)}
          {_kpi_card(pr_commit_val, "PRs<br>Merged", pr_commit_sub)}
          {_kpi_card(days_label, "Active Days", "")}
        </tr>
      </table>
    </td>
  </tr>"""


def _leverage_banner(goals: list, analysis: dict) -> str:
    """Hero-style ROI banner: services equivalent, seat cost, API savings."""
    total_human_h = sum(g.get("human_hours", 0) for g in goals)
    human_value   = total_human_h * HOURLY_RATE
    seat_cost, n_months = _prorated_seat_cost(analysis)
    leverage      = round(human_value / seat_cost) if seat_cost > 0 else 0

    # Market API cost
    tokens = analysis.get("tokens", {})
    market_cost = (tokens.get("input", 0) * 3.00
                 + tokens.get("output", 0) * 15.00
                 + tokens.get("cache_read", 0) * 0.30
                 + tokens.get("cache_creation", 0) * 3.75) / 1_000_000
    api_savings = max(0, market_cost - seat_cost)

    if leverage <= 0:
        return ""

    seat_label = (f"${seat_cost}/mo" if n_months == 1
                  else f"${seat_cost} ({n_months}mo)")

    return f"""
  <tr>
    <td style="padding:0;border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0" bgcolor="{C['green']}"
             style="background:linear-gradient(135deg,{C['green']},#15803d);border-collapse:collapse">
        <tr>
          <td bgcolor="{C['green']}" style="padding:18px 24px 6px;text-align:center">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
                        color:rgba(255,255,255,0.65);margin-bottom:6px">Return on Copilot Investment</div>
            <div style="font-size:44px;font-weight:800;color:#ffffff;line-height:1;
                        letter-spacing:-2px">{leverage:,}&times;</div>
          </td>
        </tr>
        <tr>
          <td bgcolor="#1a7f37" style="padding:4px 24px 14px">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="width:33%;text-align:center;padding:8px 8px;
                           border-right:1px solid rgba(255,255,255,0.2)">
                  <div style="font-size:10px;font-weight:700;text-transform:uppercase;
                              letter-spacing:0.8px;color:rgba(255,255,255,0.55)">Professional Services<br>Equivalent</div>
                  <div style="font-size:18px;font-weight:700;color:#fff;margin-top:4px">
                    ${human_value:,.0f}</div>
                  <div style="font-size:11px;color:rgba(255,255,255,0.7);margin-top:2px">
                    {total_human_h:.0f}h @ ${HOURLY_RATE}/hr</div>
                </td>
                <td style="width:33%;text-align:center;padding:8px 8px;
                           border-right:1px solid rgba(255,255,255,0.2)">
                  <div style="font-size:10px;font-weight:700;text-transform:uppercase;
                              letter-spacing:0.8px;color:rgba(255,255,255,0.55)">Copilot Seat<br>Cost</div>
                  <div style="font-size:18px;font-weight:700;color:#fff;margin-top:4px">
                    {seat_label}</div>
                  <div style="font-size:11px;color:rgba(255,255,255,0.7);margin-top:2px">
                    Enterprise plan</div>
                </td>
                <td style="width:33%;text-align:center;padding:8px 8px">
                  <div style="font-size:10px;font-weight:700;text-transform:uppercase;
                              letter-spacing:0.8px;color:rgba(255,255,255,0.55)">API Token<br>Savings</div>
                  <div style="font-size:18px;font-weight:700;color:#fff;margin-top:4px">
                    ${api_savings:,.0f}</div>
                  <div style="font-size:11px;color:rgba(255,255,255,0.7);margin-top:2px">
                    vs. ${market_cost:,.0f} at market rate</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>"""



def _what_i_work_on(goals: list, sessions: list) -> str:
    """Section: 'What Got Produced' — deliverables files categorized."""
    import re

    file_categories = {
        "Scripts":        {"icon": "&#128187;", "extensions": {".py", ".js", ".ts", ".sh", ".ps1"}},
        "Reports":        {"icon": "&#128202;", "extensions": {".html"}},
        "Documents":      {"icon": "&#128196;", "extensions": {".md", ".txt", ".docx", ".pdf"}},
        "Data & Config":  {"icon": "&#9881;",   "extensions": {".json", ".yaml", ".yml", ".toml", ".env", ".gitignore", ".cfg"}},
        "Presentations":  {"icon": "&#128209;", "extensions": {".pptx", ".ppt"}},
    }

    all_files: dict = {}
    for s in sessions:
        proj = s.get("project", "")
        for f in s.get("code_changes", {}).get("filesModified", []):
            fname = f.replace("\\", "/").split("/")[-1]
            all_files.setdefault(fname, proj)
        for f in s.get("files_touched", []):
            fname = f.replace("\\", "/").split("/")[-1]
            all_files.setdefault(fname, proj)
        for msg in s.get("messages", []):
            for tool in msg.get("tools_after", []):
                m = re.search(r'(?:create|edit).+[\\/]([^\\/]+\.\w{1,8})', tool, re.I)
                if m:
                    all_files.setdefault(m.group(1).rstrip('.'), proj)

    if not all_files:
        return ""

    counts: dict = {k: [] for k in file_categories}
    for fname in sorted(all_files.keys()):
        ext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if fname.lower() == ".gitignore":
            ext = ".gitignore"
        for cat, info in file_categories.items():
            if ext in info["extensions"]:
                counts[cat].append((fname, all_files[fname]))
                break

    total_files = len(all_files)

    cells = ""
    for cat, info in file_categories.items():
        c = len(counts[cat])
        if c <= 0:
            continue
        cells += (
            f'<td style="padding:8px 12px;text-align:center;vertical-align:top">'
            f'<div style="font-size:24px;font-weight:700;color:{C["accent"]};line-height:1">{c}</div>'
            f'<div style="font-size:10px;font-weight:600;color:{C["muted"]};margin-top:4px;'
            f'text-transform:uppercase;letter-spacing:0.5px">{info["icon"]} {cat}</div>'
            f'</td>'
        )

    file_list_rows = ""
    for cat, info in file_categories.items():
        if not counts[cat]:
            continue
        fnames = ", ".join(
            f'<span style="font-size:10px;color:{C["accent"]};font-weight:500">{proj}</span>'
            f'<span style="font-size:10px;color:{C["muted"]}">/{fn}</span>'
            for fn, proj in counts[cat]
        )
        file_list_rows += (
            f'<tr><td style="padding:4px 0;font-size:10px;font-weight:600;'
            f'color:{C["muted"]};white-space:nowrap;vertical-align:top;width:100px">'
            f'{info["icon"]} {cat}</td>'
            f'<td style="padding:4px 8px;font-size:10px;color:{C["text"]}">{fnames}</td></tr>'
        )

    return f"""
  <tr>
    <td style="background:{C['card']};padding:0;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);padding:10px 24px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                    color:rgba(255,255,255,0.7)">What Got Produced</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:2px">
          Artifacts created and skills augmented to produce them</div>
      </td></tr></table>
      <div style="padding:14px 24px 18px">
        <div style="font-size:11px;color:{C['muted']};margin-bottom:10px">
          <strong style="color:{C['text']}">{total_files} files</strong> created or modified</div>
        <table cellpadding="0" cellspacing="0">
          <tr>{cells}</tr>
        </table>
        <div id="deliverables-detail-hdr" style="cursor:pointer;padding:6px 0 0;margin-top:6px"
             onclick="toggleDetail('deliverables-detail')">
          <span id="deliverables-detail-arrow" style="font-size:10px;color:{C['accent']};margin-right:5px">&#9654;</span>
          <span style="font-size:10px;font-weight:600;color:{C['accent']}">Show file names</span>
        </div>
        <div id="deliverables-detail-tasks" style="display:none;margin-top:6px">
          <table cellpadding="0" cellspacing="0" width="100%">{file_list_rows}</table>
        </div>
      </div>
    </td>
  </tr>"""



def _daily_activity_detail(sessions: list) -> str:
    """GitHub-style heatmap grid: rows=days, columns=time periods, color=intensity."""
    from datetime import datetime as _dt
    from collections import defaultdict

    PERIODS = [
        ("Early Morning", "5–9am",   5,  9),
        ("Morning",       "9am–12pm", 9, 12),
        ("Afternoon",     "12–5pm", 12, 17),
        ("Evening",       "5–9pm",  17, 21),
        ("Night",         "9pm–5am", 21, 29),  # 21-24 + 0-5
    ]

    def _period_idx(hour: int) -> int:
        if 5 <= hour < 9:   return 0
        if 9 <= hour < 12:  return 1
        if 12 <= hour < 17: return 2
        if 17 <= hour < 21: return 3
        return 4  # 21-24 and 0-5

    # Collect messages per day per period
    day_periods: dict = defaultdict(lambda: [0] * 5)
    for s in sessions:
        for msg in s.get("messages", []):
            ts = msg.get("timestamp", "")
            if not ts:
                continue
            try:
                dt = _utc_to_local(ts)
                day_key = dt.strftime("%Y-%m-%d")
                day_periods[day_key][_period_idx(dt.hour)] += 1
            except (ValueError, TypeError):
                pass

    if not day_periods:
        return ""

    # Color intensity scale — logarithmic breaks for better visual spread
    global_max = max(max(p) for p in day_periods.values()) or 1
    SHADES = [
        (C["bg"],      C["text"]),     # 0 = no activity
        ("#dbeafe",    C["text"]),     # 1 = very light
        ("#93c5fd",    C["text"]),     # 2 = light
        ("#3b82f6",    "#ffffff"),     # 3 = medium
        ("#1d4ed8",    "#ffffff"),     # 4 = high
        ("#1e3a5f",    "#ffffff"),     # 5 = intense
    ]

    def _shade(count: int) -> tuple:
        """Return (bg_color, text_color) based on message count."""
        if count == 0:
            return SHADES[0]
        # Log-based scaling: 1→1, 2-3→2, 4-8→3, 9-20→4, 21+→5
        import math
        level = min(5, max(1, int(math.log2(count) + 1)))
        return SHADES[level]

    # Column headers
    header_cells = f'<td style="width:70px;padding:4px 0"></td>'
    for name, times, _, _ in PERIODS:
        header_cells += (
            f'<td style="text-align:center;padding:4px 2px;width:18%">'
            f'<div style="font-size:9px;font-weight:700;color:{C["muted"]};'
            f'text-transform:uppercase;letter-spacing:0.3px">{name}</div>'
            f'<div style="font-size:8px;color:{C["muted"]}">{times}</div>'
            f'</td>'
        )
    header_cells += f'<td style="width:50px;padding:4px 4px;text-align:right"></td>'

    # Data rows
    data_rows = ""
    for day in sorted(day_periods.keys()):
        periods = day_periods[day]
        total = sum(periods)
        try:
            d = _dt.strptime(day, "%Y-%m-%d")
            day_label = d.strftime("%b %d")
            weekday = d.strftime("%a")
        except ValueError:
            day_label = day[5:]
            weekday = ""

        cells = (
            f'<td style="padding:3px 10px 3px 0;vertical-align:middle;width:70px">'
            f'<span style="font-size:10px;font-weight:700;color:{C["text"]}">{day_label}</span>'
            f'&nbsp;<span style="font-size:9px;color:{C["muted"]}">{weekday}</span>'
            f'</td>'
        )
        for i, count in enumerate(periods):
            bg, fg = _shade(count)
            count_label = str(count) if count > 0 else ""
            cells += (
                f'<td style="padding:2px;vertical-align:middle">'
                f'<div style="background:{bg};border-radius:4px;height:28px;'
                f'line-height:28px;text-align:center;font-size:9px;font-weight:600;'
                f'color:{fg}">{count_label}</div>'
                f'</td>'
            )
        cells += (
            f'<td style="padding:3px 0 3px 6px;vertical-align:middle;text-align:right">'
            f'<span style="font-size:9px;color:{C["muted"]}">{total}</span>'
            f'</td>'
        )
        data_rows += f'<tr>{cells}</tr>'

    # Legend
    legend = (
        f'<div style="margin-top:8px;text-align:right">'
        f'<span style="font-size:8px;color:{C["muted"]};margin-right:4px">Less</span>'
    )
    for bg, _ in SHADES:
        legend += (
            f'<span style="display:inline-block;width:12px;height:12px;'
            f'background:{bg};border-radius:2px;margin:0 1px;'
            f'border:1px solid {C["border"]};vertical-align:middle"></span>'
        )
    legend += (
        f'<span style="font-size:8px;color:{C["muted"]};margin-left:4px">More</span>'
        f'</div>'
    )

    return f"""
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>{header_cells}</tr>
          {data_rows}
        </table>
        {legend}"""


def _work_pattern(sessions: list) -> str:
    """Horizontal bar chart of message counts by time-of-day bucket."""
    from datetime import datetime as _dt

    buckets = {
        "Early Morning (5–9am)":  0,
        "Morning (9am–12pm)":     0,
        "Afternoon (12–5pm)":     0,
        "Evening (5–9pm)":        0,
        "Night (9pm–5am)":        0,
    }

    def _bucket_for_hour(h: int) -> str:
        if 5 <= h < 9:   return "Early Morning (5–9am)"
        if 9 <= h < 12:  return "Morning (9am–12pm)"
        if 12 <= h < 17: return "Afternoon (12–5pm)"
        if 17 <= h < 21: return "Evening (5–9pm)"
        return "Night (9pm–5am)"

    for s in sessions:
        for msg in s.get("messages", []):
            ts = msg.get("timestamp", "")
            if not ts:
                continue
            try:
                dt = _utc_to_local(ts)
                buckets[_bucket_for_hour(dt.hour)] += 1
            except (ValueError, TypeError):
                pass

    total = sum(buckets.values())
    if total == 0:
        return ""

    max_count = max(buckets.values())
    peak_bucket = max(buckets, key=buckets.get)

    rows = ""
    for label, count in buckets.items():
        if count == 0 and label != peak_bucket:
            bar_width = 0
        else:
            bar_width = int(count / max_count * 100) if max_count else 0

        is_peak = label == peak_bucket
        label_style = (
            f"font-size:11px;font-weight:{'700' if is_peak else '400'};"
            f"color:{C['text'] if is_peak else C['muted']};white-space:nowrap"
        )
        count_style = (
            f"font-size:11px;font-weight:{'700' if is_peak else '400'};"
            f"color:{C['text'] if is_peak else C['muted']};white-space:nowrap"
        )
        peak_tag = (
            f' <span style="font-size:9px;color:{C["accent"]};font-weight:700">&larr; Peak</span>'
            if is_peak else ""
        )

        rows += f"""
          <tr>
            <td style="padding:3px 12px 3px 0;{label_style};width:160px">{label}</td>
            <td style="padding:3px 0;width:auto">
              <div style="background:{C['accent_lt']};border-radius:4px;height:16px;width:100%">
                <div style="background:{C['accent']};border-radius:4px;height:16px;width:{bar_width}%;
                            min-width:{2 if count else 0}px"></div>
              </div>
            </td>
            <td style="padding:3px 0 3px 10px;{count_style};width:100px">
              {count} msg{'s' if count != 1 else ''}{peak_tag}
            </td>
          </tr>"""

    return f"""
  <tr>
    <td style="background:{C['card']};padding:0;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);padding:10px 24px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                    color:rgba(255,255,255,0.7)">When I Worked</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:2px">
          When Copilot-assisted work happened during the day</div>
      </td></tr></table>
      <div style="padding:14px 24px 18px">
      <table width="100%" cellpadding="0" cellspacing="0">
        {rows}
      </table>
      <div id="daily-detail-hdr" style="margin-top:12px;padding:8px 12px;background:{C['accent_lt']};
                                         border-radius:6px;cursor:pointer;border:1px solid rgba(0,120,212,0.15)"
           onclick="toggleDetail('daily-detail')">
        <span id="daily-detail-arrow" style="font-size:10px;color:{C['accent']};margin-right:5px">&#9654;</span>
        <span style="font-size:11px;font-weight:600;color:{C['accent']}">See daily breakdown</span>
        <span style="font-size:10px;color:{C['muted']};margin-left:8px">Hourly activity heatmap per day</span>
      </div>
      <div id="daily-detail-tasks" style="display:none;margin-top:8px">
        {_daily_activity_detail(sessions)}
      </div>
      </div>
    </td>
  </tr>"""


def _collaboration_intent(sessions: list, goals: list) -> str:
    """Section: 'How I Collaborated' — intent donut chart with per-project breakdowns."""
    from harvest import aggregate_intents
    import harvest as _harvest

    # Prefer intent metadata from `harvest` when available; fall back to empty mappings.
    _INTENT_COLORS = getattr(_harvest, "_INTENT_COLORS", {})
    _INTENT_ICONS  = getattr(_harvest, "_INTENT_ICONS", {})
    # `goals` is accepted for API symmetry / future use.
    _ = goals

    intent_data = aggregate_intents(sessions)
    counts = intent_data["counts"]
    by_project = intent_data["by_project"]
    total = intent_data["total"]

    if total == 0:
        return ""

    # Sort categories by count descending, take top 6
    sorted_cats = sorted(counts.items(), key=lambda x: -x[1])
    if len(sorted_cats) > 6:
        top = sorted_cats[:5]
        other_count = sum(v for _, v in sorted_cats[5:])
        top.append(("Other", other_count))
    else:
        top = sorted_cats

    # Build conic-gradient stops for donut chart
    gradient_stops = []
    cumulative = 0
    for cat, n in top:
        pct = n / total * 100
        color = _INTENT_COLORS.get(cat, C["muted"])
        gradient_stops.append(f"{color} {cumulative:.1f}% {cumulative + pct:.1f}%")
        cumulative += pct
    gradient = ", ".join(gradient_stops)

    # Legend items — vertical list beside the donut
    legend_rows = ""
    for cat, n in top:
        pct = n / total * 100
        if n == 0:
            continue
        color = _INTENT_COLORS.get(cat, C["muted"])
        icon = _INTENT_ICONS.get(cat, "&#128161;")
        legend_rows += (
            f'<div style="display:flex;align-items:center;margin-bottom:6px">'
            f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
            f'border-radius:2px;margin-right:8px;flex-shrink:0"></span>'
            f'<span style="font-size:11px;font-weight:600;color:{C["text"]};'
            f'margin-right:6px;white-space:nowrap">{icon} {cat}</span>'
            f'<span style="font-size:10px;color:{C["muted"]};white-space:nowrap">'
            f'{n} ({pct:.0f}%)</span>'
            f'</div>'
        )

    # Top intent insight line
    top_cat, top_n = top[0]
    top_pct = round(top_n / total * 100)
    n_modes = len([c for c, n in top if n > 0])
    insight = (
        f'Worked across <strong style="color:{C["text"]}">{n_modes} collaboration modes</strong>. '
        f'Primary mode: <strong style="color:{_INTENT_COLORS.get(top_cat, C["accent"])}">'
        f'{top_cat}</strong> ({top_pct}% of interactions)'
    )

    # Per-project mini-bars (only if multiple projects)
    project_bars_html = ""
    if len(by_project) > 1:
        proj_rows = ""
        for proj, pcounts in sorted(by_project.items(), key=lambda x: -sum(x[1].values())):
            ptotal = sum(pcounts.values())
            if ptotal == 0:
                continue
            proj_sorted = sorted(pcounts.items(), key=lambda x: -x[1])
            proj_bar = ""
            for cat, n in proj_sorted:
                pct = n / ptotal * 100
                if pct < 3:
                    continue
                color = _INTENT_COLORS.get(cat, C["muted"])
                proj_bar += (
                    f'<td style="width:{pct:.1f}%;background:{color};height:12px;'
                    f'font-size:0;padding:0"></td>'
                )
            top2 = [f'{c} {round(n/ptotal*100)}%' for c, n in proj_sorted[:2] if n > 0]
            proj_rows += (
                f'<tr>'
                f'<td style="padding:4px 10px 4px 0;font-size:10px;font-weight:600;'
                f'color:{C["text"]};white-space:nowrap;width:120px;vertical-align:middle">{proj}</td>'
                f'<td style="padding:4px 0;vertical-align:middle">'
                f'<table width="100%" cellpadding="0" cellspacing="0" '
                f'style="border-radius:4px;overflow:hidden"><tr>{proj_bar}</tr></table></td>'
                f'<td style="padding:4px 0 4px 10px;font-size:9px;color:{C["muted"]};'
                f'white-space:nowrap;width:140px;vertical-align:middle">{" · ".join(top2)}</td>'
                f'</tr>'
            )

        if proj_rows:
            project_bars_html = f"""
            <div style="border-top:1px solid {C['border']};margin-top:14px;padding-top:10px">
              <div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.7px;
                          color:{C['muted']};margin-bottom:6px">By Project</div>
              <table width="100%" cellpadding="0" cellspacing="0">{proj_rows}</table>
            </div>"""

    return f"""
  <tr>
    <td style="background:{C['card']};padding:0;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);padding:10px 24px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                    color:rgba(255,255,255,0.7)">How I Collaborated</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:2px">
          Intent behind every interaction &mdash; from research to shipping</div>
      </td></tr></table>
      <div style="padding:14px 24px 16px">
        <div style="font-size:11px;color:{C['muted']};margin-bottom:14px;line-height:1.5">
          {insight}
        </div>
        <table cellpadding="0" cellspacing="0" width="100%">
          <tr>
            <td style="width:140px;vertical-align:middle;text-align:center;padding-right:20px">
              <div style="width:130px;height:130px;border-radius:50%;
                          background:conic-gradient({gradient});
                          display:inline-block;position:relative">
                <div style="position:absolute;top:25px;left:25px;width:80px;height:80px;
                            border-radius:50%;background:{C['card']}">
                  <div style="text-align:center;padding-top:22px">
                    <div style="font-size:22px;font-weight:800;color:{C['accent']};line-height:1">{total}</div>
                    <div style="font-size:8px;font-weight:600;color:{C['muted']};text-transform:uppercase;
                                letter-spacing:0.5px;margin-top:2px">interactions</div>
                  </div>
                </div>
              </div>
            </td>
            <td style="vertical-align:middle;padding-left:10px">
              {legend_rows}
            </td>
          </tr>
        </table>
        {project_bars_html}
      </div>
    </td>
  </tr>"""


def _skills_mobilized(goals: list) -> str:
    """Ranked horizontal bar chart of professional roles by hours of assistance."""
    from collections import defaultdict

    ROLE_ICONS = {
        # Technical
        "Software Engineer":          "&#128187;",   # 💻 laptop
        "Frontend Developer":         "&#127760;",   # 🌐 globe
        "Data Analyst":               "&#128200;",   # 📈 chart
        "Data Engineer":              "&#128202;",   # 📊 bar chart
        "DevOps Engineer":            "&#9881;",     # ⚙ gear
        "Solutions Architect":        "&#127959;",   # 🏗 building
        "Security Engineer":          "&#128274;",   # 🔒 lock
        "QA Engineer":                "&#128269;",   # 🔍 magnifying glass
        # Design & communication
        "UX Designer":                "&#9998;",     # ✎ pencil
        "Visual Designer":            "&#127912;",   # 🎨 palette
        "Technical Writer":           "&#128221;",   # 📝 memo
        # Business & strategy
        "Product Manager":            "&#127919;",   # 🎯 target
        "Program Manager":            "&#128203;",   # 📋 clipboard
        "Business Analyst":           "&#128196;",   # 📄 page
        "Management Consultant":      "&#128188;",   # 💼 briefcase
        # Domain & industry
        "Research Scientist":         "&#128300;",   # 🔬 microscope
        "Financial Analyst":          "&#128185;",   # 💹 chart with currency
        "Risk & Compliance Analyst":  "&#128737;",   # 🛡 shield
        "Domain Expert":              "&#127891;",   # 🎓 graduation cap
    }

    # Tech skill → role affinity weights.
    # Used to split hours between roles on multi-role tasks rather than
    # proration — e.g. Python weights toward Software Engineer, SQL toward
    # Data Analyst, HTML/CSS toward UX/Visual Designer.
    TECH_AFFINITY: dict = {
        "Python":      {"Software Engineer": 3, "Data Analyst": 1, "Data Engineer": 2},
        "SQL":         {"Data Analyst": 3, "Data Engineer": 2},
        "JavaScript":  {"Software Engineer": 3, "Frontend Developer": 2},
        "TypeScript":  {"Software Engineer": 3, "Frontend Developer": 2},
        "HTML/CSS":    {"Frontend Developer": 2, "UX Designer": 2, "Visual Designer": 1},
        "CSS":         {"UX Designer": 2, "Visual Designer": 2},
        "Bash/Shell":  {"Software Engineer": 2, "DevOps Engineer": 2},
        "PowerShell":  {"DevOps Engineer": 3, "Software Engineer": 1},
        "R":           {"Data Analyst": 3, "Data Engineer": 1},
        "Java":        {"Software Engineer": 3},
        "Go":          {"Software Engineer": 3, "DevOps Engineer": 1},
        "Rust":        {"Software Engineer": 3},
        "C#":          {"Software Engineer": 3},
        "C++":         {"Software Engineer": 3},
    }

    role_data: dict = defaultdict(lambda: {"count": 0, "hours": 0.0})
    for g in goals:
        for t in g.get("tasks", []):
            task_hours = t.get("human_hours", 0) or 0
            roles = t.get("professional_roles", [])
            if not roles:
                roles = t.get("domain_skills", []) + t.get("tech_skills", [])
            if not roles:
                continue
            tech = [s for s in t.get("tech_skills", []) if s in TECH_AFFINITY]

            # Build per-role affinity score from tech skills
            scores: dict = {}
            for r in roles:
                scores[r] = sum(TECH_AFFINITY[sk].get(r, 0) for sk in tech)

            total_score = sum(scores.values())
            for r in roles:
                role_data[r]["count"] += 1
                if total_score > 0:
                    role_data[r]["hours"] += task_hours * (scores[r] / total_score)
                else:
                    role_data[r]["hours"] += task_hours / len(roles)

    if not role_data:
        return ""

    sorted_roles = sorted(role_data.items(), key=lambda x: x[1]["hours"], reverse=True)
    max_hours = sorted_roles[0][1]["hours"] or 1
    total_hours = sum(d["hours"] for _, d in sorted_roles)
    n_roles = len(sorted_roles)
    total_tasks = sum(d["count"] for _, d in sorted_roles)

    rows = ""
    for role, data in sorted_roles:
        icon  = ROLE_ICONS.get(role, "&#128161;")
        hrs   = data["hours"]
        count = data["count"]
        bar   = round(hrs / max_hours * 100)
        h_str = _fmt_h(hrs)
        rows += f"""
          <tr>
            <td style="padding:5px 10px 5px 0;white-space:nowrap;vertical-align:middle;width:24px">
              <span style="font-size:15px">{icon}</span>
            </td>
            <td style="padding:5px 12px 5px 0;white-space:nowrap;vertical-align:middle;width:130px">
              <span style="font-size:12px;font-weight:600;color:{C['text']}">{role}</span>
            </td>
            <td style="padding:5px 0;vertical-align:middle">
              <div style="background:{C['bg']};border-radius:4px;height:14px;width:100%">
                <div style="background:{C['accent']};border-radius:4px;height:14px;width:{bar}%;
                            min-width:4px"></div>
              </div>
            </td>
            <td style="padding:5px 0 5px 12px;white-space:nowrap;vertical-align:middle;width:40px;text-align:right">
              <span style="font-size:13px;font-weight:700;color:{C['accent']}">{h_str}</span>
            </td>
            <td style="padding:5px 0 5px 8px;white-space:nowrap;vertical-align:middle;width:55px">
              <span style="font-size:10px;color:{C['muted']}">{count} task{'s' if count != 1 else ''}</span>
            </td>
          </tr>"""

    return f"""
  <tr>
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-bottom:6px">SKILLS AUGMENTED</div>
      <div style="font-size:14px;font-weight:700;color:{C['text']};margin-bottom:4px;line-height:1.4">
        This is the team GitHub Copilot assembled for me &mdash; on demand, at zero headcount cost.</div>
      <div style="font-size:11px;color:{C['muted']};margin-bottom:14px">
        {_fmt_h(total_hours)} of expert-level assistance across {n_roles} professional disciplines &middot; {total_tasks} tasks delivered</div>
      <table width="100%" cellpadding="0" cellspacing="0">
        {rows}
      </table>
    </td>
  </tr>"""


def _resolve_metrics(project: str, session_metrics: dict, goal_date: str = "") -> dict:
    """Look up session metrics for a goal, trying date-prefixed key first."""
    if goal_date:
        dated_key = goal_date + "|" + project
        metrics = session_metrics.get(dated_key, {})
        if metrics:
            return metrics
        last = project.replace("\\", "/").split("/")[-1]
        metrics = session_metrics.get(goal_date + "|" + last, {})
        if metrics:
            return metrics
    # Fall back to non-dated key (single-day reports)
    metrics = session_metrics.get(project, {})
    if not metrics:
        last = project.replace("\\", "/").split("/")[-1]
        metrics = session_metrics.get(last, {})
    return metrics


# ── Deterministic effort formula ─────────────────────────────────────────────

def _tier_tools(n: int) -> float:
    if n <= 0:   return 0.0
    if n <= 5:   return 0.25
    if n <= 15:  return 0.5
    if n <= 50:  return 0.75
    if n <= 150: return 1.5
    if n <= 400: return 3.0
    return 5.0


def _tier_reqs(n: int) -> float:
    if n <= 0:   return 0.0
    if n <= 5:   return 0.25
    if n <= 20:  return 0.5
    if n <= 50:  return 1.0
    if n <= 100: return 2.0
    return 3.0


def _tier_lines(n: int) -> float:
    if n <= 0:   return 0.0
    if n <= 25:  return 0.1
    if n <= 100: return 0.25
    if n <= 300: return 0.5
    return 1.0


def _tier_active(m: float) -> float:
    """Active engagement multiplier — a human without AI would need roughly
    4× the active collaboration time, accounting for the specialist skills
    Copilot augments."""
    return round(m * 4 / 60, 1)  # 4× active minutes, converted to hours


def compute_formula_estimate(metrics: dict) -> dict:
    """Deterministic effort estimate: max(tools, requests, active) + lines.

    Returns dict with per-signal multipliers and final estimate.
    """
    tool_h   = _tier_tools(metrics.get("tool_invocations", 0))
    req_h    = _tier_reqs(metrics.get("premium_requests", 0))
    active_h = _tier_active(metrics.get("active_minutes", 0))
    lines_h  = _tier_lines(metrics.get("lines_added", 0))

    base = max(tool_h, req_h, active_h)
    total = base + lines_h
    total = max(total, 0.25)           # Floor at 0.25h

    return {
        "tool_h":   tool_h,
        "req_h":    req_h,
        "active_h": active_h,
        "lines_h":  lines_h,
        "base":     base,
        "total":    round(total * 4) / 4,  # Nearest 0.25h
    }


def _estimation_waterfall_inner(goals: list, analysis: dict) -> str:
    """Evidence table showing raw signals, per-signal multipliers, and formula result."""
    session_metrics = analysis.get("session_metrics", {})
    if not goals:
        return ""

    total_h = sum(g.get("human_hours", 0) for g in goals)
    total_formula_h = 0.0

    rows = ""
    for i, g in enumerate(goals):
        bg = C["subtle"] if i % 2 == 0 else C["card"]
        project = g.get("project", "")
        metrics = _resolve_metrics(project, session_metrics, g.get("date", ""))
        fe = compute_formula_estimate(metrics)
        total_formula_h += fe["total"]

        tools      = metrics.get("tool_invocations", 0)
        reqs       = metrics.get("premium_requests", 0)
        la         = metrics.get("lines_added", 0)
        active     = metrics.get("active_minutes", 0)
        active_str = f"{active:.0f}m" if active else "&mdash;"
        ai_h       = _fmt_h(g.get("human_hours", 0))
        formula_h  = _fmt_h(fe["total"])

        title = g.get("title", "")
        if len(title) > 40:
            title = title[:37] + "..."

        # Highlight which signal is the max (the "base" driver)
        max_val = fe["base"]
        def _hl(v: float) -> str:
            """Bold the multiplier if it equals the max (base driver)."""
            s = _fmt_h(v) if v > 0 else "&mdash;"
            if v > 0 and v == max_val:
                return (f'<strong style="color:{C["accent"]}">{s}</strong>')
            return f'<span style="color:{C["muted"]}">{s}</span>'

        lines_m = _fmt_h(fe["lines_h"]) if fe["lines_h"] > 0 else "&mdash;"

        # Formula string: max(tool, req, active) + lines = total
        formula_str = (
            f'max({_fmt_h(fe["tool_h"])}, {_fmt_h(fe["req_h"])}, {_fmt_h(fe["active_h"])})'
            f' + {_fmt_h(fe["lines_h"])} = <strong>{formula_h}</strong>'
        )

        rows += f"""
        <tr style="background:{bg}">
          <td style="padding:6px 10px;border-bottom:1px solid {C['border']};vertical-align:top;width:22%"
              rowspan="2">
            <div style="font-size:11px;font-weight:600;color:{C['text']};line-height:1.3">{title}</div>
          </td>
          <td style="padding:4px 6px;font-size:11px;color:{C['text']};text-align:center;
                     font-weight:600;width:13%">{tools}</td>
          <td style="padding:4px 6px;font-size:11px;color:{C['text']};text-align:center;
                     font-weight:600;width:13%">{reqs}</td>
          <td style="padding:4px 6px;font-size:11px;color:{C['text']};text-align:center;
                     font-weight:600;width:13%">{active_str}</td>
          <td style="padding:4px 6px;font-size:11px;color:{C['text']};text-align:center;
                     font-weight:600;width:13%">+{la}</td>
          <td class="formula-col" style="padding:4px 6px;text-align:center;width:13%;vertical-align:middle;display:none" rowspan="2">
            <div style="font-size:14px;font-weight:700;color:{C['accent']}">{formula_h}</div>
            <div style="font-size:8px;color:{C['muted']};text-transform:uppercase;margin-top:1px">formula</div>
          </td>
          <td style="padding:4px 6px;text-align:center;width:13%;vertical-align:middle" rowspan="2">
            <div style="font-size:14px;font-weight:700;color:{C['green']}">{ai_h}</div>
            <div style="font-size:8px;color:{C['muted']};text-transform:uppercase;margin-top:1px">AI est.</div>
          </td>
        </tr>
        <tr style="background:{bg}">
          <td style="padding:2px 6px 6px;text-align:center;border-bottom:1px solid {C['border']}">
            {_hl(fe["tool_h"])}</td>
          <td style="padding:2px 6px 6px;text-align:center;border-bottom:1px solid {C['border']}">
            {_hl(fe["req_h"])}</td>
          <td style="padding:2px 6px 6px;text-align:center;border-bottom:1px solid {C['border']}">
            {_hl(fe["active_h"])}</td>
          <td style="padding:2px 6px 6px;text-align:center;border-bottom:1px solid {C['border']}">
            <span style="color:{C['muted']}">{lines_m}</span></td>
        </tr>"""

    # Total row
    rows += f"""
        <tr style="background:{C['accent_lt']}">
          <td style="padding:8px 10px;border-top:2px solid {C['border']};
                     font-size:11px;font-weight:700;color:{C['accent']};text-align:right" colspan="5">
            Total</td>
          <td class="formula-col" style="padding:8px 6px;border-top:2px solid {C['border']};text-align:center;display:none">
            <div style="font-size:16px;font-weight:700;color:{C['accent']}">{_fmt_h(total_formula_h)}</div>
          </td>
          <td style="padding:8px 6px;border-top:2px solid {C['border']};text-align:center">
            <div style="font-size:16px;font-weight:700;color:{C['green']}">{_fmt_h(total_h)}</div>
          </td>
        </tr>"""

    return f"""
      <div style="font-size:11px;color:{C['muted']};margin-bottom:10px;line-height:1.6">
        <strong style="color:{C['text']}">How to read this table:</strong>
        Each row shows a project's raw session data (top) and the hour multiplier each signal
        maps to (bottom). The <strong style="color:{C['accent']}">highest multiplier</strong>
        among tools, requests, and active time becomes the base estimate.
        Lines of code are added on top.
      </div>
      <div style="font-size:10px;color:{C['muted']};margin-bottom:10px;padding:8px 12px;
                  background:{C['subtle']};border-radius:6px;border:1px solid {C['border']}">
        <span style="color:{C['green']}">&#9632;</span> AI-calibrated estimate &nbsp;·&nbsp;
        <strong style="color:{C['accent']}">Bold</strong> = highest signal
        &nbsp;&nbsp;
        <span id="formula-col-toggle" data-open="0" onclick="toggleFormulaCol()"
              style="cursor:pointer;font-size:9px;color:{C['accent']};user-select:none">
          &#9654; Show formula column
        </span>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {C['border']};border-radius:7px;overflow:hidden">
        <tr style="background:{C['accent_lt']}">
          <th style="padding:6px 10px;text-align:left;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:22%">Project</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:13%">Tools</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:13%">Requests</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:13%">Active</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:13%">Lines</th>
          <th class="formula-col" style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:13%;display:none">Formula</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['green']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:13%">AI Est.</th>
        </tr>
        {rows}
      </table>"""


def _evidence_strip(goal: dict, session_metrics: dict) -> str:
    """Compact metrics bar showing evidence and formula behind a goal's estimate."""
    project = goal.get("project", "")
    metrics = _resolve_metrics(project, session_metrics, goal.get("date", ""))
    if not metrics:
        return ""

    fe = compute_formula_estimate(metrics)

    parts = []
    reqs = metrics.get("premium_requests", 0)
    if reqs:
        parts.append(f"<strong>{reqs}</strong> reqs &rarr; {_fmt_h(fe['req_h'])}")
    tok = metrics.get("tokens", 0)
    tools = metrics.get("tool_invocations", 0)
    if tools:
        parts.append(f"<strong>{tools}</strong> tools &rarr; {_fmt_h(fe['tool_h'])}")
    la = metrics.get("lines_added", 0)
    if la:
        parts.append(f"<strong>+{la}</strong> lines &rarr; {_fmt_h(fe['lines_h'])}")
    active = metrics.get("active_minutes", 0)
    if active:
        parts.append(f"<strong>{active:.0f}m</strong> active &rarr; {_fmt_h(fe['active_h'])}")

    if not parts:
        return ""

    formula_h = _fmt_h(fe["total"])
    ai_h      = _fmt_h(goal.get("human_hours", 0))
    import hashlib as _hl
    _key = (goal.get('title', '') + goal.get('date', '')).encode()
    fid  = "fs-" + _hl.sha1(_key).hexdigest()[:12]

    return f"""
            <div style="padding:8px 24px;background:{C['subtle']};border-bottom:1px solid {C['border']}">
              <div style="font-size:10px;color:{C['muted']};line-height:1.5">
                <span style="font-weight:700;color:{C['accent']};margin-right:4px">&#128202;</span>
                {' &middot; '.join(parts)}
                &nbsp;&nbsp;
                <strong style="color:{C['green']}">{ai_h}</strong>
                <span style="font-size:9px;color:{C['muted']}"> AI-calibrated</span>
                <span id="{fid}-arrow" onclick="toggleFormula('{fid}')"
                      style="cursor:pointer;font-size:9px;color:{C['accent']};
                             margin-left:10px;user-select:none">&#9654; formula</span>
              </div>
              <div id="{fid}" style="display:none;margin-top:4px;font-size:10px;color:{C['muted']}">
                <code style="font-size:9px;background:{C['bg']};padding:1px 5px;border-radius:3px;
                             color:{C['text']}">max({_fmt_h(fe['tool_h'])}, {_fmt_h(fe['req_h'])}, {_fmt_h(fe['active_h'])}) + {_fmt_h(fe['lines_h'])}</code>
                = <strong style="color:{C['accent']}">{formula_h}</strong> deterministic
              </div>
            </div>"""


def _signal_tier_table(title: str, icon: str, description: str, tiers: list) -> str:
    """Render a single signal explanation table with tiers and multipliers."""
    rows = ""
    for i, (range_label, hour_label, example) in enumerate(tiers):
        bg = C["subtle"] if i % 2 == 0 else C["card"]
        rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:3px 10px;font-size:10px;font-weight:600;color:{C["text"]};'
            f'border-bottom:1px solid {C["border"]};width:14%;white-space:nowrap">{range_label}</td>'
            f'<td style="padding:3px 10px;border-bottom:1px solid {C["border"]};width:12%;text-align:center">'
            f'<span style="font-size:10px;font-weight:700;color:{C["accent"]};'
            f'background:{C["accent_lt"]};padding:1px 8px;border-radius:8px">{hour_label}</span></td>'
            f'<td style="padding:3px 10px;font-size:10px;color:{C["muted"]};'
            f'border-bottom:1px solid {C["border"]};width:74%">{example}</td>'
            f'</tr>'
        )
    return f"""
        <div style="margin-top:14px">
          <div style="font-size:10px;font-weight:700;color:{C['text']};margin-bottom:2px">
            {icon} {title}</div>
          <div style="font-size:10px;color:{C['muted']};margin-bottom:6px;line-height:1.4">
            {description}</div>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid {C['border']};border-radius:5px;overflow:hidden">
            <tr style="background:{C['accent_lt']}">
              <th style="padding:3px 10px;font-size:9px;font-weight:700;color:{C['accent']};
                         text-transform:uppercase;letter-spacing:0.5px;
                         border-bottom:1px solid {C['border']};width:14%">Range</th>
              <th style="padding:3px 10px;font-size:9px;font-weight:700;color:{C['accent']};
                         text-transform:uppercase;letter-spacing:0.5px;text-align:center;
                         border-bottom:1px solid {C['border']};width:12%">Multiplier</th>
              <th style="padding:3px 10px;font-size:9px;font-weight:700;color:{C['accent']};
                         text-transform:uppercase;letter-spacing:0.5px;
                         border-bottom:1px solid {C['border']};width:74%">What this means</th>
            </tr>
            {rows}
          </table>
        </div>"""


def _signal_guide() -> str:
    """Detailed explanation of each session signal with tiered examples."""
    tools = _signal_tier_table(
        "Tool Invocations", "&#128295;",
        "Each time Copilot performs a discrete action: read a file, edit code, run a command, "
        "search, create a file. Higher counts indicate more complex, multi-step work.",
        [
            ("1–5",    "0.25h", "Quick task &mdash; open a file, make one edit, done. "
                                "<em>\"Fix this typo in config.yaml\"</em>"),
            ("5–15",   "0.5h",  "Small focused change &mdash; read a few files, edit a function, run tests. "
                                "<em>\"Add error handling to the upload endpoint\"</em>"),
            ("15–50",  "0.75h", "Moderate multi-file work &mdash; touch 3-4 files, debug, iterate. "
                                "<em>\"Refactor the auth module to use JWT\"</em>"),
            ("50–150", "1.5h",  "Substantial feature &mdash; design + implement across a module with tests. "
                                "<em>\"Build the report generation pipeline\"</em>"),
            ("150–400","3h",    "Major implementation &mdash; full tool or feature from scratch with iteration. "
                                "<em>\"Ship an executive deck builder from concept to working system\"</em>"),
            ("400+",   "5h",    "System overhaul &mdash; extensive multi-session redesign across many files. "
                                "<em>\"Redesign the entire report layout with branding and ROI\"</em>"),
        ]
    )
    reqs = _signal_tier_table(
        "Premium Requests", "&#9889;",
        "Opus/Sonnet-class model calls that consume your Copilot quota. Each represents a "
        "round of deep AI reasoning. More requests = more back-and-forth collaboration.",
        [
            ("0",      "0h",    "No AI reasoning &mdash; script execution or file operations only"),
            ("1–5",    "0.25h", "Quick consultation &mdash; ask one question, get answer, done. "
                                "<em>\"What does this error mean?\"</em>"),
            ("5–20",   "0.5h",  "Moderate back-and-forth &mdash; debug a problem, explore options. "
                                "<em>\"Why is this test failing? Try a different approach\"</em>"),
            ("20–50",  "1h",    "Extended collaboration &mdash; iterative feature build with refinement. "
                                "<em>\"Build this component, now adjust the styling, now add tests\"</em>"),
            ("50–100", "2h",    "Deep work session &mdash; complex design + implementation + review. "
                                "<em>\"Architect the data pipeline and implement each stage\"</em>"),
            ("100+",   "3h",    "Marathon partnership &mdash; sustained, intensive multi-hour collaboration. "
                                "<em>\"Full system design through to deployment with 162 model calls\"</em>"),
        ]
    )
    lines = _signal_tier_table(
        "Lines of Code", "&#128196;",
        "Net code added to the project. Indicates the volume of deliverable output &mdash; "
        "more lines generally means more development and review work for a human.",
        [
            ("0",      "0h",    "Research or analysis only &mdash; investigation, planning, no code written"),
            ("1–25",   "0.1h",  "Config tweak or small fix &mdash; change a setting, fix a one-liner"),
            ("25–100", "0.25h", "Small feature &mdash; a new function, helper, or template. "
                                "<em>\"Add a utility function with error handling\"</em>"),
            ("100–300","0.5h",  "Moderate development &mdash; a new module or significant feature. "
                                "<em>\"Build the session harvester with event parsing\"</em>"),
            ("300+",   "1h",    "Substantial build &mdash; major feature, new tool, or extensive refactor. "
                                "<em>\"Ship 405 lines of presentation generation code\"</em>"),
        ]
    )
    active = _signal_tier_table(
        "Active Engagement Time", "&#9201;",
        "Time you were actively engaged with Copilot, excluding idle gaps longer than 5 minutes. "
        "Multiplier is <strong>4&times; active time</strong> &mdash; reflecting that a human "
        "without AI would need roughly four times longer to achieve the same result.",
        [
            ("&lt; 5m",    "0.3h",  "Quick task &mdash; one-shot edit, single question"),
            ("5–15m",      "1h",    "Focused task &mdash; fix a bug, write a function"),
            ("15–45m",     "2–3h",  "Working session &mdash; implement and test a feature"),
            ("45m–2h",     "3–8h",  "Deep work &mdash; multi-step design, implementation, and refinement"),
            ("2–6h",       "8–24h", "Extended session &mdash; full feature build across multiple iterations"),
            ("6–12h",      "24–48h","Multi-day collaboration &mdash; system-level design and delivery"),
            ("12h+",       "48h+",  "Marathon project &mdash; comprehensive system build over many days"),
        ]
    )
    return f"""
        <div style="margin-top:16px;padding-top:12px;border-top:1px solid {C['border']}">
          <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                      color:{C['muted']};margin-bottom:4px">What each signal means</div>
          <div style="font-size:10px;color:{C['muted']};line-height:1.5;margin-bottom:4px">
            Each session signal maps to a multiplier representing equivalent human effort. The AI
            reads all signals together and assigns an estimate within the highest applicable range.
            <br><strong style="color:{C['text']}">Reading the table:</strong> find your value in the
            Range column &rarr; the Multiplier shows the hour contribution from that signal alone.
          </div>
          {tools}
          {reqs}
          {lines}
          {active}
        </div>"""


def _date_badge(iso_date: str) -> str:
    if not iso_date:
        return ""
    try:
        from datetime import date as _date
        d = _date.fromisoformat(iso_date)
        label = d.strftime("%-d %b") if hasattr(d, "strftime") else iso_date[5:]
    except Exception:
        label = iso_date[5:]
    return (f'<span style="font-size:10px;font-weight:600;color:{C["accent"]};'
            f'background:{C["accent_lt"]};padding:1px 7px;border-radius:8px;'
            f'margin-right:6px;white-space:nowrap">{label}</span>')


def _narrative_block(goals: list, fallback: str) -> str:
    """Story-style narrative: flowing prose with bold project labels, not a dry numbered list."""
    n = len(goals)
    if not goals:
        return f'<div style="font-size:13px;line-height:1.65;color:{C["text"]}">{fallback}</div>'

    total_h = sum(g.get("human_hours", 0) for g in goals)
    total_tasks = sum(len(g.get("tasks", [])) for g in goals)

    # Opening sentence — frame the impact
    if n == 1:
        g = goals[0]
        label = g.get("label") or g.get("title", "")
        summary = g.get("summary", "")
        date_badge = _date_badge(g.get("date", ""))
        opening = (
            f'<div style="font-size:14px;color:{C["text"]};line-height:1.6;margin-bottom:6px">'
            f'{date_badge}'
            f'<strong style="color:{C["accent"]}">{label}</strong>'
            f'</div>'
            f'<div style="font-size:12px;color:{C["muted"]};line-height:1.6">'
            f'{summary}'
            f'</div>'
        )
    else:
        # Multi-goal: opening paragraph + compact project list
        count_word = {2: "two", 3: "three", 4: "four", 5: "five"}.get(n, str(n))
        opening = (
            f'<div style="font-size:13px;color:{C["text"]};line-height:1.6;margin-bottom:10px">'
            f'Drove <strong>{count_word} projects</strong> forward, '
            f'spanning {total_tasks} distinct tasks and an estimated '
            f'<strong style="color:{C["accent"]}">{_fmt_h(total_h)}</strong> '
            f'of professional effort:</div>'
        )
        items = ""
        for i, g in enumerate(goals):
            label = g.get("label") or g.get("title", f"Goal {i+1}")
            summary = g.get("summary", "")
            date_badge = _date_badge(g.get("date", ""))
            items += (
                f'<div style="display:flex;align-items:baseline;margin-bottom:7px;'
                f'font-size:13px;line-height:1.55">'
                f'<span style="color:{C["accent"]};font-weight:700;min-width:18px;'
                f'margin-right:6px">{i+1}.</span>'
                f'<span>{date_badge}'
                f'<span style="font-weight:700;color:{C["text"]}">{label}:</span>'
                f'&nbsp;<span style="color:{C["muted"]}">{summary}</span></span>'
                f'</div>'
            )
        opening += items

    return opening


def _activity_bar(analysis: dict) -> str:
    """Show pricing comparison (fixed vs market), premium requests, token breakdown."""
    tokens       = analysis.get("tokens", {})
    premium_req  = analysis.get("premium_requests", 0)
    total_api_ms = analysis.get("total_api_ms", 0)
    files_mod    = analysis.get("files_modified", [])

    in_tok  = tokens.get("input", 0)
    out_tok = tokens.get("output", 0)
    cr_tok  = tokens.get("cache_read", 0)
    cc_tok  = tokens.get("cache_creation", 0)
    total_t = tokens.get("total", 0) or 1

    # Market rate: what Anthropic would charge at published API prices
    market_cost = (in_tok * 3.00 + out_tok * 15.00 + cr_tok * 0.30 + cc_tok * 3.75) / 1_000_000

    # Fixed rate: Copilot seat cost, prorated over months in the report range
    seat_cost, n_months = _prorated_seat_cost(analysis)
    raw_savings = market_cost - seat_cost
    savings     = max(0.0, raw_savings)
    savings_x   = round(market_cost / seat_cost) if seat_cost > 0 else 0

    seat_label  = (f"${seat_cost}/mo" if n_months == 1
                   else f"${seat_cost} ({n_months}mo)")

    tok_str      = f"{total_t / 1_000:.0f}K" if total_t < 1_000_000 else f"{total_t / 1_000_000:.1f}M"
    api_time_str = _fmt_ms(total_api_ms)

    # Files modified — show up to 3
    file_names  = [p.replace("\\", "/").split("/")[-1] for p in files_mod[:3]]
    extra_files = len(files_mod) - 3
    files_html  = ""
    if file_names:
        parts = [f'<span style="font-size:10px;color:{C["accent"]};font-weight:500">&#128196; {f}</span>'
                 for f in file_names]
        if extra_files > 0:
            parts.append(f'<span style="font-size:10px;color:{C["muted"]}">+{extra_files} more</span>')
        files_html = (
            '&nbsp;&nbsp;·&nbsp;&nbsp;'
            '<span style="font-size:10px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.7px;color:{C["muted"]};margin-right:6px">Files</span>'
            + "&nbsp;".join(parts)
        )

    active_days = max(1, len(analysis.get("active_dates", ["x"])))
    days_label = f"{active_days} day{'s' if active_days != 1 else ''}"

    # Pricing — compact inline row (not the main story)
    pricing_row = f"""
  <tr>
    <td style="background:{C['card']};padding:0;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);padding:10px 24px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                    color:rgba(255,255,255,0.7)">By the Numbers</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:2px">
          Cost, tokens, and Copilot usage metrics</div>
      </td></tr></table>
    </td>
  </tr>
  <tr>
    <td style="background:{C['subtle']};padding:9px 24px;
               border:1px solid {C['border']}">
      <span style="font-size:10px;font-weight:700;text-transform:uppercase;
                   letter-spacing:0.7px;color:{C['muted']};margin-right:10px">Cost</span>
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">Copilot seat</span> <strong>{seat_label}</strong>
        <span style="font-size:10px;color:{C['muted']}">(Enterprise, fixed)</span>
      </span>
      &nbsp;&nbsp;·&nbsp;&nbsp;
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">Market API rate</span> <strong>~${market_cost:.2f}</strong>
        <span style="font-size:10px;color:{C['muted']}">({tok_str} tokens)</span>
      </span>
      &nbsp;&nbsp;·&nbsp;&nbsp;
      <span style="font-size:11px;color:{C['green']}">
        Saved <strong>~${savings:.2f}</strong>
      </span>
    </td>
  </tr>"""

    return pricing_row + f"""
  <tr>
    <td style="background:{C['subtle']};padding:9px 24px;
               border:1px solid {C['border']};border-top:none">
      <span style="font-size:10px;font-weight:700;text-transform:uppercase;
                   letter-spacing:0.7px;color:{C['muted']};margin-right:10px">Copilot</span>
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">Premium requests</span> <strong>{premium_req}</strong>
        &nbsp;<span style="font-size:10px;color:{C['muted']}">(quota-consuming, Opus-class model)</span>
      </span>
      &nbsp;&nbsp;·&nbsp;&nbsp;
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">AI time</span> <strong>{api_time_str}</strong>
      </span>
      {files_html}
    </td>
  </tr>
  <tr>
    <td style="background:{C['subtle']};padding:5px 24px 9px;
               border:1px solid {C['border']};border-top:none">
      <span style="font-size:10px;font-weight:700;text-transform:uppercase;
                   letter-spacing:0.7px;color:{C['muted']};margin-right:10px">Tokens</span>
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">Input</span> <strong>{in_tok:,}</strong>
        &nbsp;({in_tok / total_t * 100:.0f}%)
      </span>
      &nbsp;&nbsp;·&nbsp;&nbsp;
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">Output</span> <strong>{out_tok:,}</strong>
        &nbsp;({out_tok / total_t * 100:.0f}%)
      </span>
      &nbsp;&nbsp;·&nbsp;&nbsp;
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">Cache hits</span> <strong>{cr_tok:,}</strong>
        &nbsp;({cr_tok / total_t * 100:.0f}%)
      </span>
      &nbsp;&nbsp;·&nbsp;&nbsp;
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">Cache written</span> <strong>{cc_tok:,}</strong>
      </span>
    </td>
  </tr>"""


def _top_skills_for_goal(goal: dict, max_domain: int = 2, max_tech: int = 2) -> tuple:
    from collections import Counter
    domain_counts: Counter = Counter()
    tech_counts:   Counter = Counter()
    for t in goal.get("tasks", []):
        for s in t.get("domain_skills", []):
            domain_counts[s] += 1
        for s in t.get("tech_skills", []):
            tech_counts[s] += 1
    return ([s for s, _ in domain_counts.most_common(max_domain)],
            [s for s, _ in tech_counts.most_common(max_tech)])


def _doc_refs_html(docs: list) -> str:
    if not docs:
        return ""
    shown = docs[:2]
    extra = len(docs) - 2
    parts = [f'<span style="font-size:11px;color:{C["accent"]};font-weight:500">'
             f'&#128196; {d}</span>' for d in shown]
    if extra > 0:
        parts.append(f'<span style="font-size:11px;color:{C["muted"]}">+{extra} more</span>')
    return '<span style="margin-right:8px">' + '</span><span style="margin-right:8px">'.join(parts) + '</span>'


def _goals_summary(goals: list, session_lookup: dict = None, session_metrics: dict = None) -> str:
    if session_lookup is None:
        session_lookup = {}
    if session_metrics is None:
        session_metrics = {}

    VISIBLE = 5
    # Sort by hours descending so highest-impact projects appear first
    sorted_goals = sorted(goals, key=lambda g: g.get("human_hours", 0), reverse=True)
    n_extra      = max(0, len(sorted_goals) - VISIBLE)

    def _goal_row(i: int, g: dict) -> str:
        gid          = f"goal-{i}"
        n            = len(g.get("tasks", []))
        h            = _fmt_h(g.get("human_hours", 0))
        bg           = C["subtle"] if i % 2 == 0 else C["card"]
        top_d, top_t = _top_skills_for_goal(g)
        skill_pills  = _pills(top_d, top_t)
        task_sub     = f'{n} task{"s" if n != 1 else ""}'
        doc_html     = _doc_refs_html(g.get("docs_referenced", []))
        date_badge   = _date_badge(g.get("date", ""))
        tasks        = g.get("tasks", [])
        return f"""
        <tr id="{gid}-hdr" style="background:{bg};cursor:pointer"
            onclick="toggleDetail('{gid}')">
          <td style="padding:10px 10px;border-bottom:1px solid {C['border']};
                     vertical-align:top;width:4%">
            <div style="width:22px;height:22px;background:{C['accent']};border-radius:50%;
                        color:#fff;font-size:11px;font-weight:700;text-align:center;
                        line-height:22px">{i+1}</div>
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid {C['border']};
                     vertical-align:top;width:42%">
            <div style="font-size:12px;font-weight:600;color:{C['text']};line-height:1.35">
              <span id="{gid}-arrow" style="font-size:10px;color:{C['accent']};
                                            margin-right:5px">&#9654;</span>
              {date_badge}{g.get('title', '')}
            </div>
            {f'<div style="margin-top:5px">{doc_html}</div>' if doc_html else ''}
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid {C['border']};
                     vertical-align:middle;width:40%">
            <div>{skill_pills}</div>
            <div style="font-size:10px;color:{C['muted']};margin-top:5px">{task_sub}</div>
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid {C['border']};
                     vertical-align:middle;text-align:right;width:14%">
            <div style="font-size:16px;font-weight:700;color:{C['accent']}">{h}</div>
            <div style="font-size:10px;color:{C['muted']};margin-top:1px">human est.</div>
          </td>
        </tr>
        <tr id="{gid}-tasks" style="display:none">
          <td colspan="4" style="padding:0 8px 12px;background:{C['bg']}">
            {_goal_context_bar(g, session_lookup)}
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border:1px solid {C['border']};border-radius:6px;overflow:hidden">
              <tr style="background:{C['accent_lt']}">
                <td style="width:3px;padding:0"></td>
                <th style="padding:6px 12px;text-align:left;font-size:10px;font-weight:700;
                           color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                           border-bottom:1px solid {C['border']};width:35%">Task &amp; Skills</th>
                <th style="padding:6px 12px;text-align:left;font-size:10px;font-weight:700;
                           color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                           border-bottom:1px solid {C['border']};width:52%">What Got Done</th>
                <th style="padding:6px 12px;text-align:center;font-size:10px;font-weight:700;
                           color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                           border-bottom:1px solid {C['border']};width:13%">Time</th>
              </tr>
              {_task_rows(tasks)}
            </table>
          </td>
        </tr>"""

    rows = ""
    for i, g in enumerate(sorted_goals[:VISIBLE]):
        rows += _goal_row(i, g)

    if n_extra > 0:
        # "Show more" toggle row
        label = f"Show {n_extra} more project{'s' if n_extra != 1 else ''}"
        rows += f"""
        <tr>
          <td colspan="4" style="padding:0;border-bottom:1px solid {C['border']}">
            <button id="goals-show-more" onclick="toggleExtraGoals({n_extra})"
                    style="width:100%;background:{C['subtle']};border:none;border-top:1px solid {C['border']};
                           padding:8px 16px;font-size:11px;font-weight:600;color:{C['accent']};
                           cursor:pointer;text-align:center;font-family:inherit">
              &#9654; {label}
            </button>
          </td>
        </tr>"""
        # Hidden extra goals wrapped in a tbody for easy toggle
        extra_rows = ""
        for i, g in enumerate(sorted_goals[VISIBLE:], start=VISIBLE):
            extra_rows += _goal_row(i, g)
        rows += f'<tbody id="goals-extra" style="display:none">{extra_rows}</tbody>'

    return f'<tbody>{rows}</tbody>'


def _goal_context_bar(g: dict, session_lookup: dict) -> str:
    """Working dir, branch, and GitHub repo link for a goal."""
    project = g.get("project", "")
    sess    = session_lookup.get(project, {})
    if not sess:
        return ""

    path      = sess.get("project_path", "")
    branch    = sess.get("branch", "")
    git_repos = sess.get("git_repos", [])

    parts = []
    if path:
        parts.append(
            f'<span style="font-size:10px;color:{C["muted"]};margin-right:12px">'
            f'&#128193; <code style="font-size:10px;background:{C["bg"]};padding:1px 5px;'
            f'border-radius:3px;color:{C["text"]}">{path}</code></span>'
        )
    if branch:
        parts.append(
            f'<span style="font-size:10px;color:{C["muted"]};margin-right:12px">'
            f'&#9135; <strong>{branch}</strong></span>'
        )
    for repo in git_repos:
        parts.append(
            f'<span style="font-size:10px;color:{C["green"]};font-weight:600;margin-right:10px">'
            f'&#128257; <a href="https://github.com/{repo}" style="color:{C["green"]};'
            f'text-decoration:none">{repo}</a></span>'
        )

    if not parts:
        return ""
    return (f'<div style="padding:5px 24px 6px;background:{C["subtle"]};'
            f'border-bottom:1px solid {C["border"]}">' + "".join(parts) + "</div>")


def _goal_detail_headers(goals: list, session_lookup: dict = None) -> str:
    if session_lookup is None:
        session_lookup = {}
    html = ""
    for i, g in enumerate(goals):
        gid   = f"goal-{i}"
        tasks = g.get("tasks", [])
        n     = len(tasks)
        h     = _fmt_h(g.get("human_hours", 0))

        html += f"""
        <tr id="{gid}-hdr" style="cursor:pointer;background:{C['card']}"
            onclick="toggleDetail('{gid}')">
          <td style="padding:11px 24px;border-bottom:1px solid {C['border']}">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="vertical-align:middle;width:85%">
                  <span id="{gid}-arrow" style="font-size:11px;color:{C['accent']};
                                                 margin-right:6px">&#9654;</span>
                  <span style="font-size:13px;font-weight:600;color:{C['text']}">
                    {g.get('title', '')}
                  </span>
                  <span style="font-size:11px;color:{C['muted']};margin-left:8px">
                    {n} task{'s' if n != 1 else ''}
                  </span>
                </td>
                <td style="text-align:right;vertical-align:middle;width:15%">
                  <span style="font-size:14px;font-weight:700;color:{C['accent']}">{h}</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr id="{gid}-tasks" style="display:none">
          <td style="padding:0 16px 12px;background:{C['bg']}">
            {_goal_context_bar(g, session_lookup)}
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border:1px solid {C['border']};border-radius:6px;overflow:hidden">
              <tr style="background:{C['accent_lt']}">
                <td style="width:3px;padding:0"></td>
                <th style="padding:6px 12px;text-align:left;font-size:10px;font-weight:700;
                           color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                           border-bottom:1px solid {C['border']};width:35%">Task &amp; Skills</th>
                <th style="padding:6px 12px;text-align:left;font-size:10px;font-weight:700;
                           color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                           border-bottom:1px solid {C['border']};width:52%">What Got Done</th>
                <th style="padding:6px 12px;text-align:center;font-size:10px;font-weight:700;
                           color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                           border-bottom:1px solid {C['border']};width:13%">Time</th>
              </tr>
              {_task_rows(tasks)}
            </table>
          </td>
        </tr>"""

    return html


def _task_rows(tasks: list) -> str:
    rows = ""
    for j, t in enumerate(tasks):
        bg     = C["card"] if j % 2 == 0 else C["subtle"]
        skills = _pills(t.get("domain_skills", []), t.get("tech_skills", []))
        h      = _fmt_h(t.get("human_hours", 0))
        rows += f"""
              <tr style="background:{bg}">
                <td style="width:3px;background:{C['accent_lt']};padding:0"></td>
                <td style="padding:10px 12px;border-bottom:1px solid {C['border']};
                           vertical-align:top;width:35%">
                  <div style="font-size:10px;color:{C['muted']};font-weight:600;
                              text-transform:uppercase;letter-spacing:0.4px">Task {j+1}</div>
                  <div style="font-size:12px;font-weight:600;color:{C['text']};
                              margin-top:2px;line-height:1.3">{t.get('title', '')}</div>
                  <div style="margin-top:5px">{skills}</div>
                </td>
                <td style="padding:10px 12px;border-bottom:1px solid {C['border']};
                           vertical-align:top;width:52%">
                  <div style="font-size:12px;color:{C['text']};line-height:1.55">
                    {t.get('what_got_done', '')}
                  </div>
                </td>
                <td style="padding:10px 12px;border-bottom:1px solid {C['border']};
                           vertical-align:middle;text-align:center;width:13%">
                  <div style="font-size:15px;font-weight:700;color:{C['accent']}">{h}</div>
                  <div style="font-size:9px;color:{C['muted']};text-transform:uppercase;
                              letter-spacing:0.4px;margin-top:1px">human</div>
                </td>
              </tr>"""
    return rows


REPO_URL = "https://github.com/microsoft/mycopilotworks"


def _share_bar(target_date: str, goals: list, headline: str, total_human_h: float) -> str:
    """Summary/share hint strip injected just below the report header."""
    import json as _json

    n_goals     = len(goals)
    total_tasks = sum(len(g.get("tasks", [])) for g in goals)
    goal_lines  = "\n".join(f"  \u2022 {g.get('label') or g.get('title', '')}" for g in goals)
    signature   = f"\n\n\u2014\n\U0001f4ca Get your own GitHub Copilot Impact Report\n{REPO_URL}"

    share_text = (
        f"{headline}\n\n"
        f"This period: {n_goals} project{'s' if n_goals != 1 else ''} \u00b7 "
        f"{total_tasks} tasks \u00b7 {_fmt_h(total_human_h)} professional effort equivalent\n\n"
        f"Key deliverables:\n{goal_lines}"
        f"{signature}"
    )

    email_subject = f"What I Did with GitHub Copilot \u2014 {target_date}"
    js_subject    = _json.dumps(email_subject)
    js_body       = _json.dumps(share_text)
    js_teams      = _json.dumps(share_text)

    return f"""
  <tr>
    <td style="background:#ffffff;padding:7px 24px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']};
               border-bottom:1px solid {C['border']}">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">
        <span style="font-size:10px;color:{C['muted']}">
          Run with <code style="font-size:10px;background:#f6f8fa;padding:1px 4px;border-radius:3px">--email</code> to send this report via Outlook
        </span>
        <div style="display:flex;align-items:center;gap:8px;margin-left:auto">
          <button type="button"
                  style="font-size:11px;padding:4px 10px;border-radius:4px;border:1px solid {C['accent']};
                         background:{C['accent']};color:#ffffff;cursor:pointer;white-space:nowrap"
                  onclick="shareViaEmail({js_subject}, {js_body})">
            Share via Email
          </button>
          <button id="teams-share-btn" type="button"
                  style="font-size:11px;padding:4px 10px;border-radius:4px;border:1px solid #6264a7;
                         background:#6264a7;color:#ffffff;cursor:pointer;white-space:nowrap"
                  onclick="shareViaTeams({js_teams})">
            Share via Teams
          </button>
        </div>
      </div>
    </td>
  </tr>"""


def generate_html(target_date: str, analysis: dict, sessions: list) -> str:
    goals      = analysis.get("goals", [])
    narrative  = analysis.get("day_narrative", "")
    headline   = analysis.get("headline", f"Daily Report — {target_date}")
    focus      = analysis.get("primary_focus", "")
    n_sessions = analysis.get("sessions_count", len(sessions))
    projects   = sorted({s["project"] for s in sessions})

    total_human_h = sum(g.get("human_hours", 0) for g in goals)
    total_tasks   = sum(len(g.get("tasks", [])) for g in goals)

    project_pills = "".join(
        f'<span style="background:rgba(255,255,255,0.18);color:#fff;padding:2px 10px;'
        f'border-radius:4px;font-size:11px;margin-right:5px;display:inline-block;'
        f'margin-bottom:3px;border:1px solid rgba(255,255,255,0.3)">{p}</span>'
        for p in projects
    )

    totals_row = f"""
        <tr style="background:{C['accent_lt']}">
          <td style="padding:10px 16px;border-top:2px solid {C['border']}"></td>
          <td style="padding:10px 16px;border-top:2px solid {C['border']};
                     font-size:12px;font-weight:700;color:{C['accent']}">
            {len(goals)} project{'s' if len(goals) != 1 else ''} &nbsp;·&nbsp; {total_tasks} tasks total
          </td>
          <td style="padding:10px 16px;border-top:2px solid {C['border']}"></td>
          <td style="padding:10px 16px;border-top:2px solid {C['border']};
                     text-align:right;font-size:18px;font-weight:700;color:{C['accent']}">
            {_fmt_h(total_human_h)}
          </td>
        </tr>"""

    session_lookup = {}
    for s in sessions:
        session_lookup[s["project"]] = s
        last = s["project"].replace("\\", "/").split("/")[-1]
        session_lookup.setdefault(last, s)

    js = """
<script>
function toggleDetail(id) {
  var tasks = document.getElementById(id + '-tasks');
  var arrow = document.getElementById(id + '-arrow');
  var hdr   = document.getElementById(id + '-hdr');
  if (!tasks) return;
  var openDisplay = tasks.tagName.toLowerCase() === 'tr' ? 'table-row' : 'block';
  var open = tasks.style.display === openDisplay;
  tasks.style.display  = open ? 'none'      : openDisplay;
  hdr.style.background = open ? ''          : '#e8f2fb';
  if (arrow) arrow.innerHTML = open ? '&#9654;' : '&#9660;';
}
function toggleFormula(id) {
  var el    = document.getElementById(id);
  var arrow = document.getElementById(id + '-arrow');
  if (!el) return;
  var open = el.style.display !== 'none';
  el.style.display = open ? 'none' : 'block';
  if (arrow) arrow.innerHTML = open ? '&#9654; formula' : '&#9660; formula';
}
function toggleFormulaCol() {
  var btn  = document.getElementById('formula-col-toggle');
  var cols = document.querySelectorAll('.formula-col');
  var hide = btn.getAttribute('data-open') === '1';
  cols.forEach(function(el) { el.style.display = hide ? 'none' : ''; });
  btn.setAttribute('data-open', hide ? '0' : '1');
  btn.innerHTML = hide ? '&#9654; Show formula column' : '&#9660; Hide formula column';
}
function shareViaEmail(subject, body) {
  var a = document.createElement('a');
  a.href = 'mailto:?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(function() { document.body.removeChild(a); }, 200);
}
function shareViaTeams(message) {
  var btn = document.getElementById('teams-share-btn');
  var orig = btn.innerHTML;
  function onCopied() {
    btn.innerHTML = '&#10003; Copied &mdash; paste into Teams';
    btn.style.background = '#1a7f37';
    btn.style.borderColor = '#1a7f37';
    setTimeout(function() { btn.innerHTML = orig; btn.style.background = '#6264a7'; btn.style.borderColor = '#6264a7'; }, 3000);
  }
  function onFailed() {
    window.prompt('Copy this and paste into Teams:', message);
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(message).then(onCopied).catch(onFailed);
  } else {
    onFailed();
  }
}
function toggleExtraGoals(count) {
  var extra = document.getElementById('goals-extra');
  var btn   = document.getElementById('goals-show-more');
  if (!extra) return;
  var showing = extra.style.display !== 'none';
  extra.style.display = showing ? 'none' : '';
  btn.innerHTML = showing
    ? '&#9654; Show ' + count + ' more project' + (count === 1 ? '' : 's')
    : '&#9660; Show fewer';
}
window.onload = function() {
  var hint = document.getElementById('expand-hint');
  if (hint) hint.style.display = 'block';
};
</script>"""

    heuristic_dates = analysis.get("heuristic_dates", [])
    active_dates    = analysis.get("active_dates", [])
    heuristic_banner = ""
    if heuristic_dates:
        n_h = len(heuristic_dates)
        n_t = len(active_dates) if active_dates else n_h
        if n_h == n_t:
            scope = "All days in this report"
        else:
            scope = f"{n_h} of {n_t} days"
        heuristic_banner = f"""
  <tr>
    <td style="background:{C['orange_lt']};padding:12px 24px;
               border-left:2px solid {C['orange']};border-right:1px solid {C['border']}">
      <div style="font-size:12px;font-weight:700;color:{C['orange']};margin-bottom:4px">
        &#9888; Approximate Estimates</div>
      <div style="font-size:11px;color:{C['text']};line-height:1.5">
        {scope} used <strong>heuristic fallback</strong> because the AI analysis API was unavailable.
        Estimates may be less accurate. Re-run with <code style="font-size:10px;background:#fff;
        padding:1px 5px;border-radius:3px">whatidid --refresh</code> when the API is available
        for precise results.
      </div>
    </td>
  </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>What I Did (Copilot) — {target_date}</title>
{js}
</head>
<body style="margin:0;padding:0;background:{C['bg']};
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;color:{C['text']}">

<table width="100%" cellpadding="0" cellspacing="0" style="background:{C['bg']};padding:24px 16px">
<tr><td align="center">
<table width="700" cellpadding="0" cellspacing="0" style="max-width:700px;width:100%">

  <!-- HEADER -->
  <tr>
    <td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);border-radius:9px 9px 0 0;padding:22px 24px">
      <div style="font-size:10px;color:rgba(255,255,255,0.6);letter-spacing:1.2px;
                  text-transform:uppercase;margin-bottom:4px">
        {target_date} &nbsp;·&nbsp; GitHub Copilot Impact Report
      </div>
      <div style="font-size:20px;font-weight:700;color:#fff;line-height:1.3"><svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" style="vertical-align:middle;margin-right:10px"><path fill="white" d="M23.922 16.992c-.861 1.495-5.859 5.023-11.922 5.023-6.063 0-11.061-3.528-11.922-5.023A.641.641 0 0 1 0 16.736v-2.869a.841.841 0 0 1 .053-.22c.372-.935 1.347-2.292 2.605-2.656.167-.429.414-1.055.644-1.517a10.195 10.195 0 0 1-.052-1.086c0-1.331.282-2.499 1.132-3.368.397-.406.89-.717 1.474-.952 1.399-1.136 3.392-2.093 6.122-2.093 2.731 0 4.767.957 6.166 2.093.584.235 1.077.546 1.474.952.85.869 1.132 2.037 1.132 3.368 0 .368-.014.733-.052 1.086.23.462.477 1.088.644 1.517 1.258.364 2.233 1.721 2.605 2.656a.832.832 0 0 1 .053.22v2.869a.641.641 0 0 1-.078.256ZM12.172 11h-.344a4.323 4.323 0 0 1-.355.508C10.703 12.455 9.555 13 7.965 13c-1.725 0-2.989-.359-3.782-1.259a2.005 2.005 0 0 1-.085-.104L4 11.741v6.585c1.435.779 4.514 2.179 8 2.179 3.486 0 6.565-1.4 8-2.179v-6.585l-.098-.104s-.033.045-.085.104c-.793.9-2.057 1.259-3.782 1.259-1.59 0-2.738-.545-3.508-1.492a4.323 4.323 0 0 1-.355-.508h-.016.016Zm.641-2.935c.136 1.057.403 1.913.878 2.497.442.544 1.134.938 2.344.938 1.573 0 2.292-.337 2.657-.751.384-.435.558-1.15.558-2.361 0-1.14-.243-1.847-.705-2.319-.477-.488-1.319-.862-2.824-1.025-1.487-.161-2.192.138-2.533.529-.269.307-.437.808-.438 1.578v.021c0 .265.021.562.063.893Zm-1.626 0c.042-.331.063-.628.063-.894v-.02c-.001-.77-.169-1.271-.438-1.578-.341-.391-1.046-.69-2.533-.529-1.505.163-2.347.537-2.824 1.025-.462.472-.705 1.179-.705 2.319 0 1.211.175 1.926.558 2.361.365.414 1.084.751 2.657.751 1.21 0 1.902-.394 2.344-.938.475-.584.742-1.44.878-2.497Z"/><path fill="white" d="M14.5 14.25a1 1 0 0 1 1 1v2a1 1 0 0 1-2 0v-2a1 1 0 0 1 1-1Zm-5 0a1 1 0 0 1 1 1v2a1 1 0 0 1-2 0v-2a1 1 0 0 1 1-1Z"/></svg>{headline}</div>
      {f'<div style="margin-top:8px"><span style="font-size:9px;font-weight:700;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:1px;margin-right:8px">Projects</span>{project_pills}</div>' if projects else ''}
    </td>
  </tr>

  {_share_bar(target_date, goals, headline, total_human_h)}

  {heuristic_banner}

  <!-- ACT 1: THE STORY -->
  <!-- NARRATIVE -->
  <tr>
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      {_narrative_block(goals, narrative)}
    </td>
  </tr>

  {_kpi_section(goals, analysis, n_sessions,
              sum(s.get("git_ops", []).count("pr") for s in sessions),
              sum(s.get("git_ops", []).count("commit") for s in sessions))}

  {_leverage_banner(goals, analysis)}

  <!-- 1. WHAT GOT ACCOMPLISHED -->
  <tr>
    <td style="background:{C['card']};padding:0;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);padding:10px 24px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                    color:rgba(255,255,255,0.7)">What Got Accomplished</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:2px">
          Detailed project breakdown with task-level evidence</div>
      </td></tr></table>
      <div style="padding:14px 24px 16px">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {C['border']};border-radius:7px;overflow:hidden">
        {_goals_summary(goals, session_lookup, analysis.get("session_metrics", {}))}
        <tbody>{totals_row}</tbody>
      </table>
      <div id="expand-hint" style="display:none;font-size:11px;color:{C['muted']};
                                    text-align:right;margin-top:6px">
        Click a project to see task details &#9656;
      </div>
      </div>
    </td>
  </tr>

  <!-- 2. WHAT GOT PRODUCED (deliverables + skills) -->
  {_what_i_work_on(goals, sessions)}

  {_skills_mobilized(goals)}

  <!-- 3. HOW I WORKED WITH COPILOT (intent) -->
  {_collaboration_intent(sessions, goals)}

  <!-- 4. WHEN I WORKED WITH COPILOT -->
  {_work_pattern(sessions)}

  <!-- 5. BY THE NUMBERS -->
  {_activity_bar(analysis)}

  <!-- 6. ESTIMATION EVIDENCE (collapsible) -->
  <tr>
    <td style="background:{C['card']};padding:0 24px 12px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div id="evidence-hdr" style="cursor:pointer;padding:10px 0 6px"
           onclick="toggleDetail('evidence')">
        <span id="evidence-arrow" style="font-size:10px;color:{C['accent']};margin-right:5px">&#9654;</span>
        <span style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                     color:{C['muted']}">Estimation Evidence &mdash; per-project session signals</span>
      </div>
      <div id="evidence-tasks" style="display:none">
        {_estimation_waterfall_inner(goals, analysis)}
        {_signal_guide()}
      </div>
    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td bgcolor="#1f2328" style="background:{C['text']};border-radius:0 0 9px 9px;padding:16px 24px;
               text-align:center">
      <div style="font-size:13px;font-weight:700;color:#ffffff;margin-bottom:4px">
        Want your own GitHub Copilot Impact Report?
      </div>
      <div style="font-size:11px;color:rgba(255,255,255,0.55);margin-bottom:8px">
        One command. Every session. A complete story of your AI-assisted work.
      </div>
      <a href="https://github.com/microsoft/mycopilotworks"
         style="display:inline-block;background:{C['accent']};color:#ffffff;
                font-size:11px;font-weight:700;text-decoration:none;
                padding:6px 16px;border-radius:6px;letter-spacing:0.3px">
        &#128279; github.com/microsoft/mycopilotworks
      </a>
      <div style="font-size:10px;color:rgba(255,255,255,0.25);margin-top:10px">
        {target_date} &nbsp;·&nbsp; GitHub Copilot Impact Report
      </div>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""
