<div align="center">

<br>

# 📝 What I Did — GitHub Copilot Impact Report

### One command. See everything you built with Copilot — and the leverage you're getting from your seat.

<br>

<img src="https://raw.githubusercontent.com/microsoft/What-I-Did-Copilot/main/docs/images/sample-report.gif" alt="What I Did — GitHub Copilot Impact Report sample" width="680">

<br>

[![Built by Microsoft](https://img.shields.io/badge/Built%20by-Microsoft-0078d4?style=for-the-badge&logo=microsoft&logoColor=white)](https://microsoft.github.io/Analytics-Hub/team/)
[![Analytics Hub](https://img.shields.io/badge/Analytics%20Hub-11%20Repositories-8661c5?style=for-the-badge&logo=github&logoColor=white)](https://microsoft.github.io/Analytics-Hub/)

<br>

**🚀 [All Analytics Hub Reports](https://microsoft.github.io/Analytics-Hub/)**

<br>

**Found this useful? ⭐ Star this repo to help others discover it!**

<br>

**[Get Started ↓](#get-started)** &nbsp;·&nbsp; **[What You'll See ↓](#what-youll-see)** &nbsp;·&nbsp; **[How It Works ↓](#how-it-works)** &nbsp;·&nbsp; **[Requirements ↓](#requirements)** &nbsp;·&nbsp; **[Privacy ↓](#privacy)**

<br>

</div>

---


<a id="get-started"></a>
## Try it now

Pick whichever matches how you use Copilot &mdash; all three install and run the same thing.

**Option A &mdash; Copilot CLI plugin** *(requires the GitHub Copilot CLI)*

In any Copilot CLI session:

```bash
/plugin install whatidid@awesome-copilot
```

Then just run:

```bash
whatidid                # defaults to a 7-day lookback
```

**Option B &mdash; VS Code (Awesome Copilot marketplace)** *(zero clone, zero terminal)*

1. Open the **Command Palette** (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> / <kbd>Cmd</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd>) &rarr; **Chat: Plugins**  
   *(or type `@agentPlugins` in the Extensions search view)*
2. Search **`whatidid`** &rarr; click **Install**
3. In Copilot Chat, just ask:
   > *"give me a 7-day Copilot report"* &nbsp;·&nbsp; *"whatidid this month"* &nbsp;·&nbsp; *"summarize what Copilot helped me with today"*

**Option C &mdash; Clone the repo** *(maximum control, dev-mode)*

```bash
git clone https://github.com/microsoft/What-I-Did-Copilot.git
cd What-I-Did-Copilot
python whatidid.py      # defaults to a 7-day lookback
```

That's it. A report opens in your browser showing your last 7 days with Copilot.

---

<a id="what-youll-see"></a>
## What you'll see

| | |
|---|---|
| ✅ **Goals & leverage** | Every project with human effort equivalents — see that a 10-min session replaced 3 hours of work. *What did Copilot actually deliver?* |
| 📦 **Artifacts produced** | Scripts, reports, docs, configs — counted and categorized. *What tangible output came out of your AI sessions?* |
| 🧠 **Skills augmented** | Hours mapped across 20+ roles — engineer, analyst, designer, architect. *What skills did Copilot make accessible to you?* |
| 🎯 **Collaboration style** | A donut chart breaks active time across 9 work modes &mdash; Designing, Analyzing, Reviewing, Researching, Learning, Building, Refining, Course-correcting, Delegating &mdash; with labels next to each slice. *How are you directing AI, and where are the skills you need to grow as a manager of AI?* |
| ⏰ **Activity heatmap** | When you collaborate and how your day breaks down. *When is AI most useful in your workflow?* |
| 📐 **Estimation evidence** | Transparent methodology grounded in [13 peer-reviewed sources](docs/effort-estimation-methodology.md). *Why should anyone trust these numbers?* |
| 💸 **Credit-burn patterns** | Every flagged pattern cites the Anthropic / OpenAI / GitHub guidance it implements &mdash; with clickable sources. *Where am I burning credits, and what does the published guidance say?* See the [credit-optimization methodology](docs/credit-optimization.md). |

---

## 🆕 What's new in this release

- **Learning intent expansion** &mdash; the classifier now catches genuine learning queries: *"how do I X"*, *"help me understand"*, *"what's the best way to..."*, *"tell me about"*, *"pros and cons of..."*, *"primer on..."*, plus dozens more phrasings. A hand-holding bypass routes *"I don't understand how X works"* to Learning instead of Course-correcting.
- **New methodology doc** &mdash; [`docs/credit-optimization.md`](docs/credit-optimization.md) synthesizes credit-burn pattern the tool detects with the exact Anthropic / OpenAI / GitHub source it implements, including short excerpts.
- **AI Investment and Consumption Patterns** &mdash; new sub-segments for Model Mix, Top Sessions and behavior pattern analysis that drive up consumption, based on guidance from OpenAI, Anthropic, and GitHub.

---

## More options

```bash
whatidid --14D                        # last 14 days
whatidid --30D                        # last 30 days
whatidid --date 2026-03-19            # specific date
whatidid --from 2026-03-01 --to 2026-03-31   # date range
whatidid --7D --email                 # send via Outlook
whatidid --7D --email you@company.com # send to a specific address
whatidid --refresh                    # force re-analysis
```

<a id="how-it-works"></a>
## 🏗️ How It Works

```
~/.copilot/session-state/<uuid>/events.jsonl          (Copilot CLI sessions)
<AppData>/Code/User/globalStorage/                    (VS Code Copilot Chat
   emptyWindowChatSessions/<uuid>.jsonl                sessions — same pipeline)
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
         whatidid.py     → opens report in browser; --email sends via Outlook COM
```

See [docs/architecture.md](docs/architecture.md) for session file formats, token cost model, and leverage calculation details.

See [docs/effort-estimation-methodology.md](docs/effort-estimation-methodology.md) for the research basis, signal definitions, and calibration logic behind effort estimates — grounded in 13 peer-reviewed sources including Alaswad et al. 2026, Cambon et al. 2023 (Microsoft Research), Ziegler et al. 2024 (CACM), and the SPACE framework (Forsgren et al. 2021).

See [docs/credit-optimization.md](docs/credit-optimization.md) for the credit-burn pattern catalogue &mdash; every detector is tied to published guidance from Anthropic, OpenAI, or GitHub, with the per-model rates sourced from Copilot's own session metadata when available.

<a id="privacy"></a>
## 🔒 Privacy

**Your data stays on your machine.** This tool is completely local-first:

- **Reads only local files** &mdash; session logs from `~/.copilot/session-state/` (Copilot CLI) and `<AppData>/Code/User/globalStorage/emptyWindowChatSessions/` (VS Code Copilot Chat) that already exist on your machine
- **No telemetry, no tracking, no cloud uploads** — the tool never phones home
- **AI analysis is optional** — uses GitHub Models API (authenticated via your own `gh` CLI token) to semantically interpret sessions. Without API access, a local heuristic fallback produces estimates with zero external calls
- **Email is optional** — the `--email` flag sends the report via your own Outlook client. If you don't use it, the HTML file stays on disk
- **No one has access to your report unless you share it** — the output is a standalone HTML file saved to your local project directory

The tool processes the same session data that GitHub Copilot already stores locally. It adds nothing new to disk beyond the HTML report and a small analysis cache in `cache/`.

<a id="requirements"></a>
## 📋 Requirements

| Requirement | Why |
|---|---|
| **Python 3.10+** | Core runtime |
| **GitHub CLI (`gh`)** | Provides API token for AI analysis — run `gh auth login` |
| **GitHub Copilot** | Session data source — must have active sessions in `~/.copilot/session-state/` |
| **Microsoft Outlook** | *(Optional)* For `--email` delivery via COM automation — auto-detects recipient from GitHub auth |

No `pip install` needed — the core report generator (`harvest.py`, `analyze.py`, `report.py`, `whatidid.py`) uses only the Python standard library + GitHub Models API.

## 🤝 Copilot Agent

This tool ships as a **Copilot CLI agent**. Anyone who clones the repo gets it automatically — run `/agent` in Copilot CLI and select `whatidid`, or just ask naturally:

> "What did I build this week?"

See [`.github/agents/whatidid.agent.md`](.github/agents/whatidid.agent.md) for the agent definition.

## 📄 License

MIT

---

<div align="center">

**Found this useful? ⭐ Star this repo to help others discover it!**

That's it! 🚀

</div>

<sub>**Keywords:** GitHub Copilot ROI, Copilot usage report, Copilot activity tracker, AI productivity metrics, token usage analysis, Copilot impact measurement, developer productivity, AI-assisted development analytics</sub>
