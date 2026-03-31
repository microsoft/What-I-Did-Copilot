"""
report.py — Daily digest HTML for GitHub Copilot sessions.
Layout: Header → Narrative → Leverage Banner → KPI cards → Complexity → Skills → Goals summary → Pricing/Activity → Task accordion
"""
from datetime import datetime
from harvest import compute_elapsed_minutes

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
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:linear-gradient(135deg,{C['green']},#15803d);border-collapse:collapse">
        <tr>
          <td style="padding:18px 24px 6px;text-align:center">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
                        color:rgba(255,255,255,0.65);margin-bottom:6px">Return on Copilot Investment</div>
            <div style="font-size:44px;font-weight:800;color:#ffffff;line-height:1;
                        letter-spacing:-2px">{leverage:,}&times;</div>
          </td>
        </tr>
        <tr>
          <td style="padding:4px 24px 14px">
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



def _complexity_breakdown(goals: list) -> str:
    """Horizontal stacked bar showing hours by task_type."""
    type_colors = {
        "Development":        C["accent"],
        "Bug Fix & Debug":    C["orange"],
        "Analysis & Research": C["green"],
        "Design & UX":        "#7b1fa2",
        "Execution & Ops":    C["muted"],
    }

    # Aggregate hours by task_type
    hours_by_type: dict = {}
    for g in goals:
        for t in g.get("tasks", []):
            tt = t.get("task_type", "")
            if tt:
                hours_by_type[tt] = hours_by_type.get(tt, 0) + t.get("human_hours", 0)

    if not hours_by_type:
        return ""

    total_h = sum(hours_by_type.values()) or 1

    # Build stacked bar segments (table cells)
    bar_cells = ""
    for tt in type_colors:
        h = hours_by_type.get(tt, 0)
        if h <= 0:
            continue
        pct = h / total_h * 100
        color = type_colors.get(tt, C["muted"])
        bar_cells += (
            f'<td style="width:{pct:.1f}%;background:{color};height:18px;'
            f'font-size:0;line-height:0;padding:0"></td>'
        )

    # Build legend rows
    legend_items = ""
    for tt in type_colors:
        h = hours_by_type.get(tt, 0)
        if h <= 0:
            continue
        pct = h / total_h * 100
        color = type_colors.get(tt, C["muted"])
        legend_items += (
            f'<td style="padding:4px 16px 4px 0;vertical-align:middle;white-space:nowrap">'
            f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
            f'border-radius:2px;margin-right:6px;vertical-align:middle"></span>'
            f'<span style="font-size:12px;font-weight:600;color:{C["text"]};'
            f'vertical-align:middle">{tt}</span>'
            f'<span style="font-size:11px;color:{C["muted"]};margin-left:6px;'
            f'vertical-align:middle">{_fmt_h(h)} ({pct:.0f}%)</span>'
            f'</td>'
        )

    return f"""
  <tr>
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-bottom:10px">Work Complexity Breakdown</div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-radius:9px;overflow:hidden;border:1px solid {C['border']}">
        <tr>{bar_cells}</tr>
      </table>
      <table cellpadding="0" cellspacing="0" style="margin-top:10px">
        <tr>{legend_items}</tr>
      </table>
    </td>
  </tr>"""


def _intent_breakdown(goals: list) -> str:
    """Horizontal stacked bar showing Research vs Build vs Debug hours."""
    import re

    research_kw = re.compile(
        r"\b(what|why|how|explain|investigate|find|understand|evaluate|compare|assess|look\s*up)\b",
        re.IGNORECASE,
    )
    build_kw = re.compile(
        r"\b(build|create|implement|write|add|design|generate|ship|develop|code|make)\b",
        re.IGNORECASE,
    )
    debug_kw = re.compile(
        r"\b(fix|debug|error|bug|broken|wrong|doesn't work|still|why doesn't|what's wrong)\b",
        re.IGNORECASE,
    )

    buckets = {"Research": 0.0, "Build": 0.0, "Debug": 0.0}
    for g in goals:
        for t in g.get("tasks", []):
            h = t.get("human_hours", 0)
            tt = t.get("task_type", "")
            text = f"{t.get('title', '')} {t.get('what_got_done', '')}"

            if "Research" in tt or research_kw.search(text):
                buckets["Research"] += h
            elif "Bug Fix" in tt or debug_kw.search(text):
                buckets["Debug"] += h
            elif "Development" in tt or "Design" in tt or build_kw.search(text):
                buckets["Build"] += h
            else:
                buckets["Build"] += h  # default to Build

    total_h = sum(buckets.values())
    if total_h <= 0:
        return ""

    intent_colors = {
        "Research": "#7b1fa2",
        "Build":    C["accent"],
        "Debug":    C["orange"],
    }

    bar_cells = ""
    for label in ("Research", "Build", "Debug"):
        h = buckets[label]
        if h <= 0:
            continue
        pct = h / total_h * 100
        color = intent_colors[label]
        bar_cells += (
            f'<td style="width:{pct:.1f}%;background:{color};height:18px;'
            f'font-size:0;line-height:0;padding:0"></td>'
        )

    legend_items = ""
    for label in ("Research", "Build", "Debug"):
        h = buckets[label]
        if h <= 0:
            continue
        pct = h / total_h * 100
        color = intent_colors[label]
        legend_items += (
            f'<td style="padding:4px 16px 4px 0;vertical-align:middle;white-space:nowrap">'
            f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
            f'border-radius:2px;margin-right:6px;vertical-align:middle"></span>'
            f'<span style="font-size:12px;font-weight:600;color:{C["text"]};'
            f'vertical-align:middle">{label}</span>'
            f'<span style="font-size:11px;color:{C["muted"]};margin-left:6px;'
            f'vertical-align:middle">{_fmt_h(h)} ({pct:.0f}%)</span>'
            f'</td>'
        )

    return f"""
  <tr>
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-bottom:2px">Research &middot; Build &middot; Debug</div>
      <div style="font-size:11px;color:{C['muted']};margin-bottom:10px">
        How Copilot time was distributed across work types</div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-radius:9px;overflow:hidden;border:1px solid {C['border']}">
        <tr>{bar_cells}</tr>
      </table>
      <table cellpadding="0" cellspacing="0" style="margin-top:10px">
        <tr>{legend_items}</tr>
      </table>
    </td>
  </tr>"""


def _deliverables_produced(sessions: list) -> str:
    """Count tangible deliverables from files modified and tool operations."""
    import re

    # Categorize files by extension/name
    file_categories = {
        "Scripts":        {"icon": "&#128187;", "extensions": {".py", ".js", ".ts", ".sh", ".ps1"}},
        "Reports":        {"icon": "&#128202;", "extensions": {".html"}},
        "Documents":      {"icon": "&#128196;", "extensions": {".md", ".txt", ".docx", ".pdf"}},
        "Data & Config":  {"icon": "&#9881;",   "extensions": {".json", ".yaml", ".yml", ".toml", ".env", ".gitignore", ".cfg"}},
        "Presentations":  {"icon": "&#128209;", "extensions": {".pptx", ".ppt"}},
    }

    # Collect unique files from all sources
    all_files: set = set()

    for s in sessions:
        # Source 1: filesModified from session shutdown
        for f in s.get("code_changes", {}).get("filesModified", []):
            all_files.add(f.replace("\\", "/").split("/")[-1])

        # Source 2: tool summaries mentioning create/edit with file paths
        for msg in s.get("messages", []):
            for tool in msg.get("tools_after", []):
                # Extract filename from tool summaries like "create a new file at C:\...\report.py"
                m = re.search(r'(?:create|edit)[^/\\]*[\\/]([^\\/]+\.\w+)', tool, re.I)
                if m:
                    all_files.add(m.group(1))

    if not all_files:
        return ""

    # Categorize files
    counts: dict = {k: [] for k in file_categories}
    uncategorized = []
    for fname in sorted(all_files):
        ext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        # Special case: .gitignore has no real extension
        if fname.lower() == ".gitignore":
            ext = ".gitignore"
        placed = False
        for cat, info in file_categories.items():
            if ext in info["extensions"]:
                counts[cat].append(fname)
                placed = True
                break
        if not placed and ext:
            uncategorized.append(fname)

    total_files = len(all_files)

    cells = ""
    for cat, info in file_categories.items():
        c = len(counts[cat])
        if c <= 0:
            continue
        # Show up to 3 file names as subtitle
        file_preview = ", ".join(counts[cat][:3])
        if len(counts[cat]) > 3:
            file_preview += f" +{len(counts[cat]) - 3}"
        cells += (
            f'<td style="padding:8px 12px;text-align:center;vertical-align:top">'
            f'<div style="font-size:24px;font-weight:700;color:{C["accent"]};line-height:1">{c}</div>'
            f'<div style="font-size:10px;font-weight:600;color:{C["muted"]};margin-top:4px;'
            f'text-transform:uppercase;letter-spacing:0.5px">{info["icon"]} {cat}</div>'
            f'<div style="font-size:9px;color:{C["muted"]};margin-top:3px;'
            f'font-style:italic;max-width:140px;overflow:hidden">{file_preview}</div>'
            f'</td>'
        )

    return f"""
  <tr>
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-bottom:2px">Deliverables Produced</div>
      <div style="font-size:11px;color:{C['muted']};margin-bottom:12px">
        <strong style="color:{C['text']}">{total_files} files</strong> created or modified with Copilot assistance</div>
      <table cellpadding="0" cellspacing="0">
        <tr>{cells}</tr>
      </table>
    </td>
  </tr>"""


def _daily_activity_detail(sessions: list) -> str:
    """Per-day hourly activity bars — 24 columns per day, height = message intensity."""
    from datetime import datetime as _dt
    from collections import defaultdict

    # Collect messages per day per hour
    day_hours: dict = defaultdict(lambda: [0] * 24)
    for s in sessions:
        for msg in s.get("messages", []):
            ts = msg.get("timestamp", "")
            if not ts:
                continue
            try:
                dt = _dt.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
                day_key = dt.strftime("%Y-%m-%d")
                day_hours[day_key][dt.hour] += 1
            except (ValueError, TypeError):
                pass

    if not day_hours:
        return ""

    # Find global max for consistent scaling
    global_max = max(max(hours) for hours in day_hours.values()) or 1

    rows = ""
    for day in sorted(day_hours.keys()):
        hours = day_hours[day]
        total_msgs = sum(hours)
        peak_hour = hours.index(max(hours))

        # Date label
        try:
            d = _dt.strptime(day, "%Y-%m-%d")
            day_label = d.strftime("%b %d")
            weekday = d.strftime("%a")
        except ValueError:
            day_label = day[5:]
            weekday = ""

        # Build 24 hour columns
        bar_cells = ""
        for h in range(24):
            count = hours[h]
            bar_h = int(count / global_max * 32) if count else 0
            is_peak = h == peak_hour and count > 0
            color = C["accent"] if not is_peak else C["green"]
            bar_cells += (
                f'<td style="padding:0 0 0 1px;vertical-align:bottom;width:{100/24:.1f}%">'
                f'<div style="background:{color};border-radius:2px 2px 0 0;'
                f'height:{bar_h}px;min-height:{1 if count else 0}px"></div>'
                f'</td>'
            )

        # Hour labels (show every 6 hours)
        hour_labels = ""
        for h in range(24):
            label = ""
            if h % 6 == 0:
                label = f"{h}:00"
            hour_labels += (
                f'<td style="padding:0;font-size:8px;color:{C["muted"]};'
                f'text-align:center;vertical-align:top">{label}</td>'
            )

        rows += f"""
          <div style="margin-bottom:12px">
            <div style="display:inline-block;width:70px;vertical-align:top;padding-top:12px">
              <div style="font-size:11px;font-weight:700;color:{C['text']}">{day_label}</div>
              <div style="font-size:9px;color:{C['muted']}">{weekday} &middot; {total_msgs} msgs</div>
            </div>
            <div style="display:inline-block;width:calc(100% - 80px);vertical-align:top">
              <table width="100%" cellpadding="0" cellspacing="0" style="height:34px">
                <tr>{bar_cells}</tr>
              </table>
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>{hour_labels}</tr>
              </table>
            </div>
          </div>"""

    return f"""
        <div style="font-size:9px;color:{C['muted']};margin-bottom:8px">
          Each bar = messages per hour. <span style="color:{C['green']}">&#9632;</span> = peak hour.
          Taller bars indicate more intensive Copilot interaction.
        </div>
        {rows}"""


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
                dt = _dt.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
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
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-bottom:2px">Work Pattern</div>
      <div style="font-size:11px;color:{C['muted']};margin-bottom:12px">
        When Copilot-assisted work happened</div>
      <table width="100%" cellpadding="0" cellspacing="0">
        {rows}
      </table>
      <div id="daily-detail-hdr" style="cursor:pointer;padding:8px 0 0;margin-top:8px;
                                         border-top:1px solid {C['border']}"
           onclick="toggleDetail('daily-detail')">
        <span id="daily-detail-arrow" style="font-size:10px;color:{C['accent']};margin-right:5px">&#9654;</span>
        <span style="font-size:10px;font-weight:700;color:{C['muted']};text-transform:uppercase;
                     letter-spacing:0.8px">Daily breakdown &mdash; click to expand</span>
      </div>
      <div id="daily-detail-tasks" style="display:none;margin-top:8px">
        {_daily_activity_detail(sessions)}
      </div>
    </td>
  </tr>"""


def _skills_mobilized(goals: list) -> str:
    """Grid of professional roles Copilot substituted for, with task counts."""
    from collections import Counter
    role_counts: Counter = Counter()
    for g in goals:
        for t in g.get("tasks", []):
            for r in t.get("professional_roles", []):
                role_counts[r] += 1

    # Fallback: aggregate domain_skills + tech_skills if no professional_roles
    if not role_counts:
        for g in goals:
            for t in g.get("tasks", []):
                for s in t.get("domain_skills", []):
                    role_counts[s] += 1
                for s in t.get("tech_skills", []):
                    role_counts[s] += 1

    if not role_counts:
        return ""

    ROLE_ICONS = {
        "Software Engineer":    "&#128187;",  # laptop
        "Frontend Developer":   "&#127912;",  # art palette
        "UX Designer":          "&#9998;",    # pencil
        "Visual Designer":      "&#127912;",  # art palette
        "Data Analyst":         "&#128200;",  # chart
        "Data Engineer":        "&#128202;",  # bar chart
        "DevOps Engineer":      "&#9881;",    # gear
        "Technical Writer":     "&#128221;",  # memo
        "Product Manager":      "&#127919;",  # target
        "Security Engineer":    "&#128274;",  # lock
        "Solutions Architect":  "&#127959;",  # building
        "QA Engineer":          "&#128269;",  # magnifying glass
    }

    n_roles = len(role_counts)
    total_tasks = sum(role_counts.values())

    # Build role cards in a table grid (3 per row)
    cards = ""
    sorted_roles = role_counts.most_common()
    for i, (role, count) in enumerate(sorted_roles):
        icon = ROLE_ICONS.get(role, "&#128161;")  # lightbulb default
        pct = round(count / total_tasks * 100) if total_tasks else 0
        cards += f"""
              <td style="padding:4px 6px;width:33%;vertical-align:top">
                <div style="border:1px solid {C['border']};border-radius:6px;padding:10px 12px;
                            background:{C['subtle']};height:50px">
                  <div style="font-size:16px;margin-bottom:4px">{icon}</div>
                  <div style="font-size:11px;font-weight:700;color:{C['text']};line-height:1.3">{role}</div>
                  <div style="font-size:10px;color:{C['muted']};margin-top:2px">{count} task{'s' if count != 1 else ''} &middot; {pct}%</div>
                </div>
              </td>"""
        # Close row every 3 cards
        if (i + 1) % 3 == 0 and i < len(sorted_roles) - 1:
            cards += "</tr><tr>"

    # Pad last row if needed
    remainder = len(sorted_roles) % 3
    if remainder:
        for _ in range(3 - remainder):
            cards += '<td style="padding:4px 6px;width:33%"></td>'

    return f"""
  <tr>
    <td style="background:{C['card']};padding:14px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-bottom:4px">Specialist Skills Augmented</div>
      <div style="font-size:11px;color:{C['muted']};margin-bottom:10px">
        Copilot augmented <strong style="color:{C['text']}">{n_roles} specialist skill sets</strong>
        across {total_tasks} tasks &mdash; enabling work that would otherwise require
        additional expertise or consulting.</div>
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>{cards}</tr>
      </table>
    </td>
  </tr>"""


CALIBRATION_RANGES = {
    "Execution & Ops":     "0.25h",
    "Development":         "1–2h",
    "Bug Fix & Debug":     "1–2h",
    "Analysis & Research": "0.5–2h",
    "Design & UX":         "1–3h",
}


def _dominant_task_type(goal: dict) -> str:
    type_hours: dict = {}
    for t in goal.get("tasks", []):
        tt = t.get("task_type", "Development")
        type_hours[tt] = type_hours.get(tt, 0) + t.get("human_hours", 0)
    return max(type_hours, key=type_hours.get) if type_hours else "Development"


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


def _fmt_tok(tok: int) -> str:
    if tok < 1_000:
        return str(tok)
    if tok < 1_000_000:
        return f"{tok / 1_000:.0f}K"
    return f"{tok / 1_000_000:.1f}M"


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
          <td style="padding:4px 6px;text-align:center;width:13%;vertical-align:middle" rowspan="2">
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
          <td style="padding:8px 6px;border-top:2px solid {C['border']};text-align:center">
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
        <code style="font-size:10px;color:{C['accent']}">estimate = max(tools, requests, active) + lines</code>
        &nbsp;&nbsp;
        <span style="color:{C['accent']}">&#9632;</span> Formula &nbsp;
        <span style="color:{C['green']}">&#9632;</span> AI estimate &nbsp;
        <strong style="color:{C['accent']}">Bold</strong> = highest signal
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
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:13%">Formula</th>
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
    ai_h = _fmt_h(goal.get("human_hours", 0))

    return f"""
            <div style="padding:8px 24px;background:{C['subtle']};border-bottom:1px solid {C['border']}">
              <div style="font-size:10px;color:{C['muted']};line-height:1.5">
                <span style="font-weight:700;color:{C['accent']};margin-right:4px">&#128202;</span>
                {' &middot; '.join(parts)}
              </div>
              <div style="font-size:10px;color:{C['muted']};margin-top:2px">
                <code style="font-size:9px;background:{C['bg']};padding:1px 5px;border-radius:3px;
                             color:{C['text']}">max({_fmt_h(fe['tool_h'])}, {_fmt_h(fe['req_h'])}, {_fmt_h(fe['active_h'])}) + {_fmt_h(fe['lines_h'])}</code>
                = <strong style="color:{C['accent']}">{formula_h}</strong> formula
                &middot; <strong style="color:{C['green']}">{ai_h}</strong> AI estimate
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
    """McKinsey-style summary: intro line + numbered bold-label list."""
    n = len(goals)
    if not goals:
        return f'<div style="font-size:13px;line-height:1.65;color:{C["text"]}">{fallback}</div>'

    count_word = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}.get(n, str(n))
    plural = "pieces of work" if n != 1 else "piece of work"
    intro = (f'<div style="font-size:13px;color:{C["text"]};margin-bottom:10px;line-height:1.5">'
             f'Completed {count_word} distinct {plural}:</div>')

    items = ""
    for i, g in enumerate(goals):
        label      = g.get("label") or g.get("title", f"Goal {i+1}")
        summary    = g.get("summary", "")
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

    return intro + items


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
    rows = ""
    for i, g in enumerate(goals):
        gid         = f"goal-{i}"
        n           = len(g.get("tasks", []))
        h           = _fmt_h(g.get("human_hours", 0))
        bg          = C["subtle"] if i % 2 == 0 else C["card"]
        top_d, top_t = _top_skills_for_goal(g)
        skill_pills = _pills(top_d, top_t)
        task_sub    = f'{n} task{"s" if n != 1 else ""}'
        docs        = g.get("docs_referenced", [])
        doc_html    = _doc_refs_html(docs)
        date_badge  = _date_badge(g.get("date", ""))
        tasks       = g.get("tasks", [])

        rows += f"""
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
            {_evidence_strip(g, session_metrics)}
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
    return rows


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
        f'border-radius:10px;font-size:11px;margin-right:5px;display:inline-block;'
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
  var open = tasks.style.display === 'table-row';
  tasks.style.display  = open ? 'none'    : 'table-row';
  hdr.style.background = open ? ''        : '#e8f2fb';
  if (arrow) arrow.innerHTML = open ? '&#9654;' : '&#9660;';
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
    <td style="background:linear-gradient(135deg,#24292f,#1b1f23);border-radius:9px 9px 0 0;padding:22px 24px">
      <div style="font-size:10px;color:rgba(255,255,255,0.6);letter-spacing:1.2px;
                  text-transform:uppercase;margin-bottom:4px">
        {target_date} &nbsp;·&nbsp; GitHub Copilot Impact Report
      </div>
      <div style="font-size:20px;font-weight:700;color:#fff;line-height:1.3"><svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" style="vertical-align:middle;margin-right:10px"><path fill="white" d="M23.922 16.992c-.861 1.495-5.859 5.023-11.922 5.023-6.063 0-11.061-3.528-11.922-5.023A.641.641 0 0 1 0 16.736v-2.869a.841.841 0 0 1 .053-.22c.372-.935 1.347-2.292 2.605-2.656.167-.429.414-1.055.644-1.517a10.195 10.195 0 0 1-.052-1.086c0-1.331.282-2.499 1.132-3.368.397-.406.89-.717 1.474-.952 1.399-1.136 3.392-2.093 6.122-2.093 2.731 0 4.767.957 6.166 2.093.584.235 1.077.546 1.474.952.85.869 1.132 2.037 1.132 3.368 0 .368-.014.733-.052 1.086.23.462.477 1.088.644 1.517 1.258.364 2.233 1.721 2.605 2.656a.832.832 0 0 1 .053.22v2.869a.641.641 0 0 1-.078.256ZM12.172 11h-.344a4.323 4.323 0 0 1-.355.508C10.703 12.455 9.555 13 7.965 13c-1.725 0-2.989-.359-3.782-1.259a2.005 2.005 0 0 1-.085-.104L4 11.741v6.585c1.435.779 4.514 2.179 8 2.179 3.486 0 6.565-1.4 8-2.179v-6.585l-.098-.104s-.033.045-.085.104c-.793.9-2.057 1.259-3.782 1.259-1.59 0-2.738-.545-3.508-1.492a4.323 4.323 0 0 1-.355-.508h-.016.016Zm.641-2.935c.136 1.057.403 1.913.878 2.497.442.544 1.134.938 2.344.938 1.573 0 2.292-.337 2.657-.751.384-.435.558-1.15.558-2.361 0-1.14-.243-1.847-.705-2.319-.477-.488-1.319-.862-2.824-1.025-1.487-.161-2.192.138-2.533.529-.269.307-.437.808-.438 1.578v.021c0 .265.021.562.063.893Zm-1.626 0c.042-.331.063-.628.063-.894v-.02c-.001-.77-.169-1.271-.438-1.578-.341-.391-1.046-.69-2.533-.529-1.505.163-2.347.537-2.824 1.025-.462.472-.705 1.179-.705 2.319 0 1.211.175 1.926.558 2.361.365.414 1.084.751 2.657.751 1.21 0 1.902-.394 2.344-.938.475-.584.742-1.44.878-2.497Z"/><path fill="white" d="M14.5 14.25a1 1 0 0 1 1 1v2a1 1 0 0 1-2 0v-2a1 1 0 0 1 1-1Zm-5 0a1 1 0 0 1 1 1v2a1 1 0 0 1-2 0v-2a1 1 0 0 1 1-1Z"/></svg>{headline}</div>
      {f'<div style="margin-top:8px"><span style="font-size:9px;font-weight:700;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:1px;margin-right:8px">Projects</span>{project_pills}</div>' if projects else ''}
    </td>
  </tr>

  {heuristic_banner}

  <!-- NARRATIVE -->
  <tr>
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      {_narrative_block(goals, narrative)}
    </td>
  </tr>

  {_leverage_banner(goals, analysis)}

  {_kpi_section(goals, analysis, n_sessions,
              sum(s.get("git_ops", []).count("pr") for s in sessions),
              sum(s.get("git_ops", []).count("commit") for s in sessions))}

  {_complexity_breakdown(goals)}

  {_intent_breakdown(goals)}

  {_skills_mobilized(goals)}

  {_deliverables_produced(sessions)}

  {_work_pattern(sessions)}

  <!-- GOALS SUMMARY TABLE -->
  <tr>
    <td style="background:{C['card']};padding:0 24px 16px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};padding:0 0 8px 0">What got accomplished</div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {C['border']};border-radius:7px;overflow:hidden">
        {_goals_summary(goals, session_lookup, analysis.get("session_metrics", {}))}
        {totals_row}
      </table>
      <div id="expand-hint" style="display:none;font-size:11px;color:{C['muted']};
                                    text-align:right;margin-top:6px">
        Click a project to see task details &#9656;
      </div>
    </td>
  </tr>

  {_activity_bar(analysis)}

  <!-- ESTIMATION EVIDENCE (collapsible) -->
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
    <td style="background:{C['text']};border-radius:0 0 9px 9px;padding:12px 24px;
               text-align:center">
      <div style="font-size:10px;color:rgba(255,255,255,0.4)">
        <strong style="color:rgba(255,255,255,0.65)">whatididghcp</strong>
        &nbsp;·&nbsp; GitHub Copilot &nbsp;·&nbsp; {target_date}
      </div>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""
