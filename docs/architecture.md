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
Uses Anthropic's published per-token rates (sessions use Claude models via Copilot):

| Token type | Field | Rate |
|---|---|---|
| Input | `inputTokens` | $3.00 / 1M |
| Output | `outputTokens` | $15.00 / 1M |
| Cache read | `cacheReadTokens` | $0.30 / 1M |
| Cache creation | `cacheWriteTokens` | $3.75 / 1M |

Update these in `report.py → _cost()` if rates change.

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
