"""
report.py — Daily digest HTML for GitHub Copilot sessions.
Layout: Header → Narrative → Goals summary → KPI cards → Activity bar → Token bar → Task accordion
"""
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


HOURLY_RATE = 150  # $/hr for leverage calculation
# Enterprise Copilot seat: ~$19–39/month. Use $39/month enterprise / 260 working days.
SEAT_COST_PER_DAY = 39 * 12 / 260  # ≈ $1.80/day


def _kpi_card(value: str, label: str, sub: str = "") -> str:
    return f"""
    <td style="padding:8px;width:25%;vertical-align:top">
      <div style="background:{C['card']};border:1px solid {C['border']};border-radius:10px;
                  padding:20px 14px;text-align:center;
                  box-shadow:0 1px 4px rgba(0,0,0,0.06)">
        <div style="font-size:32px;font-weight:700;color:{C['accent']};line-height:1;
                    letter-spacing:-1px">{value}</div>
        <div style="font-size:10px;font-weight:700;color:{C['muted']};text-transform:uppercase;
                    letter-spacing:0.9px;margin-top:8px;line-height:1.3">{label}</div>
        {f'<div style="font-size:11px;color:{C["muted"]};margin-top:4px;line-height:1.4">{sub}</div>' if sub else ""}
      </div>
    </td>"""


def _kpi_section(goals: list, analysis: dict, n_sessions: int) -> str:
    total_human_h   = sum(g.get("human_hours", 0) for g in goals)
    n_goals         = len(goals)
    lines_added     = analysis.get("lines_added", 0)
    lines_removed   = analysis.get("lines_removed", 0)

    # Leverage: use actual number of active days so multi-day ranges are fair
    active_days = max(1, len(analysis.get("active_dates", ["x"])))
    seat_cost   = SEAT_COST_PER_DAY * active_days
    human_value = total_human_h * HOURLY_RATE
    leverage    = round(human_value / seat_cost) if seat_cost > 0 else "—"

    h_str = _fmt_h(total_human_h)

    # Code impact card
    if lines_added or lines_removed:
        code_val = f"+{lines_added:,}"
        code_sub = f"{lines_removed:,} removed"
    else:
        code_val = "—"
        code_sub = "no code changes tracked"

    days_label = f"{active_days} day{'s' if active_days != 1 else ''}"
    lev_sub = (f"${human_value:,.0f} value / ${seat_cost:.2f} seat ({days_label})"
               if isinstance(leverage, int) else "")

    session_sub = f"{n_sessions} session{'s' if n_sessions != 1 else ''}"

    return f"""
  <tr>
    <td style="background:{C['bg']};padding:16px 24px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {_kpi_card(str(n_goals), "Goals<br>Assisted", session_sub)}
          {_kpi_card(h_str, "Human Effort<br>Equivalent", f"{total_human_h:.0f}h × ${HOURLY_RATE}/hr")}
          {_kpi_card(code_val, "Lines of Code<br>Added", code_sub)}
          {_kpi_card(f"{leverage}×", "Human<br>Leverage", lev_sub)}
        </tr>
      </table>
    </td>
  </tr>"""


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

    # Fixed rate: Copilot seat cost for the active days
    active_days = max(1, len(analysis.get("active_dates", ["x"])))
    seat_cost   = SEAT_COST_PER_DAY * active_days
    savings     = market_cost - seat_cost
    savings_x   = round(market_cost / seat_cost) if seat_cost > 0 else 0

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
              <div style="font-size:26px;font-weight:700;color:{C['green']};letter-spacing:-0.5px">~${seat_cost:.2f}</div>
              <div style="font-size:11px;color:{C['green']};margin-top:4px">{days_label} · ${SEAT_COST_PER_DAY:.2f}/day</div>
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


def _goals_summary(goals: list) -> str:
    rows = ""
    for i, g in enumerate(goals):
        n           = len(g.get("tasks", []))
        h           = _fmt_h(g.get("human_hours", 0))
        bg          = C["subtle"] if i % 2 == 0 else C["card"]
        top_d, top_t = _top_skills_for_goal(g)
        skill_pills = _pills(top_d, top_t)
        task_sub    = f'{n} task{"s" if n != 1 else ""}'
        docs        = g.get("docs_referenced", [])
        doc_html    = _doc_refs_html(docs)
        date_badge  = _date_badge(g.get("date", ""))

        rows += f"""
        <tr style="background:{bg}">
          <td style="padding:12px 16px;border-bottom:1px solid {C['border']};
                     vertical-align:top;width:5%">
            <div style="width:22px;height:22px;background:{C['accent']};border-radius:50%;
                        color:#fff;font-size:11px;font-weight:700;text-align:center;
                        line-height:22px">{i+1}</div>
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid {C['border']};
                     vertical-align:top;width:53%">
            <div style="font-size:13px;font-weight:600;color:{C['text']};line-height:1.35">
              {date_badge}{g.get('title', '')}
            </div>
            {f'<div style="margin-top:5px">{doc_html}</div>' if doc_html else ''}
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid {C['border']};
                     vertical-align:middle;width:28%">
            <div>{skill_pills}</div>
            <div style="font-size:10px;color:{C['muted']};margin-top:5px">{task_sub}</div>
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid {C['border']};
                     vertical-align:middle;text-align:right;width:14%">
            <div style="font-size:16px;font-weight:700;color:{C['accent']}">{h}</div>
            <div style="font-size:10px;color:{C['muted']};margin-top:1px">human est.</div>
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
            {len(goals)} goal{'s' if len(goals) != 1 else ''} &nbsp;·&nbsp; {total_tasks} tasks total
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
    <td style="background:{C['accent']};border-radius:9px 9px 0 0;padding:22px 24px">
      <div style="font-size:10px;color:rgba(255,255,255,0.6);letter-spacing:1.2px;
                  text-transform:uppercase;margin-bottom:4px">
        {target_date} &nbsp;·&nbsp; GitHub Copilot Daily Digest
      </div>
      <div style="font-size:20px;font-weight:700;color:#fff;line-height:1.3">{headline}</div>
      {f'<div style="margin-top:6px;font-size:12px;color:rgba(255,255,255,0.8)">Focus: <strong>{focus}</strong></div>' if focus else ''}
      {f'<div style="margin-top:8px">{project_pills}</div>' if projects else ''}
    </td>
  </tr>

  <!-- NARRATIVE -->
  <tr>
    <td style="background:{C['card']};padding:16px 24px 18px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      {_narrative_block(goals, narrative)}
    </td>
  </tr>

  {_kpi_section(goals, analysis, n_sessions)}

  <!-- GOALS SUMMARY TABLE -->
  <tr>
    <td style="background:{C['card']};padding:0 24px 16px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};padding:0 0 8px 0">What got accomplished</div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {C['border']};border-radius:7px;overflow:hidden">
        {_goals_summary(goals)}
        {totals_row}
      </table>
      <div id="expand-hint" style="display:none;font-size:11px;color:{C['muted']};
                                    text-align:right;margin-top:6px">
        Click any row to expand task breakdown
      </div>
    </td>
  </tr>

  {_activity_bar(analysis)}

  <!-- TASK DETAIL ACCORDION -->
  <tr>
    <td style="background:{C['bg']};padding:16px 24px 4px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']}">Task breakdown</div>
    </td>
  </tr>

  <tr>
    <td style="padding:0;background:{C['bg']};
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0">
        {_goal_detail_headers(goals, session_lookup)}
      </table>
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
