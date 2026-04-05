# Effort Estimation Methodology

**How this tool estimates the human-equivalent effort of AI-assisted work**

This document describes the research basis, signals, and calibration logic behind
the effort estimates in *What I Did (Copilot)*. Every design decision traces to a
specific research finding. The methodology draws on peer-reviewed research in
software engineering cost estimation, cognitive load theory, and the emerging
field of LLM-assisted productivity measurement.

---

## 1. The Core Question

> If a skilled professional had done this work entirely without AI assistance,
> how many hours would it have taken?

This is the "human-equivalent effort" — the counterfactual cost of the work that
Copilot accelerated. It is **not** how long the user spent, nor how long the AI
took. It is what a competent expert would bill for delivering the same outcome
by hand.

---

## 2. Research → Design Decisions

### 2.1 "No single metric captures effort" → Multi-signal max() formula

Classic software effort estimation relies on size-oriented metrics — lines of
code (LOC) and function points (FP). However:

- **Lavazza et al. (2024)** analysed hundreds of projects and found that simpler
  proxies (counting requirements or data entities) performed as well as full
  function-point analysis — and *all* methods underestimated effort on highly
  complex projects.

- **Hao et al. (2023)** measured actual brain activity (EEG) and eye-tracking of
  developers and found that popular code complexity metrics (cyclomatic complexity,
  Halstead volume) often *mis-predict* how hard code is for humans to understand.

- **Forsgren et al. (2021)** proposed the SPACE framework, arguing that productivity
  requires measuring multiple dimensions: Satisfaction, Performance, Activity,
  Communication, and Efficiency.

**Our response:** We take `max(tools, turns, active)` — each signal measures the
same work from a different angle, and the strongest signal wins as the base. Lines
of code are additive because coding output is independent work beyond research and
iteration. No single number drives the estimate alone.


### 2.2 "LLMs provide 1.4–4× speed-ups" → Active time × 4 multiplier

- **Cambon et al. (2023)** — Microsoft's AI Productivity study synthesised 30+
  experiments and found that participants with Copilot tools completed tasks in
  26–73% of the time (1.4× to 4× faster) without significant quality loss.

- **Peng et al. (2023)** — In a controlled trial with 95 developers, those using
  GitHub Copilot completed a programming task **55.8% faster** on average.

**Our response:** `active_minutes × 4 / 60` converts the user's engagement time to
human-equivalent hours. The 4× multiplier sits at the upper end of observed speed-ups
because Copilot handles the easier portions while the human retains the harder parts.


### 2.3 "78% of 'complex' tasks done in <25% effort; 22% of 'simple' tasks took >180%" → Task-type classification with caps

- **Alaswad et al. (2026)** documented that human-perceived complexity is a poor
  predictor of AI-assisted effort. Installing a tool seems "complex" but AI
  handles it in seconds. Integrating a one-line change into legacy code seems
  "simple" but may require extensive verification.

**Our response:** The AI prompt classifies tasks by type using tool distribution
(read-heavy = research, edit-heavy = implementation, run-heavy = debugging).
Mechanical tasks (install, deploy, git push) are **always capped at 0.25–0.5h**
regardless of tool count. Complex multi-step tasks (balanced reads + edits + runs)
get the full formula treatment.


### 2.4 "Suggestion counts are misleading — acceptance rate matters" → Reqs capped by turns

- **Ziegler et al. (2024)** found that the **acceptance rate of AI suggestions**
  is a meaningful productivity signal. Higher acceptance = less rework = lower
  human effort. Raw suggestion counts are misleading — high counts with low
  acceptance mean wasted overhead, not productive work.

Premium requests include both user-initiated conversations AND automated inline
code completions. A session with 276 premium requests but only 8 conversation
turns is mostly automated completions — valuing each at "8–12 min of thinking"
would absurdly overestimate.

**Our response:** When conversation turns data is available, it replaces premium
requests as the primary interaction signal. Premium requests are excluded from the
`max()` base calculation. Effective reqs are capped at 10× conversation turns.


### 2.5 "Iteration count and prompt efficiency predict true complexity" → Iteration depth multiplier

- **Chen et al. (2023)** introduced "prompt efficiency" — measuring how many
  interactions were needed before the AI produced a correct solution — as an
  indicator of task complexity. Ambiguous tasks led to lengthy prompt dialogues
  and increased human effort.

- **Alaswad et al. (2026)** identified **iterative reasoning cycles** as one of
  five key dimensions driving effort in LLM-assisted work.

**Our response:** `iteration_depth` (average edits per file) and `conversation_turns`
both contribute complexity multipliers:

| Signal | Threshold | Multiplier |
|--------|-----------|------------|
| Conversation turns > 15 | Moderate iteration | +15% |
| Conversation turns > 40 | Heavy iteration | +35% cumulative |
| Iteration depth > 5 edits/file | Debugging/refinement | +15% |
| Iteration depth > 12 edits/file | Extensive rework | +35% cumulative |


### 2.6 "Broader scope projects have significantly larger effort overruns" → Files-touched multiplier

- **Morcov et al. (2020)** reviewed 125 IT projects and found that projects with
  more stakeholders, requirements, and moving parts had significantly larger
  effort overruns.

- **Tregubov et al. (2017)** measured that software engineers working across
  multiple contexts spent **17% of their time** simply recovering from context
  switches.

**Our response:** `files_touched_count` adjusts the estimate upward:

| Files touched | Multiplier | Rationale |
|---------------|------------|-----------|
| ≤ 3 | 1.0× | Contained scope |
| 4–10 | 1.1× | Cross-cutting changes, integration testing |
| 11+ | 1.3× | System-wide impact, heavy context-switching (Tregubov: 17% loss) |


### 2.7 "Code volume is decoupled from effort in AI-assisted work" → Lines as additive, not primary

- **Alaswad et al. (2026)** emphasise that an LLM can generate 1,000 lines of
  boilerplate in seconds. But an expert human writing 500 lines of production
  code needs 4+ hours.

**Our response:** Lines are additive on top of the base estimate (not part of the
`max()`). They use an effective rate of ~200 LoC/hr in the formula (higher than the
raw 100–150 LoC/hr expert rate because some writing effort is already captured in
tool invocations).

| Lines added | Formula hours | Rationale |
|-------------|---------------|-----------|
| 1–50 | 0.25h | Config tweak |
| 51–150 | 0.75h | Small feature |
| 151–300 | 1.5h | Moderate module |
| 301–500 | 2.5h | Major implementation |
| 501–800 | 4h | Large build |
| 800+ | lines ÷ 200 | Continuous scaling |


### 2.8 "New effort emerges in managing the AI" → Conversation turns as primary interaction signal

- **Vaithilingam et al. (2022)** observed that programmers using a code generator
  spent significant time **iteratively probing and correcting the AI** — adding
  cognitive load even as the AI saved them typing.

- **Santos et al. (2025)** found that while code-writing effort decreased with AI,
  effort spent on **debugging and validating AI-generated code remained high**.

**Our response:** `_tier_turns()` is the primary interaction signal, replacing
premium requests. Each turn represents a full cognitive cycle: formulate the
problem, evaluate the response, decide next steps (~5–10 min per turn):

| Turns | Formula hours | Typical scenario |
|-------|---------------|------------------|
| 1–3 | 0.25h | Quick Q&A |
| 4–8 | 0.75h | Focused task |
| 9–15 | 1.5h | Working session |
| 16–30 | 3h | Extended session |
| 31–60 | 5h | Deep collaboration |
| 61–100 | 8h | Full-day partnership |
| 100+ | 12h | Marathon session |

---

## 3. The Five-Dimension Framework

Our estimation model is grounded in the **Hybrid Intelligence Effort** framework
proposed by Alaswad et al. (2026), which identifies five dimensions that drive
effort in LLM-assisted work:

| # | Dimension | What it measures | Our session-log proxy |
|---|-----------|------------------|-----------------------|
| 1 | **LLM reasoning complexity** | How hard was it for the AI to solve | `conversation_turns`, conversation depth |
| 2 | **Context completeness** | Did the task need external lookups/clarification | File reads, searches, web fetches (from tool distribution) |
| 3 | **Transformation scope** | Breadth and impact of changes | `files_touched`, `lines_added`, `lines_removed` |
| 4 | **Iterative reasoning cycles** | Back-and-forth to reach a solution | `conversation_turns`, `iteration_depth` (re-edits per file) |
| 5 | **Human oversight effort** | Review, testing, correction by the human | `active_minutes` relative to `wall_clock_minutes` (engagement ratio) |

---

## 4. The Complete Formula

### 4.1 Deterministic formula (transparent, auditable)

```
Step 1 — Primary signals (take the strongest):
    tool_h   = tier_tools(tool_invocations)
    turns_h  = tier_turns(conversation_turns)
    active_h = active_minutes × 4 ÷ 60

    if conversation_turns > 0:
        base = max(tool_h, turns_h, active_h)
    else:
        req_h = tier_reqs(premium_requests)     # fallback for older sessions
        base  = max(tool_h, req_h, active_h)

Step 2 — Complexity multipliers:
    iteration_factor = 1.0
        + 0.15 if turns > 15
        + 0.20 if turns > 40
        + 0.15 if iteration_depth > 5
        + 0.20 if iteration_depth > 12

    scope_factor = 1.0
        + 0.10 if files_touched > 3
        + 0.20 if files_touched > 10

Step 3 — Lines of code (additive):
    lines_h = tier_lines(lines_added)

Step 4 — Total:
    total = (base × iteration_factor × scope_factor) + lines_h
    total = max(total, 0.25)                          # floor
    total = round to nearest 0.25h
```

