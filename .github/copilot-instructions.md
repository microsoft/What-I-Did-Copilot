---
description: "Instructions for working on the What-I-Did-Copilot codebase — a tool that generates branded HTML impact reports from GitHub Copilot session logs."
globs: "**/*.py"
---

# What-I-Did-Copilot Development Instructions

## Architecture

This is a Python CLI tool with four core modules:
- `harvest.py` — reads Copilot session logs from `~/.copilot/session-state/`, extracts messages, tool calls, code changes, and computes metrics
- `analyze.py` — sends session transcripts to GitHub Models API for semantic analysis, with a heuristic fallback when API is unavailable
- `report.py` — generates a self-contained HTML report with KPI cards, goal summaries, collaboration charts, and estimation evidence
- `whatidid.py` — CLI entry point that orchestrates harvest → analyze → report → email

## Key Conventions

- **Zero external dependencies** — core functionality uses only the Python standard library + GitHub Models API
- **All prompts live in `prompts/`** as plain text files — never hardcode prompt text in Python
- **The HTML report must be email-compatible** — use inline styles, table-based layout, no JavaScript for content (JS only for interactive toggles)
- **Browser report renders at 960px**, email version at 700px — controlled by `max_width` parameter on `generate_html()`
- **Session metrics include enriched signals** — `substantive_turns`, `reads`, `edits`, `runs`, `iteration_depth`, `files_touched_count` — always aggregate these alongside the original fields

## Effort Estimation

The estimation methodology is research-grounded (see `docs/effort-estimation-methodology.md`). When modifying estimation logic:
- Update the formula in `report.py` (`compute_formula_estimate`)
- Update the AI prompt in `prompts/analysis.txt` (Step 2 signal rates)
- Update the signal guide in `report.py` (`_signal_guide`)
- Update the methodology doc in `docs/effort-estimation-methodology.md`
- All four must stay aligned

## Project Name Consistency

All report sections must show the same project names. The `project_label_map` in `generate_html()` maps raw session folder names to AI-generated goal labels. When adding new sections that display project names, use this map.

## Privacy

Never add telemetry, tracking, or external data collection. The tool is local-first. The privacy banner at the top of every report is intentional.
