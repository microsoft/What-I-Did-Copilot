<div align="center">

# 🤖 What I Did — GitHub Copilot Impact Report

**Turn invisible AI collaboration into a visible story of impact.**

*One command. Every session harvested. Every task classified. A polished report that shows what you accomplished, how you collaborated, and what it would have cost without Copilot.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![GitHub Copilot](https://img.shields.io/badge/GitHub%20Copilot-powered-green)](https://github.com/features/copilot)

</div>

---

> **"In March, Copilot delivered $4,380 worth of professional services for a $39/mo seat — a 112× return on investment."**

That's a real output from this tool. It reads your local Copilot session logs, classifies every task with AI, and renders a report that tells the complete story of your AI-assisted work:

### 📊 Return on Copilot Investment
A hero banner showing your **ROI multiplier** — professional services equivalent vs. your $39/mo seat cost. See exactly what those tokens translated into in dollar value.

### ✅ What Got Accomplished
Every project broken down into tasks with effort estimates. Expandable detail shows the what, how, and skills involved in each deliverable. This is the evidence trail.

### 📦 What Got Produced
Tangible artifacts — **scripts, reports, documents, presentations, config files** — categorized and counted. See exactly what Copilot helped you create or modify.

### 🧠 Skills Augmented
The professional roles Copilot substituted for — Software Engineer, Data Analyst, UX Designer, Technical Writer — with task counts showing how your capabilities were multiplied.

### 🎯 How I Collaborated
A **donut chart** breaking down every interaction by intent — Building, Investigating, Designing, Researching, Iterating, Shipping. See your collaboration signature: were you mostly building, or debugging? Designing, or researching? Per-project breakdowns reveal how your approach varied across workstreams.

### ⏰ When I Worked
Time-of-day activity patterns with an expandable **daily heatmap** — see whether you're an early-morning builder or a late-night debugger, with intensity shading across every time slot.

### 🔢 By the Numbers
The raw metrics: Copilot seat cost vs. market API rates, premium request consumption, token breakdown (input, output, cache hits), and AI processing time.

### 📐 Estimation Evidence
Collapsible detail showing exactly how effort estimates were calculated — tool invocations, premium requests, active engagement time, and the deterministic formula behind each number.

## 📸 Sample Report

<div align="center">
<em>Report generated with <code>whatidid --from 2026-03-01 --to 2026-03-30</code></em>

<!-- Replace with actual screenshot: take a full-page screenshot of a generated report and save as docs/images/sample-report.png -->
<img src="docs/images/sample-report.jpg" alt="Sample Impact Report" width="680">
</div>

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/microsoft/mycopilotworks.git
cd mycopilotworks
```

### 2. Open in GitHub Copilot CLI or VS Code
   
```bash
# Option A: Open in VS Code with Copilot
code mycopilotworks
   
# Option B: Use GitHub Copilot in the terminal
cd mycopilotworks
gh copilot
```

### 3. Run your first report

```bash
# Today's report
python whatidid.py

# Last 7 days
python whatidid.py --date 7D

# Last 30 days
python whatidid.py --date 30D

# Specific date
python whatidid.py --date 2026-03-19

# Date range (e.g., all of March)
python whatidid.py --from 2026-03-01 --to 2026-03-31

# Save HTML without emailing
python whatidid.py --date 7D --html

# Send report via Outlook
python whatidid.py --email you@company.com

# Force re-analysis (bypass cache)
python whatidid.py --refresh
```

### 4. (Optional) Set up a shortcut

Add this to your PowerShell profile (`$PROFILE`) so you can run `whatidid` from anywhere:

```powershell
function whatidid { python "C:/path/to/mycopilotworks/whatidid.py" @args }
```

Then:
```bash
whatidid --date 7D --html
```

## 🏗️ How It Works

```
~/.copilot/session-state/<uuid>/events.jsonl
                │
                ▼
           harvest.py    → scan sessions, extract messages, tools, files, intents
                │
                ▼
           analyze.py    → AI categorization via GitHub Models API (gpt-4o-mini)
                │         → calibrated effort estimation with quantitative signals
                ▼
           report.py     → HTML report: story arc, donut charts, heatmaps, ROI
                │
                ▼
         email_send.py   → send via Outlook COM automation (optional)
```

See [docs/architecture.md](docs/architecture.md) for session file formats, token cost model, and leverage calculation details.

## 📋 Requirements

| Requirement | Why |
|---|---|
| **Python 3.10+** | Core runtime |
| **GitHub CLI (`gh`)** | Provides API token for AI analysis — run `gh auth login` |
| **GitHub Copilot** | Session data source — must have active sessions in `~/.copilot/session-state/` |
| **Microsoft Outlook** | *(Optional)* For email delivery via COM automation |

No `pip install` needed — the tool uses only Python standard library + GitHub Models API.

## 🤝 Copilot CLI Skill

This tool can also be invoked as a [GitHub Copilot CLI](https://githubnext.com/projects/copilot-cli) skill. See [skill/SKILL.md](skill/SKILL.md) for the skill definition.

## 📄 License

MIT
