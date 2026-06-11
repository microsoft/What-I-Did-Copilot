"""
report.py — Daily digest HTML for GitHub Copilot sessions.
Layout: Act 1 (Story) → Act 2 (Journey) → Act 3 (Evidence)
  Act 1: Header → Narrative → KPIs → ROI
  Act 2: How I Collaborated → What Got Built → Skills Augmented → When I Worked
  Act 3: What Got Accomplished → Pricing → Estimation Evidence
"""
from datetime import datetime, timezone
from harvest import compute_elapsed_minutes

# Branded logo embedded as a data URI so the report stays self-contained
# (no external image files, email-compatible).
LOGO_DATA_URI = "data:image/png;base64,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"


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


def _fmt_tokens(t: int) -> str:
    """Format token count with K/M suffix."""
    if not t or t <= 0:
        return ""
    if t >= 1_000_000:
        return f"{t / 1_000_000:.1f}M"
    if t >= 1_000:
        return f"{t / 1_000:.0f}K"
    return str(t)


def _fmt_ms(ms: int) -> str:
    """Format milliseconds as Xm Ys."""
    if not ms:
        return "—"
    s = ms // 1000
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60}s"


# Per-model token pricing ($ per 1M tokens). Source of truth:
# https://docs.github.com/copilot/reference/copilot-billing/models-and-pricing
# Used by GitHub Copilot's AI Credits billing model (effective June 1, 2026):
# tokens × per-model rate → USD → AI Credits (1 credit = $0.01 USD).
#
# Keys are matched by longest-prefix against model names from session data.
# Keep more-specific prefixes before less-specific ones for readability
# (e.g. "gpt-4o-mini" before "gpt-4o"); the algorithm always picks the
# longest matching prefix regardless of insertion order. "cache_read" is the
# cached-input rate; "cache_creation" is the cache-write rate (Anthropic only —
# for non-Anthropic providers we mirror the input rate since they don't bill
# a separate cache-write line).
_MODEL_PRICING = {
    # ── OpenAI (GitHub Copilot) ──
    "gpt-5.5":          {"input":  5.00, "output": 30.00, "cache_read": 0.50,   "cache_creation":  5.00},
    "gpt-5.4-mini":     {"input":  0.75, "output":  4.50, "cache_read": 0.075,  "cache_creation":  0.75},
    "gpt-5.4-nano":     {"input":  0.20, "output":  1.25, "cache_read": 0.02,   "cache_creation":  0.20},
    "gpt-5.4":          {"input":  2.50, "output": 15.00, "cache_read": 0.25,   "cache_creation":  2.50},
    "gpt-5.3-codex":    {"input":  1.75, "output": 14.00, "cache_read": 0.175,  "cache_creation":  1.75},
    "gpt-5.2-codex":    {"input":  1.75, "output": 14.00, "cache_read": 0.175,  "cache_creation":  1.75},
    "gpt-5.2":          {"input":  1.75, "output": 14.00, "cache_read": 0.175,  "cache_creation":  1.75},
    "gpt-5-mini":       {"input":  0.25, "output":  2.00, "cache_read": 0.025,  "cache_creation":  0.25},
    "gpt-5":            {"input":  2.50, "output": 10.00, "cache_read": 1.25,   "cache_creation":  2.50},  # legacy
    "gpt-4.1":          {"input":  2.00, "output":  8.00, "cache_read": 0.50,   "cache_creation":  2.00},
    "gpt-4o-mini":      {"input":  0.15, "output":  0.60, "cache_read": 0.075,  "cache_creation":  0.15},  # legacy
    "gpt-4o":           {"input":  2.50, "output": 10.00, "cache_read": 1.25,   "cache_creation":  2.50},  # legacy
    "o3":               {"input": 10.00, "output": 40.00, "cache_read": 2.50,   "cache_creation": 10.00},  # legacy
    "o4-mini":          {"input":  1.10, "output":  4.40, "cache_read": 0.275,  "cache_creation":  1.10},  # legacy
    # ── Anthropic (Claude) — cache_creation is a real, separate write cost ──
    "claude-opus-4.8":  {"input":  5.00, "output": 25.00, "cache_read": 0.50,   "cache_creation":  6.25},
    "claude-opus-4.7":  {"input":  5.00, "output": 25.00, "cache_read": 0.50,   "cache_creation":  6.25},
    "claude-opus-4.6":  {"input":  5.00, "output": 25.00, "cache_read": 0.50,   "cache_creation":  6.25},
    "claude-opus-4.5":  {"input":  5.00, "output": 25.00, "cache_read": 0.50,   "cache_creation":  6.25},
    "claude-opus-4":    {"input": 15.00, "output": 75.00, "cache_read": 1.50,   "cache_creation": 18.75},  # legacy
    "claude-sonnet-4.6":{"input":  3.00, "output": 15.00, "cache_read": 0.30,   "cache_creation":  3.75},
    "claude-sonnet-4.5":{"input":  3.00, "output": 15.00, "cache_read": 0.30,   "cache_creation":  3.75},
    "claude-sonnet-4":  {"input":  3.00, "output": 15.00, "cache_read": 0.30,   "cache_creation":  3.75},
    "claude-haiku-4.5": {"input":  1.00, "output":  5.00, "cache_read": 0.10,   "cache_creation":  1.25},
    "claude-haiku":     {"input":  0.80, "output":  4.00, "cache_read": 0.08,   "cache_creation":  1.00},  # legacy
    # ── Google (Gemini) ──
    "gemini-3.5-flash": {"input":  1.50, "output":  9.00, "cache_read": 0.15,   "cache_creation":  1.50},
    "gemini-3.1-pro":   {"input":  2.00, "output": 12.00, "cache_read": 0.20,   "cache_creation":  2.00},
    "gemini-3-flash":   {"input":  0.50, "output":  3.00, "cache_read": 0.05,   "cache_creation":  0.50},
    "gemini-2.5-pro":   {"input":  1.25, "output": 10.00, "cache_read": 0.125,  "cache_creation":  1.25},
    "gemini-2.5-flash": {"input":  0.15, "output":  0.60, "cache_read": 0.0375, "cache_creation":  0.15},
    "gemini-2.0-flash": {"input":  0.10, "output":  0.40, "cache_read": 0.025,  "cache_creation":  0.10},
    # ── GitHub fine-tuned ──
    "raptor-mini":      {"input":  0.25, "output":  2.00, "cache_read": 0.025,  "cache_creation":  0.25},
}
# Models included with paid plans at no credit cost (GitHub-published list).
# We still surface the market rate (it's the "open market value" story), but
# downstream features can use this set to mark sessions as "no credits charged".
_INCLUDED_MODELS = {"gpt-4.1", "gpt-5-mini", "raptor-mini"}

# Fallback: if model name doesn't match any prefix, use mid-range pricing.
_DEFAULT_PRICING = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_creation": 3.75}

# GitHub AI Credits conversion: 1 credit = $0.01 USD (effective 2026-06-01).
# Paid plans get a 10% discount on auto-model selection in Chat / CLI / cloud agent.
USD_PER_CREDIT = 0.01
AUTO_MODEL_DISCOUNT = 0.10


def _get_model_pricing(model_name: str, inline: dict | None = None) -> dict:
    """Return pricing dict for a model name, matching by longest prefix.

    When ``inline`` is provided (e.g. authoritative rate metadata harvested
    from a VS Code Copilot Chat session JSONL), an exact-id match takes
    precedence over the hardcoded ``_MODEL_PRICING`` table. Inline rates
    come straight from Copilot's own ``selectedModel.metadata`` block, so
    they self-update when GitHub revises rates and handle unknown models
    that aren't yet in the table.
    """
    if inline:
        hit = inline.get(model_name) or inline.get(model_name.lower())
        if isinstance(hit, dict) and "input" in hit and "output" in hit:
            return hit
    name = model_name.lower()
    best_prefix = ""
    best_rates = _DEFAULT_PRICING
    for prefix, rates in _MODEL_PRICING.items():
        if name.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_rates = rates
    return best_rates


def _cost(tokens: dict) -> str:
    """Calculate API cost using per-token pricing for models used by GitHub Copilot."""
    c = (tokens.get("input", 0)          * _DEFAULT_PRICING["input"]
       + tokens.get("output", 0)         * _DEFAULT_PRICING["output"]
       + tokens.get("cache_read", 0)     * _DEFAULT_PRICING["cache_read"]
       + tokens.get("cache_creation", 0) * _DEFAULT_PRICING["cache_creation"]) / 1_000_000
    return f"~${c:.2f}"


def _cost_by_model(tokens_by_model: dict, auto_model: bool = False,
                   inline_pricing: dict | None = None) -> float:
    """Calculate total API cost using per-model pricing. Returns dollar amount.

    When ``auto_model`` is True, applies the 10% auto-model-selection discount
    that paid Copilot plans receive in Chat / CLI / cloud agent.

    When ``inline_pricing`` is provided (per-session authoritative rates
    harvested from a VS Code Copilot Chat JSONL), it takes precedence over
    the hardcoded ``_MODEL_PRICING`` table for any matching model id.
    """
    total = 0.0
    for model_name, toks in tokens_by_model.items():
        rates = _get_model_pricing(model_name, inline=inline_pricing)
        total += (toks.get("input", 0)          * rates["input"]
                + toks.get("output", 0)         * rates["output"]
                + toks.get("cache_read", 0)     * rates["cache_read"]
                + toks.get("cache_creation", 0) * rates["cache_creation"]) / 1_000_000
    if auto_model and total > 0:
        total *= (1.0 - AUTO_MODEL_DISCOUNT)
    return total


def _credits(usd: float) -> int:
    """Convert a USD cost into GitHub AI Credits (1 credit = $0.01)."""
    if usd <= 0:
        return 0
    return int(round(usd / USD_PER_CREDIT))


def _fmt_credits(n: int) -> str:
    """Format an AI-credit count with K/M suffix."""
    if not n or n <= 0:
        return "0"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _resolve_market_cost(analysis: dict) -> float:
    """Compute the market-rate API cost from per-model or aggregate tokens.

    Honours the optional ``auto_model_selection`` flag carried through from
    the session log (10% discount on paid plans). Also honours the optional
    ``inline_model_pricing`` map (authoritative per-session rates harvested
    from VS Code Copilot Chat JSONL) when present.
    """
    auto = bool(analysis.get("auto_model_selection") or analysis.get("auto_model"))
    inline = analysis.get("inline_model_pricing") or None
    tokens_by_model = analysis.get("tokens_by_model", {})
    if tokens_by_model:
        return _cost_by_model(tokens_by_model, auto_model=auto, inline_pricing=inline)
    tokens = analysis.get("tokens", {})
    if not isinstance(tokens, dict):
        # Per-project session_metrics stores ``tokens`` as a scalar total. We
        # have no per-bucket breakdown in that shape, so we can't price it
        # without tokens_by_model. Treat as zero rather than crashing.
        return 0.0
    cost = (tokens.get("input", 0)          * _DEFAULT_PRICING["input"]
          + tokens.get("output", 0)         * _DEFAULT_PRICING["output"]
          + tokens.get("cache_read", 0)     * _DEFAULT_PRICING["cache_read"]
          + tokens.get("cache_creation", 0) * _DEFAULT_PRICING["cache_creation"]) / 1_000_000
    if auto and cost > 0:
        cost *= (1.0 - AUTO_MODEL_DISCOUNT)
    return cost


def _ai_credits_for(analysis: dict) -> int:
    """Return AI credits consumed for an analysis dict.

    Prefers the server-emitted ``ai_credits`` field when present (future-proof
    for when ``session.shutdown`` starts carrying it), otherwise falls back to
    computing credits from per-model token cost.
    """
    if (server := analysis.get("ai_credits")) is not None:
        try:
            return int(server)
        except (TypeError, ValueError):
            pass
    return _credits(_resolve_market_cost(analysis))


HOURLY_RATE = 72  # $/hr — blended professional services rate (conservative)
SEAT_COST_PER_MONTH = 39  # Enterprise Copilot seat $/month (default when plan unknown)


