# Experiment Log (Faisal): chart-generator-model

A **deterministic-first chart agent**: code does every step it can do reliably, and Gemma models make only the
judgements code can't. A CSV and an optional question go in. A reviewed Plotly chart comes out, in Arabic or
English, with a short insight text checked against code's facts.

This log covers the sibling repo `chart-generator-model` (branch `fm-visualization_agent_with_ollama_cloud`,
commit `55aad3c`, 2026-09-15 to 10-15) and the Claude Code chats that built it.

> **Result:** on a held-out set labelled blind before any run, **72/93 (77%)** top charts were acceptable and
> 12/12 numbers were exact. Later fixes reached 81/93, but they saw those cases, so a fresh set is needed. Labels
> are model-generated; the owner's spot-check is outstanding.

| # | Section | What's in it |
| --- | --- | --- |
| 1 | [System Structure](01-system-structure.md) | Goal, principles, parts |
| 2 | [Stack & Architecture](02-stack-and-architecture.md) | Technologies, layers, model roles |
| 3 | [How It Works](03-how-it-works.md) | One request, chart choice, review loop, screenshots |
| 4 | [Rulesets](04-rulesets.md) | The rules every chart is checked against |
| 5 | [Design Decisions](05-design-decisions.md) | Main decisions, measured results, open gaps |
| 6 | [Work Log](06-work-log.md) | Timeline, chats, lessons, what carries over here |

**Short on time:** read 1, then 5. **Porting a feature:** read 6.4.

**Sources.** Paths are relative to `chart-generator-model/`: `docs/PROJECT_BRIEF.md`, `docs/decisions/`
(ADRs 0001–0081), `docs/phase-notes/`, `backend/evals/reports/`, and four chat transcripts. Numbers are quoted as
reported, not re-run. **[Measured]** marks one; **[Open]** marks something waiting for review.
