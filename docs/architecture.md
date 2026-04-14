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
  - Reads token breakdown, premium requests, AI time, code changes from session.shutdown
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
| `session.shutdown` | `data.totalPremiumRequests`, `data.totalApiDurationMs`, `data.codeChanges`, `data.modelMetrics` |

### workspace.yaml

Simple key:value file with fields: `id`, `cwd`, `git_root`, `repository`, `host_type`, `branch`, `summary`, `created_at`, `updated_at`.

The `summary` field is a Copilot-generated session title (e.g. "Create Exec Deck From PBIP").

## Token cost model

Token data is in `session.shutdown.modelMetrics.<model>.usage`.
The `modelMetrics` dict is keyed by model name (e.g. `claude-opus-4.6`, `gpt-4o`, `gemini-2.5-pro`),
so per-model pricing is applied automatically.

Pricing is defined in `report.py → _MODEL_PRICING` with prefix-matched model names:

| Provider | Models | Input $/1M | Output $/1M |
|---|---|---|---|
| Anthropic | claude-opus-4 | $15.00 | $75.00 |
| Anthropic | claude-sonnet-4 | $3.00 | $15.00 |
| Anthropic | claude-haiku | $0.80 | $4.00 |
| OpenAI | gpt-5, gpt-4o | $2.50 | $10.00 |
| OpenAI | gpt-4.1 | $2.00 | $8.00 |
| OpenAI | o3 | $10.00 | $40.00 |
| Google | gemini-2.5-pro | $1.25 | $10.00 |
| Google | gemini-2.5-flash | $0.15 | $0.60 |

Cache read/write rates also vary per model. If a model name doesn't match any prefix, mid-range
fallback pricing ($3.00/$15.00) is used. Update `_MODEL_PRICING` in `report.py` when rates change.

## Leverage metric

```
human_value    = total_human_hours × HOURLY_RATE   ($72/hr blended rate)
seat_cost/mo   = $39/mo enterprise plan
leverage       = human_value / seat_cost_per_month
```

Example: 29h × $72 = $2,088 human value ÷ $39/mo seat = **54×**

This measures return on Copilot seat investment per day used.

## GitHub Models API

- Endpoint: `https://models.inference.ai.azure.com/chat/completions`
- Auth: `Authorization: Bearer <github_token>` (from `gh auth token`)
- Model: `gpt-4o-mini` (OpenAI-compatible request body)
- No extra credentials — uses the same GitHub token as `gh` CLI
