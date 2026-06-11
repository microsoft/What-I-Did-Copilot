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

### 2.1 "No single metric captures effort" → Two complementary estimation systems

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

| System | Approach | Strength | Limitation |
|--------|----------|----------|------------|
| Deterministic formula | `base × complexity_mult` where `base = max(interaction_h + lines_h + reads_h + tools_h, active_anchor_h)` (log curves + active-time floor + bounded multiplier) | Transparent, reproducible, auditable floor | Cannot see context, business value, or qualitative complexity |
| AI semantic estimate | Reads full transcript, applies judgment using active time × 2–6 as anchor | Understands what was done, distinguishes boilerplate from architecture | Depends on prompt quality, may vary across model versions |

**Our response:** We use two complementary systems — a deterministic formula as
the transparency floor, and an AI semantic estimate as the primary output. Each
addresses a different failure mode: the formula is reproducible and auditable but
blind to context; the AI understands what was done but is opaque. No single number
drives the estimate alone.


### 2.2 "LLMs provide 1.4–4× speed-ups" → Active time as estimation anchor

- **Cambon et al. (2023)** — Microsoft's AI Productivity study synthesised 30+
  experiments and found that participants with Copilot tools completed tasks in
  26–73% of the time (1.4× to 4× faster) without significant quality loss.

- **Peng et al. (2023)** — In a controlled trial with 95 developers, those using
  GitHub Copilot completed a programming task **55.8% faster** on average.

**Our response:** Active time is a primary anchor for both estimators. The
deterministic formula uses an **active-time anchor floor**
(`active_anchor_h = active_minutes × 5`) via
`base = max(additive_terms, active_anchor_h)`, so agentic sessions with heavy
review/decision work are not undercounted by mechanical counters alone. The AI
estimator applies the speedup contextually (typically ×2–6) based on work type
and transcript evidence:

| Work type | Speedup applied | Rationale |
|-----------|-----------------|-----------|
| Mechanical/routine | ×2 | 1.4× lower bound — AI handles most of the work |
| Implementation/feature | ×3 | Midpoint of the 1.4–4× research range |
| Design/debugging/research | ×4 | Upper bound (Cambon et al.) — human thinking dominates |
| Complex iterative work | ×5–6 | High iteration depth or broad scope (complexity multiplier) |


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

> **Billing-model note (2026-06-01):** GitHub Copilot's "premium requests"
> (PRUs) were superseded by **GitHub AI Credits** — a token-priced billing
> model where 1 credit = $0.01 USD. Sessions logged after the migration
> emit `totalAiCredits` (or, if not yet emitted, this repo computes credits
> locally from `tokens × per-model rate`). For effort estimation the
> *request counter* is still useful as a fallback interaction signal when
> conversation-turn data is unavailable, regardless of whether it's
> labelled as PRUs (legacy) or derived from `modelMetrics.requests.count`
> (new). The wording below refers to "premium requests" for historical
> accuracy; substitute "request counter" mentally.

Premium requests include both user-initiated conversations AND automated inline
code completions. A session with 276 premium requests but only 8 conversation
turns is mostly automated completions — valuing each at "8–12 min of thinking"
would absurdly overestimate.

**Our response:** When conversation turns data is available, it replaces premium
requests as the primary interaction signal. Premium requests are excluded from the
`max()` base calculation. Effective reqs are capped at 10× conversation turns.


### 2.5 "Iteration count and prompt efficiency predict true complexity" → Iteration depth as complexity multiplier

- **Chen et al. (2023)** introduced "prompt efficiency" — measuring how many
  interactions were needed before the AI produced a correct solution — as an
  indicator of task complexity. Ambiguous tasks led to lengthy prompt dialogues
  and increased human effort.

- **Alaswad et al. (2026)** identified **iterative reasoning cycles** as one of
  five key dimensions driving effort in LLM-assisted work.

**Our response:** The deterministic formula now includes a bounded **complexity
multiplier** (1.0–1.60×) that activates when the base estimate ≥ 0.50h.
`iteration_depth` (average edits per unique file) directly measures rework
intensity — the "iterative reasoning cycles" that Alaswad et al. identify as a
key effort driver. The multiplier applies tiered boosts:

| Iteration depth | Multiplier contribution | Interpretation |
|-----------------|------------------------|----------------|
| < 2.5 | +0% | Normal editing — no rework signal |
| ≥ 2.5 | +10% | Moderate rework or refinement |
| ≥ 5.0 | +25% (cumulative) | Heavy debugging / iteration cycles |
| ≥ 10.0 | +35% (cumulative) | Extreme rework — multiple failed approaches |

The logarithmic `turns_h` curve still handles basic iteration implicitly (each
additional turn adds diminishing effort), but the complexity multiplier captures
the *qualitative* difference: a session with 10 edits per file is fundamentally
harder than one with 1 edit per file, even at the same turn count.


### 2.6 "Broader scope projects have significantly larger effort overruns" → Files touched as bounded complexity modifier

