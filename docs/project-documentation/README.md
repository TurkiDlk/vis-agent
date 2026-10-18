# Visualization Agent: Project Documentation

The visualization team turns a finished CSV from an upstream data agent into a correct, readable chart. One lead
agent chooses every step; code checks everything that can be checked. This documentation describes branch
`test-agent` at commit `8da1564`, verified against the code on 2026-10-18.

## Sections

| # | Section | Read it to learn |
| --- | --- | --- |
| 1 | [The System Structure](01-system-structure.md) | Purpose and principles, components, the end-to-end pipeline, saved state, inputs and outputs, glossary |
| 2 | [Stack & Architecture](02-stack-and-architecture.md) | Technologies, the architecture diagram, model seats and providers, module map, entry points, files to read first |
| 3 | [How It Works](03-how-it-works.md) | A routine request as a sequence diagram, the lead's 14 tools, every stage, the request lifecycle, budgets |
| 4 | [Rulesets](04-rulesets.md) | Every validation layer: input contracts, source reading, spec grammar and checks, resolve rules, inspector evidence, policy rules (H/S/C/I), analyst SQL guard, lead convergence rules |
| 5 | [Design Decisions](05-design-decisions.md) | Each decision with its reason and cost, known gaps (G1–G10), the experiment evidence, key takeaways |

**Suggested path:** new readers go 1 → 3 → 4. To change the code, start with section 2 ("files to read first").

## Status labels

| Label | Meaning |
| --- | --- |
| **[Runtime]** | Implemented and on the production request path (chat, API, CLI). |
| **[Offline]** | Implemented, but used only by evaluations or explicit developer commands. Never gates a user request. |
| **[Optional]** | Implemented, but off by default or used only when the lead or an operator chooses it. |
| **[Proposed]** | Written down (patch, plan, or note) but not applied to the code. |
| **[Gap]** | A known defect, or a mismatch between documentation and code. |

## Sources

The product contract is `AGENTS.md`; the current design is `docs/lead-directed-team.md`. All file paths are relative to
the repository root, and line references (`file.py:120`) point to commit `8da1564`. Numbers quoted from `docs/experiments/` and `docs/phase-*-lessons.md` are as reported there
and were not re-run.
