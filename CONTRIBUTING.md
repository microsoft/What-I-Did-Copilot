# Contributing to What I Did (Copilot)

Thank you for your interest in contributing! We welcome improvements to the
report design, estimation methodology, prompt calibration, and documentation.

## How to Contribute

1. **Fork the repo** and create a feature branch
2. **Make your changes** — see below for what we accept
3. **Test locally** — run `python whatidid.py --date 7D` and verify the report generates correctly
4. **Submit a PR** with a clear description of what changed and why

## What We Accept

- **Prompt improvements** — better calibration, new task types, improved goal grouping
  (edit files in `prompts/`)
- **New signals** — additional session metrics that improve effort estimation accuracy
- **Report design** — layout, visualisation, and UX improvements to the HTML report
- **Documentation** — corrections, clarifications, or expansions to the methodology doc
- **Bug fixes** — especially around session parsing, metric aggregation, or encoding issues
- **Cross-platform support** — Linux/macOS compatibility improvements

## What We Don't Accept

- Changes that introduce telemetry, tracking, or external data collection
- Hardcoded personal identifiers (usernames, emails, paths)
- Dependencies beyond the Python standard library (the tool is zero-install by design)

## Editing Prompts

All AI prompts and classification rules live in `prompts/` as plain text files.
You can edit them without touching Python code:

| File | What it controls |
|------|-----------------|
| `prompts/analysis.txt` | Main AI analysis prompt (goal grouping, effort estimation, output schema) |
| `prompts/skills_taxonomy.txt` | Domain and tech skill labels |
| `prompts/intent_classification.txt` | Collaboration intent regex patterns and colours |
| `prompts/role_classification.txt` | Professional role keyword mappings |

## Calibration Changes

If you're adjusting effort estimation rates or multipliers:

1. Document your rationale — cite research or show before/after comparisons
2. Update `docs/effort-estimation-methodology.md` to match
3. Update the prompt in `prompts/analysis.txt` to match
4. Update the signal guide in `report.py` to match
5. Run a 7D and 30D report and verify the AI-to-formula gap is reasonable (~1.5-2×)

## Code Style

- Python 3.10+ with type hints where helpful
- No external dependencies for core functionality
- Keep the report as a single self-contained HTML file (email-compatible)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