# Plan seat prices under the AI Credits billing model (effective 2026-06-01).
# We intentionally do NOT model included credit allowances, flex amounts, or
# promotional bonuses here — those depend on the user's specific subscription
# configuration in ways the local session log can't observe, and presenting
# them as if they were billing facts risks misleading the reader. The seat
# price is real and public; everything else stays out of the report.
# Source: https://docs.github.com/copilot/concepts/billing/usage-based-billing-for-individuals
PLAN_ALLOWANCES = {
    "free":       {"seat":   0},
    "pro":        {"seat":  10},
    "pro+":       {"seat":  39},
    "max":        {"seat": 100},
    "business":   {"seat":  19},
    "enterprise": {"seat":  39},
}


def _plan_key(analysis: dict) -> str:
    """Normalize the plan label coming from session data or env var.

    Defaults to ``enterprise`` when unknown — matches the historical
    ``SEAT_COST_PER_MONTH = 39`` assumption so existing reports stay stable.
    """
    raw = (analysis.get("plan") or "").lower().strip().replace(" ", "")
    if raw in PLAN_ALLOWANCES:
        return raw
    return {
        "biz": "business", "ent": "enterprise",
        "proplus": "pro+", "pro_plus": "pro+",
    }.get(raw, "enterprise")


def _plan_seat_per_month(analysis: dict) -> int:
    return PLAN_ALLOWANCES[_plan_key(analysis)]["seat"]


def _prorated_seat_cost(analysis: dict) -> "tuple[int, int]":
    """Return (seat_cost, n_months) prorated over the report's time span.

    Uses the user's plan when known; falls back to the Enterprise seat
    price ($39) when no plan information is available.

    For short reports (≤31 days), always use 1 month regardless of calendar
    month boundaries — a 7-day export shouldn't show 2 months of seat cost
    just because it crosses a month boundary.
    """
    seat_per_month = _plan_seat_per_month(analysis)
    dates = analysis.get("active_dates", [])
    if not dates:
        return seat_per_month, 1

    # Parse dates and determine the span
    parsed = []
    for d in dates:
        try:
            parsed.append(datetime.strptime(str(d)[:10], "%Y-%m-%d"))
        except ValueError:
            pass
    if not parsed:
        return seat_per_month, 1

    span_days = (max(parsed) - min(parsed)).days + 1
    if span_days <= 31:
        return seat_per_month, 1

    # For longer reports, prorate by distinct calendar months
    months = {(dt.year, dt.month) for dt in parsed}
    n_months = max(1, len(months))
    return seat_per_month * n_months, n_months


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


def _open_session_note(analysis: dict) -> str:
    """Inline disclosure shown when one or more sessions never wrote a clean
    `session.shutdown` event. For those sessions the harvester captures
    output tokens (per assistant message) and compaction billing (per
    compaction event) directly from the event stream, but non-compaction
    input tokens are not in the stream, so credit totals are a lower bound.
    Returns empty string when all sessions closed cleanly."""
    open_n = analysis.get("open_session_count", 0)
    total_n = analysis.get("total_session_count", 0)
    if open_n <= 0 or total_n <= 0:
        return ""
    return (
        f' <strong style="color:{C["text"]}">Note:</strong> {open_n} of {total_n} '
        f'session{"s" if total_n != 1 else ""} did not write a clean shutdown record '
        f'(still active, killed, or crashed). Their output and compaction tokens '
        f'are captured directly from the event log; non-compaction input tokens '
        f'are not emitted for open sessions, so credit totals for those projects '
        f'are a lower bound.'
    )


def _kpi_section(goals: list, analysis: dict, n_sessions: int, total_prs: int = 0, total_commits: int = 0) -> str:
    total_human_h   = sum(g.get("human_hours", 0) for g in goals)
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
          {_kpi_card(pr_commit_val, "PRs<br>Merged", pr_commit_sub)}
        </tr>
      </table>
    </td>
  </tr>"""


def _leverage_banner(goals: list, analysis: dict) -> str:
    """Stacked Value / Investment banner — disambiguates output from input.

    The hero (top section) shows **what was delivered** — research-grounded
    human-hour estimate × blended hourly rate, the headline value claim.

    A secondary section beneath it shows **what was invested** — measured
    tokens converted to AI Credits + open-market value using GitHub's
    published per-model rates. Sized smaller so it visually reads as
    supporting context rather than competing with the hero.

    A footer disclaimer makes the estimate caveat explicit, because the
    user's actual GitHub bill depends on plan, included allowance,
    auto-model discount, and other factors we cannot observe locally.
    """
    total_human_h = sum(g.get("human_hours", 0) for g in goals)
    human_value   = total_human_h * HOURLY_RATE
    market_cost   = _resolve_market_cost(analysis)
    ai_credits    = _ai_credits_for(analysis)

    if total_human_h <= 0:
        return ""

    credits_str = (f"{_fmt_credits(ai_credits)} credits"
                   if ai_credits else "— credits")
    market_str  = (f"~${market_cost:,.0f} open-market value (estimated)"
                   if market_cost > 0 else "no AI activity recorded")

    return f"""
  <tr>
    <td style="padding:0;border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0" bgcolor="{C['green']}"
             style="background:linear-gradient(135deg,{C['green']},#15803d);border-collapse:collapse">
        <tr>
          <td bgcolor="{C['green']}" style="padding:18px 24px 14px;text-align:center">
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
                        color:rgba(255,255,255,0.7)">Value Delivered</div>
            <div style="font-size:34px;font-weight:700;color:#fff;margin-top:6px;line-height:1.1">
              ${human_value:,.0f}</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.8);margin-top:4px">
              {total_human_h:.1f}h &times; ${HOURLY_RATE}/hr blended rate</div>
          </td>
        </tr>
        <tr>
          <td bgcolor="#15803d" style="padding:12px 24px;text-align:center;
                                       border-top:1px solid rgba(255,255,255,0.18)">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;
                        color:rgba(255,255,255,0.55)">AI Investment</div>
            <div style="font-size:20px;font-weight:700;color:#fff;margin-top:3px;line-height:1.1">
              {credits_str}</div>
            <div style="font-size:11px;color:rgba(255,255,255,0.7);margin-top:3px">
              {market_str}</div>
          </td>
        </tr>
        <tr>
          <td bgcolor="#15803d" style="padding:0 24px 12px;text-align:center">
            <div style="font-size:10px;color:rgba(255,255,255,0.55);line-height:1.4;
                        font-style:italic">
              AI investment estimated from measured tokens &times; GitHub's published
              per-model rates — your actual bill depends on your plan and included
              credit allowance.</div>
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
    """Section: 'How I Collaborated' — SVG donut chart with adjacent labels.

    A donut chart shows how active collaboration time split across the
    work modes (Designing / Analyzing / Reviewing / Learning /
    Researching / Refining / Building / Course-correcting / Delegating).
    Labels sit directly next to each slice, connected by short leader
    lines, so the eye doesn't have to bounce to a legend to decode
    colors.

    Implementation notes:
      * Donut uses one ``<circle>`` per slice with ``stroke-dasharray``
        and ``stroke-dashoffset`` for clean, scalable rendering. All
        slices are rotated -90&deg; so 0% starts at 12 o'clock.
      * Labels are positioned radially around the donut, then split
        into left/right groups and collision-resolved vertically so
        adjacent labels don't overlap.
      * Each slice has a ``<title>`` for hover tooltips.
      * Each label shows ``mode`` in bold, then ``%`` colored to match
        its slice, then minutes/hours in a smaller muted line below.
      * SVG renders in modern browsers, Gmail web, Apple Mail and
        Outlook 365 web. Outlook desktop strips SVG; in that case
        labels collapse but tooltips/raw text remain.
    """
    import math
    from harvest import compute_active_time_quality, _QUALITY_COLORS

    if project_label_map is None:
        project_label_map = {}

    modes = compute_active_time_quality(sessions)
    total = sum(modes.values())
    if total < 1:
        return ""

    HIGH_VALUE = {"Designing", "Analyzing", "Reviewing",
                  "Researching", "Learning", "Building", "Refining"}

    sorted_modes = sorted(modes.items(), key=lambda x: -x[1])
    visible = [(m, mins) for m, mins in sorted_modes if mins >= 0.1]

    # Narrative stats.
    low_value_mins = sum(mins for m, mins in sorted_modes if m not in HIGH_VALUE)
    high_value_pct = max(0, min(100, round((total - low_value_mins) / total * 100)))
    course_pct = round(modes.get("Course-correcting", 0) / total * 100)
    delegating_pct = round(modes.get("Delegating", 0) / total * 100)
    total_str = f"{total:.0f}m" if total < 60 else f"{total / 60:.1f}h"
    n_modes = len(visible)

    hv_names = sorted(m.lower() for m in HIGH_VALUE)
    hv_list = ", ".join(hv_names[:-1]) + ", and " + hv_names[-1] if len(hv_names) > 1 else hv_names[0]
    headline = (f"{high_value_pct}% of your collaboration was high-value work "
                f"&mdash; {hv_list}.")
    sub_parts = []
    if delegating_pct > 0:
        sub_parts.append(f"Copilot automated {delegating_pct}% of routine tasks")
    if course_pct > 0:
        sub_parts.append(f"{course_pct}% was spent course-correcting AI output")
    subtitle = " &middot; ".join(sub_parts) if sub_parts else ""

    # ── SVG donut chart with adjacent labels ─────────────────────────────
    SIZE_W = 540
    SIZE_H = 300
    CX = SIZE_W // 2             # 270
    CY = SIZE_H // 2             # 150
    R = 64                       # stroke centreline radius
    SW = 28                      # stroke width (donut thickness)
    CIRC = 2 * math.pi * R       # circumference
    GAP = 1.5                    # gap between slices (in path units)

    # Background track to mask rounding-error gaps with neutral grey.
    slices_svg = (
        f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" '
        f'stroke="{C["border"]}" stroke-width="{SW}" opacity="0.4"/>'
    )

    # Build slices and collect per-slice geometry for label placement.
    label_data = []
    cumulative = 0.0
    for mode, mins in visible:
        pct = mins / total
        seg_len = pct * CIRC
        visible_len = max(0.5, seg_len - GAP)
        color = _QUALITY_COLORS.get(mode, C["muted"])
        mins_str = f"{mins:.0f}m" if mins < 60 else f"{mins / 60:.1f}h"
        pct_str = f"{pct * 100:.0f}%"
        tooltip = f"{mode} \u2014 {pct_str} \u2014 {mins_str}"
        slices_svg += (
            f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" '
            f'stroke="{color}" stroke-width="{SW}" '
            f'stroke-dasharray="{visible_len:.2f} {CIRC - visible_len:.2f}" '
            f'stroke-dashoffset="{-cumulative:.2f}" '
            f'transform="rotate(-90 {CX} {CY})">'
            f'<title>{tooltip}</title>'
            f'</circle>'
        )

        # Midpoint angle of this slice. ``phi`` is in standard math
        # coords (0 = right, +y down because SVG y increases downward).
        # We started at 12 o'clock and wrap clockwise, so:
        mid_frac = (cumulative + seg_len / 2) / CIRC
        phi = math.radians(mid_frac * 360 - 90)
        slice_outer_r = R + SW / 2
        # Initial anchor where leader exits the slice edge.
        p1_x = CX + slice_outer_r * math.cos(phi)
        p1_y = CY + slice_outer_r * math.sin(phi)
        # Initial label y at radial extension (collision-resolved later).
        init_y = CY + (slice_outer_r + 14) * math.sin(phi)
        side = "right" if math.cos(phi) >= 0 else "left"
        label_data.append({
            "mode": mode, "pct": pct, "mins": mins,
            "pct_str": pct_str, "mins_str": mins_str,
            "color": color, "p1": (p1_x, p1_y),
            "phi": phi, "side": side, "y": init_y,
        })
        cumulative += seg_len

    # ── Resolve vertical collisions on each side ─────────────────────────
    MIN_GAP = 28               # two-line label needs ~28 px
    TOP_MARGIN = 16
    BOTTOM_MARGIN = SIZE_H - 16

    for side in ("left", "right"):
        group = sorted([l for l in label_data if l["side"] == side],
                       key=lambda d: d["y"])
        # Forward pass: push down to maintain min gap.
        for i in range(1, len(group)):
            min_y = group[i - 1]["y"] + MIN_GAP
            if group[i]["y"] < min_y:
                group[i]["y"] = min_y
        # If the last label overflows the bottom, shift the whole group
        # up but never push the first above TOP_MARGIN.
        if group and group[-1]["y"] > BOTTOM_MARGIN:
            shift = group[-1]["y"] - BOTTOM_MARGIN
            for d in group:
                d["y"] = max(TOP_MARGIN, d["y"] - shift)
        # Backward pass: same forward logic in reverse to maintain gap
        # after the top-clamp from the previous step.
        for i in range(len(group) - 2, -1, -1):
            max_y = group[i + 1]["y"] - MIN_GAP
            if group[i]["y"] > max_y:
                group[i]["y"] = max_y
        # Final top-clamp
        if group and group[0]["y"] < TOP_MARGIN:
            for d in group:
                d["y"] = max(d["y"], TOP_MARGIN)

    # ── Render leader lines + labels ─────────────────────────────────────
    LABEL_X_LEFT = 10
    LABEL_X_RIGHT = SIZE_W - 10
    leaders_svg = ""
    text_svg = ""
    for d in label_data:
        p1x, p1y = d["p1"]
        side = d["side"]
        # Bend point: short radial extension just outside the slice,
        # then horizontal to the label x position.
        bend_x = CX + (R + SW / 2 + 10) * math.cos(d["phi"])
        # Constrain bend so the horizontal segment isn't backwards.
        if side == "right":
            bend_x = max(bend_x, p1x + 6)
            label_x = LABEL_X_RIGHT
            stub_x = label_x - 4
            anchor = "end"
        else:
            bend_x = min(bend_x, p1x - 6)
            label_x = LABEL_X_LEFT
            stub_x = label_x + 4
            anchor = "start"
        leaders_svg += (
            f'<polyline points="{p1x:.1f},{p1y:.1f} '
            f'{bend_x:.1f},{d["y"]:.1f} {stub_x:.1f},{d["y"]:.1f}" '
            f'fill="none" stroke="{C["border"]}" stroke-width="1"/>'
        )
        # Two-line label: name + colored % on top, minutes muted below.
        text_svg += (
            f'<text x="{label_x}" y="{d["y"] - 1}" text-anchor="{anchor}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="11" font-weight="700" fill="{C["text"]}">'
            f'{d["mode"]} '
            f'<tspan font-weight="700" fill="{d["color"]}">{d["pct_str"]}</tspan>'
            f'</text>'
            f'<text x="{label_x}" y="{d["y"] + 12}" text-anchor="{anchor}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="10" fill="{C["muted"]}">{d["mins_str"]}</text>'
        )

    # Centre labels — total active time + "ACTIVE" subtitle.
    center_svg = (
        f'<text x="{CX}" y="{CY - 2}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="24" font-weight="700" fill="{C["text"]}">{total_str}</text>'
        f'<text x="{CX}" y="{CY + 18}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="9" letter-spacing="1.5" fill="{C["muted"]}">ACTIVE</text>'
    )

    donut_svg = (
        f'<svg width="100%" viewBox="0 0 {SIZE_W} {SIZE_H}" '
        f'preserveAspectRatio="xMidYMid meet" '
        f'style="max-width:{SIZE_W}px;display:block;margin:0 auto" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="Collaboration mix donut chart">'
        f'{slices_svg}'
        f'{leaders_svg}'
        f'{text_svg}'
        f'{center_svg}'
        f'</svg>'
    )

    visual_html = f'<div style="margin-top:10px">{donut_svg}</div>'

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
        <div style="font-size:11px;color:{C['muted']};margin-bottom:4px">
          {total_str} of active collaboration across {n_modes} modes &middot; {subtitle}</div>
        {visual_html}
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
    """Look up session metrics for a goal.

    Lookup priority:
      1. Exact date|project (single-day or precise match)
      2. Exact date|<last-segment> match
      3. Non-dated project key (single-day reports)
      4. **Cross-date aggregate** for the project. This catches the common
         multi-day case where a goal is tagged with its *first* observed
         date but the project incurred credits on later dates too.
    """
    if goal_date:
        dated_key = goal_date + "|" + project
        metrics = session_metrics.get(dated_key, {})
        if metrics and (metrics.get("ai_credits") or metrics.get("tokens")):
            return metrics
        last = project.replace("\\", "/").split("/")[-1]
        metrics_alt = session_metrics.get(goal_date + "|" + last, {})
        if metrics_alt and (metrics_alt.get("ai_credits") or metrics_alt.get("tokens")):
            return metrics_alt

    # Non-dated key (single-day reports)
    metrics = session_metrics.get(project, {})
    if metrics and (metrics.get("ai_credits") or metrics.get("tokens")):
        return metrics
    last = project.replace("\\", "/").split("/")[-1]
    metrics = session_metrics.get(last, {})
    if metrics and (metrics.get("ai_credits") or metrics.get("tokens")):
        return metrics

    # Cross-date aggregate: walk all date|project keys and sum credits/tokens
    # for any whose project segment matches (either full path or last segment).
    last_seg = project.replace("\\", "/").split("/")[-1].lower()
    proj_lc = project.lower()
    agg_credits = None
    agg_tokens_by_model: dict = {}
    agg_tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0, "total": 0}
    auto_flag = False
    matched_any = False
    seen_ids = set()  # avoid double-counting alias entries
    for key, m in session_metrics.items():
        if "|" not in key:
            continue
        _date, _proj = key.split("|", 1)
        if _proj.lower() != proj_lc and _proj.replace("\\", "/").split("/")[-1].lower() != last_seg:
            continue
        if id(m) in seen_ids:
            continue
        seen_ids.add(id(m))
        matched_any = True
        if (credits := m.get("ai_credits")) is not None:
            agg_credits = (agg_credits or 0) + credits
        if isinstance(m.get("tokens"), dict):
            for k in agg_tokens:
                agg_tokens[k] += m["tokens"].get(k, 0)
        for mdl, toks in (m.get("tokens_by_model") or {}).items():
            if mdl not in agg_tokens_by_model:
                agg_tokens_by_model[mdl] = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
            for k in ("input", "output", "cache_read", "cache_creation"):
                agg_tokens_by_model[mdl][k] = agg_tokens_by_model[mdl].get(k, 0) + toks.get(k, 0)
        if m.get("auto_model_selection"):
            auto_flag = True

    if matched_any:
        return {
            "ai_credits": agg_credits,
            "tokens": agg_tokens,
            "tokens_by_model": agg_tokens_by_model,
            "auto_model_selection": auto_flag,
        }
    return {}


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


