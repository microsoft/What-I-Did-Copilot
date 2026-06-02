"""best_practices.py — research-backed best-practice catalogue.

Each entry encodes one optimization practice published by Anthropic,
OpenAI, GitHub, or a recognised AI thought leader. The catalogue gives
the report renderer a single source of truth for icon, label, ranking
weight, and source attribution per detector kind, so adding a new
detector becomes:

    1. write the detector in harvest._analyze_burn_patterns (it emits
       a finding with the matching `kind` string)
    2. add the catalogue entry here with its citation

Sources are spelled out so users can read the underlying guidance.
Detection logic lives in harvest.py — this module is data only.
"""

# Each catalogue entry is a dict so we can extend it without touching
# call sites that only need icon/label.  Keys:
#
#   icon         single emoji for the report row gutter
#   label        short display name (≤ 28 chars)
#   weight       1..5 — tie-breaker when two findings have equal credits
#   source       short attribution string ("Anthropic", "OpenAI",
#                "GitHub", or a named person)
#   source_url   public URL (clickable in the HTML report)
#   summary      one-sentence rationale (≤ 120 chars) — surfaced as
#                a tooltip/inline copy under the citation
BP_CATALOGUE: dict[str, dict] = {
    # ── existing detectors (migrated with citations) ─────────────────
    "hot_file": {
        "icon": "🔁",
        "label": "Repeated file churn",
        "weight": 3,
        "source": "Anthropic — context engineering",
        "source_url": "https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents",
        "summary": "Just-in-time retrieval with narrow reads outperforms repeated whole-file scans.",
    },
    "fail_loop": {
        "icon": "❌",
        "label": "Failed-retry loop",
        "weight": 4,
        "source": "Anthropic — writing tools for agents",
        "source_url": "https://www.anthropic.com/engineering/writing-tools-for-agents",
        "summary": "Each retry re-pays the full context; sanity-check inputs once before the first call.",
    },
    "compaction_storm": {
        "icon": "📦",
        "label": "Long-session compaction",
        "weight": 2,
        "source": "Anthropic — harness design",
        "source_url": "https://www.anthropic.com/engineering/harness-design-long-running-apps",
        "summary": "Context resets beat compaction for long tasks — compaction alone keeps paying for old summaries.",
    },
    "output_spike": {
        "icon": "📈",
        "label": "Large single-turn output",
        "weight": 3,
        "source": "OpenAI — GPT-5 prompting guide",
        "source_url": "https://github.com/openai/openai-cookbook/blob/main/examples/gpt-5/gpt-5_prompting_guide.ipynb",
        "summary": "Break multi-part work across turns; peak performance comes from one focused goal per turn.",
    },
    "exploration_premium": {
        "icon": "🔍",
        "label": "Investigation on premium model",
        "weight": 2,
        "source": "Anthropic — model routing",
        "source_url": "https://docs.anthropic.com/en/docs/claude-code/costs",
        "summary": "Reserve frontier reasoning models for true complexity; route read-only work to lighter models.",
    },
    "broad_search_repeat": {
        "icon": "🌐",
        "label": "Broad search repetition",
        "weight": 1,
        "source": "Anthropic — Claude Code best practices",
        "source_url": "https://docs.anthropic.com/en/docs/claude-code/best-practices",
        "summary": "Narrow grep/glob beats broad scanning — repeated broad scans rediscover the same files.",
    },

    # ── new detectors backed by published guidance ───────────────────
    "parallel_missed": {
        "icon": "⏸️",
        "label": "Sequential single-tool turns",
        "weight": 3,
        "source": "Anthropic — multi-agent research system",
        "source_url": "https://www.anthropic.com/engineering/multi-agent-research-system",
        "summary": "Independent tool calls can run in parallel — Anthropic reports up to 90% latency reduction.",
    },
    "no_verification": {
        "icon": "🧪",
        "label": "No runnable verification",
        "weight": 3,
        "source": "Anthropic — effective harnesses",
        "source_url": "https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents",
        "summary": "Without a check the agent can run, 'looks done' becomes the only stopping signal.",
    },
    "subagent_missed": {
        "icon": "🪆",
        "label": "No delegation in long session",
        "weight": 2,
        "source": "Anthropic — costs guide",
        "source_url": "https://docs.anthropic.com/en/docs/claude-code/costs",
        "summary": "Delegating verbose ops (tests, doc fetches, broad scans) to subagents keeps the main context clean.",
    },
    "bundled_prompt": {
        "icon": "🧺",
        "label": "Multi-goal user message",
        "weight": 2,
        "source": "OpenAI — GPT-5 prompting guide",
        "source_url": "https://github.com/openai/openai-cookbook/blob/main/examples/gpt-5/gpt-5_prompting_guide.ipynb",
        "summary": "Distinct, separable tasks perform best when split across turns — bundles force expensive reconciliation.",
    },
    "model_thrash": {
        "icon": "🔀",
        "label": "Model switching mid-session",
        "weight": 2,
        "source": "GitHub — auto model selection",
        "source_url": "https://docs.github.com/en/copilot/concepts/auto-model-selection",
        "summary": "Switching models mid-session crosses cache boundaries — costs go up without quality gains.",
    },
}


def get(kind: str) -> dict:
    """Return the catalogue entry for `kind` or a safe default."""
    return BP_CATALOGUE.get(kind, {
        "icon": "•",
        "label": kind,
        "weight": 0,
        "source": "",
        "source_url": "",
        "summary": "",
    })
