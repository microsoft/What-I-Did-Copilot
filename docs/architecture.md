# Architecture

## Data flow

```
~/.copilot/session-state/<uuid>/events.jsonl
~/.copilot/session-state/<uuid>/workspace.yaml
           │
           ▼
       harvest.py
  - Scans all session directories for target date
  - Extracts user instructions from user.message events (filters approvals + injected context)
  - Captures tool summaries from assistant.message.toolRequests[].intentionSummary
  - Reads token breakdown, AI credits / premium requests (legacy), AI time, code changes from session.shutdown
  - Reads project summary, cwd, repo, branch from workspace.yaml + session.start
  - Returns: list of session dicts
           │
           ▼
       analyze.py
  - Builds a structured transcript from session data (includes code impact, workspace summary)
  - Calls GitHub Models API (gpt-4o-mini) using gh CLI token
  - Returns: goals[] with tasks[], skills, hours, docs_referenced
  - Caches result to <install-dir>/cache/YYYY-MM-DD.json
           │
           ▼
       report.py
  - Generates Outlook-compatible HTML
  - Layout: header → narrative → KPI cards → goals table → activity bar → token bar → task accordion
           │
           ▼
   email_send.py (optional)
  - Writes HTML to temp file
  - PowerShell Outlook COM automation sends it
```

## Session file format

Copilot writes one directory per session at `~/.copilot/session-state/<uuid>/`.

### events.jsonl

Each line is a JSON object. Relevant event types:

| Type | Content |
|---|---|
| `session.start` | `data.context`: cwd, gitRoot, repository, branch, headCommit |
| `user.message` | `data.content`: raw user instruction (may include injected `<current_datetime>` tags) |
| `assistant.message` | `data.toolRequests[]`: name, intentionSummary (human-readable tool call summary) |
| `tool.execution_start` | `data.toolName`, `data.arguments` |
| `tool.execution_complete` | `data.model`, `data.success`, `data.result` |
| `session.shutdown` | `data.totalPremiumRequests` (legacy), `data.totalAiCredits` (future), `data.planTier`, `data.autoModelSelection`, `data.totalApiDurationMs`, `data.codeChanges`, `data.modelMetrics` (per-model `usage.*Tokens`, `requests.count`, `creditsUsed`) |

### workspace.yaml

Simple key:value file with fields: `id`, `cwd`, `git_root`, `repository`, `host_type`, `branch`, `summary`, `created_at`, `updated_at`.

The `summary` field is a Copilot-generated session title (e.g. "Create Exec Deck From PBIP").

## Token cost model

Token data is in `session.shutdown.modelMetrics.<model>.usage`.
The `modelMetrics` dict is keyed by model name (e.g. `claude-opus-4.6`, `gpt-5.4`, `gemini-2.5-pro`),
so per-model pricing is applied automatically.

### Billing model (effective June 1, 2026): GitHub AI Credits

GitHub Copilot moved from Premium Request Units (PRUs) to **GitHub AI Credits**
on 2026-06-01. The conversion is `1 AI credit = $0.01 USD`. Cost per interaction
is calculated as `tokens × per-model rate → USD → credits`. Paid plans get a
10% discount when "auto model selection" is active in Chat / CLI / cloud agent.

Until the CLI starts emitting `totalAiCredits` / per-model `creditsUsed`
directly in `session.shutdown`, this repo derives credits locally from the
token-cost calculation. Set `COPILOT_PLAN=pro|pro+|max|business|enterprise`
to surface plan context in the report.

Pricing is defined in `report.py → _MODEL_PRICING` with prefix-matched model names.
Source of truth: <https://docs.github.com/copilot/reference/copilot-billing/models-and-pricing>.

| Provider  | Model family            | Input $/1M | Output $/1M |
|-----------|-------------------------|-----------:|------------:|
| OpenAI    | GPT-5.5                 |       5.00 |       30.00 |
| OpenAI    | GPT-5.4 / 5.2 / Codex   |  1.75–2.50 |  14.00–15.00 |
| OpenAI    | GPT-5 mini, GPT-4.1     |  0.25–2.00 |   2.00–8.00 |
| Anthropic | Claude Opus 4.5–4.8     |       5.00 |       25.00 |
| Anthropic | Claude Sonnet 4.x       |       3.00 |       15.00 |
| Anthropic | Claude Haiku 4.5        |       1.00 |        5.00 |
| Google    | Gemini 3.1 Pro          |       2.00 |       12.00 |
| Google    | Gemini 3 Flash / 3.5    |  0.50–1.50 |   3.00–9.00 |
| Google    | Gemini 2.5 Pro          |       1.25 |       10.00 |
| GitHub    | Raptor mini             |       0.25 |        2.00 |

GPT-4.1, GPT-5 mini, and Raptor mini are *included* models for paid plans (no
credit cost), but the market rate is still shown to surface the underlying value.
Anthropic cache-write rates are billed separately (`cache_creation` in code).
If a model name doesn't match any prefix, mid-range fallback pricing ($3 / $15)
is used. Update `_MODEL_PRICING` in `report.py` when GitHub publishes rate changes.

## Value-delivered banner

The report's green hero banner is a **value display, not a billing claim**.
We deliberately omit any ROI multiplier and any "true cost" / "savings"
figure because we cannot observe the user's plan, included credit
allowance, auto-model discount, or actual GitHub bill from a local session
log alone. Three independent, defensible signals are shown side-by-side:

```
human_value     = total_human_hours × HOURLY_RATE       ($72/hr blended)
market_cost     = Σ (tokens × per-model rate)           (estimated, see pricing table)
hours_delivered = total_human_hours                     (research-grounded estimate)
```

* **Professional Services Value** — `human_value`, derived from our
  documented effort-estimation methodology. Defensible because it's
  `hours × rate`, no billing inference.
* **AI Activity (estimated)** — measured tokens converted to AI Credits +
  open-market USD value, labelled in the banner as *"estimated from
  measured tokens × GitHub's published per-model rates — your actual
  bill depends on your plan and included credit allowance."* Defensible
  because tokens are measured locally and rates are public, while the
  disclaimer makes it clear this is not a bill.
* **Hours Delivered** — the underlying time-saved signal stated plainly.

The "By the Numbers" panel surfaces the **Copilot seat** (real, plan-aware
via `PLAN_ALLOWANCES`) and the **open-market API value** (clearly tagged as
estimated). We removed the prior "Saved ~$X" line because it was a derived
ROI-style claim that quietly depended on assumptions about the bill.

## GitHub Models API

- Endpoint: `https://models.inference.ai.azure.com/chat/completions`
- Auth: `Authorization: Bearer <github_token>` (from `gh auth token`)
- Model: `gpt-4o-mini` (OpenAI-compatible request body)
- No extra credentials — uses the same GitHub token as `gh` CLI
