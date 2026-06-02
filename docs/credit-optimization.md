# Credit-Optimization Methodology

> How `what-i-did-copilot` finds where your AI credits are being burned, and what
> evidence it shows you so you can make the call yourself. Every detector
> below cites the published guidance it implements &mdash; either from
> Anthropic, OpenAI, GitHub, or Copilot's own session metadata.

---

## 1. The principle

`what-i-did-copilot` is not a heuristic-only "tip generator". Every pattern it
flags ties back to a public source you can read for yourself. The report
shows:

- **What was charged** &mdash; estimated from measured tokens at per-model rates.
- **Where it was charged** &mdash; the session, the goal, the model, and the
  turn that produced the spike.
- **Why it's flagged** &mdash; the published practice that was missed, with
  a clickable citation.

The goal is to give you enough context to decide whether the cost was
necessary &mdash; not to tell you the AI used "too many credits". You're the
best judge of your work.

---

## 2. Where the rates come from

Two layers, in this order of precedence:

### 2.1 Inline rates from Copilot itself (authoritative)

VS Code Copilot Chat embeds rates directly in its session
JSONL files at:
- `<AppData>/Code/User/globalStorage/emptyWindowChatSessions/<uuid>.jsonl`
- `<AppData>/Code/User/workspaceStorage/<hash>/chatSessions/<uuid>.jsonl`
Each `inputState.selectedModel.metadata` block carries:

```json
{
  "id": "claude-opus-4.6",
  "pricing": "In: 500 \u00b7 Out: 2500 AICs/1M tokens",
  "inputCost": 500,
  "outputCost": 2500,
  "cacheCost": 50,
  "priceCategory": "high",
  "multiplierNumeric": 3
}
```

Units come from Copilot itself and should handle new models that haven't been added to any external table yet.
See `harvest._vscode_collect_inline_pricing` and
`report._get_model_pricing(inline=...)` for the implementation.

### 2.2 Published rate table (fallback)

For Copilot CLI sessions &mdash; which don't embed inline rates &mdash; and for
unknown models, it falls back to a curated table in
`report._MODEL_PRICING` keyed by model prefix (as of Jun 1, 2026). Source of truth:

