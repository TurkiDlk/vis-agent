# Chart issues

Problems seen in the charts the team delivers, including runs that deliver no chart. There is one entry per chart
image: the picture, then every problem in it with its own severity and status. A chart drawn again (another
run, another repo) gets its own entry. Each problem is checked against the
[visualization standards](../visualization-standards.md). Problems in the agent flow alone (stuck requests, tool
contracts) belong in a gap analysis such as [the lead gap analysis](../experiments/2026-09-19-lead-gap-analysis.md).

## Index

| ID | Chart | Problems | Highest severity | Status |
| --- | --- | --- | --- | --- |
| [CI-001](2026-10-18-gdp-co2-scatter-old-repo.md) | GDP per capita vs. CO₂ emissions, old repo (scatter) | 1 high, 4 medium, 1 low | high | open |
| [CI-002](2026-10-18-gdp-co2-scatter-command-line.md) | GDP per capita vs. CO₂ emissions, command line (scatter) | 1 high, 5 medium, 2 low | high | open |
| [CI-003](2026-10-18-gdp-co2-scatter-chat.md) | GDP per capita vs. CO₂ emissions, chat (scatter) | 2 high, 4 medium | high | open |
| [CI-004](2026-10-18-sales-by-region-old-repo.md) | Total sales by region in 2025, old repo (columns) | 4 medium (1 fixed) | medium | open |
| [CI-005](2026-10-18-sales-by-region-command-line.md) | Total sales by region in 2025, command line (horizontal bars) | 1 high, 3 medium | high | open |
| [CI-006](2026-10-18-spend-by-department-old-repo.md) | Total spend by department 2025, old repo (horizontal bars) | 3 medium (1 fixed) | medium | open |
| [CI-007](2026-10-18-spend-by-department-command-line.md) | Total spend by department 2025, command line (horizontal bars) | 2 medium | medium | open |
| [CI-008](2026-10-18-sales-share-arabic-donut-old-repo.md) | Sales share by region in Arabic, old repo (donut) | 1 high, 2 medium | high | open |
| [CI-009](2026-10-18-sales-share-arabic-donut-command-line.md) | Sales share by region in Arabic, command line (donut) | 3 medium | medium | open |
| [CI-010](2026-10-18-units-by-product-45-command-line.md) | Units sold by product, 45 products, command line (horizontal bars) | 1 high, 3 medium | high | open |
| [CI-011](2026-10-18-units-by-product-60-command-line.md) | Units sold by product, 60 products, command line (horizontal bars) | 1 high, 3 medium | high | open |
| [CI-012](2026-10-18-units-by-product-100-command-line.md) | Units sold by product, 100 products, command line (not delivered) | 3 high, 1 medium | high | open |
| [CI-013](2026-10-18-units-by-product-100-chat.md) | Units sold by product, 100 products, chat (not delivered) | 2 high, 1 medium | high | open |
| [CI-014](2026-10-18-messy-csv-refused-in-chat.md) | Sales by city from a messy CSV, chat (refused at upload) | 1 medium | medium | open |
| [CI-015](2026-10-18-messy-csv-accepted-command-line.md) | Sales by city from a messy CSV, command line (grouped columns) | 5 medium | medium | open |

The index is rebuilt from the entries by `new_issue.py`; don't edit it by hand.

**Severity** (per problem): `high` means the chart is wrong or misleading, or no chart arrives; `medium` means
correct but hard to read or incomplete; `low` means cosmetic.

**Status** (per problem): `open`, `fixed` (with the commit and the test that guards it), `won't fix` or `withdrawn`
(with the reason). A chart is `open` while any of its problems is.

## Adding an issue

### 1. Start the entry

From the repository root:

```bash
uv run docs/chart-issues/new_issue.py "Sales by channel"
```

It asks for the chart type, then for each problem a few words and a severity. Then it lists the standards related to
that chart type as a checklist:

```text
? Which standards does it break? (related to donut) (space to pick, enter when done)
 » ○ 1.1   Every value comes from the CSV unchanged; nothing is invented.
   ● 2.3   Pie or donut only for 2–6 non-negative parts of one whole.
   ○ 2.9   The chart answers the question's form: a share question shows shares.
   …
   ---------------
   ○ Other: show all standards
   ○ Suggest a new standard
```

