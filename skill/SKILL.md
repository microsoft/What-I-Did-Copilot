---
name: whatididghcp
description: "Generate a daily analytics report of what GitHub Copilot helped accomplish today. Shows tasks completed, human effort equivalent, code impact (lines added/removed), premium requests used, and a narrative story. Use when the user asks about their daily Copilot activity, what Copilot helped with today, or wants a digest of the day's work."
---

# whatididghcp — Daily Copilot Digest

Run the following to generate and email today's activity report:

```bash
python "C:/Users/shahegde/Github Copilot/whatididghcp/whatidid.py" --email shahegde@microsoft.com
```

If the user asks for a specific date, use:
```bash
python "C:/Users/shahegde/Github Copilot/whatididghcp/whatidid.py" --date YYYY-MM-DD --email shahegde@microsoft.com
```

If the user wants a date range:
```bash
python "C:/Users/shahegde/Github Copilot/whatididghcp/whatidid.py" --from YYYY-MM-DD --to YYYY-MM-DD --email shahegde@microsoft.com
```

If the user just wants to view (no email):
```bash
python "C:/Users/shahegde/Github Copilot/whatididghcp/whatidid.py" --html
```

After running, tell the user:
- How many sessions and projects were found
- The headline and primary focus identified
- The total human effort estimate and code impact (lines added/removed)
- That the email has been sent (or HTML saved)

If there are no sessions for the date, explain that Copilot session data is stored in ~/.copilot/session-state/ and suggest checking the date.
