# Copilot Instructions — What I Did (mycopilotworks)

## Architecture

Pipeline: `whatidid.py` → `harvest.py` → `analyze.py` → `report.py` → `email_send.py`

- **whatidid.py** — CLI entry point. Parses dates/flags, orchestrates the pipeline, opens report in browser or sends via Outlook.
- **harvest.py** — Reads `~/.copilot/session-state/<uuid>/events.jsonl`, extracts messages, tools, code changes, token metrics, and intent classification.
- **analyze.py** — Sends harvested transcripts to GitHub Models API (`gpt-4o-mini`), caches results in `cache/<date>.json`, falls back to heuristics when API is unavailable.
- **report.py** — Generates a self-contained HTML report with inline CSS/JS. Table-based layout for Outlook compatibility. Color palette is in `C = {...}`.
- **email_send.py** — Sends HTML via Outlook COM automation (optional).

No tests, no linter, no build step. Standard library only — no pip dependencies.

## Conventions

- `snake_case` for everything; `_` prefix for private helpers.
- Constants are UPPER_CASE (`SESSION_DIR`, `API_URL`, `HOURLY_RATE`, `C`).
- Dates are `YYYY-MM-DD`; lookback shorthand: `7D`, `14D`, `30D`.
- Cache files: `cache/YYYY-MM-DD.json`. Reports: `report_<label>.html`.
- HTML is built as f-string templates with inline styles — no external CSS/JS.

## Git workflow

- **`main` is protected** — never push directly. Always create a feature branch.
- **This is an EMU (Enterprise Managed User) repo** — `gh pr create` will fail. Push the branch and provide the browser URL for PR creation: `https://github.com/microsoft/mycopilotworks/pull/new/<branch>`
- Don't commit local tool configs (`.claude/`, `.vscode/`, IDE settings) or scratch/utility scripts that aren't part of the core pipeline. If in doubt, ask.

## Writing style

When editing user-facing content (README, report headlines, section descriptions):
- Write from the reader's perspective — focus on what they'll learn and why they should care.
- Lead with value and outcomes, not implementation details (e.g., "see which skills Copilot augmented" not "a ranked bar chart of 20 professional roles").
- Avoid technical jargon for chart types or internal data structures.

## Change approach

For multi-file refactors or report redesigns, propose the plan and wait for approval before implementing. Break large changes into reviewable stages.