- **Pick:** move with the arrow keys, pick with space, finish with Enter.
- **Other:** opens every remaining standard; type to filter the list.
- **Suggest a new standard:** asks for the rule, its section and why it's needed, adds it to
  [standards-suggestions.md](../standards-suggestions.md) for review, and cites it in the issue until it's decided.

Run it as `uv run docs/chart-issues/new_issue.py` (not `uv run python …`) so uv installs the checklist library,
[questionary](https://github.com/tmbo/questionary), for this script only. Without it, or outside a terminal, the
same choices come as a numbered menu: numbers to pick, `o` for Other, `s` to suggest.

The command then:

- writes `YYYY-MM-DD-sales-by-channel.md` from [TEMPLATE.md](TEMPLATE.md), with the next ID and today's date;
- fills the problem table and one section per problem, with the text of each standard you picked (the preview
  can't jump to a section of the standards file, so the rule is shown where it's cited);
- rebuilds the index above and the issue links in the standards checklist.

**Without the questions:**
`--type pie --problem "Labels overlap:medium:4.2" --problem "Seven slices:high:2.3,4.1"`. For a problem seen on an
earlier day, add `--date 2026-10-15`.

**Suggesting a standard on its own:** `uv run docs/chart-issues/new_issue.py --suggest`. Suggestions are reviewed
in [standards-suggestions.md](../standards-suggestions.md); once one is approved and numbered, `--sync` swaps it for
the new rule in every issue that cited it.

### 2. Fill it in

Keep each part to a few lines.

| Part | What goes in it |
| --- | --- |
| Image | The chart as you saw it, saved as `images/<chart>.png`. |
| **Asked**, **Data** | The question as typed; the CSV or the data in a phrase. |
| Problem table | One row per problem: severity, status, standards. Add a row and a section to add a problem later. |
| **Seen** | What this problem looks like in the chart. |
| **Expected** | What a correct chart shows. |
| **Standard** | Written by the command from the problem table: each rule's number and text, so you don't have to look it up. |
| **Cause** | Where it goes wrong in the code, with `file:line`; "Not traced yet" until it is known. |
| **Fix** | Add once fixed: the change, its commit and the test that guards it; set the row's status to `fixed`. |
| **Evidence** | Request and artifact IDs (`rq_…`, `art_…`) if you have them, and the models if the result depends on them. |

After editing a problem table by hand (a status, a new row, a standard), run
`uv run docs/chart-issues/new_issue.py --sync` to update the index and the standards links.

**Images.** Show them as clickable thumbnails in a table, as in the template:
`[![Caption](images/x.png)](images/x.png)`. The preview strips HTML `<img>` tags, so don't use them. Commit only
images without real data.

**Arabic.** Keep Arabic out of inline code: mixed with `%` or numbers, the preview reorders it. Put an Arabic
question on its own `>` line.

**By yourself.** Add your screenshot, write **Asked** and **Data**, each problem's **Seen**, and adjust
**Expected**. **Cause** and **Evidence** can wait; leave "Not traced yet".

**With an AI assistant.** Start the entry with the command, then give the assistant your screenshot, the entry's ID
and the question you asked. It doesn't need to reproduce the chart; the screenshot is the evidence. For example:

> Fill in CI-016 in docs/chart-issues. Here is my screenshot; I asked "Sales by channel". Save the image in
> images/, check the chart against the standards checklist for any problem I missed and add it with a severity,
> fill in each problem's Seen, Expected and Cause, then run `new_issue.py --sync`. Keep it short.

The assistant can:
- describe what is wrong in the picture;
- add problems you missed, checked against the standards;
- trace causes in this repo's code.

Check what it writes: causes should cite real `file:line` references, or say "Not traced yet" rather than guess.

## Reproducing (optional)

Only needed to test a fix or to see whether a problem is still there. [`data/`](data/) holds dummy CSVs and
briefs for the logged charts; `make_data.py` writes them. Run one in its own data
folder so it doesn't touch the app's database:

```bash
uv run python docs/chart-issues/data/make_data.py
DATA_DIRECTORY=data/chart-issues/ci-sales-region uv run vis draw \
  --upload docs/chart-issues/data/ci-sales-region.csv \
  --brief docs/chart-issues/data/ci-sales-region.brief.json \
  "Total sales by region in 2025"
```

The output gives the request and artifact IDs; the PNG is under `data/chart-issues/<case>/renders/`. Models
aren't deterministic, so a re-run can differ from the one logged.
