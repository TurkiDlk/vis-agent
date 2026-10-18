# 3. How It Works

[← 2. Stack & Architecture](02-stack-and-architecture.md) · [Index](README.md) · [4. Rulesets →](04-rulesets.md)

## 3.1 One request

```mermaid
sequenceDiagram
    actor U as User
    participant W as React UI
    participant A as FastAPI
    participant G as ChartAgent
    participant M as Gemma (Ollama)

    U->>W: uploads sales.csv, asks "Sales by region in 2025"
    W->>A: POST /sessions/{id}/messages
    A-->>W: run_id
    W->>A: GET /runs/{run_id}/events (SSE)
    G->>G: ingest, exclude totals, profile, candidates
    G->>M: intent_ranking (question + candidates)
    M-->>G: relevance per candidate
    G->>G: final score, clear lead → plot directly
    G->>M: chart_generation (profile, ≤ 10 rows, examples)
    M-->>G: ChartSpec
    G->>G: complete_spec → validate → render → Review A
    G->>M: visual_review (PNG)
    M-->>G: pass
    G->>M: insight_writer (code's facts)
    M-->>G: text, checked against the facts
    A-->>W: step.* events, then chart.ready
    W-->>U: chart reveal, insight text, source line, views
```

About 4 model calls and 6 seconds per request **[Measured]**.

| The first chart reply | Insight text, English | Arabic with a Mapbox map |
| --- | --- | --- |
| [![A line chart of trips by vehicle type, 2016–2024, with the refine box below](images/phase-4-chart-revealed.png)](images/phase-4-chart-revealed.png) | [![A question sent, the chart drawn, then the insight text written word by word](images/phase-8-insight-text-en.gif)](images/phase-8-insight-text-en.gif) | [![An Arabic question answered with a choropleth of Saudi regions and Arabic insight text](images/phase-8-insight-text-ar.gif)](images/phase-8-insight-text-ar.gif) |

Click to enlarge. Sample data, from `docs/phase-notes/media/`.

## 3.2 How the chart is chosen

```mermaid
flowchart LR
    A["1 · Rules<br/>insight types + allowed charts"] --> B["2 · Model + code<br/>which insight answers the question"]
    B --> C["3 · Model<br/>chart type from the allowed list"]
    C --> D["4 · Code<br/>completes, validates, reviews"]
```

- **Score** = 45% model relevance + 25% code's evidence (the question names the columns) + 30% structural fit.
- **Plot directly** only when the top score is ≥ 0.75 and leads by ≥ 0.15; otherwise show 3–5 option cards.
- A requested chart ("as a pie") is settled by rule first, with a note if refused.

## 3.3 Review and revise

```mermaid
flowchart TD
    S["ChartSpec"] --> C["complete_spec<br/>code-owned fields"]
    C --> V["Validate + auto-fix"]
    V --> R["Render: fold → filters → aggregate → derive → top-N"]
    R --> A["Review A: 47 checks + SQL oracle"]
    A --> B["Review B: vision rubric"]
    B --> D{"Judgment issues?"}
    D -->|"none"| OK["clean → answer"]
    D -->|"yes"| P["Reviser → SpecPatch"]
    P --> Q{"Stop?<br/>2 revisions · repeated issue<br/>no improvement · reviser failed"}
    Q -->|"no"| C
    Q -->|"yes"| BEST["Best passing version<br/>with warnings"]
```

If nothing passes, the user gets a rules-only chart, then a data table. A failed model call degrades its step
instead of failing the run.

## 3.4 Other requests

- **Single number** ("How many orders in 2025?"): the model names the metric, code computes it, SQL checks it.
- **Named comparison** ("Riyadh vs. Jeddah"): code finds the names and draws by rule.
- **Refine** ("sort ascending") or **other ways to plot**: a patch to the current chart, or new option cards.
- **Instant views:** switch orientation, measure, page or table without another model call.
