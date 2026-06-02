---
name: whatidid
description: "Generate a daily analytics report of what GitHub Copilot helped accomplish. Shows tasks completed, human effort equivalent, code impact, AI credits used, and a narrative story. Use when the user asks about their daily Copilot activity, what Copilot helped with today, or wants a digest of the day's work."
---

# whatidid — Copilot Impact Report

This skill lives in the `What-I-Did-Copilot` repo. Locate the repo on the user's machine before running.

## Find the repo

```bash
# Check common locations
for dir in "$HOME/What-I-Did-Copilot" "$HOME/Github Copilot/whatididghcp" "$HOME/repos/What-I-Did-Copilot"; do
  [ -f "$dir/whatidid.py" ] && echo "$dir" && break
done
```

If not found, clone it:
```bash
git clone https://github.com/microsoft/What-I-Did-Copilot.git
cd What-I-Did-Copilot
```

## Generate the report

From the repo directory, run:

```bash
# Default: last 7 days, open in browser
python whatidid.py

# Lookback shortcuts
python whatidid.py --7D
python whatidid.py --14D
python whatidid.py --30D

# Specific date or range
python whatidid.py --date YYYY-MM-DD
python whatidid.py --from YYYY-MM-DD --to YYYY-MM-DD

# Send via Outlook (auto-detects email from gh auth)
python whatidid.py --email

# Send to a specific address
python whatidid.py --14D --email user@company.com

# View only (no email)
python whatidid.py --html
```

## After running, tell the user:
- How many sessions and projects were found
- The headline and primary focus identified
- The total human effort estimate and code impact (lines added/removed)
- Whether the email was sent or HTML was saved

If there are no sessions for the date, explain that Copilot session data is stored in `~/.copilot/session-state/` and suggest checking the date or that the user may need active Copilot CLI or VS Code agent sessions.
