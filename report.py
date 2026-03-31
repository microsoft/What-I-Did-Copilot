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
    <td style="padding:6px;width:25%;vertical-align:top">
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


def _kpi_section(goals: list, analysis: dict, n_sessions: int, total_prs: int = 0) -> str:
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

    return f"""
  <tr>
    <td style="background:{C['bg']};padding:12px 24px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {_kpi_card(str(n_goals), "Projects<br>Assisted", f"{n_sessions} sessions")}
          {_kpi_card(h_str, "Human Effort<br>Equivalent", f"@ ${HOURLY_RATE}/hr")}
          {_kpi_card(code_val, "Lines of Code<br>Added", code_sub)}
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


def _skills_mobilized(goals: list) -> str:
    """Prominent pills showing professional roles (or fallback to domain+tech skills)."""
    roles: set = set()
    for g in goals:
        for t in g.get("tasks", []):
            for r in t.get("professional_roles", []):
                roles.add(r)

    # Fallback: aggregate domain_skills + tech_skills if no professional_roles
    if not roles:
        for g in goals:
            for t in g.get("tasks", []):
                for s in t.get("domain_skills", []):
                    roles.add(s)
                for s in t.get("tech_skills", []):
                    roles.add(s)

    if not roles:
        return ""

    pill_style = (
        f"display:inline-block;padding:5px 14px;border-radius:16px;"
        f"font-size:12px;font-weight:600;margin:3px 4px 3px 0;"
        f"background:{C['accent_lt']};color:{C['accent']};white-space:nowrap;"
        f"border:1px solid rgba(0,120,212,0.15)"
    )

    pills = "".join(f'<span style="{pill_style}">{r}</span>' for r in sorted(roles))

    return f"""
  <tr>
    <td style="background:{C['card']};padding:14px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-bottom:4px">Skills Mobilized</div>
      <div style="font-size:11px;color:{C['muted']};margin-bottom:10px">
        Professional roles Copilot substituted for</div>
      <div>{pills}</div>
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


def _estimation_waterfall(goals: list, analysis: dict) -> str:
    """Evidence table mapping raw session signals to effort estimates."""
    session_metrics = analysis.get("session_metrics", {})
    if not goals:
        return ""

    total_h = sum(g.get("human_hours", 0) for g in goals)

    rows = ""
    for i, g in enumerate(goals):
        bg = C["subtle"] if i % 2 == 0 else C["card"]
        project = g.get("project", "")
        metrics = _resolve_metrics(project, session_metrics, g.get("date", ""))

        dom_type  = _dominant_task_type(g)
        cal_range = CALIBRATION_RANGES.get(dom_type, "1–2h")

        tok_str    = _fmt_tok(metrics.get("tokens", 0))
        tools      = metrics.get("tool_invocations", 0)
        la, lr     = metrics.get("lines_added", 0), metrics.get("lines_removed", 0)
        code_str   = f"+{la}/&minus;{lr}" if (la or lr) else "&mdash;"
        reqs       = metrics.get("premium_requests", 0)
        active     = metrics.get("active_minutes", 0)
        active_str = f"{active:.0f}m" if active else "&mdash;"
        h          = _fmt_h(g.get("human_hours", 0))

        title = g.get("title", "")
        if len(title) > 45:
            title = title[:42] + "..."

        rows += f"""
        <tr style="background:{bg}">
          <td style="padding:8px 10px;border-bottom:1px solid {C['border']};vertical-align:top;width:28%">
            <div style="font-size:11px;font-weight:600;color:{C['text']};line-height:1.3">{title}</div>
            <div style="font-size:9px;color:{C['muted']};margin-top:2px">{dom_type} &middot; {cal_range} range</div>
          </td>
          <td style="padding:8px 6px;border-bottom:1px solid {C['border']};text-align:center;
                     font-size:11px;color:{C['text']};width:10%">{tok_str}</td>
          <td style="padding:8px 6px;border-bottom:1px solid {C['border']};text-align:center;
                     font-size:11px;color:{C['text']};width:8%">{tools}</td>
          <td style="padding:8px 6px;border-bottom:1px solid {C['border']};text-align:center;
                     font-size:11px;color:{C['text']};width:14%">{code_str}</td>
          <td style="padding:8px 6px;border-bottom:1px solid {C['border']};text-align:center;
                     font-size:11px;color:{C['text']};width:10%">{reqs}</td>
          <td style="padding:8px 6px;border-bottom:1px solid {C['border']};text-align:center;
                     font-size:11px;color:{C['text']};width:10%">{active_str}</td>
          <td style="padding:8px 6px;border-bottom:1px solid {C['border']};text-align:center;
                     font-size:11px;color:{C['muted']};width:5%">&rarr;</td>
          <td style="padding:8px 6px;border-bottom:1px solid {C['border']};text-align:center;width:15%">
            <div style="font-size:14px;font-weight:700;color:{C['accent']}">{h}</div>
          </td>
        </tr>"""

    rows += f"""
        <tr style="background:{C['accent_lt']}">
          <td colspan="6" style="padding:8px 10px;border-top:2px solid {C['border']};
                     font-size:11px;font-weight:700;color:{C['accent']};text-align:right">Total</td>
          <td style="padding:8px 6px;border-top:2px solid {C['border']};text-align:center;
                     font-size:11px;color:{C['muted']}">&rarr;</td>
          <td style="padding:8px 6px;border-top:2px solid {C['border']};text-align:center">
            <div style="font-size:16px;font-weight:700;color:{C['accent']}">{_fmt_h(total_h)}</div>
          </td>
        </tr>"""

    return f"""
  <tr>
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-bottom:4px">Estimation Evidence</div>
      <div style="font-size:11px;color:{C['muted']};margin-bottom:12px">
        How session activity maps to human effort estimates</div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {C['border']};border-radius:7px;overflow:hidden">
        <tr style="background:{C['accent_lt']}">
          <th style="padding:6px 10px;text-align:left;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:28%">Project</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:10%">Tokens</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:8%">Tools</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:14%">Code</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:10%">Requests</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:10%">Active</th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;
                     border-bottom:1px solid {C['border']};width:5%"></th>
          <th style="padding:6px 6px;text-align:center;font-size:9px;font-weight:700;
                     color:{C['accent']};text-transform:uppercase;letter-spacing:0.5px;
                     border-bottom:1px solid {C['border']};width:15%">Estimate</th>
        </tr>
        {rows}
      </table>
    </td>
  </tr>"""