- **Morcov et al. (2020)** reviewed 125 IT projects and found that projects with
  more stakeholders, requirements, and moving parts had significantly larger
  effort overruns.

- **Tregubov et al. (2017)** measured that software engineers working across
  multiple contexts spent **17% of their time** simply recovering from context
  switches.

**Our response:** `files_touched_count` now contributes to the deterministic
formula as a **bounded multiplicative modifier** — not as an independent additive
term. In earlier calibration testing, adding files-touched as an additive formula
term yielded marginal R² of +0.00–0.03 — not statistically significant as a
standalone effort predictor. However, as a *multiplier* applied to an
already-meaningful base (≥ 0.50h), it amplifies the estimate for genuinely
broad-scope sessions without inflating trivial ones:

| Files touched | Multiplier contribution | Interpretation |
|---------------|------------------------|----------------|
| < 5 | +0% | Focused single-module change |
| ≥ 5 | +10% | Multi-file change with context switching |
| ≥ 10 | +25% (cumulative) | Broad architectural change |

The complexity multiplier (combining iteration depth and file scope) is capped at
1.60× to keep the formula as a conservative floor. The AI semantic estimator
applies the same logic and may go higher when transcript evidence supports it.


### 2.7 "Code volume is decoupled from effort in AI-assisted work" → Lines as additive, not primary

- **Alaswad et al. (2026)** emphasise that an LLM can generate 1,000 lines of
  boilerplate in seconds. But an expert human writing 500 lines of production
  code needs 4+ hours.

**Our response:** Lines are an additive component in the deterministic base
(`interaction_h + lines_h + reads_h + tools_h`) before the active-time
`max()` anchor and complexity multiplier. They use an effective rate of
~200 LoC/hr in the formula
(higher than the raw 100–150 LoC/hr expert rate because some writing effort is
already captured in tool invocations).

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
premium requests. Only **substantive turns** count — trivial confirmations like
"yes", "commit", "looks good" (under 20 characters) are filtered out, as they
represent ~8-50% of all turns but near-zero human thinking effort. Each
substantive turn represents ~5–7 min of thinking:

| Substantive Turns | Formula hours | Typical scenario |
|-------------------|---------------|------------------|
| 1–3 | 0.25h | Quick Q&A |
| 4–8 | 0.75h | Focused task |
| 9–15 | 1.5h | Working session |
| 16–30 | 3h | Extended session |
| 31–60 | 5h | Deep collaboration |
| 61–100 | 8h | Full-day partnership |
| 100+ | 10h | Marathon session |

---

## 3. The Five-Dimension Framework

Our estimation model is grounded in the **Hybrid Intelligence Effort** framework
proposed by Alaswad et al. (2026), which identifies five dimensions that drive
effort in LLM-assisted work:

| # | Dimension | What it measures | Deterministic formula proxy | AI estimator proxy |
|---|-----------|------------------|----------------------------|-------------------|
| 1 | **LLM reasoning complexity** | How hard was it for the AI to solve | `conversation_turns` (via `turns_h` log curve) | Transcript analysis — assesses problem difficulty |
| 2 | **Context completeness** | Did the task need external lookups/clarification | `read_calls` (via `reads_h` log curve) | Reads tool distribution and investigation patterns |
| 3 | **Transformation scope** | Breadth and impact of changes | `lines_logic` (via `lines_h` log curve) | Distinguishes logic from boilerplate, assesses architectural impact |
| 4 | **Iterative reasoning cycles** | Back-and-forth to reach a solution | `iteration_depth` and `files_touched_count` (via `complexity_mult`) | +25–50% qualitative adjustment for heavy iteration |
| 5 | **Tool execution breadth** | Total tool calls including non-coding work | `tool_invocations` (via `tools_h` log curve) | Recognises image analysis, synthesis, browser tasks |
| 6 | **Human oversight effort** | Review, testing, correction by the human | `active_anchor_h = active_minutes × 5` (base floor via `max()`) | `active_minutes` × 2–6 as primary anchor |

---

## 4. The Complete Formula

### 4A. AI Semantic Estimate (primary output)

An LLM reads the full session transcript — every user instruction, every tool
action, every code change — and produces a calibrated estimate. This is the
primary output shown as the "AI Est." column. The AI uses these anchors:

- **Active time anchor:** `active_minutes × 2` (mechanical/routine) to
  `active_minutes × 4` (design/debugging/research), reflecting the 1.4–4×
  speedup range from Cambon et al.
- **Conversation turns** provide a scale reference — more substantive turns
  generally indicate more complex work requiring more human-equivalent effort.
- **Logic lines** at expert writing speed (80–130 LoC/hr) — the AI distinguishes
  boilerplate generation from novel logic and applies appropriate rates.
- **Read calls** for investigation — heavy reading patterns indicate research
  and context-gathering work that is effort-intensive for humans.
- **Qualitative upward adjustments:**
  - +25–50% for rework (repeated edits to the same files, failed approaches)
  - +20–30% for broad scope (10+ files touched, cross-cutting changes)
- **Mechanical task caps:** 0.25–0.5h always, regardless of other signals.
  Installing a tool or pushing a commit is execution, not thinking.
