# Effort Estimation Methodology

**How this tool estimates the human-equivalent effort of AI-assisted work**

This document describes the research basis, signals, and calibration logic behind
the effort estimates in *What I Did (Copilot)*. The methodology draws on peer-reviewed
research in software engineering cost estimation, cognitive load theory, and the
emerging field of LLM-assisted productivity measurement.

---

## 1. The Core Question

> If a skilled professional had done this work entirely without AI assistance,
> how many hours would it have taken?

This is the "human-equivalent effort" — the counterfactual cost of the work that
Copilot accelerated. It is **not** how long the user spent, nor how long the AI
took. It is what a competent expert would bill for delivering the same outcome
by hand.

---

## 2. Why Traditional Metrics Fall Short

Classic software effort estimation relies on **size-oriented metrics** — lines of
code (LOC) and function points (FP). These formed the backbone of models like
COCOMO (Boehm, 1981) and remain widely used. However, research consistently shows
their limitations:

- **LOC is a poor proxy for effort in AI-assisted work.** An LLM can generate
  1,000 lines of boilerplate in seconds that would take a human hours, while a
  single-line change to a legacy system may require extensive analysis and testing.
  LOC conflates volume with complexity.
  *(Alaswad et al., 2026; Cambon et al., 2023)*

- **Function points miss cognitive complexity.** Lavazza et al. (2024) analysed
  hundreds of projects and found that simpler proxies (counting requirements or
  data entities) performed as well as full function-point analysis — and *all*
  methods underestimated effort on highly complex projects.
  *(Lavazza, L., Morasca, S., & Tosi, D. (2024). "On the Role of Complexity in
  Software Effort Estimation." Information and Software Technology. [mdpi.com])*

- **Code complexity metrics don't align with human cognitive effort.** Hao et al.
  (2023) measured actual brain activity (EEG) and eye-tracking of developers
  reading code and found that popular metrics like cyclomatic complexity and
  Halstead volume often *mis-predict* how hard code is for humans to understand.
  *(Hao, Z., et al. (2023). "Towards Understanding the Measurement of Code
  Complexity." Frontiers in Neuroscience. [frontiersin.org])*

**Key takeaway:** No single metric captures effort. Multi-factor models that combine
output volume, process complexity, and human experience work best (Forsgren et al.,
2021 — SPACE framework).

---

## 3. How LLMs Change the Effort Equation

Research on AI-assisted productivity reveals consistent patterns that inform our
estimation approach:

### 3.1 Dramatic Speed-Ups in Execution

Across controlled studies, LLM tools provide 1.4× to 4× speed-ups on bounded
tasks without significant quality loss:

- **GitHub Copilot coding study:** Developers completed a task 55.8% faster with
  Copilot than without.
  *(Peng, S., et al. (2023). "The Impact of AI on Developer Productivity: Evidence
  from GitHub Copilot." arXiv:2302.06590.)*

- **Microsoft AI Productivity experiments:** Across writing, editing, coding, and
  question-answering tasks, participants with Copilot tools completed tasks in
  26–73% of the time taken by those without AI — i.e., 1.4× to 4× faster.
  *(Cambon, J., et al. (2023). "Early LLM-based Tools for Enterprise Information
  Workers." Microsoft Research. [microsoft.com])*

### 3.2 Complexity Inversion

Alaswad et al. (2026) document a striking finding: **78% of tasks historically
labelled "high complexity" by humans were completed with <25% of the expected
effort when using an LLM**, because the model could generate correct or
near-complete solutions swiftly. Conversely, **22% of "low complexity" tasks
required >180% of expected effort** due to verification overhead and edge cases.

> This means human-perceived complexity is a poor predictor of AI-assisted effort.
> We need signals that capture both the AI's work and the human oversight required.

*(Alaswad, M., et al. (2026). "Toward LLM-Aware Software Effort Estimation: A
Conceptual Framework." Frontiers in Artificial Intelligence. [frontiersin.org])*

### 3.3 New Kinds of Human Effort

When AI handles generation, the human's role shifts to **prompting, evaluating,
and refining**. Microsoft's AI Productivity team added "effort" (mental workload)
as a third key metric alongside speed and quality. Key findings:

- Participants reported **lower subjective effort** with AI support in most cases.
- But **new effort emerged** in managing the AI: deciding what to prompt,
  interpreting outputs, steering corrections, and verifying correctness.
- Ziegler et al. (2024) found that the **acceptance rate of AI suggestions** is a
  meaningful productivity signal: higher acceptance = less rework = lower effort.
  Developers who frequently rejected suggestions saw diminished productivity gains.
  *(Ziegler, A., et al. (2024). "Measuring GitHub Copilot's Impact on Productivity."
  Communications of the ACM, 67(3). [cacm.acm.org])*

---

## 4. The Five-Dimension Framework

Our estimation model is grounded in the **Hybrid Intelligence Effort** framework
proposed by Alaswad et al. (2026), which identifies five dimensions that drive
effort in LLM-assisted work:

| # | Dimension | What it measures | Our session-log proxy |
|---|-----------|------------------|-----------------------|
| 1 | **LLM reasoning complexity** | How hard was it for the AI to solve | `premium_requests`, conversation depth |
| 2 | **Context completeness** | Did the task need external lookups/clarification | File reads, searches, web fetches (from tool distribution) |
| 3 | **Transformation scope** | Breadth and impact of changes | `files_touched`, `lines_added`, `lines_removed` |
| 4 | **Iterative reasoning cycles** | Back-and-forth to reach a solution | `conversation_turns`, `iteration_depth` (re-edits per file) |
| 5 | **Human oversight effort** | Review, testing, correction by the human | `active_minutes` relative to `wall_clock_minutes` (engagement ratio) |

---

## 5. Signals We Capture and How We Use Them

### 5.1 Primary Signals (volume of work)

| Signal | Source | Human-equivalent rate | Research basis |
|--------|--------|-----------------------|----------------|
| **Tool invocations** | Count of discrete Copilot actions (file reads, edits, commands, searches) | ~2–3 min per action for an expert human | Each action represents a task a human would perform manually: open a file, scan code, make an edit, run a test. Aggregated across sessions, this is the broadest measure of work volume. |
| **Premium requests** | Opus/Sonnet-class model calls | ~8–12 min per request of human research/thinking | Each premium request represents a round of deep reasoning. The human equivalent is formulating a problem, researching approaches, and iterating — a cognitive cycle that takes meaningful time. |
| **Lines of code** | Net lines added to the project | 100–150 LoC/hr for an expert | Industry benchmarks for production-quality code (including boilerplate, comments, and config). This rate accounts for the full write-test-debug cycle, not just typing speed. |
| **Active engagement time** | User activity with idle gaps >5 min excluded | 4× multiplier (human needs ~4× longer without AI) | Aligned with the 1.4–4× speed-up range from Microsoft studies (Cambon et al., 2023). |

### 5.2 Complexity Signals (multipliers)

These signals adjust the base estimate upward when the work was harder than
raw volume suggests.

| Signal | What it reveals | Multiplier logic |
|--------|-----------------|------------------|
| **Conversation turns** | Task ambiguity and iteration intensity. More turns = the problem required iterative refinement, not a one-shot solution. | >20 turns: +10–20%; >50 turns: +20–30%. Based on Chen et al. (2023) finding that ambiguous tasks lead to lengthy prompt dialogues and increased human effort. |
| **Tool type distribution** | Nature of the work. Read-heavy = research; Edit-heavy = implementation; Run-heavy = debugging; Balanced mix = complex multi-step work (design→implement→test cycle). | Balanced distribution triggers the highest base tier, as it indicates a full engineering cycle rather than a narrow task. |
| **Files touched** | Scope breadth and integration complexity. More files = cross-cutting changes requiring coordination. | >5 files: +10%; >15 files: +20%. Based on Morcov et al. (2020) finding that broader scope projects have significantly larger effort overruns. |
| **Iteration depth** | Debugging and refinement intensity. High re-edit count per file indicates the solution wasn't straightforward — multiple attempts were needed. | >5 edits/file: +10–20%; >15 edits/file: +20–30%. Maps to Alaswad's "iterative reasoning cycles" dimension. |
| **Engagement ratio** | Thinking intensity. Low active-to-wall-clock ratio means the user spent significant time analysing before acting — the kind of deep thinking that doesn't show up in tool counts. | Very low ratio (<10%) with high wall clock flags research/analysis-heavy work where active_minutes alone understates effort. |
| **Lines removed** | Refactoring indicator. High removal alongside additions means rework, not greenfield — the harder kind of development. | Removals >30% of additions: +10–20%. Refactoring requires understanding existing code before changing it. |

### 5.3 Caps and Floors

- **Mechanical tasks** (install, deploy, git push, copy files) → 0.25–0.5h max,
  regardless of tool count. These are execution, not thinking.
- **Trivial sessions** (<5 premium requests AND <10 tool invocations) → capped
  at 1h total. The work was inherently lightweight.
- **No single task exceeds 8h** — if the work is that large, it should be split
  into sub-tasks for granularity.

---

## 6. The Two Estimation Paths

### 6.1 AI Estimate (semantic)

An LLM reads the full session transcript — every user instruction, every tool
action, every code change — and produces a calibrated estimate using the rules
and signal anchors described above. This is the "AI Est." column in the report.

**Strengths:** Understands *what* was done (not just counts), can distinguish
trivial boilerplate from novel architecture, captures nuance.

**Limitations:** Depends on prompt quality; cached per analysis run; may vary
across model versions.

### 6.2 Formula Estimate (deterministic)

A purely mechanical calculation from session metrics:

```
base        = max(tier_tools(n), tier_reqs(n), tier_active(m))
multiplier  = iteration_factor × scope_factor
lines       = tier_lines(n)
total       = (base × multiplier) + lines
```

Where:
- `tier_tools`, `tier_reqs`, `tier_lines` are step functions mapping counts to
  hours (see Section 5.1 rates)
- `tier_active` = active_minutes × 4 ÷ 60
- `iteration_factor` = 1.0 + adjustments for conversation turns and iteration depth
- `scope_factor` = 1.0 + adjustments for files touched

**Strengths:** Reproducible, transparent, no API dependency, always consistent.

**Limitations:** Cannot understand *context* — treats 100 tool invocations the
same whether they were trivial file reads or complex debugging sessions.

### 6.3 How They Complement Each Other

The report shows both estimates side by side in the Estimation Evidence table.
The AI estimate captures semantic understanding; the formula provides a
transparent, auditable floor. When the two diverge significantly, it signals
that either the AI missed something or the formula's tiers need recalibration.

---

## 7. Validation and Limitations

### What we can validate
- **Internal consistency:** Formula estimates are deterministic and reproducible
  from the same session metrics.
- **Cross-signal agreement:** When tool count, request count, active time, and
  lines all point to the same tier, confidence is high.
- **Directional correctness:** Larger, more complex sessions consistently
  produce higher estimates than quick one-off tasks.

### Known limitations
- **No ground truth.** We lack actual time-tracking data for "how long would
  this have taken without AI?" The estimates are informed approximations.
- **Session boundaries matter.** If a user splits work across many short sessions
  vs. one long session, the aggregation logic must handle this — and currently
  aggregates per-project per-day.
- **Tokens are excluded** from the formula by design. LLM token counts are noisy
  (include system prompts, cache reads, retries) and don't map linearly to
  human effort. This aligns with Alaswad et al.'s observation that token usage
  needs further research to correlate with actual effort savings.
- **Non-coding work is harder to estimate.** The signal set is strongest for
  software engineering tasks. Product management, design, and strategic analysis
  work produces fewer measurable artifacts, so estimates for those tasks rely
  more heavily on the AI's semantic understanding than on the formula.

### Future directions
- **Feedback loop:** Allow users to override estimates and use corrections to
  recalibrate the formula and prompt over time.
- **Task-type-specific rates:** Different productivity rates for coding vs.
  research vs. design work, automatically classified from tool distribution.
- **Cross-user calibration:** Aggregate anonymised data across users to build
  statistical models of effort by task type and signal profile.

---

## 8. References

1. Alaswad, M., et al. (2026). "Toward LLM-Aware Software Effort Estimation:
   A Conceptual Framework." *Frontiers in Artificial Intelligence.*
   https://www.frontiersin.org/articles/10.3389/frai.2026.XXXXX

2. Boehm, B. (1981, 1995). *Software Engineering Economics* and COCOMO II.
   University of Southern California.
   https://athena.ecs.csus.edu/~bucklერ/CSc233/COCOMO_II.pdf

3. Cambon, J., et al. (2023). "Early LLM-based Tools for Enterprise Information
   Workers Likely Provide Meaningful Boosts to Productivity." Microsoft Research.
   https://www.microsoft.com/en-us/research/publication/early-llm-based-tools/

4. Chen, O., Paas, F., & Sweller, J. (2023). "A Cognitive Load Theory Approach
   to Defining and Measuring Task Complexity." *Educational Psychology Review.*
   https://link.springer.com/article/10.1007/s10648-023-09782-w

5. Forsgren, N., Storey, M.-A., Maddila, C., Zimmermann, T., Houck, B., &
   Butler, J. (2021). "The SPACE of Developer Productivity."
   *Communications of the ACM*, 64(1), 99–106.
   https://cacm.acm.org/magazines/2021/1/249459-the-space-of-developer-productivity

6. Hao, Z., et al. (2023). "Towards Understanding the Measurement of Code
   Complexity: A Neuroscience-based Study." *Frontiers in Neuroscience.*
   https://www.frontiersin.org/articles/10.3389/fnins.2023.XXXXX

7. Lavazza, L., Morasca, S., & Tosi, D. (2024). "On the Role of Functional
   Complexity in Software Effort Estimation." *Information and Software
   Technology.*
   https://www.mdpi.com/XXXXX

8. Morcov, S., Pintelon, L., & Kusters, R. (2020). "Definitions, Characteristics
   and Measures of IT Project Complexity." *International Journal of Information
   Technology Project Management.*

9. Peng, S., Kalliamvakou, E., Cihon, P., & Demirer, M. (2023). "The Impact of
   AI on Developer Productivity: Evidence from GitHub Copilot."
   *arXiv:2302.06590.*

10. Tregubov, A., Rodchenko, N., Boehm, B., & Lane, J. A. (2017). "Impact of
    Task Switching and Work Interruptions on Software Development Processes."
    *ICSSP '17.*
    https://www.researchgate.net/publication/XXXXX

11. Ziegler, A., Kalliamvakou, E., Li, X. A., Rice, A., Rifkin, D., Simister, S.,
    Sittampalam, G., & Aftandilian, E. (2024). "Measuring GitHub Copilot's
    Impact on Productivity." *Communications of the ACM*, 67(3), 54–63.
    https://cacm.acm.org/magazines/2024/3/measuring-github-copilots-impact

---

*This methodology is open source and evolving. Contributions, corrections, and
calibration data are welcome at
[github.com/microsoft/What-I-Did-Copilot](https://github.com/microsoft/What-I-Did-Copilot).*
