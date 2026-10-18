# 2. Stack & Architecture

Technologies, model seats, the architectural pattern, the module map, and where to start reading.

> Snapshot of branch `test-agent` at commit `8da1564`, verified against the code on 2026-10-18. `file.py:120` means line 120 of that file at this commit. Status labels such as **[Runtime]** are defined in the [index](README.md#status-labels).

[← 1. The System Structure](01-system-structure.md) · [Index](README.md) · [3. How It Works →](03-how-it-works.md)

---

## 2.1 Technology stack

| Layer | Technology (version) | Purpose | Evidence for why |
| --- | --- | --- | --- |
| Language | **Python 3.12**, managed by **uv** | Everything except drawing | `.python-version`, `pyproject.toml`, `AGENTS.md` |
| Agent framework | **Pydantic AI** (`pydantic-ai-slim[cli,openrouter,temporal,web] >= 2.38`) | Agents, tools, output functions, usage limits, web chat UI, Temporal capability | `AGENTS.md`. Rule 3 of the original design: "Follow the Pydantic AI documentation" (`docs/superpowers/specs/2026-09-06-vis-agent-design.md`). |
| Agent extras | **pydantic-ai-harness** (`[code-mode] >= 0.28.1`) | `Advisor` capability on the lead. CodeMode is installed but deliberately unused. | `vis_agent/lead.py:16, 661-663`. CodeMode was removed after Phase 1 because it cost a model turn for no benefit (`docs/phase-1-lessons.md`). |
| Validation | **Pydantic** | Every contract (brief, spec, reports, requests) | All `models.py` files under `vis_agent/` |
| Model access | **OpenRouter** (primary), **LiteLLM** proxy (air-gapped cluster) | One complete team per provider | `vis_agent/providers.py`, `docs/phase-6-lessons.md` ("Two providers in one dropdown") |
| Data and storage | **DuckDB** (`>= 1.5.5`) | CSV import, typed views, read-only SQL, request/artifact tables | `vis_agent/store.py`, `vis_agent/requests/store.py`, `vis_agent/analyst/query.py` |
| Web | **Starlette** (through Pydantic AI web), `python-multipart`, `httpx` | Chat, upload, render, and request routes, plus callbacks | `vis_agent/app.py`, `vis_agent/uploads.py`, `vis_agent/requests/api.py` |
| Renderer | **Node 22+**, **@antv/gpt-vis-ssr 0.3.8** (pinned), G2 SSR, `canvas` | Server-side PNG and HTML chart drawing | `vis_agent/render/gptvis/package.json`, `docs/spikes/2026-09-07-gpt-vis-server-renderer.md` |
| Observability | **Logfire** (`instrument_pydantic_ai`, sends only when a token is set) | Traces for agent runs, tools, and model requests | `vis_agent/app.py:21-22`. The experiment reports query Logfire for latency. |
| Evaluation | **pydantic-evals**, **DSPy** + `hijridate` (optional `optimize` group) | Offline eval harnesses and instruction optimization (GEPA) | `pyproject.toml`, `evals/**/optimize_instructions.py` |
| Tests | **pytest** with fake models through `agent.override` | Unit and integration tests with no credentials | `tests/`, `AGENTS.md` ("Use fake models through agent.override") |

```mermaid
flowchart TB
    subgraph Interfaces
        I1["Pydantic AI Web Chat UI"]
        I2["Starlette HTTP API"]
        I3["argparse CLI: vis"]
    end
    subgraph Agents["Agents: Pydantic AI 2.38"]
        A1["Lead + TemporalDurability + optional Advisor"]
        A2["Designer / Analyst / Profiler / Inspector"]
    end
    subgraph Models["Models via OpenRouter or LiteLLM"]
        M1["z-ai/glm-5.3"]
        M2["deepseek/deepseek-v4-pro"]
        M3["google/gemma-4-31b-it"]
    end
    subgraph Data
        D1["DuckDB"]
        D2["Local files: data/"]
    end
    subgraph Render
        R1["Node subprocess"]
        R2["@antv/gpt-vis-ssr 0.3.8 + G2 SSR + canvas"]
    end
    subgraph Ops["Quality and ops"]
        O1["Logfire traces"]
        O2["pytest + fake models"]
        O3["pydantic-evals, DSPy GEPA (offline)"]
    end
    Interfaces --> Agents
    Agents --> Models
    Agents --> Data
    Agents --> Render
    Agents -.-> O1
```

## 2.2 High-level architecture

```mermaid
flowchart LR
    subgraph Callers
        U["Person in web chat"]
        P["Upstream data agent / program"]
        T["Developer CLI: vis"]
    end

    subgraph App["Starlette app from Agent.to_web (vis_agent/app.py)"]
        CHAT["POST /api/chat<br/>add_chat_route"]
        UP["/datasets/upload, /datasets,<br/>/datasets/{id}/profile"]
        API["/requests..., /artifacts...,<br/>/agents/ask"]
        RR["GET /renders/{id}/{file}"]
    end

    subgraph Team["One team per provider (providers.py)"]
        LEAD["Lead agent<br/>GLM 5.3, low reasoning"]
        DES["Designer<br/>DeepSeek V4 Pro"]
        REV["Visual inspector<br/>Gemma 4 31B IT, thinking off"]
        ANA["Analyst (optional)<br/>GLM 5.3"]
        PRO["Profiler (optional)<br/>GLM 5.3"]
    end

    subgraph Code["Deterministic code"]
        SRC["Source reader<br/>analyst/source.py"]
        CHK["Spec checker<br/>designer/check.py"]
        REN["Resolver + GPT-Vis SSR<br/>Node subprocess"]
        SQL["Read-only SQL guard<br/>analyst/query.py"]
    end

    DB[("DuckDB<br/>datasets, requests, artifacts")]
    FS[("data/uploads, data/renders")]

    U --> CHAT
    P --> UP
    P --> API
    T --> LEAD
    CHAT --> LEAD
    API --> LEAD
    UP --> DB
    UP --> FS
    LEAD -->|"design_visualization"| DES
    LEAD -->|"review_visualization"| REV
    LEAD -->|"consult_analyst"| ANA
    LEAD -->|"profile_csv"| PRO
    LEAD -->|"draw / revise"| SRC
    LEAD -->|"render_visualization"| REN
    DES --> CHK
    REN --> CHK
    ANA --> SQL
    SRC --> DB
    SQL --> DB
    REN --> FS
    LEAD -->|"publish_visualization"| DB
    RR --> FS
```

No specialist calls another, and no tool schedules another tool (`AGENTS.md`; `vis_agent/lead.py:44-107`). The chat
route is inserted in front of the web UI's own `/api/chat` so that the dropdown can choose a team
(`vis_agent/providers.py:126-151`). The agent API always uses the first configured team (`vis_agent/app.py:34, 46`).

## 2.3 Models per seat (current defaults)

| Seat | OpenRouter default | Settings | Override variable | LiteLLM team |
| --- | --- | --- | --- | --- |
| Lead | `z-ai/glm-5.3` | reasoning effort `low`, `require_parameters` | `PYDANTIC_AI_MODEL`, `PYDANTIC_AI_LEAD_REASONING_EFFORT` | `LOCAL_LLM`, no model settings |
| Profiler, Analyst | `z-ai/glm-5.3` | reasoning `low`, `require_parameters`, temperature 0 (`vis_agent/model_settings.py`) | `PYDANTIC_AI_PROFILER_MODEL`, `PYDANTIC_AI_ANALYST_MODEL` | `LOCAL_LLM` |
| Designer | `deepseek/deepseek-v4-pro` | thinking off, temperature 0 | `PYDANTIC_AI_DESIGNER_MODEL` | `LOCAL_LLM` |
| Fallback designer | same as designer | used only if the lead passes `use_fallback=true` | `PYDANTIC_AI_DESIGNER_FALLBACK_MODEL` | `LOCAL_LLM` |
| Visual inspector | `google/gemma-4-31b-it` | thinking off, temperature 0 | `PYDANTIC_AI_REVIEWER_MODEL` | `LITELLM_REVIEWER_MODEL`, default `Qwen/Qwen3.8-27B` |
| Advisor | unset (off) | native Advisor capability | `PYDANTIC_AI_ADVISOR_MODEL` | not available |

Sources: `vis_agent/providers.py:49-123`, `vis_agent/designer/agent.py:37-39`, `vis_agent/reviewer/agent.py:30, 104`,
`vis_agent/profiler/agent.py:50`, `.env.example`. How these seats were chosen, and what evidence is missing:
[Design Decisions 5.10](05-design-decisions.md).

```mermaid
flowchart TD
    START["App start: teams_from_env"] --> Q1{"OPENROUTER_API_KEY set?"}
    Q1 -- "yes" --> OR["Add OpenRouter team"]
    Q1 -- "no" --> Q2
    OR --> Q2{"LITELLM_BASE_URL set?"}
    Q2 -- "yes" --> LL["Add LiteLLM team"]
    Q2 -- "no" --> Q3
    LL --> Q3{"Any team?"}
    Q3 -- "no" --> ERR["RuntimeError: no provider configured"]
    Q3 -- "yes" --> OK["Chat dropdown lists every team.<br/>The first team serves the agent API."]
```

The lead is text-only by design: rendered image bytes go only to the inspector (`vis_agent/lead.py:71-75`).

## 2.4 Architectural pattern

The system follows the **agent delegation** pattern from the Pydantic AI multi-agent docs, cited in
`docs/lead-directed-team.md`. Each specialist is a separate `Agent` that runs inside an `async` tool of the lead. It
shares the parent's `ctx.usage`, and its own request cap is clamped to the parent's limits. Three ideas sit on top:

| Idea | How it shows up | Source |
| --- | --- | --- |
| **"The model drives, the code checks."** | Models speak a small, line-oriented DSL. Code parses and checks every spec before it can reach the renderer. | Rule 9 of the original design (`docs/superpowers/specs/2026-09-06-vis-agent-design.md`, section 2) |
| **Output functions as gates** | Each specialist's final answer goes through a tool-style output function (`deliver_design`, `deliver_review`, `deliver_analysis`, `review_profile`). It validates the answer and can send the model back with `ModelRetry`. | specialist `agent.py` files |
| **Saved tool results, not a workflow engine** | Durability comes from saving each tool's result on the request record, not from a step machine. | `vis_agent/requests/service.py` |

## 2.5 Module map and dependencies

```mermaid
flowchart TD
    app["app.py<br/>wiring only"] --> providers["providers.py<br/>teams, chat route"]
    app --> uploads["uploads.py"]
    app --> renders["renders.py"]
    app --> api["requests/api.py"]
    cli["cli.py"] --> providers
    providers --> lead["lead.py<br/>lead + delegation tools"]
    api --> service["requests/service.py<br/>persistence, publish, run_request"]
    lead --> service
    service --> rstore["requests/store.py<br/>DuckDB requests/artifacts"]
    service --> source["analyst/source.py<br/>direct CSV read"]
    lead --> designer["designer/agent.py"]
    lead --> reviewer["reviewer/agent.py"]
    lead --> analyst["analyst/agent.py"]
    lead --> profiler["profiler/agent.py"]
    designer --> check["designer/check.py"]
    check --> syntax["designer/syntax.py"]
    check --> catalogue["designer/catalogue.json"]
    check --> indicator["designer/indicator.py"]
    check -. "policy=True only" .-> rules["designer/rules.py<br/>H/S/C rules"]
    recommend["designer/recommend.py<br/>offline ranking"] --> rules
    designer --> gptvis["render/gptvis.py"]
    gptvis --> resolve["designer/resolve.py"]
    gptvis --> node["render/gptvis/render.mjs"]
    analyst --> query["analyst/query.py<br/>SQL guard"]
    analyst --> checks["analyst/checks.py"]
    source --> dstore["store.py<br/>DuckDB datasets"]
    query --> dstore
    labels["labels.py, units.py, models.py<br/>shared contracts"] --- designer
    labels --- reviewer
```

`vis_agent/requests/runner.py` holds **compatibility imports only**. The old fixed runner was removed
(`vis_agent/requests/runner.py:1-7`).

## 2.6 Entry points and the files to read first

| Order | File | Why read it |
| --- | --- | --- |
| 1 | `AGENTS.md`, `docs/lead-directed-team.md` | The product contract and the current architecture decision |
| 2 | `vis_agent/lead.py` | The instructions, every tool, budget hooks, and the output validator. This file *is* the control flow. |
| 3 | `vis_agent/requests/service.py` | How a request is prepared, invalidated, published, and run from the API/CLI |
| 4 | `vis_agent/designer/agent.py`, `vis_agent/designer/rulebook.md` | How a spec is produced and gated |
| 5 | `vis_agent/designer/check.py`, `vis_agent/designer/syntax.py` | What "valid spec" means at runtime |
| 6 | `vis_agent/designer/resolve.py`, `vis_agent/render/gptvis.py` | How a spec becomes a picture, and which errors appear only there |
| 7 | `vis_agent/reviewer/agent.py`, `vis_agent/reviewer/rulebook.md`, `vis_agent/reviewer/rubric.py` | The visual inspection contract |
| 8 | `vis_agent/providers.py`, `vis_agent/app.py` | Model wiring and HTTP surface |

| Entry point | Command or route | Code |
| --- | --- | --- |
| Web chat | `uv run uvicorn vis_agent.app:app --host 127.0.0.1 --port 7932` | `vis_agent/app.py`, `vis_agent/providers.py:126` |
| Upload | `POST /datasets/upload` (multipart `file` + `brief`); also `GET /datasets`, `GET /datasets/{id}/profile` | `vis_agent/uploads.py:42-116` |
| Agent API | `POST /requests`, `GET /requests/{id}`, `POST .../answer`, `POST .../resume`, `GET /artifacts`, `GET /artifacts/{id}`, `POST /agents/ask` | `vis_agent/requests/api.py:83-222` |
| Renders | `GET /renders/{render_id}/{file}` | `vis_agent/renders.py` |
| CLI | `vis chat / profile / ask / draw / revise / resume / requests / artifacts / suggest / failures / recommend / check / render / design / doctor` | `vis_agent/cli.py:48-96` |

---

[← 1. The System Structure](01-system-structure.md) · [Index](README.md) · [3. How It Works →](03-how-it-works.md)
