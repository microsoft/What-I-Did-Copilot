---
name: whatidid
description: "Generate a daily analytics report of what GitHub Copilot helped accomplish. Shows tasks completed, human effort equivalent, token usage, and a narrative story. Sends a formatted email summary. Use when the user asks about their daily activity, what Copilot helped with today, or wants a digest of the day's work."
---

# What I Did (Copilot) — Impact Report Generator

Run the following from the repo root to generate and email today's activity report. Use `--email` with **no argument** so the tool auto-detects the user's address (from `gh` / git config) — never substitute a literal placeholder like `user@example.com`:

```bash
python whatidid.py --email
```

If the user asks for a specific date range, use:
```bash
python whatidid.py --date 30D --email
```

To send to a specific address instead of the auto-detected one, pass it explicitly: `--email someone@example.com`.

After running, tell the user:
- How many sessions and projects were found
- The headline and primary focus identified
- The total human effort estimate vs elapsed time (leverage ratio)
- That the email has been sent (or HTML saved)

The report is always opened in the browser automatically — no need to add --html.

If there are no sessions for the date, explain that Copilot session data is stored in the user's Copilot session-state directory (for example, `~/.copilot/session-state/` on macOS/Linux or `%USERPROFILE%\.copilot\session-state\` on Windows) and suggest checking the date.

For full methodology, see [effort-estimation-methodology.md](../../docs/effort-estimation-methodology.md).