def _complexity_multiplier(metrics: dict, base_total: float) -> float:
    """Bounded complexity multiplier based on iteration depth and file scope.

    Only activates when base_total ≥ 0.50h (non-trivial sessions).
    Research basis: Alaswad et al. (2026) iterative reasoning cycles;
    Morcov et al. (2020) / Tregubov et al. (2017) scope breadth → effort overruns.
    Capped at 1.60× to keep the formula as a conservative floor.
    """
    if base_total < 0.50:
        return 1.0
    mult = 1.0
    iter_depth = metrics.get("iteration_depth", 0)
    files_count = metrics.get("files_touched_count", 0)
    # Iteration depth: high rework/debugging cycles indicate harder problems
    if iter_depth >= 2.5:
        mult += 0.10
    if iter_depth >= 5:
        mult += 0.15
    if iter_depth >= 10:
        mult += 0.10
    # File scope: broad changes require more human context-switching
    if files_count >= 5:
        mult += 0.10
    if files_count >= 10:
        mult += 0.15
    return min(mult, 1.60)


def compute_formula_estimate(metrics: dict) -> dict:
    """Deterministic effort estimate — additive log formula with active-time anchor.

    Formula: base  = max(interaction_h + lines_h + reads_h + tools_h,  active_anchor_h)
             total = base × complexity_mult
      interaction_h    = turns_h when turns > 0, else reqs_h (fallback)
      turns_h          = max(0, −0.15 + 0.67 × ln(turns + 1))
      reqs_h           = max(0, −0.10 + 0.45 × ln(reqs + 1))     [fallback]
      lines_h          = 0.40 × log₂(lines_logic ÷ 100 + 1)
      reads_h          = 0.10 × log₂(read_calls + 1)
      tools_h          = 0.07 × log₂(tool_invocations + 1)
      active_anchor_h  = active_minutes ÷ 60 × ACTIVE_ANCHOR_MULT  [5.0]
      complexity_mult  = 1.0–1.60× based on iteration_depth and files_touched_count

    active_anchor_h acts as a floor on the additive base.  Agentic sessions
    often have short bursts of typing with long stretches of reading diffs,
    reviewing tool output, and making decisions — work the additive log
    counters (turns, lines, reads, tools) systematically undercount.  The
    methodology calibration places "design / debugging / research /
    decision-making" at active × 4-6×; using 5× as the floor sits in the
    middle of that range and lets the complexity multiplier push complex
    sessions to 7-8×.
    tools_h continues to credit non-coding work (image analysis, doc
    synthesis, browser tasks) for sessions with little active-time signal.
    reqs_h is a fallback for older sessions without conversation turn data.
    complexity_mult amplifies the base for sessions with high rework depth
    or broad file scope, only when base ≥ 0.50h.
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
    active_min  = metrics.get("active_minutes", 0)

    th = _turns_h(turns)
    rqh = _reqs_h(reqs)
    lh = _lines_h(logic_lines)
    rh = _reads_h(read_calls)
    tlh = _tools_h(tools)

    # Use turns as the interaction signal; fall back to premium requests
    # for older sessions that lack conversation turn data.
    interaction_h = th if turns > 0 else rqh

    # Active-time anchor — matches "design/debugging/research" tier in the
    # methodology (active × 5). Acts as a floor, not an additional term,
    # to avoid double-counting work already captured by turns/lines/reads.
    ACTIVE_ANCHOR_MULT = 5.0
    active_anchor_h = (active_min / 60.0) * ACTIVE_ANCHOR_MULT

    # For multi-day merged goals, use pre-computed per-day sums so that
    # the component breakdown is consistent with the displayed total.
    per_day_total = metrics.get("_per_day_formula_total")
    if per_day_total is not None:
        return {
            "turns_h":         metrics.get("_per_day_turns_h", th),
            "reqs_h":          rqh,
            "lines_h":         metrics.get("_per_day_lines_h", lh),
            "reads_h":         metrics.get("_per_day_reads_h", rh),
            "tools_h":         metrics.get("_per_day_tools_h", tlh),
            "active_h":        metrics.get("_per_day_active_h", active_anchor_h),
            "interaction_h":   interaction_h,
            "complexity_mult": metrics.get("_per_day_complexity_mult", 1.0),
            "total":           per_day_total,
        }

    additive_base = interaction_h + lh + rh + tlh
    base = max(additive_base, active_anchor_h)
    base = max(base, 0.25)  # floor at 15 min
    cmult = _complexity_multiplier(metrics, base)
    total = base * cmult

    return {
        "turns_h":         th,
        "reqs_h":          rqh,
        "lines_h":         lh,
        "reads_h":         rh,
        "tools_h":         tlh,
        "active_h":        active_anchor_h,
        "interaction_h":   interaction_h,
        "complexity_mult": cmult,
        "total":           round(total * 4) / 4,  # nearest 0.25h
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

        # Formula sub-row: show which interaction signal was used.
        # When the active-time anchor dominates the additive base, show it
        # so the formula breakdown matches the displayed total.
        int_label = f"turns {_fmt_h(fe['turns_h'])}" if turns > 0 else f"reqs {_fmt_h(fe['reqs_h'])}"
        cmult = fe.get("complexity_mult", 1.0)
        cmult_label = f" &times; {cmult:.2f}" if cmult > 1.0 else ""
        additive_h = fe['turns_h'] + fe['lines_h'] + fe['reads_h'] + fe['tools_h'] if turns > 0 \
                     else fe['reqs_h'] + fe['lines_h'] + fe['reads_h'] + fe['tools_h']
        active_h_val = fe.get('active_h', 0.0)
        additive_label = f"{int_label} + lines {_fmt_h(fe['lines_h'])} + reads {_fmt_h(fe['reads_h'])} + tools {_fmt_h(fe['tools_h'])}"
        if active_h_val > additive_h and active_h_val > 0.25:
            # Active anchor wins — show it as the dominant term
            formula_parts = f"max({additive_label}, active &times; 5 = {_fmt_h(active_h_val)}){cmult_label}"
        else:
            formula_parts = f"({additive_label}){cmult_label}"

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
          browser tasks) where logic lines are zero. The request counter (legacy PRU,
          now superseded by AI Credits) serves as a fallback interaction signal when
          conversation turn data is unavailable.
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
    cmult = fe.get("complexity_mult", 1.0)
    cmult_label = f" &times; {cmult:.2f}" if cmult > 1.0 else ""

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
                             color:{C['text']}">({int_label} + lines {_fmt_h(fe['lines_h'])} + reads {_fmt_h(fe['reads_h'])} + tools {_fmt_h(fe['tools_h'])}){cmult_label}</code>
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
            +400 logic lines (+800 boilerplate), 35 reads + 15 searches, 120 tool invocations,
            iteration depth 6.2, 12 files touched</div>
          <div style="font-family:monospace;font-size:10px;line-height:1.7;color:{C['text']}">
            turns_h = max(0, &minus;0.15 + 0.67 &times; ln(23)) = <strong>1.95h</strong><br>
            lines_h = 0.40 &times; log&#8322;(400 &divide; 100 + 1) = 0.40 &times; 2.32 = <strong>0.93h</strong><br>
            reads_h = 0.10 &times; log&#8322;(50 + 1) = 0.10 &times; 5.67 = <strong>0.57h</strong><br>
            tools_h = 0.07 &times; log&#8322;(120 + 1) = 0.07 &times; 6.93 = <strong>0.49h</strong><br>
            base = 1.95 + 0.93 + 0.57 + 0.49 = <strong>3.94h</strong><br>
            complexity = 1.0 + 0.10 (ItD&ge;2.5) + 0.15 (ItD&ge;5) + 0.10 (files&ge;5) + 0.15 (files&ge;10) = <strong>1.50&times;</strong><br>
            <strong style="color:{C['accent']}">Total = 3.94 &times; 1.50 = 5.91h &rarr; 6.00h</strong>
            &nbsp;&nbsp;<span style="color:{C['muted']}">(nearest 0.25h)</span>
          </div>
        </div>"""

    # Complexity multiplier table
    cmult_table = ""
    for signal, tiers in [
        ("Iteration depth<br><span style='font-size:8px;color:{0}'>(avg edits/file)</span>".format(C['muted']),
         [("&ge; 2.5", "+10%", "Moderate rework"),
          ("&ge; 5.0", "+25%", "Heavy debugging / iteration"),
          ("&ge; 10.0", "+35%", "Extreme rework")]),
        ("Files touched<br><span style='font-size:8px;color:{0}'>(unique files)</span>".format(C['muted']),
         [("&ge; 5", "+10%", "Multi-file change"),
          ("&ge; 10", "+25%", "Broad architectural change")]),
    ]:
        for j, (threshold, boost, desc) in enumerate(tiers):
            bg = C["subtle"] if j % 2 == 0 else C["card"]
            cmult_table += (
                f'<tr style="background:{bg}">'
                f'<td style="{td}">{signal if j == 0 else ""}</td>'
                f'<td style="{td};font-weight:600">{threshold}</td>'
                f'<td style="{td};color:{C["green"]};font-weight:700">{boost}</td>'
                f'<td style="{tdm}">{desc}</td>'
                f'</tr>'
            )

    return f"""
        <div style="margin-top:16px;padding-top:12px;border-top:1px solid {C['border']}">
          <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                      color:{C['muted']};margin-bottom:6px">How the effort estimate is calculated</div>
          <div style="font-size:10px;color:{C['muted']};line-height:1.5;margin-bottom:8px">
            <code style="font-size:10px;background:{C['subtle']};padding:2px 6px;border-radius:3px;
                         color:{C['accent']}">
              total = (interaction_h + lines_h + reads_h + tools_h) &times; complexity_mult
            </code>
            &nbsp;&mdash;&nbsp; four questions added together then multiplied by a complexity factor:
            How deep was the collaboration?
            How much logic code was written (not HTML/CSS/JSON/MD)?
            How much investigation happened? How much tool execution occurred?
            The complexity multiplier (1.0&ndash;1.60&times;) amplifies the base for sessions
            with high iteration depth or broad file scope.
            Tool invocations capture non-coding work (image analysis, synthesis, browser tasks).
            The request counter (legacy PRU, now superseded by AI Credits) serves as a fallback
            interaction signal when turn data is unavailable.
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

          <div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.7px;
                      color:{C['muted']};margin-bottom:4px;margin-top:12px">Complexity multiplier
            <span style="font-weight:400;text-transform:none">(applied when base &ge; 0.50h, capped at 1.60&times;)</span></div>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid {C['border']};border-radius:5px;overflow:hidden;margin-bottom:12px">
            <tr style="background:{C['accent_lt']}">
              <th style="{th};width:22%">Signal</th>
              <th style="{th};width:14%">Threshold</th>
              <th style="{th};width:12%">Boost</th>
              <th style="{th}">Interpretation</th>
            </tr>
            {cmult_table}
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


def _ai_investment_breakdown(goals: list, sessions: list, analysis: dict,
                             total_prs: int = 0,
                             project_label_map: dict = None) -> str:
    """Three-segment breakdown of where the AI investment went.

    Each segment answers a question a manager / engineer asks once they
    know the headline credit number from the banner: *which model burned
    them, which sessions cost the most and why, and what patterns recur
    across the period?* All three segments share the same dark-banner
    visual treatment used by other top-level sections of the report, so
    each one reads as its own distinct sub-section.

    1. **Model mix** — credits + share-of-spend + request count per model,
       sorted by credits desc. Surfaces "Opus 4.6 = 60% of spend" type
       insights without making attribution claims about *outcomes per
       model* (which is much harder and would need real per-goal model
       attribution).
    2. **Top 5 most-expensive sessions** — single-session call-outs
       (project · model · credits · open-market estimate). Each row
       expands to show the aggregated burn-pattern findings observed in
       that session, so "why this session cost what it did" is answered
       in place rather than in a separate flat list.
    3. **Patterns across all sessions** — cross-cutting roll-up of every
       observed best-practice deviation, counted across the whole period.
       Surfaces signals (like compaction storms or model thrash) whose
       cost lands on *subsequent* turns and so would be misleading to
       attribute to a single expensive session.

    Skipped entirely when no AI activity recorded (keeps reports that
    cover only completion-only or unmeasured sessions clean).
    """
    if project_label_map is None:
        project_label_map = {}

    total_credits = _ai_credits_for(analysis)
    if total_credits <= 0:
        return ""

    # ── Model mix ────────────────────────────────────────────────────────
    auto = bool(analysis.get("auto_model_selection") or analysis.get("auto_model"))
    tokens_by_model = analysis.get("tokens_by_model", {}) or {}
    requests_by_model = analysis.get("requests_by_model", {}) or {}

    def _req_count(rbm: dict, model_name: str) -> int:
        """Read a request count tolerant of both shapes used historically.

        The CLI parser writes ``{model: int}`` (long-standing), while an
        earlier draft of the VS Code parser wrote ``{model: {count: int}}``.
        Cached analyses produced before this normalisation may carry the
        dict form, so accept both here.
        """
        v = rbm.get(model_name, 0)
        if isinstance(v, dict):
            return int(v.get("count", 0))
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    model_rows: list = []
    for model_name, toks in tokens_by_model.items():
        cost = _cost_by_model({model_name: toks}, auto_model=auto)
        credits = _credits(cost)
        if credits <= 0:
            continue
        req_count = _req_count(requests_by_model, model_name)
        pct = (credits / total_credits * 100) if total_credits else 0
        model_rows.append((model_name, credits, pct, req_count))
    model_rows.sort(key=lambda r: -r[1])

    # ── 3. Top 5 most-expensive sessions ─────────────────────────────────
    def _hhmm(ts: str) -> str:
        """Extract HH:MM from an ISO timestamp, tolerant of missing/short input."""
        if not ts or len(ts) < 16:
            return ""
        # ISO 8601: 'YYYY-MM-DDTHH:MM:SS...' — slice positions 11..16
        return ts[11:16]

    # Build a (project, date) → set of skills index from goals, so each
    # session in the top-N table can show the skills it actually involved.
    # Skill attribution here is *precise* per-session (no equal-split): we
    # union the top skills of every goal matching this session's project+date.
    goals_by_key: dict = {}
    for g in goals:
        key = (g.get("project", ""), g.get("date", ""))
        goals_by_key.setdefault(key, []).append(g)

    def _skills_for_session(s: dict) -> list:
        from collections import Counter
        proj = s.get("project", "")
        date = s.get("date", "")
        cands = goals_by_key.get((proj, date), [])
        # Fall back to project-only match if dated lookup misses (e.g. when
        # goal label uses last path component)
        if not cands:
            last = proj.replace("\\", "/").split("/")[-1]
            for k, gs in goals_by_key.items():
                if k[0].replace("\\", "/").split("/")[-1] == last and k[1] == date:
                    cands.extend(gs)
        seen: list = []
        for g in cands:
            top_d, top_t = _top_skills_for_goal(g)
            for sk in top_d + top_t:
                if sk not in seen:
                    seen.append(sk)
        return seen[:4]  # cap to keep cell tidy

    session_costs: list = []
    for s in sessions:
        s_credits = _ai_credits_for(s)
        if s_credits <= 0:
            continue
        raw_proj = s.get("project", "?")
        proj = project_label_map.get(raw_proj, raw_proj)
        s_model = s.get("model_used", "") or "—"
        s_market = _resolve_market_cost(s)
        session_costs.append({
            "project": proj,
            "model":   s_model,
            "credits": s_credits,
            "market":  s_market,
            "pct":     (s_credits / total_credits * 100) if total_credits else 0,
            "started": _hhmm(s.get("session_start", "")),
            "date":    s.get("date", ""),
            "skills":  _skills_for_session(s),
        })
    session_costs.sort(key=lambda x: -x["credits"])
    top_sessions = session_costs[:5]

    # Build a "when" string for every row so users can always tell sessions
    # apart, even when several share the same project label. For multi-day
    # ranges include the date; otherwise show time-of-day only.
    multi_day = len({s["date"] for s in top_sessions if s["date"]}) > 1
    for s in top_sessions:
        if multi_day and s["date"]:
            s["when"] = f"{s['date']} {s['started']}".strip()
        else:
            s["when"] = s["started"]

    # ── Match burn findings to their session of origin ───────────────────
    # Each finding carries (project, date) so we can group findings by
    # the session that produced them, then render them inline under
    # their session row. Project labels are normalised through the
    # same map used for the session table so the join is reliable.
    findings_all = analysis.get("burn_findings") or []
    findings_by_session: dict = {}
    for f in findings_all:
        raw_p = f.get("project", "")
        norm_p = project_label_map.get(raw_p, raw_p) or raw_p
        key = (norm_p, f.get("date", ""))
        findings_by_session.setdefault(key, []).append(f)

    for s in top_sessions:
        key = (s["project"], s["date"])
        raw = findings_by_session.get(key, [])
        # Aggregate per-session findings:
        #  * drop low-impact findings (< max(20 cr, 0.5% of session spend))
        #    — including flag-only kinds like compaction_storm whose direct
        #    credit attribution is 0; their real cost falls on later turns
        #    (cache invalidation, input-token re-sends) so listing them
        #    here under "why this session cost what it did" would be
        #    misleading. They still surface in the cross-session rollup
        #    below where the framing is "patterns observed", not cost,
        #  * group remaining findings by kind so repeated patterns
        #    (e.g. hot_file across multiple files) show once with combined
        #    credits and a merged evidence line,
        #  * sort by combined credits and keep the top 5 distinct kinds.
        sess_cred = s.get("credits", 0) or 0
        threshold = max(20, int(sess_cred * 0.005))
        kept: list = []
        for f in raw:
            cr = _burn_finding_credits(f)
            if cr < threshold:
                continue
            kept.append(f)

        from collections import defaultdict as _dd
        groups: dict = _dd(list)
        for f in kept:
            groups[f.get("kind", "")].append(f)

        aggregated: list = []
        for kind, group in groups.items():
            group.sort(key=lambda f: -_burn_finding_credits(f))
            total_cr = sum(_burn_finding_credits(f) for f in group)
            top = dict(group[0])  # copy so we don't mutate the source
            if len(group) > 1:
                # Concatenate up to 3 unique evidence snippets so the reader
                # can see WHAT recurred without drowning in repetition.
                evidences: list = []
                for f in group:
                    ev = (f.get("evidence", "") or "").strip()
                    if ev and ev not in evidences:
                        evidences.append(ev)
                    if len(evidences) >= 3:
                        break
                merged_ev = " &middot; ".join(evidences)
                if len(group) > 3:
                    merged_ev += f" &middot; +{len(group) - 3} more"
                top["evidence"] = f"{len(group)}\u00d7 \u2014 {merged_ev}"
            top["_total_credits"] = total_cr
            top["_count"] = len(group)
            aggregated.append(top)

        aggregated.sort(key=lambda f: -f.get("_total_credits", 0))
        s["findings"] = aggregated[:5]

    # ── Render ───────────────────────────────────────────────────────────
    # Model mix table
    if model_rows:
        mix_rows = ""
        for name, credits, pct, reqs in model_rows:
            bar_w = max(2, int(pct))
            mix_rows += f"""
        <tr>
          <td style="padding:6px 8px;font-size:11px;color:{C['text']};
                     border-bottom:1px solid {C['border']}">{name}</td>
          <td style="padding:6px 8px;font-size:11px;color:{C['text']};text-align:right;
                     border-bottom:1px solid {C['border']}">{_fmt_credits(credits)}</td>
          <td style="padding:6px 8px;border-bottom:1px solid {C['border']}">
            <table cellpadding="0" cellspacing="0" style="width:100%">
              <tr>
                <td style="width:{bar_w}%;background:{C['accent']};height:6px"></td>
                <td style="background:{C['border']};height:6px"></td>
              </tr>
            </table>
          </td>
          <td style="padding:6px 8px;font-size:11px;color:{C['muted']};text-align:right;
                     border-bottom:1px solid {C['border']}">{pct:.0f}%</td>
          <td style="padding:6px 8px;font-size:11px;color:{C['muted']};text-align:right;
                     border-bottom:1px solid {C['border']}">{reqs:,} req{'s' if reqs != 1 else ''}</td>
        </tr>"""
        mix_html = f"""
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);padding:10px 24px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                    color:rgba(255,255,255,0.7)">Model Mix</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:2px">
          Credits and request volume by model</div>
      </td></tr></table>
      <div style="padding:14px 24px">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;background:{C['bg']};
                    border:1px solid {C['border']}">
        <tr>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:left;border-bottom:1px solid {C['border']}">Model</th>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:right;border-bottom:1px solid {C['border']}">Credits</th>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:left;border-bottom:1px solid {C['border']}">Share</th>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:right;border-bottom:1px solid {C['border']}">%</th>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:right;border-bottom:1px solid {C['border']}">Requests</th>
        </tr>
        {mix_rows}
      </table>
      </div>"""
    else:
        mix_html = ""

    # Top expensive sessions table — each row expands to show the burn
    # findings observed in that session. Findings live where the spend
    # happened, so the question "why was THIS session expensive?" gets
    # answered in place instead of in a separate flat list.
    if top_sessions:
        sess_rows = ""
        for i, s in enumerate(top_sessions, 1):
            skills_html = ""
            if s.get("skills"):
                pills = "".join(
                    f'<span style="font-size:9px;color:{C["accent"]};background:{C["accent_lt"]};'
                    f'padding:1px 6px;border-radius:7px;margin-right:3px;display:inline-block;'
                    f'white-space:nowrap">{sk}</span>'
                    for sk in s["skills"]
                )
                skills_html = f'<div style="margin-top:3px">{pills}</div>'

            s_findings = s.get("findings", [])
            n_find = len(s_findings)
            sess_id = f"sess-{i}"

            # Header cell shows a chevron only when there are findings to expand.
            if n_find > 0:
                chev_html = (
                    f'<span id="{sess_id}-arrow" style="font-size:10px;'
                    f'color:{C["accent"]};margin-right:5px">&#9654;</span>'
                )
                count_pill = (
                    f'<span style="font-size:9px;color:{C["accent"]};'
                    f'background:{C["accent_lt"]};padding:1px 6px;'
                    f'border-radius:7px;margin-left:6px;font-weight:600">'
                    f'{n_find} finding{"s" if n_find != 1 else ""}</span>'
                )
                row_attrs = (
                    f' id="{sess_id}-hdr" onclick="toggleDetail(\'{sess_id}\')" '
                    f'style="cursor:pointer"'
                )
            else:
                chev_html = ""
                count_pill = ""
                row_attrs = ""

            sess_rows += f"""
        <tr{row_attrs}>
          <td style="padding:8px;font-size:11px;color:{C['muted']};
                     border-bottom:1px solid {C['border']};width:36px;vertical-align:top">
            {chev_html}#{i}
          </td>
          <td style="padding:8px;font-size:11px;color:{C['text']};
                     border-bottom:1px solid {C['border']};vertical-align:top">
            <div>{s['project']}{count_pill}</div>
            {f'<div style="font-size:10px;color:{C["muted"]};margin-top:1px">{s["when"]}</div>' if s['when'] else ''}
            {skills_html}
          </td>
          <td style="padding:8px;font-size:11px;color:{C['muted']};
                     border-bottom:1px solid {C['border']};vertical-align:top">{s['model']}</td>
          <td style="padding:8px;font-size:11px;color:{C['text']};text-align:right;
                     border-bottom:1px solid {C['border']};vertical-align:top">{_fmt_credits(s['credits'])}</td>
          <td style="padding:8px;font-size:11px;color:{C['muted']};text-align:right;
                     border-bottom:1px solid {C['border']};vertical-align:top">{s['pct']:.0f}%</td>
          <td style="padding:8px;font-size:11px;color:{C['muted']};text-align:right;
                     border-bottom:1px solid {C['border']};vertical-align:top">~${s['market']:,.2f}</td>
        </tr>"""

            if n_find > 0:
                # Inline findings rendered inside a hidden <tr> that spans all
                # 6 columns. Detail rendering mirrors the standalone-section
                # layout but is more compact (no per-row title, no source
                # citation footer) because the rows are nested inside a row
                # the reader already drilled into.
                fr_html = ""
                for f in s_findings:
                    meta = _bp_meta(f.get("kind", ""))
                    icon = meta.get("icon", "•")
                    label = meta.get("label", f.get("kind", ""))
                    source = meta.get("source", "")
                    source_url = meta.get("source_url", "")
                    cr = f.get("_total_credits", _burn_finding_credits(f))
                    n_occ = f.get("_count", 1)
                    evidence = (f.get("evidence", "") or "").strip()
                    detail = (f.get("detail", "") or "").strip()
                    advice = (f.get("advice", "") or "").strip()
                    if cr > 0 and n_occ > 1:
                        credits_str = f"{_fmt_credits(cr)} cred. &middot; {n_occ}\u00d7"
                    elif cr > 0:
                        credits_str = f"{_fmt_credits(cr)} cred."
                    elif n_occ > 1:
                        credits_str = f"{n_occ}\u00d7"
                    else:
                        credits_str = "\u2014"
                    source_html = ""
                    if source and source_url:
                        source_html = (
                            f' &middot; <a href="{source_url}" target="_blank" '
                            f'style="color:{C["muted"]};text-decoration:none;'
                            f'border-bottom:1px dotted {C["border"]}">{source}</a>'
                        )
                    elif source:
                        source_html = f' &middot; {source}'
                    fr_html += f"""
            <tr>
              <td style="vertical-align:top;padding:8px 6px 8px 0;width:26px;font-size:16px">
                {icon}
              </td>
              <td style="vertical-align:top;padding:8px 0;border-bottom:1px solid {C['border']}">
                <div style="font-size:11px;font-weight:700;color:{C['text']};margin-bottom:2px">
                  {label}: <span style="font-weight:500;color:{C['muted']}">{evidence}</span>
                </div>
                <div style="font-size:10px;color:{C['text']};line-height:1.45;margin-bottom:3px">
                  {detail}
                </div>
                <div style="font-size:10px;color:{C['accent']};line-height:1.45">
                  <strong style="color:{C['text']}">Try next time:</strong> {advice}{source_html}
                </div>
              </td>
              <td style="vertical-align:top;padding:8px 0 8px 10px;text-align:right;
                         font-size:10px;color:{C['muted']};white-space:nowrap;
                         border-bottom:1px solid {C['border']}">{credits_str}</td>
            </tr>"""

                sess_rows += f"""
        <tr id="{sess_id}-tasks" style="display:none">
          <td colspan="6" style="background:{C['subtle']};padding:10px 16px 6px;
                                 border-bottom:1px solid {C['border']}">
            <table width="100%" cellpadding="0" cellspacing="0">
              {fr_html}
            </table>
          </td>
        </tr>"""

        # ── Cross-session rollup: counts by kind across ALL sessions ──────────
        # Quick "patterns I see across the whole period" line so readers don't
        # lose the bird's-eye view when findings live inside session rows. We
        # count every kind across every session, not just the top-5, so the
        # rollup is informative even when most spend lives outside the top
        # expensive sessions. Rendered as its own segment (with the standard dark
        # banner) so it reads as a distinct cross-cutting view rather than a
        # footer to the sessions table.
        from collections import Counter as _C
        kind_counts = _C(f.get("kind", "") for f in findings_all)
        n_total_sessions = max(1, len(sessions))
        rollup_html = ""
        if kind_counts:
            parts = []
            for kind, cnt in kind_counts.most_common(8):
                meta = _bp_meta(kind)
                icon = meta.get("icon", "•")
                label = meta.get("label", kind)
                parts.append(
                    f'<span style="font-size:11px;color:{C["text"]};margin-right:14px;'
                    f'white-space:nowrap;display:inline-block;padding:2px 0">{icon} '
                    f'<strong>{cnt}</strong> '
                    f'<span style="color:{C["muted"]}">{label.lower()}</span></span>'
                )
            rollup_html = f"""
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);padding:10px 24px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                    color:rgba(255,255,255,0.7)">Patterns across all {n_total_sessions} session{'s' if n_total_sessions != 1 else ''}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:2px">
          Cross-cutting cost-saving signals observed across the period</div>
      </td></tr></table>
      <div style="padding:14px 24px;line-height:1.9">
        {"".join(parts)}
      </div>"""

        sess_html = f"""
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);padding:10px 24px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                    color:rgba(255,255,255,0.7)">Top {len(top_sessions)} most-expensive session{'s' if len(top_sessions) != 1 else ''}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:2px">
          Click a row to see why it cost what it did</div>
      </td></tr></table>
      <div style="padding:14px 24px">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;background:{C['bg']};
                    border:1px solid {C['border']}">
        <tr>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:left;border-bottom:1px solid {C['border']}">#</th>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:left;border-bottom:1px solid {C['border']}">Project</th>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:left;border-bottom:1px solid {C['border']}">Model</th>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:right;border-bottom:1px solid {C['border']}">Credits</th>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:right;border-bottom:1px solid {C['border']}">Share</th>
          <th style="padding:6px 8px;font-size:10px;color:{C['muted']};text-transform:uppercase;
                     text-align:right;border-bottom:1px solid {C['border']}">~$ market</th>
        </tr>
        {sess_rows}
      </table>
      </div>"""
    else:
        sess_html = ""
        rollup_html = ""

    return f"""
  <tr>
    <td style="background:{C['card']};padding:0;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <table width="100%" cellpadding="0" cellspacing="0"><tr><td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);padding:10px 24px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                    color:rgba(255,255,255,0.7)">AI Investment Breakdown</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:2px">
          Where {_fmt_credits(total_credits)} credits went &middot; all figures are estimates from measured tokens &times; GitHub's published per-model rates</div>
      </td></tr></table>
      {mix_html}
      {sess_html}
      {rollup_html}
    </td>
  </tr>"""


# ── Where Your Credits Went (behaviour-grounded cost-saving findings) ────────

# Catalogue is sourced from best_practices.py — each entry carries icon,
# label, ranking weight, and the published source (Anthropic / OpenAI /
# GitHub / named author) so every finding can cite its underlying guidance.
from best_practices import BP_CATALOGUE as _BP_CATALOGUE
from best_practices import get as _bp_meta


def _burn_finding_credits(f: dict) -> int:
    """Convert a burn finding's observed output tokens into credits.

    Uses the same per-model pricing the rest of the report uses (output
    rate only — the finding's `output_tokens` field is directly observed
    from assistant.message events). Returns 0 when no model is known.
    """
    tokens = int(f.get("output_tokens", 0) or 0)
    if tokens <= 0:
        return 0
    model = f.get("model") or ""
    if not model:
        return 0
    rates = _get_model_pricing(model)
    usd = (tokens / 1_000_000) * rates["output"]
    return _credits(usd)


def _render_burn_findings_html(analysis: dict, C: dict,
                               project_label_map: dict) -> str:
    """Render the 'Where Your Credits Went' section.

    Surfaces the top observed cost-saving opportunities sourced from
    `analysis['burn_findings']`. Each finding is tied to a published
    best-practice catalogued in `best_practices.BP_CATALOGUE`, so the
    row shows its source attribution alongside the observed credits.
    All credit numbers are computed from directly observed
    assistant.message output tokens (no extrapolation). Language is
    deliberately observational — "observed during", not "wasted on" —
    because the time-window attribution is a slice, not causal evidence.
    """
    findings = analysis.get("burn_findings") or []
    if not findings:
        return ""

    # Score each finding by credits + small kind weight for tie-breaking.
    scored = []
    for f in findings:
        cr = _burn_finding_credits(f)
        meta = _bp_meta(f.get("kind", ""))
        scored.append((cr, meta.get("weight", 0), f))
    # Sort by credits desc, then weight, then keep original order.
    scored.sort(key=lambda x: (-x[0], -x[1]))

    # Take top N, prefer at most 2 per kind so the list shows variety
    # (a single hot session can otherwise produce 6 hot_file findings
    # and crowd out other patterns the user might benefit from seeing).
    # We split slots: 5 for credit-ranked findings plus reserved slots
    # for flag-only kinds (compaction_storm, broad_search_repeat,
    # subagent_missed, no_verification, model_thrash) so they always
    # surface as behavioural signals even when their direct credit
    # attribution is low.
    from collections import Counter
    per_kind = Counter()
    picked = []
    seen_ids = set()
    for cr, w, f in scored:
        kind = f.get("kind", "")
        if per_kind[kind] >= 2:
            continue
        per_kind[kind] += 1
        picked.append((cr, f))
        seen_ids.add(id(f))
        if len(picked) >= 5:
            break

    # Reserve up to 3 extra slots for flag-only kinds the user benefits
    # from seeing — even if their observed credits are smaller than
    # other patterns above.
    flag_only_kinds = (
        "compaction_storm", "broad_search_repeat", "subagent_missed",
        "no_verification", "model_thrash",
    )
    for cr, w, f in scored:
        if len(picked) >= 9:
            break
        if id(f) in seen_ids:
            continue
        if f.get("kind") not in flag_only_kinds:
            continue
        if per_kind[f.get("kind", "")] >= 2:
            continue
        per_kind[f.get("kind", "")] += 1
        picked.append((cr, f))
        seen_ids.add(id(f))

    # Fill any remaining slots from the credit-ranked list (skipping
    # already-picked items). Skip kinds already represented twice so the
    # tail of the list shows variety rather than another hot_file/fail_loop.
    for cr, w, f in scored:
        if len(picked) >= 9:
            break
        if id(f) in seen_ids:
            continue
        if per_kind[f.get("kind", "")] >= 2:
            continue
        per_kind[f.get("kind", "")] += 1
        picked.append((cr, f))
        seen_ids.add(id(f))

    if not picked:
        return ""

    rows_html = ""
    for cr, f in picked:
        meta = _bp_meta(f.get("kind", ""))
        icon = meta.get("icon", "•")
        label = meta.get("label", f.get("kind", ""))
        source = meta.get("source", "")
        source_url = meta.get("source_url", "")
        # Project label normalisation so display matches the rest of the report
        raw_proj = f.get("project", "")
        proj = project_label_map.get(raw_proj, raw_proj) or raw_proj
        date = f.get("date", "")
        evidence = (f.get("evidence", "") or "").strip()
        detail = (f.get("detail", "") or "").strip()
        advice = (f.get("advice", "") or "").strip()
        model = f.get("model", "")
        credits_str = (
            f"{_fmt_credits(cr)} observed cred."
            if cr > 0 else "no token cost"
        )
        # Build a compact byline: project · date · model (when present)
        byline_parts = [proj] if proj else []
        if date:
            byline_parts.append(date)
        if model:
            byline_parts.append(model)
        byline = " &middot; ".join(byline_parts)

        # Source citation: clickable when we have a URL, plain text otherwise.
        source_html = ""
        if source:
            if source_url:
                source_html = (
                    f'<a href="{source_url}" target="_blank" '
                    f'style="color:{C["muted"]};text-decoration:none;'
                    f'border-bottom:1px dotted {C["border"]}">{source}</a>'
                )
            else:
                source_html = source

        rows_html += f"""
        <tr>
          <td style="vertical-align:top;padding:10px 8px 10px 0;width:30px;font-size:18px">
            {icon}
          </td>
          <td style="vertical-align:top;padding:10px 0;border-bottom:1px solid {C['border']}">
            <div style="font-size:11px;font-weight:700;color:{C['text']};margin-bottom:2px">
              {label}: <span style="font-weight:500;color:{C['muted']}">{evidence}</span>
            </div>
            <div style="font-size:10px;color:{C['muted']};margin-bottom:4px">
              {byline}{(' &middot; based on ' + source_html) if source_html else ''}
            </div>
            <div style="font-size:10px;color:{C['text']};line-height:1.45;margin-bottom:4px">
              {detail}
            </div>
            <div style="font-size:10px;color:{C['accent']};line-height:1.45">
              <strong style="color:{C['text']}">Try next time:</strong> {advice}
            </div>
          </td>
          <td style="vertical-align:top;padding:10px 0 10px 12px;text-align:right;
                     font-size:11px;color:{C['muted']};white-space:nowrap;
                     border-bottom:1px solid {C['border']}">
            {credits_str}
          </td>
        </tr>"""

    return f"""
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-top:18px;margin-bottom:4px">
        Where Your Credits Went
      </div>
      <div style="font-size:10px;color:{C['muted']};margin-bottom:8px;line-height:1.5">
        Observable patterns in your sessions that coincided with credit
        spend, ranked by impact. Each finding is matched to a published
        best-practice from Anthropic, OpenAI, or GitHub &mdash; click
        the source link to read the underlying guidance. Credits shown
        are output-token credits directly observed in the event log
        during each pattern's window &mdash; not causal claims, just
        signal. The "try next time" suggestions are pre-session or
        in-session behaviours, not mid-session model switches.
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
        {rows_html}
      </table>"""


# ── Credit Drivers (what consumed credits & how to work better) ──────────────

# Map model name (longest-prefix matched) → recommended "next-tier-down"
# model for downshift recommendations on lightweight sessions. The
# heuristic: pick a model in the same family with materially lower
# output pricing that can still handle short Q&A / small-edit work.
# Used by the lightweight-session downshift callout.
_DOWNSHIFT_TARGET = {
    # Anthropic: opus → sonnet → haiku
    "claude-opus":    "claude-sonnet-4.5",
    "claude-sonnet":  "claude-haiku-4.5",
    # OpenAI: large → standard → mini
    "gpt-5.5":        "gpt-5.4",
    "gpt-5.4":        "gpt-5.4-mini",
    "gpt-5.3-codex":  "gpt-5-mini",
    "gpt-5.2":        "gpt-5-mini",
    # Gemini: pro → flash
    "gemini-3.1-pro": "gemini-3-flash",
    "gemini-2.5-pro": "gemini-2.5-flash",
}


def _downshift_model(model_name: str) -> str:
    """Return the recommended cheaper alternative model, or '' if none."""
    name = (model_name or "").lower()
    best = ""
    target = ""
    for prefix, alt in _DOWNSHIFT_TARGET.items():
        if name.startswith(prefix) and len(prefix) > len(best):
            best = prefix
            target = alt
    return target


def _is_lightweight_session(s: dict) -> bool:
    """Classify a session as lightweight Q&A / small-edit work.

    Lightweight = signals the work didn't need a top-tier reasoning model:
    short total output, few tool invocations, at most one file modified.
    The thresholds are conservative — we want false negatives (miss some
    downshift candidates) over false positives (recommend downshifting
    work that genuinely needed Opus).
    """
    tok = s.get("tokens") or {}
    out_tok = tok.get("output", 0) if isinstance(tok, dict) else 0
    tools = s.get("tool_invocations") or 0
    files = s.get("files_touched") or []
    return out_tok <= 2000 and tools <= 5 and len(files) <= 1


# Map file extensions → human language label. Conservative coverage of the
# languages we actually see in Copilot sessions; anything else falls into
# "Other" so the chart stays legible.
_EXT_TO_LANG = {
    "py":   "Python",
    "js":   "JavaScript", "mjs": "JavaScript", "cjs": "JavaScript",
    "jsx":  "JavaScript", "ts":  "TypeScript", "tsx": "TypeScript",
    "go":   "Go",
    "rs":   "Rust",
    "java": "Java",
    "kt":   "Kotlin",
    "rb":   "Ruby",
    "php":  "PHP",
    "cs":   "C#",
    "c":    "C", "h": "C",
    "cpp":  "C++", "hpp": "C++", "cc": "C++", "cxx": "C++",
    "swift": "Swift",
    "scala": "Scala",
    "sh":   "Shell", "bash": "Shell", "zsh": "Shell", "ps1": "PowerShell",
    "sql":  "SQL",
    "html": "HTML", "htm": "HTML", "css": "CSS", "scss": "CSS", "sass": "CSS",
    "md":   "Markdown", "rst": "Markdown", "txt": "Markdown",
    "json": "Config/Data", "yaml": "Config/Data", "yml": "Config/Data",
    "toml": "Config/Data", "ini": "Config/Data", "xml": "Config/Data",
    "csv":  "Config/Data", "env": "Config/Data",
}


def _classify_lang(path: str) -> str:
    p = (path or "").lower().replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    # Special-case dotfiles + common no-extension build files
    if name in ("dockerfile", "makefile", "rakefile", "gemfile", "procfile"):
        return "Config/Data"
    if "." not in name:
        return "Other"
    ext = name.rsplit(".", 1)[-1]
    return _EXT_TO_LANG.get(ext, "Other")


def _credit_drivers(goals: list, sessions: list, analysis: dict) -> str:
    """Show *what* consumed credits and turn it into actionable feedback.

    Two sub-sections (skill split was removed — at session-level billing
    granularity any per-skill split degenerates to equal arithmetic and
    isn't honest signal):

    A. **Credits by language** — session credits split proportionally
       across the languages of files *modified* in that session. Approximate
       (file-count weighted; we don't have per-file line attribution) but
       grounded in real edits, not reads.
    B. **Working patterns** — auto-generated insights from session-level
       signals (iteration depth, no-commit sessions, reads-to-edits ratio,
       long sessions, cache reuse). Each callout is a precise count or
       ratio derived from harvested data.
    """
    total_credits = _ai_credits_for(analysis)
    if total_credits <= 0:
        return ""

    # ── A. Credits by language ───────────────────────────────────────────
    # Each session's credits get split proportionally across the language
    # mix of files it modified.
    lang_credits: dict = {}
    for s in sessions:
        sc = _ai_credits_for(s)
        if sc <= 0:
            continue
        files = s.get("files_touched") or []
        if not files:
            lang_credits["No files modified"] = lang_credits.get("No files modified", 0) + sc
            continue
        counts: dict = {}
        for f in files:
            lang = _classify_lang(f)
            counts[lang] = counts.get(lang, 0) + 1
        n_total = sum(counts.values())
        for lang, n in counts.items():
            lang_credits[lang] = lang_credits.get(lang, 0) + sc * (n / n_total)
    lang_rows = sorted(lang_credits.items(), key=lambda x: -x[1])[:6]

    # ── B. Efficiency callouts ───────────────────────────────────────────
    callouts: list = []

    # 1. High iteration depth → "same files edited many times"
    deep_iter = [s for s in sessions
                 if (s.get("iteration_depth") or 0) >= 5 and _ai_credits_for(s) > 0]
    if deep_iter:
        deep_credits = sum(_ai_credits_for(s) for s in deep_iter)
        callouts.append((
            "warn",
            f"{len(deep_iter)} session{'s' if len(deep_iter) != 1 else ''} edited the same files "
            f"5+ times on average — {_fmt_credits(deep_credits)} credits "
            f"({deep_credits / total_credits * 100:.0f}% of total). "
            "Smaller, focused asks often land changes in fewer turns."
        ))

    # 2. No-commit exploration tax — sessions with credits but no git ops
    no_commit = [s for s in sessions
                 if _ai_credits_for(s) > 0 and not s.get("git_ops")]
    if no_commit:
        nc_credits = sum(_ai_credits_for(s) for s in no_commit)
        nc_pct = nc_credits / total_credits * 100
        if nc_pct >= 15:
            callouts.append((
                "info",
                f"{nc_pct:.0f}% of credits ({_fmt_credits(nc_credits)}) went to "
                f"{len(no_commit)} session{'s' if len(no_commit) != 1 else ''} with no commit or PR — "
                "exploration / scaffolding work. Worth tracking if the trend grows."
            ))

    # 3. Read-heavy sessions — reads ≥ 4× edits
    read_heavy = [s for s in sessions
                  if (s.get("reads") or 0) >= 4 * max(s.get("edits") or 0, 1)
                  and (s.get("reads") or 0) >= 10
                  and _ai_credits_for(s) > 0]
    if read_heavy:
        rh_credits = sum(_ai_credits_for(s) for s in read_heavy)
        if rh_credits / total_credits >= 0.15:
            callouts.append((
                "info",
                f"{len(read_heavy)} session{'s' if len(read_heavy) != 1 else ''} were read-heavy "
                f"(4×+ more reads than edits) — {_fmt_credits(rh_credits)} credits. "
                "Indexing or summarising upfront can cut repeated context loads."
            ))

    # 4. Long sessions hog — top quartile by turns consumed disproportionate share
    sess_with_credits = [s for s in sessions if _ai_credits_for(s) > 0]
    if len(sess_with_credits) >= 4:
        sorted_by_turns = sorted(sess_with_credits,
                                 key=lambda s: -(s.get("substantive_turns")
                                                 or s.get("conversation_turns") or 0))
        top_q = sorted_by_turns[: max(1, len(sorted_by_turns) // 4)]
        tq_credits = sum(_ai_credits_for(s) for s in top_q)
        tq_pct = tq_credits / total_credits * 100
        if tq_pct >= 60:
            callouts.append((
                "warn",
                f"Top {len(top_q)} longest session{'s' if len(top_q) != 1 else ''} consumed "
                f"{tq_pct:.0f}% of credits ({_fmt_credits(tq_credits)}). "
                "Breaking long agent runs into shorter, scoped tasks reduces context bloat."
            ))

    # 5. Cache-miss heuristic (CLI-only — VS Code doesn't expose cache tokens).
    # Guard: only fire when there's evidence cache fields are populated
    # (cache_creation > 0 means the provider IS writing to cache and we
    # have visibility). Without that guard, every VS Code report would
    # falsely claim "0% cache reuse".
    agg_tokens = analysis.get("tokens", {}) or {}
    if isinstance(agg_tokens, dict):
        inp = agg_tokens.get("input", 0)
        cache_r = agg_tokens.get("cache_read", 0)
        cache_w = agg_tokens.get("cache_creation", 0)
        if cache_w > 0 and inp + cache_r >= 50_000:
            cache_pct = cache_r / (inp + cache_r) * 100 if (inp + cache_r) else 0
            if cache_pct < 25:
                callouts.append((
                    "info",
                    f"Cache reuse was {cache_pct:.0f}% — most prompts re-sent full context. "
                    "Keeping prompts stable across turns lets the provider's prompt cache do more work."
                ))

    # 6. Lightweight sessions on heavy models — model-default recommendation.
    # We don't recommend mid-session model switching (impractical); instead
    # we surface the *class* of sessions for which the user could pick a
    # cheaper default model at session start (or rely on auto-model
    # selection which captures this automatically). Only fires when the
    # estimated saving is material — small days won't trigger noise.
    lw_savings: dict = {}  # (current_model → savings) for grouping
    lw_count = 0
    lw_current_credits = 0.0
    for s in sessions:
        if not _is_lightweight_session(s):
            continue
        sc = _ai_credits_for(s)
        if sc <= 0:
            continue
        model = s.get("model_used", "") or ""
        if model.lower() in _INCLUDED_MODELS:
            continue  # already free
        target = _downshift_model(model)
        if not target:
            continue
        tbm = s.get("tokens_by_model") or {}
        # If the session is single-model (typical for chat), recompute the
        # cost under the downshift target. If it's mixed, we still apply
        # the downshift only to the matching model's tokens.
        recomputed = 0.0
        for mdl, toks in tbm.items():
            if mdl == model:
                t = _get_model_pricing(target)
                recomputed += (
                    toks.get("input", 0)          * t["input"]
                  + toks.get("output", 0)         * t["output"]
                  + toks.get("cache_read", 0)     * t["cache_read"]
                  + toks.get("cache_creation", 0) * t["cache_creation"]
                ) / 1_000_000
            else:
                # Leave other models in the session untouched
                recomputed += _cost_by_model({mdl: toks},
                                             auto_model=bool(s.get("auto_model_selection")))
        savings_credits = max(0, _credits(_resolve_market_cost(s) - recomputed))
        if savings_credits <= 0:
            continue
        lw_count += 1
        lw_current_credits += sc
        key = (model, target)
        lw_savings[key] = lw_savings.get(key, 0) + savings_credits

    if lw_savings:
        total_save = sum(lw_savings.values())
        # Only emit if the saving is meaningful relative to total spend
        if total_save / total_credits >= 0.05 or total_save >= 500:
            # Build a "from → to" hint listing the dominant downshift pair
            top_pair = max(lw_savings.items(), key=lambda x: x[1])
            from_m, to_m = top_pair[0]
            callouts.append((
                "warn",
                f"{lw_count} lightweight session{'s' if lw_count != 1 else ''} "
                f"(short output, few tools, ≤1 file edited) ran on a top-tier model "
                f"— ~{_fmt_credits(lw_current_credits)} spent, "
                f"~{_fmt_credits(total_save)} savings estimated if defaulted to a smaller model "
                f"(e.g. {from_m} → {to_m}). "
                "Set a cheaper default for Q&amp;A sessions, or enable auto-model selection."
            ))

    # 7. Auto-model selection off — flat 10% nudge.
    # If the user hasn't enabled auto-model selection and there's any
    # credit spend on non-included models, the 10% discount is a free win
    # with no behaviour change required.
    auto_on = bool(analysis.get("auto_model_selection") or analysis.get("auto_model"))
    if not auto_on:
        # Estimate the 10% savings on the portion of credits NOT already
        # on included (free) models. We can't perfectly attribute included
        # vs non-included from the aggregate, but we can use the tokens_by_model
        # breakdown to be precise.
        non_inc_credits = 0
        tbm = analysis.get("tokens_by_model") or {}
        for mdl, toks in tbm.items():
            if mdl.lower() in _INCLUDED_MODELS:
                continue
            non_inc_credits += _credits(_cost_by_model({mdl: toks}, auto_model=False))
        auto_savings = int(round(non_inc_credits * AUTO_MODEL_DISCOUNT))
        if auto_savings >= 100:  # only nudge when material
            callouts.append((
                "info",
                f"Auto-model selection appears to be off. Enabling it would apply a "
                f"flat 10% discount on paid-plan model usage — estimated "
                f"~{_fmt_credits(auto_savings)} credits saved this period, with no change "
                "to how you start sessions."
            ))

    # ── Render ───────────────────────────────────────────────────────────
    def _bar_table(rows: list[tuple], unit: str) -> str:
        if not rows:
            return f'<div style="font-size:11px;color:{C["muted"]};margin:6px 0">No data.</div>'
        max_c = max(c for _, c in rows) or 1
        out = ""
        for label, credits in rows:
            pct_total = credits / total_credits * 100
            bar_w = max(2, int(credits / max_c * 100))
            out += f"""
        <tr>
          <td style="padding:6px 8px;font-size:11px;color:{C['text']};
                     border-bottom:1px solid {C['border']};width:32%">{label}</td>
          <td style="padding:6px 8px;border-bottom:1px solid {C['border']}">
            <table cellpadding="0" cellspacing="0" style="width:100%">
              <tr>
                <td style="width:{bar_w}%;background:{C['accent']};height:6px"></td>
                <td style="background:{C['border']};height:6px"></td>
              </tr>
            </table>
          </td>
          <td style="padding:6px 8px;font-size:11px;color:{C['text']};text-align:right;
                     border-bottom:1px solid {C['border']};width:14%">{_fmt_credits(int(round(credits)))}</td>
          <td style="padding:6px 8px;font-size:11px;color:{C['muted']};text-align:right;
                     border-bottom:1px solid {C['border']};width:10%">{pct_total:.0f}%</td>
        </tr>"""
        return f"""
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;background:{C['bg']};
                    border:1px solid {C['border']}">
        {out}
      </table>"""

    skill_html = ""

    lang_html = f"""
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-top:6px;margin-bottom:6px">
        Credits by language <span style="font-weight:400;text-transform:none;letter-spacing:0;color:{C['muted']}">
          — proportional to files modified per session</span></div>
      {_bar_table(lang_rows, 'credits')}""" if lang_rows else ""

    if callouts:
        bullet_rows = ""
        for kind, text in callouts:
            icon = "&#9888;" if kind == "warn" else "&#128161;"  # ⚠ or 💡
            color = C["text"] if kind == "warn" else C["muted"]
            bullet_rows += f"""
        <tr>
          <td style="padding:6px 8px;font-size:13px;color:{C['accent']};
                     vertical-align:top;width:22px">{icon}</td>
          <td style="padding:6px 8px;font-size:11px;color:{color};line-height:1.5">{text}</td>
        </tr>"""
        callout_html = f"""
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-top:18px;margin-bottom:6px">
        Working patterns to watch <span style="font-weight:400;text-transform:none;letter-spacing:0;color:{C['muted']}">
          — auto-detected from session signals</span></div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:{C['bg']};border:1px solid {C['border']}">
        {bullet_rows}
      </table>"""
    else:
        callout_html = f"""
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;
                  color:{C['muted']};margin-top:18px;margin-bottom:6px">Working patterns to watch</div>
      <div style="font-size:11px;color:{C['muted']};padding:8px 4px">
        No notable patterns detected — sessions look balanced.</div>"""

    return f"""
  <tr>
    <td style="background:{C['card']};padding:14px 24px;
               border-left:1px solid {C['border']};border-right:1px solid {C['border']}">
      <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
                  color:{C['text']};margin-bottom:4px">Credit Drivers</div>
      <div style="font-size:11px;color:{C['muted']};margin-bottom:8px">
        What consumed credits and patterns to consider for next time.
        Language split is <em>approximate</em> (weighted by file count, not
        per-message billing). Working-pattern callouts are exact counts and
        ratios from harvested session signals.</div>
      {skill_html}
      {lang_html}
      {callout_html}
    </td>
  </tr>"""


def _activity_bar(analysis: dict) -> str:
    """Show pricing comparison (fixed vs market), AI credits, token breakdown."""
    tokens       = analysis.get("tokens", {})
    premium_req  = analysis.get("premium_requests", 0)
    total_api_ms = analysis.get("total_api_ms", 0)
    files_mod    = analysis.get("files_modified", [])

    in_tok  = tokens.get("input", 0)
    out_tok = tokens.get("output", 0)
    cr_tok  = tokens.get("cache_read", 0)
    cc_tok  = tokens.get("cache_creation", 0)
    total_t = tokens.get("total", 0) or 1

    # Market rate: honours per-model pricing + auto-model discount.
    market_cost = _resolve_market_cost(analysis)
    ai_credits  = _ai_credits_for(analysis)
    plan        = analysis.get("plan") or ""
    auto_model  = bool(analysis.get("auto_model_selection") or analysis.get("auto_model"))

    # Models used — build display label
    tokens_by_model = analysis.get("tokens_by_model", {})
    models_used = sorted(tokens_by_model.keys()) if tokens_by_model else []
    if models_used:
        model_label = ", ".join(models_used)
    else:
        model_label = analysis.get("model_used", "") or "unknown"

    # Copilot seat cost intentionally omitted — actual GitHub bill depends on
    # plan, included allowance, auto-model discount, and surface (Chat vs CLI
    # vs API), none of which we can observe reliably from local logs.

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
        <span style="color:{C['muted']}">Open-market API value</span> <strong>~${market_cost:.2f}</strong>
        <span style="font-size:10px;color:{C['muted']}">(est. from published per-model rates)</span>
      </span>
    </td>
  </tr>"""

    requests_cell = (f"""
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">Requests</span> <strong>{premium_req}</strong>
        &nbsp;<span style="font-size:10px;color:{C['muted']}">(legacy PRU)</span>
      </span>
      &nbsp;&nbsp;·&nbsp;&nbsp;""" if premium_req else "")

    return pricing_row + f"""
  <tr>
    <td style="background:{C['subtle']};padding:9px 24px;
               border:1px solid {C['border']};border-top:none">
      <span style="font-size:10px;font-weight:700;text-transform:uppercase;
                   letter-spacing:0.7px;color:{C['muted']};margin-right:10px">Copilot</span>
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">AI credits</span> <strong>{_fmt_credits(ai_credits)}</strong>
        &nbsp;<span style="font-size:10px;color:{C['muted']}">(~${ai_credits * USD_PER_CREDIT:.2f}{', auto-model −10%' if auto_model else ''}{f', {plan} plan' if plan else ''})</span>
      </span>
      &nbsp;&nbsp;·&nbsp;&nbsp;
      {requests_cell}
      <span style="font-size:11px;color:{C['text']}">
        <span style="color:{C['muted']}">AI compute time</span> <strong>{api_time_str}</strong>
        &nbsp;<span style="font-size:10px;color:{C['muted']}">(cumulative across parallel requests · {model_label})</span>
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
        top_d, _     = _top_skills_for_goal(g)
        skill_pills  = _pills(top_d, [])
        task_sub     = f'{n} task{"s" if n != 1 else ""}'
        doc_html     = _doc_refs_html(g.get("docs_referenced", []))
        date_badge   = _date_badge(g.get("date", ""))
        tasks        = g.get("tasks", [])
        # Resolve AI credits for this goal from session metrics
        project       = g.get("project", "")
        goal_date     = g.get("date", "")
        metrics       = _resolve_metrics(project, session_metrics, goal_date)
        goal_credits  = _ai_credits_for(metrics)
        # Always show a credits cell — empty looks broken. Render "0"
        # explicitly when a goal really cost nothing (e.g., all included
        # models or no token data harvested for that project).
        credits_html  = _fmt_credits(goal_credits) if goal_credits > 0 else "0"
        credits_color = C['green'] if goal_credits > 0 else C['muted']
        credits_cell  = f"""
          <td style="padding:10px 8px;border-bottom:1px solid {C['border']};
                     vertical-align:middle;text-align:right;width:10%">
            <div style="font-size:14px;font-weight:700;color:{credits_color}">{credits_html}</div>
            <div style="font-size:10px;color:{C['muted']};margin-top:1px">credits</div>
          </td>"""
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
                     vertical-align:top;width:40%">
            <div style="font-size:12px;font-weight:600;color:{C['text']};line-height:1.35">
              <span id="{gid}-arrow" style="font-size:10px;color:{C['accent']};
                                            margin-right:5px">&#9654;</span>
              {date_badge}{g.get('label') or g.get('title', '')}
            </div>
            {f'<div style="margin-top:5px">{doc_html}</div>' if doc_html else ''}
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid {C['border']};
                     vertical-align:middle;width:34%">
            <div>{skill_pills}</div>
            <div style="font-size:10px;color:{C['muted']};margin-top:5px">{task_sub}</div>
          </td>
          {credits_cell}
          <td style="padding:10px 8px;border-bottom:1px solid {C['border']};
                     vertical-align:middle;text-align:right;width:12%">
            <div style="font-size:16px;font-weight:700;color:{C['accent']}">{h}</div>
            <div style="font-size:10px;color:{C['muted']};margin-top:1px">human est.</div>
          </td>
        </tr>
        <tr id="{gid}-tasks" style="display:none">
          <td colspan="5" style="padding:0 8px 12px;background:{C['bg']}">
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
          <td colspan="5" style="padding:0;border-bottom:1px solid {C['border']}">>
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
                  max_width: int = 1080) -> str:
    goals      = analysis.get("goals", [])

    # Render the goals exactly as provided in the analyzed data so the saved
    # report stays consistent with any CLI summary already produced for this run.
    # Any formula-floor normalization must happen before rendering, not here.

    # Sort goals once by hours descending so all sections are consistent
    goals      = sorted(goals, key=lambda g: g.get("human_hours", 0), reverse=True)
    narrative  = analysis.get("day_narrative", "")
    headline   = analysis.get("headline", f"Daily Report — {target_date}")
    focus      = analysis.get("primary_focus", "")
    n_sessions = analysis.get("sessions_count", len(sessions))
    projects   = sorted({s["project"] for s in sessions})

    total_human_h = sum(g.get("human_hours", 0) for g in goals)
    total_tasks   = sum(len(g.get("tasks", [])) for g in goals)
    total_credits = _ai_credits_for(analysis)
    total_cred_fmt = _fmt_credits(total_credits) if total_credits > 0 else ""
    total_prs     = sum(s.get("git_ops", []).count("pr")     for s in sessions)
    total_commits = sum(s.get("git_ops", []).count("commit") for s in sessions)

    totals_row= f"""
        <tr style="background:{C['accent_lt']}">
          <td style="padding:10px 16px;border-top:2px solid {C['border']}"></td>
          <td style="padding:10px 16px;border-top:2px solid {C['border']};
                     font-size:12px;font-weight:700;color:{C['accent']}">
            {len(goals)} project{'s' if len(goals) != 1 else ''} &nbsp;·&nbsp; {total_tasks} tasks total
          </td>
          <td style="padding:10px 16px;border-top:2px solid {C['border']}"></td>
          <td style="padding:10px 16px;border-top:2px solid {C['border']};
                     text-align:right;font-size:14px;font-weight:700;color:{C['green']}">
            {total_cred_fmt}
          </td>
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
<style>
  /* Browser-friendly responsive overrides */
  body {{ -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }}
  .report-wrap {{ max-width: {max_width}px; width: 100%; margin: 0 auto; }}
  @media screen and (max-width: 640px) {{
    .report-wrap {{ max-width: 100% !important; }}
  }}
  /* Smooth collapsible toggles */
  details summary {{ cursor: pointer; user-select: none; }}
  details summary::-webkit-details-marker {{ display: none; }}
  /* Scrollbar styling for browser */
  ::-webkit-scrollbar {{ width: 8px; }}
  ::-webkit-scrollbar-track {{ background: {C['bg']}; }}
  ::-webkit-scrollbar-thumb {{ background: {C['border']}; border-radius: 4px; }}
  ::-webkit-scrollbar-thumb:hover {{ background: {C['muted']}; }}
</style>
{js}
</head>
<body style="margin:0;padding:0;background:{C['bg']};
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;color:{C['text']}">

<table width="100%" cellpadding="0" cellspacing="0" style="background:{C['bg']};padding:24px 16px">
<tr><td align="center">
<table class="report-wrap" width="{max_width}" cellpadding="0" cellspacing="0" style="max-width:{max_width}px;width:100%">

  <!-- HEADER -->
  <tr>
    <td bgcolor="#24292f" style="background:linear-gradient(135deg,#24292f,#1b1f23);border-radius:9px 9px 0 0;padding:22px 24px">
     <table cellpadding="0" cellspacing="0" style="width:100%"><tr>
      <td valign="top" style="width:62px;padding-right:16px">
        <img src="{LOGO_DATA_URI}" width="48" height="48" alt=""
             style="display:block;width:48px;height:48px;border:0;border-radius:11px" />
      </td>
      <td valign="top">
      <div style="font-size:10px;color:rgba(255,255,255,0.6);letter-spacing:1.2px;
                  text-transform:uppercase;margin-bottom:4px">
        {target_date} &nbsp;·&nbsp; GitHub Copilot Impact Report
      </div>
      <div style="font-size:20px;font-weight:700;color:#fff;line-height:1.3"><svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" style="vertical-align:middle;margin-right:10px"><path fill="white" d="M23.922 16.992c-.861 1.495-5.859 5.023-11.922 5.023-6.063 0-11.061-3.528-11.922-5.023A.641.641 0 0 1 0 16.736v-2.869a.841.841 0 0 1 .053-.22c.372-.935 1.347-2.292 2.605-2.656.167-.429.414-1.055.644-1.517a10.195 10.195 0 0 1-.052-1.086c0-1.331.282-2.499 1.132-3.368.397-.406.89-.717 1.474-.952 1.399-1.136 3.392-2.093 6.122-2.093 2.731 0 4.767.957 6.166 2.093.584.235 1.077.546 1.474.952.85.869 1.132 2.037 1.132 3.368 0 .368-.014.733-.052 1.086.23.462.477 1.088.644 1.517 1.258.364 2.233 1.721 2.605 2.656a.832.832 0 0 1 .053.22v2.869a.641.641 0 0 1-.078.256ZM12.172 11h-.344a4.323 4.323 0 0 1-.355.508C10.703 12.455 9.555 13 7.965 13c-1.725 0-2.989-.359-3.782-1.259a2.005 2.005 0 0 1-.085-.104L4 11.741v6.585c1.435.779 4.514 2.179 8 2.179 3.486 0 6.565-1.4 8-2.179v-6.585l-.098-.104s-.033.045-.085.104c-.793.9-2.057 1.259-3.782 1.259-1.59 0-2.738-.545-3.508-1.492a4.323 4.323 0 0 1-.355-.508h-.016.016Zm.641-2.935c.136 1.057.403 1.913.878 2.497.442.544 1.134.938 2.344.938 1.573 0 2.292-.337 2.657-.751.384-.435.558-1.15.558-2.361 0-1.14-.243-1.847-.705-2.319-.477-.488-1.319-.862-2.824-1.025-1.487-.161-2.192.138-2.533.529-.269.307-.437.808-.438 1.578v.021c0 .265.021.562.063.893Zm-1.626 0c.042-.331.063-.628.063-.894v-.02c-.001-.77-.169-1.271-.438-1.578-.341-.391-1.046-.69-2.533-.529-1.505.163-2.347.537-2.824 1.025-.462.472-.705 1.179-.705 2.319 0 1.211.175 1.926.558 2.361.365.414 1.084.751 2.657.751 1.21 0 1.902-.394 2.344-.938.475-.584.742-1.44.878-2.497Z"/><path fill="white" d="M14.5 14.25a1 1 0 0 1 1 1v2a1 1 0 0 1-2 0v-2a1 1 0 0 1 1-1Zm-5 0a1 1 0 0 1 1 1v2a1 1 0 0 1-2 0v-2a1 1 0 0 1 1-1Z"/></svg>{headline}</div>
      </td>
     </tr></table>
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

  {_kpi_section(goals, analysis, n_sessions, total_prs, total_commits)}

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
      <div style="font-size:10px;color:{C['muted']};margin-bottom:10px;line-height:1.5">
        <strong style="color:{C['text']}">Credits</strong> = the unit GitHub now bills in
        (1 credit = $0.01). Each request consumes credits at a model-specific rate
        (e.g. Claude Opus is ~30× more credit-intensive per token than GPT-4.1).
        Tokens are the underlying input/output units the model processed; credits =
        tokens &times; per-model rate. A project showing
        <strong style="color:{C['muted']}">0 credits</strong> means one of:
        (a) it ran entirely on included models (GPT-4.1, GPT-4.1 mini — no credit
        charge), (b) the session log didn't expose any token data (older VS Code
        sessions, or sessions killed before any assistant message), or
        (c) only completions (free, unlimited) were used.{_open_session_note(analysis)}
      </div>
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

  <!-- 5. AI INVESTMENT (credits, model mix, top sessions, where credits went) -->
  {_ai_investment_breakdown(goals, sessions, analysis, total_prs, project_label_map)}

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