def _evidence_strip(goal: dict, session_metrics: dict) -> str:
    """Compact metrics bar showing evidence behind a goal's estimate."""
    project = goal.get("project", "")
    metrics = _resolve_metrics(project, session_metrics, goal.get("date", ""))
    if not metrics:
        return ""

    dom_type  = _dominant_task_type(goal)
    cal_range = CALIBRATION_RANGES.get(dom_type, "1–2h")

    parts = []
    reqs = metrics.get("premium_requests", 0)
    if reqs:
        parts.append(f"<strong>{reqs}</strong> premium reqs")
    tok = metrics.get("tokens", 0)
    if tok:
        parts.append(f"<strong>{_fmt_tok(tok)}</strong> tokens")
    tools = metrics.get("tool_invocations", 0)
    if tools:
        parts.append(f"<strong>{tools}</strong> tool calls")
    la = metrics.get("lines_added", 0)
    lr = metrics.get("lines_removed", 0)
    if la or lr:
        parts.append(f"<strong>+{la}/&minus;{lr}</strong> lines")
    active = metrics.get("active_minutes", 0)
    if active:
        parts.append(f"<strong>{active:.0f}m</strong> active")

    if not parts:
        return ""

    h = _fmt_h(goal.get("human_hours", 0))

    return f"""
            <div style="padding:8px 24px;background:{C['subtle']};border-bottom:1px solid {C['border']}">
              <div style="font-size:10px;color:{C['muted']};line-height:1.5">
                <span style="font-weight:700;color:{C['accent']};margin-right:4px">&#128202;</span>
                {' &middot; '.join(parts)}
              </div>
              <div style="font-size:10px;color:{C['muted']};margin-top:2px">
                Calibration: <strong style="color:{C['text']}">{dom_type}</strong>
                ({cal_range} range) &rarr; Estimated <strong style="color:{C['accent']}">{h}</strong>
              </div>
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

    # Pricing comparison — 3-card layout
    pricing_row = f"""
  <tr>
    <td style="background:{C['bg']};padding:8px 24px 0;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};padding-bottom:6px">Fixed vs. Market Pricing</div>
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="width:33%;padding:0 6px 12px 0">
            <div style="background:{C['card']};border:1px solid {C['border']};border-radius:8px;
                        padding:14px 16px;text-align:center">
              <div style="font-size:10px;font-weight:700;text-transform:uppercase;
                          letter-spacing:0.8px;color:{C['muted']};margin-bottom:6px">Market API Rate</div>
              <div style="font-size:26px;font-weight:700;color:{C['text']};letter-spacing:-0.5px">~${market_cost:.2f}</div>
              <div style="font-size:11px;color:{C['muted']};margin-top:4px">{tok_str} tokens · Anthropic list price</div>
            </div>
          </td>
          <td style="width:33%;padding:0 3px 12px 3px">
            <div style="background:{C['green_lt']};border:1px solid #b7ddb0;border-radius:8px;
                        padding:14px 16px;text-align:center">
              <div style="font-size:10px;font-weight:700;text-transform:uppercase;
                          letter-spacing:0.8px;color:{C['green']};margin-bottom:6px">Copilot Fixed Seat</div>
              <div style="font-size:26px;font-weight:700;color:{C['green']};letter-spacing:-0.5px">{seat_label}</div>
              <div style="font-size:11px;color:{C['green']};margin-top:4px">Enterprise plan · fixed price</div>
            </div>
          </td>
          <td style="width:33%;padding:0 0 12px 6px">
            <div style="background:{C['green']};border-radius:8px;
                        padding:14px 16px;text-align:center">
              <div style="font-size:10px;font-weight:700;text-transform:uppercase;
                          letter-spacing:0.8px;color:rgba(255,255,255,0.7);margin-bottom:6px">You Saved</div>
              <div style="font-size:26px;font-weight:700;color:#fff;letter-spacing:-0.5px">~${savings:.2f}</div>
              <div style="font-size:11px;color:rgba(255,255,255,0.8);margin-top:4px">{savings_x}x cheaper than pay-per-token</div>
            </div>
          </td>
        </tr>
      </table>
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

  <!-- NARRATIVE -->
  <tr>
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      {_narrative_block(goals, narrative)}
    </td>
  </tr>

  {_leverage_banner(goals, analysis)}

  {_kpi_section(goals, analysis, n_sessions, sum(s.get("git_ops", []).count("pr") for s in sessions))}

  {_complexity_breakdown(goals)}

  {_skills_mobilized(goals)}

  {_estimation_waterfall(goals, analysis)}

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

  <!-- METHODOLOGY -->
  <tr>
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-bottom:10px">How estimates are calculated</div>
      <div style="font-size:11px;color:{C['muted']};line-height:1.65">
        Human effort estimates reflect what a professional would need to complete the same work
        without AI assistance, using a conservative blended rate of <strong style="color:{C['text']}">${HOURLY_RATE}/hr</strong>.
        Each task is calibrated against a standardised scale:
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;margin-bottom:6px">
        <tr style="background:{C['subtle']}">
          <td style="padding:5px 10px;font-size:10px;font-weight:700;color:{C['accent']};
                     border-bottom:1px solid {C['border']};width:20%">Category</td>
          <td style="padding:5px 10px;font-size:10px;font-weight:700;color:{C['accent']};
                     border-bottom:1px solid {C['border']};width:50%">Examples</td>
          <td style="padding:5px 10px;font-size:10px;font-weight:700;color:{C['accent']};
                     border-bottom:1px solid {C['border']};width:15%;text-align:center">Estimate</td>
        </tr>
        <tr>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']}">
            <strong>Execution</strong></td>
          <td style="padding:4px 10px;font-size:10px;color:{C['muted']};border-bottom:1px solid {C['border']}">
            Install package, run CLI command, push to repo, deploy</td>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']};
                     text-align:center;font-weight:600">0.25h</td>
        </tr>
        <tr style="background:{C['subtle']}">
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']}">
            <strong>Simple edit</strong></td>
          <td style="padding:4px 10px;font-size:10px;color:{C['muted']};border-bottom:1px solid {C['border']}">
            Config change, format/style tweak, rename, run existing script</td>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']};
                     text-align:center;font-weight:600">0.5h</td>
        </tr>
        <tr>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']}">
            <strong>Research</strong></td>
          <td style="padding:4px 10px;font-size:10px;color:{C['muted']};border-bottom:1px solid {C['border']}">
            Investigate a technology, competitive analysis, find best approach</td>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']};
                     text-align:center;font-weight:600">0.5–1h</td>
        </tr>
        <tr style="background:{C['subtle']}">
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']}">
            <strong>Analysis</strong></td>
          <td style="padding:4px 10px;font-size:10px;color:{C['muted']};border-bottom:1px solid {C['border']}">
            Data analysis, metric compilation, impact assessment, report drafting</td>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']};
                     text-align:center;font-weight:600">1–2h</td>
        </tr>
        <tr>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']}">
            <strong>Development</strong></td>
          <td style="padding:4px 10px;font-size:10px;color:{C['muted']};border-bottom:1px solid {C['border']}">
            Implement feature, write function, fix unknown bug, build template</td>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']};
                     text-align:center;font-weight:600">1–2h</td>
        </tr>
        <tr style="background:{C['subtle']}">
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']}">
            <strong>Design &amp; UX</strong></td>
          <td style="padding:4px 10px;font-size:10px;color:{C['muted']};border-bottom:1px solid {C['border']}">
            Report layout, visual design, information architecture, presentation design</td>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};border-bottom:1px solid {C['border']};
                     text-align:center;font-weight:600">1–3h</td>
        </tr>
        <tr>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']}">
            <strong>Document writing</strong></td>
          <td style="padding:4px 10px;font-size:10px;color:{C['muted']}">
            Detailed report, executive brief, comprehensive documentation</td>
          <td style="padding:4px 10px;font-size:10px;color:{C['text']};text-align:center;font-weight:600">2–4h</td>
        </tr>
      </table>
      <div style="font-size:10px;color:{C['muted']};line-height:1.55;margin-top:6px">
        Estimates are calibrated using session signals (tool invocations, premium requests, code impact)
        and verified by AI analysis. The intent is conservative — credibility over impressiveness.
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