### 4.2 Worked example

> **Project:** Built a reporting tool — 150 tools, 25 turns, 40 reqs,
> 45m active, +320 lines, 6 files, 8.2 edits/file

```
Step 1 — Primary signals:
    Tools: 150 → 5h
    Turns: 25  → 3h
    Active: 45m × 4 = 3h
    Base = max(5, 3, 3) = 5h

Step 2 — Complexity multipliers:
    Turns 25 > 20        → +10%
    Iter. depth 8.2 > 5  → +10%
    Files 6 > 5          → +10%
    Combined: 1.1 × 1.1 × 1.1 = 1.33×

Step 3 — Lines (additive):
    320 lines → 1.5h

Step 4 — Total:
    (5h × 1.33) + 1.5h = 6.65 + 1.5 = 8.25h
```

### 4.3 AI estimate (semantic)

An LLM reads the full session transcript — every user instruction, every tool
action, every code change — and produces a calibrated estimate using the same
research-backed anchors described in Section 2. This is the "AI Est." column.

**Strengths:** Understands *what* was done (not just counts), can distinguish
trivial boilerplate from novel architecture, captures nuance.

**Limitations:** Depends on prompt quality; cached per analysis run; may vary
across model versions.

### 4.4 How they complement each other

The report shows both estimates side by side in the Estimation Evidence table.
The AI estimate captures semantic understanding; the formula provides a
transparent, auditable floor. When the two diverge significantly, it signals
that either the AI missed something or the formula's tiers need recalibration.

---

## 5. Caps and Floors

| Rule | Rationale |
|------|-----------|
| Mechanical tasks (install, deploy, git push) → 0.25–0.5h max | These are execution, not thinking. Alaswad's complexity inversion: AI handles these trivially. |
| Trivial sessions (<5 reqs AND <10 tools) → capped at 1h total | The work was inherently lightweight regardless of other signals. |
| No single task exceeds 8h | If the work is that large, it should be split into sub-tasks for granularity. |
| Premium reqs capped at 10× conversation turns | Excess reqs are automated completions, not human thinking (Ziegler et al. 2024). |

---

## 6. Validation and Limitations

### What we can validate
- **Internal consistency:** Formula estimates are deterministic and reproducible
  from the same session metrics.
- **Cross-signal agreement:** When tool count, conversation turns, active time, and
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

## 7. References

1. Alaswad, M., et al. (2026). "Toward LLM-Aware Software Effort Estimation:
   A Conceptual Framework." *Frontiers in Artificial Intelligence.*
   https://www.frontiersin.org/journals/artificial-intelligence

2. Boehm, B. (1981, 1995). *Software Engineering Economics* and COCOMO II.
   University of Southern California.

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
   https://www.frontiersin.org/journals/neuroscience

7. Lavazza, L., Morasca, S., & Tosi, D. (2024). "On the Role of Functional
   Complexity in Software Effort Estimation." *Information and Software Technology.*

8. Morcov, S., Pintelon, L., & Kusters, R. (2020). "Definitions, Characteristics
   and Measures of IT Project Complexity." *International Journal of Information
   Technology Project Management.*

9. Peng, S., Kalliamvakou, E., Cihon, P., & Demirer, M. (2023). "The Impact of
   AI on Developer Productivity: Evidence from GitHub Copilot."
   *arXiv:2302.06590.*

10. Santos, N., et al. (2025). "The Impact of AI Code Assistants on Developer
    Workload." *IEEE Software.*

11. Tregubov, A., Rodchenko, N., Boehm, B., & Lane, J. A. (2017). "Impact of
    Task Switching and Work Interruptions on Software Development Processes."
    *ICSSP '17.*

12. Vaithilingam, P., Zhang, T., & Glassman, E. L. (2022). "Expectation vs.
    Experience: Evaluating the Usability of Code Generation Tools Powered by
    Large Language Models." *CHI EA '22.*

13. Ziegler, A., Kalliamvakou, E., Li, X. A., Rice, A., Rifkin, D., Simister, S.,
    Sittampalam, G., & Aftandilian, E. (2024). "Measuring GitHub Copilot's
    Impact on Productivity." *Communications of the ACM*, 67(3), 54–63.
    https://cacm.acm.org/magazines/2024/3/measuring-github-copilots-impact

---

*This methodology is open source and evolving. Contributions, corrections, and
calibration data are welcome at
[github.com/microsoft/What-I-Did-Copilot](https://github.com/microsoft/What-I-Did-Copilot).*