- **No single task exceeds 8h.** If the work is that large, it should be split
  into sub-tasks for granularity.


### 4B. Deterministic Formula (transparency floor)

```
turns_h  = max(0,  −0.15 + 0.67 × ln(turns + 1))
reqs_h   = max(0,  −0.10 + 0.45 × ln(reqs + 1))     ← fallback when turns = 0
lines_h  = 0.40 × log₂(lines_logic ÷ 100 + 1)
reads_h  = 0.10 × log₂(read_calls + 1)
tools_h  = 0.07 × log₂(tool_invocations + 1)
active_anchor_h = active_minutes ÷ 60 × 5.0

interaction_h = turns_h if turns > 0, else reqs_h
additive_base = interaction_h + lines_h + reads_h + tools_h
base     = max(additive_base, active_anchor_h)
base     = max(base, 0.25)           ← floor at 15 min
complexity_mult = 1.0–1.60 (from iteration_depth + files_touched_count; activates when base ≥ 0.50h)
total    = base × complexity_mult
total    = round to nearest 0.25h
```

**Definitions:**

- **turns** = substantive conversation turns only. Trivial confirmations like
  "yes", "commit", "looks good" (under 20 characters) are excluded, as they
  represent near-zero human thinking effort.
- **reqs** = premium requests (API calls). Used as a fallback interaction signal
  when conversation turn data is unavailable (e.g., older Copilot sessions).
- **lines_logic** = lines added to logic code files only (`.py` `.js` `.ts` `.go`
  `.rs` `.java` `.cs` `.cpp` etc.) — excludes `.html` `.css` `.json` `.md`
  `.yaml` and other non-logic files.
- **read_calls** = file-read tool calls + grep/glob/search/find calls combined.
- **tool_invocations** = total tool calls across a session. Captures non-coding
  work (image analysis, document synthesis, browser automation, data exploration)
  where `lines_logic` = 0 but meaningful work still occurred. Uses a low
  coefficient (0.07) to avoid double-counting with `reads_h` for coding tasks.
- **active_minutes** = active user-engagement minutes in the session. Converted
  to `active_anchor_h = active_minutes ÷ 60 × 5.0` and used as a floor via
  `max(additive_base, active_anchor_h)`.
- **complexity_mult** = bounded multiplier (1.0–1.60×) driven by
  `iteration_depth` and `files_touched_count`; activates only when `base ≥ 0.50h`.

For multi-day merged goals: compute per-day, then sum (matches how the AI
analyses each day independently).


### 4C. Worked example

> **Project:** Built a reporting tool — 22 substantive turns, +400 logic lines,
> +800 boilerplate lines, 35 reads + 15 searches, 120 tool invocations,
> 45 active minutes

```
turns_h = max(0, −0.15 + 0.67 × ln(23)) = 1.95h
lines_h = 0.40 × log₂(400 ÷ 100 + 1)   = 0.40 × 2.32 = 0.93h
reads_h = 0.10 × log₂(50 + 1)           = 0.10 × 5.67 = 0.57h
tools_h = 0.07 × log₂(120 + 1)          = 0.07 × 6.93 = 0.49h
active_anchor_h = 45 ÷ 60 × 5.0         = 3.75h

additive_base = 1.95 + 0.93 + 0.57 + 0.49 = 3.94h
base          = max(3.94, 3.75)            = 3.94h
complexity_mult (low iteration + focused scope) = 1.00
Total         = 3.94 × 1.00 = 3.94h → 4.00h (nearest 0.25h)
```

Note: The 800 boilerplate lines (HTML/CSS/config) are excluded from `lines_logic`
by design — the AI generated them in seconds and they don't represent meaningful
human-equivalent coding effort.


### 4D. How they complement each other

The report shows both estimates side by side in the Estimation Evidence table.
The deterministic formula provides a transparent, reproducible floor — anyone can
verify it from the raw metrics. The AI estimate captures semantic understanding:
what the work *meant*, not just how many artifacts it produced.

R² ≈ 0.40 per signal in the deterministic formula means ~0.45–0.60 of variance
in actual effort is explained by AI semantic judgment — context, business value,
qualitative complexity. This is why the formula serves as the floor and the AI
estimate is the primary output. When the two diverge significantly, it signals
that either the AI identified complexity the formula cannot see, or the formula
caught an edge case the AI overlooked.

---

## 5. Caps and Floors

| Rule | Rationale |
|------|-----------|
| Mechanical tasks (install, deploy, git push) → 0.25–0.5h max | These are execution, not thinking. Alaswad's complexity inversion: AI handles these trivially. |
| No single task exceeds 8h | If the work is that large, it should be split into sub-tasks for granularity. |
| Multi-day goals: formula computed per-day, then summed | Matches how the AI analyses each day independently. Prevents metrics accumulation from inflating estimates. |
| Deterministic formula base floor: 0.25h (15 min minimum) before multiplier | Any meaningful work — even a quick fix — involves context-gathering, understanding, and verification. |

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
