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
    """Return (seat_cost, n_months) prorated over the report's time span.

    For short reports (≤31 days), always use 1 month regardless of calendar
    month boundaries — a 7-day export shouldn't show 2 months of seat cost
    just because it crosses a month boundary.
    """
    dates = analysis.get("active_dates", [])
    if not dates:
        return SEAT_COST_PER_MONTH, 1

    # Parse dates and determine the span
    parsed = []
    for d in dates:
        try:
            parsed.append(datetime.strptime(str(d)[:10], "%Y-%m-%d"))
        except ValueError:
            pass
    if not parsed:
        return SEAT_COST_PER_MONTH, 1

    span_days = (max(parsed) - min(parsed)).days + 1
    if span_days <= 31:
        return SEAT_COST_PER_MONTH, 1

    # For longer reports, prorate by distinct calendar months
    months = {(dt.year, dt.month) for dt in parsed}
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
    lines_added     = analysis.get("lines_added", 0)
    lines_removed   = analysis.get("lines_removed", 0)
    active_days     = max(1, len(analysis.get("active_dates", ["x"])))

    # Total active engagement time across all sessions.
    _seen_metric_keys: set = set()
    total_active_min = 0
    for _key, _m in analysis.get("session_metrics", {}).items():
        if isinstance(_m, str):
            continue
        if "|" in _key:
            _date, _proj = _key.split("|", 1)
            _canon_key = (_date, _proj.replace("\\", "/").split("/")[-1].lower().strip().replace(" ", "-"))
        else:
            _canon_key = (_key,)
        if _canon_key in _seen_metric_keys:
            continue
        _seen_metric_keys.add(_canon_key)
        total_active_min += _m.get("active_minutes", 0)

    # Active time display
    if total_active_min >= 60:
        active_val = f"{total_active_min / 60:.1f}h"
    else:
        active_val = f"{total_active_min:.0f}m"
    active_sub = f"{active_days} active day{'s' if active_days != 1 else ''}"

    # Speed multiplier
    if total_active_min > 0:
        speed_x = total_human_h / (total_active_min / 60)
        speed_val = f"{speed_x:.1f}×"
    else:
        speed_val = "—"

    # Human effort
    h_str = _fmt_h(total_human_h)
    effort_sub = (f'<a href="#evidence-hdr" style="color:{C["accent"]};'
                  f'text-decoration:none;font-size:9px" onclick="toggleDetail(\'evidence\');'
                  f'return false;">see evidence &#9656;</a>')

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
          {_kpi_card(h_str, "Human Effort<br>Equivalent", effort_sub)}
          {_kpi_card(active_val, "Active<br>Time", active_sub)}
          {_kpi_card(speed_val, "Speed<br>Multiplier", "vs. unassisted expert")}
          {_kpi_card(code_val, "Lines of Code<br>Added", code_sub)}
          {_kpi_card(pr_commit_val, "PRs<br>Merged", pr_commit_sub)}
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



def _what_i_work_on(goals: list, sessions: list, project_label_map: dict = None) -> str:
    """Section: 'What Got Produced' — deliverables files categorized."""
    import re

    if project_label_map is None:
        project_label_map = {}

    file_categories = {
        "Scripts":        {"icon": "&#128187;", "extensions": {".py", ".js", ".ts", ".sh", ".ps1"}},
        "Reports":        {"icon": "&#128202;", "extensions": {".html"}},
        "Documents":      {"icon": "&#128196;", "extensions": {".md", ".txt", ".docx", ".pdf"}},
        "Data & Config":  {"icon": "&#9881;",   "extensions": {".json", ".yaml", ".yml", ".toml", ".env", ".gitignore", ".cfg"}},
        "Presentations":  {"icon": "&#128209;", "extensions": {".pptx", ".ppt"}},
    }

    all_files: dict = {}
    for s in sessions:
        raw_proj = s.get("project", "")
        proj = project_label_map.get(raw_proj, raw_proj)
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


