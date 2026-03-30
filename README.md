# whatididghcp — Daily GitHub Copilot Activity Digest

Generates a daily analytics report of what GitHub Copilot helped you accomplish. Harvests session data from `~/.copilot/session-state/`, uses AI to extract goals and estimate human effort, then produces a styled HTML report (optionally emailed via Outlook).

## Features

- **Session harvesting** — scans Copilot session logs for instructions, tool usage, code changes, and token metrics
- **AI-powered analysis** — calls GitHub Models API (gpt-4o-mini) to categorize tasks, estimate human hours, and generate narrative
- **Rich HTML report** — KPI cards, goal tables, activity timeline, token cost breakdown, and leverage metrics
- **Email delivery** — sends report via Outlook COM automation
- **Copilot skill** — can be invoked as a GitHub Copilot CLI skill

## Usage

```bash
# Today's report
python whatidid.py

# Specific date
python whatidid.py --date 2026-03-19

# Date range
python whatidid.py --from 2026-03-09 --to 2026-03-19

# Send email
python whatidid.py --email you@company.com

# Save HTML only (no email)
python whatidid.py --html

# Force re-analysis (bypass cache)
python whatidid.py --refresh
```

## Architecture

```
~/.copilot/session-state/<uuid>/events.jsonl
                │
                ▼
           harvest.py    → scan sessions, extract instructions & metrics
                │
                ▼
           analyze.py    → AI categorization via GitHub Models API
                │
                ▼
           report.py     → generate Outlook-compatible HTML
                │
                ▼
         email_send.py   → send via Outlook COM (optional)
```

See [docs/architecture.md](docs/architecture.md) for full details.

## Requirements

- Python 3.10+
- GitHub CLI (`gh`) authenticated (for GitHub Models API token)
- Microsoft Outlook (for email delivery, optional)
