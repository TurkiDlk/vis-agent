# Suggested standards

Proposed rules for the [visualization standards](visualization-standards.md), waiting for review. Suggest one with
`uv run docs/chart-issues/new_issue.py --suggest`, or choose "Suggest a new standard" while logging a chart issue.
An issue that cites a suggestion links here until the suggestion is decided.

## Suggestions

| ID | Suggested rule | Section | Why | From | Status | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| S-001 | No broken axes on bars, columns or areas; use a log scale (3.2) or name the far-out value (3.3) instead. | 3. Honest encoding | A break makes bar lengths lie. It came up when one bar flattened the rest of a long ranking. | [CI-012](chart-issues/2026-10-18-units-by-product-100-command-line.md) | proposed | – |

**Status:** `proposed` (waiting for review), `approved` (Decision is the new rule's number) or `rejected` (Decision
is the reason).

## Reviewing a suggestion

1. Read the suggestion and, if there is one, the issue in **From**.
2. **To approve:**
   - Add the rule to [visualization-standards.md](visualization-standards.md) with the next number in its section:
     one line in the checklist and a fuller rule in Details.
   - Set **Status** to `approved` and **Decision** to the new number, e.g. `4.7`.
   - Run `uv run docs/chart-issues/new_issue.py --sync`. Issues that cited the suggestion now cite the rule.
3. **To reject:** set **Status** to `rejected` and write the reason in **Decision**. Issues keep showing the
   suggestion, marked rejected.