def _collaboration_intent(sessions: list, project_label_map: dict = None) -> str:
    """Section: 'How I Collaborated' — card grid showing how Copilot contributed."""
    from harvest import compute_active_time_quality, _QUALITY_COLORS

    if project_label_map is None:
        project_label_map = {}

    modes = compute_active_time_quality(sessions)
    total = sum(modes.values())
    if total < 1:
        return ""

    MODE_META = {
        "Designing":         {"icon": "&#127912;", "desc": "Design, strategy, architecture",       "high_value": True},
        "Analyzing":         {"icon": "&#128202;", "desc": "Data analysis, metrics, interpretation", "high_value": True},
        "Reviewing":         {"icon": "&#128269;", "desc": "Code review, auditing, feedback",       "high_value": True},
        "Researching":       {"icon": "&#128300;", "desc": "Exploring options, investigating",      "high_value": True},
        "Learning":          {"icon": "&#127891;", "desc": "Understanding concepts, knowledge transfer", "high_value": True},
        "Building":          {"icon": "&#128679;", "desc": "Writing code, generating files",        "high_value": True},
        "Refining":          {"icon": "&#128260;", "desc": "Iterating, polishing, improving",       "high_value": True},
        "Course-correcting": {"icon": "&#128295;", "desc": "Errors, retries, course-correcting AI", "high_value": False},
        "Delegating":        {"icon": "&#9889;",   "desc": "Git ops, config, installs, routine",    "high_value": False},
    }

    sorted_modes = sorted(modes.items(), key=lambda x: -x[1])

    # Narrative stats — high-value vs low-value based on mode metadata
    low_value_mins = sum(
        mins for mode, mins in sorted_modes
        if not MODE_META.get(mode, {}).get("high_value", True)
    )
    high_value_raw = (total - low_value_mins) / total * 100
    course_raw = modes.get("Course-correcting", 0) / total * 100
    delegating_raw = modes.get("Delegating", 0) / total * 100
    high_value_pct = max(0, min(100, round(high_value_raw)))
    course_pct = round(course_raw)
    delegating_pct = round(delegating_raw)
    total_str = f"{total:.0f}m" if total < 60 else f"{total / 60:.1f}h"
    n_modes = len([m for m in sorted_modes if m[1] >= 0.1])

    # Headline insight
    headline = (f"{high_value_pct}% of your collaboration was high-value work "
                f"&mdash; designing, researching, building, and refining.")
    sub_parts = []
    if delegating_pct > 0:
        sub_parts.append(f"Copilot automated {delegating_pct}% of routine tasks")
    if course_pct > 0:
        sub_parts.append(f"{course_pct}% was spent course-correcting AI output")
    subtitle = " &middot; ".join(sub_parts) if sub_parts else ""

    # Card grid — build explicit <tr> rows to avoid mismatched nesting.
    visible = [(mode, mins) for mode, mins in sorted_modes if mins >= 0.1]
    grid_rows = []
    for pair_start in range(0, len(visible), 2):
        pair = visible[pair_start:pair_start + 2]
        cells = ""
        for mode, mins in pair:
            pct = mins / total * 100
            meta = MODE_META.get(mode, {"icon": "", "desc": ""})
            color = _QUALITY_COLORS.get(mode, C["muted"])
            mins_str = f"{mins:.0f}m" if mins < 60 else f"{mins / 60:.1f}h"
            bar_width = max(pct, 4)
            cells += f"""
          <td style="padding:5px;width:50%;vertical-align:top">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border:1px solid {C['border']};border-left:4px solid {color};
                          border-radius:6px;overflow:hidden">
              <tr>
                <td style="padding:10px 12px">
                  <div style="display:flex;align-items:baseline;margin-bottom:6px">
                    <span style="font-size:18px;margin-right:6px">{meta['icon']}</span>
                    <span style="font-size:12px;font-weight:700;color:{C['text']}">{mode}</span>
                    <span style="font-size:16px;font-weight:800;color:{color};margin-left:auto">
                      {pct:.0f}%</span>
                  </div>
                  <div style="background:{C['bg']};border-radius:3px;height:8px;margin-bottom:6px;
                              overflow:hidden">
                    <div style="width:{bar_width:.0f}%;background:{color};height:100%;
                                border-radius:3px"></div>
                  </div>
                  <div style="font-size:11px;color:{C['muted']};line-height:1.3">
                    {meta['desc']} &middot; <strong style="color:{C['text']}">{mins_str}</strong></div>
                </td>
              </tr>
            </table>
          </td>"""
        # Pad last row if it has only one card
        if len(pair) == 1:
            cells += '<td style="padding:5px;width:50%"></td>'
        grid_rows.append(f"<tr>{cells}</tr>")

    grid_html = "\n          ".join(grid_rows)

    return f"""
  <tr>
    <td style="background:{C['card']};padding:0;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);padding:10px 24px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                    color:rgba(255,255,255,0.7)">How I Collaborated</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:2px">
          The different types of work Copilot handled for you</div>
      </td></tr></table>
      <div style="padding:16px 24px 18px">
        <div style="font-size:14px;font-weight:700;color:{C['text']};margin-bottom:4px;line-height:1.4">
          {headline}</div>
        <div style="font-size:11px;color:{C['muted']};margin-bottom:16px">
          {total_str} of active collaboration across {n_modes} modes &middot; {subtitle}</div>
        <table width="100%" cellpadding="0" cellspacing="0">
          {grid_html}
        </table>
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

import math as _math


def _turns_h(n: int) -> float:
    """Substantive conversation turns → hours (log curve, OLS-calibrated).
    turns_h = max(0, −0.15 + 0.67 × ln(turns + 1))"""
    if n <= 0:
        return 0.0
    return max(0.0, -0.15 + 0.67 * _math.log(n + 1))


def _lines_h(logic_lines: int) -> float:
    """Logic code lines → hours (log₂ curve).
    lines_h = 0.40 × log₂(lines_logic ÷ 100 + 1)
    Only .py/.ts/.go/.rs/.java/.sh etc. — not HTML/CSS/JSON/MD."""
    if logic_lines <= 0:
        return 0.0
    return 0.40 * _math.log2(logic_lines / 100 + 1)


def _reads_h(read_calls: int) -> float:
    """File reads + search/grep/glob calls → hours (log₂ curve).
    reads_h = 0.10 × log₂(read_calls + 1)"""
    if read_calls <= 0:
        return 0.0
    return 0.10 * _math.log2(read_calls + 1)


def _tools_h(n: int) -> float:
    """Total tool invocations → hours (log₂ curve, low coefficient).
    Captures execution work (browser, commands, image processing) not already
    counted by reads_h. Essential for non-coding tasks where lines_h ≈ 0.
    tools_h = 0.07 × log₂(tool_invocations + 1)"""
    if n <= 0:
        return 0.0
    return 0.07 * _math.log2(n + 1)


def _reqs_h(n: int) -> float:
    """Premium requests → hours (log curve, fallback when turns unavailable).
    Premium requests include automated completions so the coefficient is lower
    than turns_h. Used ONLY when substantive_turns == 0.
    reqs_h = max(0, −0.10 + 0.45 × ln(reqs + 1))"""
    if n <= 0:
        return 0.0
    return max(0.0, -0.10 + 0.45 * _math.log(n + 1))


def compute_formula_estimate(metrics: dict) -> dict:
    """Deterministic effort estimate — additive log formula.

    Formula: total = interaction_h + lines_h + reads_h + tools_h
      interaction_h = turns_h when turns > 0, else reqs_h (fallback)
      turns_h = max(0, −0.15 + 0.67 × ln(turns + 1))
      reqs_h  = max(0, −0.10 + 0.45 × ln(reqs + 1))     [fallback]
      lines_h = 0.40 × log₂(lines_logic ÷ 100 + 1)
      reads_h = 0.10 × log₂(read_calls + 1)
      tools_h = 0.07 × log₂(tool_invocations + 1)

    tools_h ensures non-coding work (image analysis, doc synthesis, browser
    tasks) gets meaningful credit even when lines_h ≈ 0.
    reqs_h is a fallback for older sessions without conversation turn data.
    """
    turns = metrics.get("substantive_turns")
    if turns is None:
        turns = metrics.get("conversation_turns", 0)
    reqs        = metrics.get("premium_requests", 0)
    logic_lines = metrics.get("lines_logic")
    if logic_lines is None:
        logic_lines = metrics.get("lines_added", 0)
    read_calls  = metrics.get("reads", 0) + metrics.get("searches", 0)
    tools       = metrics.get("tool_invocations", 0)

    th = _turns_h(turns)
    rqh = _reqs_h(reqs)
    lh = _lines_h(logic_lines)
    rh = _reads_h(read_calls)
    tlh = _tools_h(tools)

    # Use turns as the interaction signal; fall back to premium requests
    # for older sessions that lack conversation turn data.
    interaction_h = th if turns > 0 else rqh

    # For multi-day merged goals, use pre-computed per-day sums so that
    # the component breakdown is consistent with the displayed total.
    per_day_total = metrics.get("_per_day_formula_total")
    if per_day_total is not None:
        return {
            "turns_h":       metrics.get("_per_day_turns_h", th),
            "reqs_h":        rqh,
            "lines_h":       metrics.get("_per_day_lines_h", lh),
            "reads_h":       metrics.get("_per_day_reads_h", rh),
            "tools_h":       tlh,
            "interaction_h": interaction_h,
            "total":         per_day_total,
        }

    total = interaction_h + lh + rh + tlh
    total = max(total, 0.25)  # floor at 15 min

    return {
        "turns_h":       th,
        "reqs_h":        rqh,
        "lines_h":       lh,
        "reads_h":       rh,
        "tools_h":       tlh,
        "interaction_h": interaction_h,
        "total":         round(total * 4) / 4,  # nearest 0.25h
    }


def _estimation_waterfall_inner(goals: list, analysis: dict) -> str:
    """Evidence table showing raw signals, formula components, and AI estimate."""
    session_metrics = analysis.get("session_metrics", {})
    if not goals:
        return ""

    VISIBLE = 5
    total_h = sum(g.get("human_hours", 0) for g in goals)
    total_formula_h = 0.0

    rows = ""
    for i, g in enumerate(goals):
        bg = C["subtle"] if i % 2 == 0 else C["card"]
        project = g.get("project", "")
        metrics = _resolve_metrics(project, session_metrics, g.get("date", ""))
        fe = compute_formula_estimate(metrics)
        total_formula_h += fe["total"]

        turns = metrics.get("substantive_turns")
        if turns is None:
            turns = metrics.get("conversation_turns", 0)
        logic_lines = metrics.get("lines_logic")
        if logic_lines is None:
            logic_lines = metrics.get("lines_added", 0)
        bp_lines    = metrics.get("lines_boilerplate", 0)
        read_calls  = metrics.get("reads", 0) + metrics.get("searches", 0)
        tools       = metrics.get("tool_invocations", 0)
        active      = metrics.get("active_minutes", 0)
        active_str  = f"{active:.0f}m" if active else "&mdash;"
        ai_h        = _fmt_h(g.get("human_hours", 0))
        formula_h   = _fmt_h(fe["total"])

        # Formula sub-row: show which interaction signal was used
        int_label = f"turns {_fmt_h(fe['turns_h'])}" if turns > 0 else f"reqs {_fmt_h(fe['reqs_h'])}"
        formula_parts = f"{int_label} + lines {_fmt_h(fe['lines_h'])} + reads {_fmt_h(fe['reads_h'])} + tools {_fmt_h(fe['tools_h'])}"

        # Lines display: logic lines prominent, boilerplate in grey
        if logic_lines or bp_lines:
            lines_display = f'+{logic_lines}'
            if bp_lines:
                lines_display += f'<span style="color:{C["muted"]};font-size:9px"> +{bp_lines}bp</span>'
        else:
            lines_display = "&mdash;"

        title = g.get("label") or g.get("title", "")
        if len(title) > 40:
            title = title[:37] + "..."

        # Insert see-more toggle row for >5 projects
        if i == VISIBLE and len(goals) > VISIBLE:
            n_extra = len(goals) - VISIBLE
            rows += f"""
        <tr id="evidence-more-toggle" style="cursor:pointer;background:{C['accent_lt']}"
            onclick="var rows=document.getElementsByClassName('evidence-extra-row');
                     var show=rows.length && rows[0].style.display==='none';
                     for(var j=0;j<rows.length;j++){{rows[j].style.display=show?'':'none';}}
                     this.style.display='none';">
          <td colspan="8" style="padding:6px 10px;text-align:center;font-size:11px;
                     font-weight:600;color:{C['accent']}">
            &#9660; Show {n_extra} more project{'s' if n_extra != 1 else ''}</td>
        </tr>"""

        extra = len(goals) > VISIBLE and i >= VISIBLE
        extra_attrs = f' class="evidence-extra-row" style="display:none;background:{bg}"' if extra else f' style="background:{bg}"'

        # Row 1: raw signal values
        rows += f"""
        <tr{extra_attrs}>
          <td style="padding:6px 8px;border-bottom:1px solid {C['border']};vertical-align:top"
              rowspan="2">
            <div style="font-size:11px;font-weight:600;color:{C['text']};line-height:1.3">{title}</div>
          </td>
          <td style="padding:4px 5px;font-size:11px;color:{C['text']};text-align:center;
                     font-weight:600">{turns}</td>
          <td style="padding:4px 5px;font-size:11px;color:{C['text']};text-align:center;
                     font-weight:600">{lines_display}</td>
          <td style="padding:4px 5px;font-size:11px;color:{C['text']};text-align:center;
                     font-weight:600">{read_calls}</td>
          <td style="padding:4px 5px;font-size:11px;color:{C['text']};text-align:center;
                     font-weight:600">{tools}</td>
          <td style="padding:4px 5px;font-size:11px;color:{C['muted']};text-align:center">{active_str}</td>
          <td class="formula-col" style="padding:4px 5px;text-align:center;vertical-align:middle;display:none" rowspan="2">
            <div style="font-size:14px;font-weight:700;color:{C['accent']}">{formula_h}</div>
            <div style="font-size:8px;color:{C['muted']};text-transform:uppercase;margin-top:1px">formula</div>
          </td>
          <td style="padding:4px 5px;text-align:center;vertical-align:middle" rowspan="2">
            <div style="font-size:14px;font-weight:700;color:{C['green']}">{ai_h}</div>
            <div style="font-size:8px;color:{C['muted']};text-transform:uppercase;margin-top:1px">AI est.</div>
          </td>
        </tr>
        <tr{extra_attrs}>
          <td colspan="5" style="padding:2px 5px 6px;text-align:center;border-bottom:1px solid {C['border']};
                     font-size:9px;color:{C['muted']}">
            {formula_parts}</td>
        </tr>"""

    # Total row
    rows += f"""
        <tr style="background:{C['accent_lt']}">
          <td style="padding:8px 8px;border-top:2px solid {C['border']};
                     font-size:11px;font-weight:700;color:{C['accent']};text-align:right" colspan="6">
            Total</td>
          <td class="formula-col" style="padding:8px 5px;border-top:2px solid {C['border']};text-align:center;display:none">
            <div style="font-size:16px;font-weight:700;color:{C['accent']}">{_fmt_h(total_formula_h)}</div>
          </td>
          <td style="padding:8px 5px;border-top:2px solid {C['border']};text-align:center">
            <div style="font-size:16px;font-weight:700;color:{C['green']}">{_fmt_h(total_h)}</div>
          </td>
        </tr>"""

    # Column headers
    th_style = (f"padding:6px 5px;text-align:center;font-size:8px;font-weight:700;"
                f"color:{C['accent']};text-transform:uppercase;letter-spacing:0.4px;"
                f"border-bottom:1px solid {C['border']}")
    th_muted = th_style.replace(f"color:{C['accent']}", f"color:{C['muted']}")

    return f"""
      <div style="font-size:11px;color:{C['text']};margin-bottom:14px;line-height:1.7">
        <strong>Why we lead with AI estimation:</strong>
        The AI reads your full session transcript &mdash; every instruction, every tool action,
        every code change &mdash; and understands <em>what</em> was accomplished, not just how many
        actions were taken. It distinguishes a 200-line boilerplate scaffold from a 50-line
        algorithm that required deep design thinking, and it recognises that &ldquo;commit and push&rdquo;
        is 0.25h regardless of how many tool calls it triggered.
        This contextual understanding produces more accurate estimates than counting actions alone.
        <br><span style="font-size:10px;color:{C['muted']}">
        Calibrated against peer-reviewed research &mdash;
        <a href="https://github.com/microsoft/What-I-Did-Copilot/blob/main/docs/effort-estimation-methodology.md"
           style="color:{C['accent']};text-decoration:none">full methodology &amp; sources</a></span>
      </div>
      <div style="font-size:10px;color:{C['muted']};margin-bottom:10px;padding:8px 12px;
                  background:{C['subtle']};border-radius:6px;border:1px solid {C['border']}">
        Det. Est. = interaction_h + lines_h + reads_h + tools_h (deterministic formula) &nbsp;&middot;&nbsp;
        Lines = logic code only (.py/.ts/.go/&hellip; &mdash; HTML/CSS/JSON/MD excluded) &nbsp;&middot;&nbsp;
        <span style="color:{C['green']}">&#9632;</span> AI Est. = semantic AI analysis
        &nbsp;&nbsp;
        <span id="formula-col-toggle" data-open="0" onclick="toggleFormulaCol()"
              style="cursor:pointer;font-size:9px;color:{C['accent']};user-select:none;
                     border:1px solid {C['accent']};padding:2px 8px;border-radius:4px">
          &#9654; Insert deterministic formula
        </span>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {C['border']};border-radius:7px;overflow:hidden">
        <tr style="background:{C['accent_lt']}">
          <th style="{th_style};text-align:left;width:20%">Project</th>
          <th style="{th_style};width:9%">Turns</th>
          <th style="{th_style};width:12%">Lines</th>
          <th style="{th_style};width:9%">Reads</th>
          <th style="{th_style};width:9%">Tools</th>
          <th style="{th_muted};width:9%">Active</th>
          <th class="formula-col" style="{th_style};width:9%;display:none">Formula</th>
          <th style="{th_style.replace(f"color:{C['accent']}", f"color:{C['green']}")};width:9%">AI Est.</th>
        </tr>
        {rows}
      </table>
      <div class="formula-col" style="display:none;margin-top:12px;padding:10px 12px;
                  background:{C['subtle']};border:1px solid {C['border']};border-radius:6px">
        <div style="font-size:10px;color:{C['text']};line-height:1.6;margin-bottom:6px">
          <strong>About the deterministic formula:</strong>
          Four signals added together: How deep was the collaboration? How much logic code
          was written? How much investigation happened? How much tool execution occurred?
          Tool invocations capture non-coding work (image analysis, document synthesis,
          browser tasks) where logic lines are zero. Premium requests serve as a fallback
          interaction signal when conversation turn data is unavailable.
        </div>
        <div style="font-family:monospace;font-size:10px;color:{C['muted']};line-height:1.5;
                    padding:6px 8px;background:{C['card']};border-radius:4px">
          turns_h &nbsp;= max(0, &minus;0.15 + 0.67 &times; ln(turns + 1))<br>
          reqs_h &nbsp;&nbsp;= max(0, &minus;0.10 + 0.45 &times; ln(reqs + 1)) &nbsp; <em>[fallback when turns=0]</em><br>
          lines_h &nbsp;= 0.40 &times; log&#8322;(logic_lines &divide; 100 + 1)<br>
          reads_h &nbsp;= 0.10 &times; log&#8322;(read_calls + 1)<br>
          tools_h &nbsp;= 0.07 &times; log&#8322;(tool_invocations + 1)<br>
          total &nbsp;&nbsp;&nbsp;= interaction_h + lines_h + reads_h + tools_h &nbsp;&nbsp;(floor 0.25h)
        </div>
      </div>"""


def _evidence_strip(goal: dict, session_metrics: dict) -> str:
    """Compact metrics bar showing evidence and formula behind a goal's estimate."""
    project = goal.get("project", "")
    metrics = _resolve_metrics(project, session_metrics, goal.get("date", ""))
    if not metrics:
        return ""

    fe = compute_formula_estimate(metrics)

    parts = []
    turns = metrics.get("substantive_turns")
    if turns is None:
        turns = metrics.get("conversation_turns", 0)
    if turns:
        parts.append(f"<strong>{turns}</strong> turns &rarr; {_fmt_h(fe['turns_h'])}")
    elif metrics.get("premium_requests", 0):
        parts.append(f"<strong>{metrics['premium_requests']}</strong> reqs &rarr; {_fmt_h(fe['reqs_h'])}")
    logic_lines = metrics.get("lines_logic")
    if logic_lines is None:
        logic_lines = metrics.get("lines_added", 0)
    if logic_lines:
        parts.append(f"<strong>+{logic_lines}</strong> logic lines &rarr; {_fmt_h(fe['lines_h'])}")
    read_calls = metrics.get("reads", 0) + metrics.get("searches", 0)
    if read_calls:
        parts.append(f"<strong>{read_calls}</strong> reads &rarr; {_fmt_h(fe['reads_h'])}")
    tools = metrics.get("tool_invocations", 0)
    if tools:
        parts.append(f"<strong>{tools}</strong> tools &rarr; {_fmt_h(fe['tools_h'])}")

    if not parts:
        return ""

    formula_h = _fmt_h(fe["total"])
    ai_h      = _fmt_h(goal.get("human_hours", 0))
    import hashlib as _hl
    _key = (goal.get('title', '') + goal.get('date', '')).encode()
    fid  = "fs-" + _hl.sha1(_key).hexdigest()[:12]

    int_label = f"turns {_fmt_h(fe['turns_h'])}" if turns > 0 else f"reqs {_fmt_h(fe['reqs_h'])}"

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
                             color:{C['text']}">{int_label} + lines {_fmt_h(fe['lines_h'])} + reads {_fmt_h(fe['reads_h'])} + tools {_fmt_h(fe['tools_h'])}</code>
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
    """Compact explanation of the estimation formula with a worked example."""

    th = (f"padding:4px 8px;font-size:9px;font-weight:700;color:{C['accent']};"
          f"text-transform:uppercase;letter-spacing:0.4px;border-bottom:1px solid {C['border']}")
    td = f"padding:3px 8px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']}"
    tdm = td.replace(f"color:{C['text']}", f"color:{C['muted']}")

    # Formula terms table — one row per term
    term_rows = ""
    for term, formula, samples in [
        ("turns_h", "max(0, &minus;0.15 + 0.67 &times; ln(turns + 1))",
         "3&rarr;0.75h &nbsp; 8&rarr;1.21h &nbsp; 15&rarr;1.57h &nbsp; 30&rarr;2.02h &nbsp; 60&rarr;2.50h &nbsp; 100&rarr;2.82h"),
        ("reqs_h", "max(0, &minus;0.10 + 0.45 &times; ln(reqs + 1)) <em>[fallback when turns=0]</em>",
         "3&rarr;0.52h &nbsp; 8&rarr;0.89h &nbsp; 15&rarr;1.16h &nbsp; 30&rarr;1.44h &nbsp; 60&rarr;1.75h"),
        ("lines_h", "0.40 &times; log&#8322;(logic_lines &divide; 100 + 1)",
         "100&rarr;0.40h &nbsp; 200&rarr;0.63h &nbsp; 500&rarr;1.03h &nbsp; 1000&rarr;1.33h &nbsp; 3000&rarr;1.68h"),
        ("reads_h", "0.10 &times; log&#8322;(read_calls + 1)",
         "5&rarr;0.26h &nbsp; 10&rarr;0.35h &nbsp; 20&rarr;0.44h &nbsp; 50&rarr;0.57h &nbsp; 100&rarr;0.67h"),
        ("tools_h", "0.07 &times; log&#8322;(tool_invocations + 1)",
         "10&rarr;0.24h &nbsp; 50&rarr;0.40h &nbsp; 100&rarr;0.47h &nbsp; 200&rarr;0.54h &nbsp; 500&rarr;0.63h"),
    ]:
        term_rows += (
            f'<tr>'
            f'<td style="{td};white-space:nowrap;font-weight:600">{term}</td>'
            f'<td style="{tdm};font-family:monospace;font-size:9px">{formula}</td>'
            f'<td style="{tdm};font-size:9px">{samples}</td>'
            f'</tr>'
        )

    # Worked example
    example = f"""
        <div style="margin-top:14px;padding:10px 12px;background:{C['subtle']};
                    border:1px solid {C['border']};border-radius:6px">
          <div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.7px;
                      color:{C['accent']};margin-bottom:6px">&#128270; Example: 22 substantive turns,
            +400 logic lines (+800 boilerplate), 35 reads + 15 searches, 120 tool invocations</div>
          <div style="font-family:monospace;font-size:10px;line-height:1.7;color:{C['text']}">
            turns_h = max(0, &minus;0.15 + 0.67 &times; ln(23)) = <strong>1.95h</strong><br>
            lines_h = 0.40 &times; log&#8322;(400 &divide; 100 + 1) = 0.40 &times; 2.32 = <strong>0.93h</strong><br>
            reads_h = 0.10 &times; log&#8322;(50 + 1) = 0.10 &times; 5.67 = <strong>0.57h</strong><br>
            tools_h = 0.07 &times; log&#8322;(120 + 1) = 0.07 &times; 6.93 = <strong>0.49h</strong><br>
            <strong style="color:{C['accent']}">Total = 1.95 + 0.93 + 0.57 + 0.49 = 3.94h &rarr; 4.00h</strong>
            &nbsp;&nbsp;<span style="color:{C['muted']}">(nearest 0.25h)</span>
          </div>
        </div>"""

    return f"""
        <div style="margin-top:16px;padding-top:12px;border-top:1px solid {C['border']}">
          <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                      color:{C['muted']};margin-bottom:6px">How the effort estimate is calculated</div>
          <div style="font-size:10px;color:{C['muted']};line-height:1.5;margin-bottom:8px">
            <code style="font-size:10px;background:{C['subtle']};padding:2px 6px;border-radius:3px;
                         color:{C['accent']}">
              total = interaction_h + lines_h + reads_h + tools_h
            </code>
            &nbsp;&mdash;&nbsp; four questions added together: How deep was the collaboration?
            How much logic code was written (not HTML/CSS/JSON/MD)?
            How much investigation happened? How much tool execution occurred?
            Tool invocations capture non-coding work (image analysis, synthesis, browser tasks).
            Premium requests serve as a fallback interaction signal when turn data is unavailable.
            <a href="https://github.com/microsoft/What-I-Did-Copilot/blob/main/docs/effort-estimation-methodology.md"
               style="color:{C['accent']};text-decoration:none;font-weight:600">
              Full methodology &amp; research basis &#8599;</a>
          </div>

          <div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.7px;
                      color:{C['muted']};margin-bottom:4px">Formula terms</div>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid {C['border']};border-radius:5px;overflow:hidden;margin-bottom:12px">
            <tr style="background:{C['accent_lt']}">
              <th style="{th};width:14%">Term</th>
              <th style="{th};width:36%">Formula</th>
              <th style="{th}">Sample scale values</th>
            </tr>
            {term_rows}
          </table>
          {example}
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
    # Goals arrive pre-sorted by hours descending from generate_html
    sorted_goals = list(goals)
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
              {date_badge}{g.get('label') or g.get('title', '')}
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
                    {g.get('label') or g.get('title', '')}
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


REPO_URL = "https://github.com/microsoft/What-I-Did-Copilot"


def _share_bar(target_date: str, goals: list, headline: str, total_human_h: float) -> str:
    """Summary/share hint strip injected just below the report header."""
    return f"""
  <tr>
    <td style="background:#ffffff;padding:7px 24px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']};
               border-bottom:1px solid {C['border']}">
      <span style="font-size:10px;color:{C['muted']}">
        Run with <code style="font-size:10px;background:#f6f8fa;padding:1px 4px;border-radius:3px">--email</code> to send this report via Outlook
      </span>
    </td>
  </tr>"""


def generate_html(target_date: str, analysis: dict, sessions: list,
                  max_width: int = 960) -> str:
    goals      = analysis.get("goals", [])
    # Sort goals once by hours descending so all sections are consistent
    goals      = sorted(goals, key=lambda g: g.get("human_hours", 0), reverse=True)
    narrative  = analysis.get("day_narrative", "")
    headline   = analysis.get("headline", f"Daily Report — {target_date}")
    focus      = analysis.get("primary_focus", "")
    n_sessions = analysis.get("sessions_count", len(sessions))
    projects   = sorted({s["project"] for s in sessions})

    total_human_h = sum(g.get("human_hours", 0) for g in goals)
    total_tasks   = sum(len(g.get("tasks", [])) for g in goals)

    totals_row= f"""
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

    # Build mapping from raw session project names to goal display labels
    # so session-based sections (collaboration, deliverables) use consistent names
    project_label_map = {}
    for g in goals:
        raw = g.get("project", "")
        label = g.get("label") or g.get("title", "")
        if raw and label:
            project_label_map[raw] = label
            last = raw.replace("\\", "/").split("/")[-1]
            project_label_map.setdefault(last, label)
    # Map unmapped session projects by fuzzy-matching goal projects (case-insensitive,
    # hyphen/space normalized) so e.g. "Frontier Firm" matches "frontier-firm"
    _norm = lambda s: s.lower().replace("-", " ").replace("_", " ").strip()
    goal_norm_map = {_norm(g.get("project", "")): g for g in goals if g.get("project")}
    # Also build a repo→goal map: if a goal's sessions share a git repo, map that repo name
    repo_to_goal = {}
    for g in goals:
        gp = g.get("project", "")
        if not gp:
            continue
        # Find sessions belonging to this goal's project
        for s in sessions:
            sp = s.get("project", "")
            if sp == gp or _norm(sp) == _norm(gp):
                for repo in s.get("git_repos", []):
                    repo_short = repo.replace("\\", "/").split("/")[-1]
                    repo_to_goal.setdefault(repo_short, g)
    for s in sessions:
        sp = s.get("project", "")
        if sp and sp not in project_label_map:
            normed = _norm(sp)
            matched_goal = goal_norm_map.get(normed)
            if not matched_goal:
                # Try matching via git repo name
                for repo in s.get("git_repos", []):
                    repo_short = repo.replace("\\", "/").split("/")[-1]
                    matched_goal = repo_to_goal.get(repo_short)
                    if matched_goal:
                        break
                if not matched_goal:
                    # Try matching session project name as a repo name
                    matched_goal = repo_to_goal.get(sp)
            if matched_goal:
                label = matched_goal.get("label") or matched_goal.get("title", "")
                if label:
                    project_label_map[sp] = label

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
  btn.innerHTML = hide ? '&#9654; Insert deterministic formula' : '&#9660; Hide deterministic formula';
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
<table width="{max_width}" cellpadding="0" cellspacing="0" style="max-width:{max_width}px;width:100%">

  <!-- HEADER -->
  <tr>
    <td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);border-radius:9px 9px 0 0;padding:22px 24px">
      <div style="font-size:10px;color:rgba(255,255,255,0.6);letter-spacing:1.2px;
                  text-transform:uppercase;margin-bottom:4px">
        {target_date} &nbsp;·&nbsp; GitHub Copilot Impact Report
      </div>
      <div style="font-size:20px;font-weight:700;color:#fff;line-height:1.3"><svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" style="vertical-align:middle;margin-right:10px"><path fill="white" d="M23.922 16.992c-.861 1.495-5.859 5.023-11.922 5.023-6.063 0-11.061-3.528-11.922-5.023A.641.641 0 0 1 0 16.736v-2.869a.841.841 0 0 1 .053-.22c.372-.935 1.347-2.292 2.605-2.656.167-.429.414-1.055.644-1.517a10.195 10.195 0 0 1-.052-1.086c0-1.331.282-2.499 1.132-3.368.397-.406.89-.717 1.474-.952 1.399-1.136 3.392-2.093 6.122-2.093 2.731 0 4.767.957 6.166 2.093.584.235 1.077.546 1.474.952.85.869 1.132 2.037 1.132 3.368 0 .368-.014.733-.052 1.086.23.462.477 1.088.644 1.517 1.258.364 2.233 1.721 2.605 2.656a.832.832 0 0 1 .053.22v2.869a.641.641 0 0 1-.078.256ZM12.172 11h-.344a4.323 4.323 0 0 1-.355.508C10.703 12.455 9.555 13 7.965 13c-1.725 0-2.989-.359-3.782-1.259a2.005 2.005 0 0 1-.085-.104L4 11.741v6.585c1.435.779 4.514 2.179 8 2.179 3.486 0 6.565-1.4 8-2.179v-6.585l-.098-.104s-.033.045-.085.104c-.793.9-2.057 1.259-3.782 1.259-1.59 0-2.738-.545-3.508-1.492a4.323 4.323 0 0 1-.355-.508h-.016.016Zm.641-2.935c.136 1.057.403 1.913.878 2.497.442.544 1.134.938 2.344.938 1.573 0 2.292-.337 2.657-.751.384-.435.558-1.15.558-2.361 0-1.14-.243-1.847-.705-2.319-.477-.488-1.319-.862-2.824-1.025-1.487-.161-2.192.138-2.533.529-.269.307-.437.808-.438 1.578v.021c0 .265.021.562.063.893Zm-1.626 0c.042-.331.063-.628.063-.894v-.02c-.001-.77-.169-1.271-.438-1.578-.341-.391-1.046-.69-2.533-.529-1.505.163-2.347.537-2.824 1.025-.462.472-.705 1.179-.705 2.319 0 1.211.175 1.926.558 2.361.365.414 1.084.751 2.657.751 1.21 0 1.902-.394 2.344-.938.475-.584.742-1.44.878-2.497Z"/><path fill="white" d="M14.5 14.25a1 1 0 0 1 1 1v2a1 1 0 0 1-2 0v-2a1 1 0 0 1 1-1Zm-5 0a1 1 0 0 1 1 1v2a1 1 0 0 1-2 0v-2a1 1 0 0 1 1-1Z"/></svg>{headline}</div>

    </td>
  </tr>

  {_share_bar(target_date, goals, headline, total_human_h)}

  <!-- PRIVACY -->
  <tr>
    <td style="background:{C['card']};padding:6px 24px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:9px;color:{C['muted']};text-align:center">
        &#128274; <strong style="color:{C['text']}">Your data, private to you.</strong>
        Generated locally from your Copilot session logs &mdash; no telemetry, no cloud uploads.
        No one has access to this unless you share it.
      </div>
    </td>
  </tr>

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
  {_what_i_work_on(goals, sessions, project_label_map)}

  {_skills_mobilized(goals)}

  <!-- 3. HOW I WORKED WITH COPILOT (intent) -->
  {_collaboration_intent(sessions, project_label_map)}

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
                     color:{C['muted']}">Estimation Evidence &mdash; how these numbers were calculated</span>
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
      <a href="https://github.com/microsoft/What-I-Did-Copilot"
         style="display:inline-block;background:{C['accent']};color:#ffffff;
                font-size:11px;font-weight:700;text-decoration:none;
                padding:6px 16px;border-radius:6px;letter-spacing:0.3px">
        &#128279; github.com/microsoft/What-I-Did-Copilot
      </a>
      <div style="font-size:10px;color:rgba(255,255,255,0.25);margin-top:10px">
        {target_date} &nbsp;·&nbsp; GitHub Copilot Impact Report
      </div>
      <div style="font-size:11px;color:rgba(255,255,255,0.45);margin-top:10px">
        ⭐ If you found this useful, consider <a href="https://github.com/microsoft/What-I-Did-Copilot" style="color:rgba(255,255,255,0.7);text-decoration:none;font-weight:600">starring the repo</a> to help others discover it
      </div>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""