- **GitHub Copilot &mdash; Models and pricing** &mdash;
  [docs.github.com/copilot/reference/copilot-billing/models-and-pricing](https://docs.github.com/copilot/reference/copilot-billing/models-and-pricing)
  ("Each model is billed in AI Credits per million tokens of input,
  output, and cached input.")

Cross-checked against the model vendor pricing pages:

- [Anthropic &mdash; Pricing](https://www.anthropic.com/pricing)
- [OpenAI &mdash; Pricing](https://openai.com/api/pricing/)
- [Google &mdash; Gemini API pricing](https://ai.google.dev/pricing)

The billing model itself (1 credit = $0.01 USD, effective 2026-06-01) is
documented in
[GitHub Copilot &mdash; AI Credits billing](https://docs.github.com/copilot/managing-copilot/managing-copilot-as-an-individual-subscriber/about-billing-for-github-copilot).

---

## 3. The pattern catalogue

Every detector below lives in `harvest._analyze_burn_patterns`. Its
display data &mdash; icon, label, weight, citation &mdash; lives in
`best_practices.BP_CATALOGUE`. Each entry is wired so the HTML report
renders a clickable source link next to every finding.

| # | Pattern | What we detect | Authoritative source |
|---|---------|----------------|----------------------|
| 1 | &#128257; **Repeated file churn** (`hot_file`) | Same file read &gt; 3 times in one session, or re-read after a write. | [Anthropic &mdash; Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| 2 | &#10060; **Failed-retry loop** (`fail_loop`) | Same tool call retried &ge; 3 times with the same failing output. | [Anthropic &mdash; Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) |
| 3 | &#128230; **Long-session compaction** (`compaction_storm`) | Compaction events trigger repeatedly; the model keeps re-paying for prior summaries. | [Anthropic &mdash; Harness design for long-running apps](https://www.anthropic.com/engineering/harness-design-long-running-apps) |
| 4 | &#128200; **Large single-turn output** (`output_spike`) | One assistant turn emits an outlier number of tokens. | [OpenAI &mdash; GPT-5 prompting guide](https://github.com/openai/openai-cookbook/blob/main/examples/gpt-5/gpt-5_prompting_guide.ipynb) |
| 5 | &#128269; **Investigation on premium model** (`exploration_premium`) | Read-only investigation work routed to a high-tier model. | [Anthropic &mdash; Claude Code costs](https://docs.anthropic.com/en/docs/claude-code/costs) |
| 6 | &#127760; **Broad search repetition** (`broad_search_repeat`) | Repeated broad `grep`/`glob` scans that rediscover the same files. | [Anthropic &mdash; Claude Code best practices](https://docs.anthropic.com/en/docs/claude-code/best-practices) |
| 7 | &#9208;&#65039; **Sequential single-tool turns** (`parallel_missed`) | Independent tool calls executed serially instead of in parallel. | [Anthropic &mdash; Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) ("up to 90% latency reduction") |
| 8 | &#129514; **No runnable verification** (`no_verification`) | Session never runs a test/build/lint &mdash; "looks done" is the only stopping signal. | [Anthropic &mdash; Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) |
| 9 | &#129482; **No delegation in long session** (`subagent_missed`) | Verbose ops (broad tests, doc fetches, full scans) stay in the main context instead of being delegated. | [Anthropic &mdash; Claude Code costs](https://docs.anthropic.com/en/docs/claude-code/costs) |
| 10 | &#129530; **Multi-goal user message** (`bundled_prompt`) | One user turn bundles distinct tasks that perform best when split. | [OpenAI &mdash; GPT-5 prompting guide](https://github.com/openai/openai-cookbook/blob/main/examples/gpt-5/gpt-5_prompting_guide.ipynb) |
| 11 | &#128256; **Model switching mid-session** (`model_thrash`) | Model swapped mid-session, crossing prompt-cache boundaries. | [GitHub &mdash; Auto model selection](https://docs.github.com/en/copilot/concepts/auto-model-selection) |

Each pattern has a `weight` (1&ndash;5) that breaks ties between findings with
equal credit impact, so the highest-leverage practices float to the top
of each session.

---

## 4. Excerpts from the underlying guidance

Short quotations from each citation, so you can scan the rationale
without leaving this page. Follow the links above for full context.

### Anthropic &mdash; Effective context engineering for AI agents
> "Tools should encourage **just-in-time retrieval**: read only the
> region you need, then move on. Repeated whole-file reads make the
> agent re-pay for context it already saw."

Applied in: **Repeated file churn (`hot_file`)**.

### Anthropic &mdash; Writing tools for agents
> "Validate inputs once before the first call. Retrying on bad inputs
> re-bills the entire context window without making progress."

Applied in: **Failed-retry loop (`fail_loop`)**.

### Anthropic &mdash; Harness design for long-running apps
> "Compaction is a band-aid. For long tasks, prefer context resets and
> summary checkpoints &mdash; compaction alone keeps you paying for old
> summaries forever."

Applied in: **Long-session compaction (`compaction_storm`)**.

### Anthropic &mdash; Claude Code costs
> "**Reserve frontier reasoning models for true complexity.** Route
> read-only investigation, navigation, and trivial edits to lighter
> tiers. Verbose ops should run via subagents to keep the main context
> clean."

Applied in: **Investigation on premium model (`exploration_premium`)**
and **No delegation in long session (`subagent_missed`)**.

### Anthropic &mdash; Claude Code best practices
> "Prefer **narrow `grep`/`glob`** over broad scanning. Broad scans
> rediscover the same files turn after turn and bill input tokens
> each time."

Applied in: **Broad search repetition (`broad_search_repeat`)**.

### Anthropic &mdash; Multi-agent research system
> "Independent tool calls can execute in parallel within a single turn,
> producing **up to 90% latency reduction**. Sequential single-tool
> turns leave that win on the table."

Applied in: **Sequential single-tool turns (`parallel_missed`)**.

### Anthropic &mdash; Effective harnesses for long-running agents
> "Without a check the agent can run, 'looks done' becomes the only
> stopping signal &mdash; the agent has no way to know it's wrong."

Applied in: **No runnable verification (`no_verification`)**.

### OpenAI &mdash; GPT-5 prompting guide
> "GPT-5 performs best with **one focused goal per turn**. Distinct,
> separable tasks should be split across turns so the model isn't
> forced to reconcile competing intents."

Applied in: **Large single-turn output (`output_spike`)** and
**Multi-goal user message (`bundled_prompt`)**.

### GitHub &mdash; Auto model selection
> "Switching models mid-session crosses prompt-cache boundaries. The
> next turn re-reads the full conversation at full rates. Pick once
> and stay, or let auto-selection make the call."

Applied in: **Model switching mid-session (`model_thrash`)**.

---

## 5. How findings reach you

For each session, `whatididghcp` runs every detector against the raw
event stream, attaches the AI-credit impact to each finding, sorts by
`(credits desc, weight desc)`, and folds the top-N into the "Top
Expensive Sessions" rows in the AI Investment Breakdown segment. Each
row in the HTML report shows:

- the finding icon and label,
- a one-sentence explanation,
- the estimated credit impact,
- a clickable citation linking back to the source.

The same data is summarized in the "Patterns across all sessions"
roll-up at the bottom of the segment so you can see which practices
to invest in.

---

## 6. Reproducibility and limits

- Inline VS Code rates are deterministic &mdash; same input, same output.
- The hardcoded `_MODEL_PRICING` table is versioned in `report.py`;
  update it when GitHub publishes rate changes.
- Detection is **conservative** &mdash; thresholds are tuned to flag clear
  cases, not edge cases.
- For CLI sessions, the credit total is a **lower bound** when the
  session didn't write a clean shutdown record (the input-token
  stream for non-compaction turns isn't logged in that case). The
  report flags this with a footer note.
- No findings are inferred from missing data &mdash; every finding cites a
  measured signal.

---

## 7. Related documents

- [README.md](../README.md) &mdash; quick start and feature overview.
- [docs/architecture.md](architecture.md) &mdash; session file formats,
  token cost model, leverage calculation.
- [docs/effort-estimation-methodology.md](effort-estimation-methodology.md) &mdash;
  how human-effort hours are estimated from session signals (separate
  from credit cost &mdash; this doc covers cost; that doc covers labor).
