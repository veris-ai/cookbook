# HolmesGPT Agent

[HolmesGPT](https://github.com/HolmesGPT/holmesgpt) — the CNCF SRE agent — wrapped in a thin FastAPI/WebSocket server that investigates a single PagerDuty incident per turn and writes the analysis back as a note on the incident.

Per turn, the agent:

1. Parses a PagerDuty incident ID from the message (e.g. `PT4KHLK`) — or picks the highest-urgency open incident if no ID is given.
2. Uses HolmesGPT's built-in `PagerDutySource` to fetch the incident and enrich the description with alert payload details.
3. Runs HolmesGPT's `ToolCallingLLM` investigation with the **Datadog toolset only** (`datadog/logs`, `datadog/metrics`) — every other built-in toolset (Kubernetes, Prometheus, Grafana, shell, etc.) is disabled. The LLM may call Datadog tools 0–N times.
4. Writes the analysis back to the incident as a PagerDuty note (via `PagerDutySource.write_back_result`). That's the terminal action — the incident is left open.

HolmesGPT is consumed as a Python dependency — no source vendoring.

## Architecture: Source vs Toolset

**This is important for understanding what the LLM does vs what the wrapper does** — and for any downstream system that generates assertions about the agent's behavior.

```
                            ┌────────────────────────────────┐
                            │            LLM loop            │
   ┌──────────────┐         │                                │       ┌──────────────┐
   │   PagerDuty  │ ──────► │  user prompt (incident JSON)   │ ◄───► │   Datadog    │
   │   (Source)   │         │                                │       │  (Toolset)   │
   │              │ ◄────── │  fetch_datadog_logs (...)      │       │              │
   └──────────────┘  note   │  query_datadog_metrics (...)   │       └──────────────┘
        ▲                   │  → analysis                    │
        │                   └────────────────────────────────┘
        │                                  │
        │       Python wrapper code        │       LLM-driven tool calls
        └────── (deterministic) ───────────┘
```

| | PagerDuty | Datadog |
|---|---|---|
| Role | **Source** | **Toolset** |
| Who calls it | The Python wrapper (`app/__init__.py`, `app/investigator.py`) | The LLM, mid-investigation |
| When | Before the LLM (fetch) + after the LLM (write-back note) | Inside the LLM loop |
| LLM sees it as a tool? | **No.** The incident JSON is pasted into the user message as text. | Yes — `fetch_datadog_logs`, `query_datadog_metrics`, etc. |
| Deterministic? | Yes — same incident every time | No — the LLM decides whether and how to query |

**Implication for assertions:** an assertion like _"The agent fetched the highest-urgency open incident from PagerDuty"_ is **not** verifiable by inspecting LLM tool calls — that fetch happens in our Python code regardless of what the LLM does. Verify it by checking that the PagerDuty mock received `GET /incidents` or `GET /incidents/{id}`, **not** by checking the LLM's tool-call trace.

Assertions about Datadog usage **are** verifiable from the LLM trace — those are real tool calls the model chose to make.

## Services used

| Service    | Direction   | Surface | Purpose |
|------------|-------------|---------|---------|
| PagerDuty  | read+write  | Source  | Python fetches incident/alerts; Python writes the analysis note |
| Datadog    | read        | Toolset | LLM may search logs (`/api/v2/logs/events/search`) or query metrics (`/api/v1/query`) during investigation |
| LLM (OpenAI / Anthropic) | call out | — | HolmesGPT's reasoning + tool-calling backbone |

## Quickstart

Prerequisites: Python ≥ 3.12, an OpenAI or Anthropic API key.

```bash
cd holmes-gpt-agent
uv sync
cp .env.example .env
# fill in ANTHROPIC_API_KEY (or OPENAI_API_KEY), PAGERDUTY_API_TOKEN, DATADOG_API_KEY, DATADOG_APP_KEY
uv run uvicorn app.main:app --reload --port 8008
```

WebSocket (primary): `ws://localhost:8008/ws/chat`. Send:
```json
{"message": "Investigate PagerDuty incident PT4KHLK"}
```
or
```json
{"message": "Investigate the most urgent open incident"}
```

HTTP fallback (single-turn): `POST /chat` with `{"message": "..."}` — drains the stream and returns the final analysis.

## Tools the LLM can call

Configured in `.holmes/config.yaml`. The wrapper passes `toolset_tag_filter=[ToolsetTag.CORE]` + `enable_all_toolsets_possible=False`, so **only** the toolsets explicitly enabled below are loaded. Everything else HolmesGPT ships with (Kubernetes, Prometheus, Grafana, AWS, bash, kubectl, …) stays off.

| Toolset | Tool | Purpose |
|---|---|---|
| `datadog/logs` | `fetch_datadog_logs` | Search logs by query + time range with cursor pagination |
| `datadog/metrics` | `list_active_datadog_metrics` | List metrics seen in the last 24h (filterable by host/tag/regex) |
| `datadog/metrics` | `query_datadog_metrics` | Query a metric's timeseries with custom aggregation |
| `datadog/metrics` | `get_datadog_metric_metadata` | Get metadata (type, unit, description) for a metric |
| `datadog/metrics` | `list_datadog_metric_tags` | List available tags/dimensions for a metric |

To swap in a different toolset surface (e.g. add `datadog/traces`, or replace Datadog with Prometheus), edit `.holmes/config.yaml`.

## Investigation pipeline

| Step | Component | Type | Purpose |
|------|-----------|------|---------|
| Fetch incident      | `holmes.plugins.sources.pagerduty.PagerDutySource` | Python (Source) | GET `/incidents/{id}` + `/incidents/{id}/alerts` |
| Investigate         | `holmes.core.tool_calling_llm.ToolCallingLLM`      | LLM agentic loop | Model may call Datadog tools; produces analysis text |
| Write back analysis | `PagerDutySource.write_back_result`                | Python (Source) | POST `/incidents/{id}/notes` |

## Docker

```bash
docker compose up --build
```

(Without DNS aliasing, PagerDuty/Datadog hit the real APIs. Under Veris, the `.veris/veris.yaml` mock-service config intercepts both.)

## Running Veris simulations

`.veris/veris.yaml` configures the sandbox:
- **`pagerduty` mock service** with DNS alias `api.pagerduty.com` — intercepts PagerDuty REST calls
- **`datadog` mock service** with DNS alias `api.datadoghq.com` — intercepts `/api/v2/logs/events/search`, `/api/v1/query`, `/api/v1/series`, etc.
- **WebSocket actor channel** at `ws://localhost:8008/ws/chat` with `nudge_after: 90`
- **`actor.config.MAX_TURNS: "2"`** — one actor message, one agent reply, then end
- **`HOLMES_CONFIGPATH_DIR: /agent/.holmes`** — points HolmesGPT at the toolset config

Install the [Veris CLI](https://github.com/veris-ai/veris-cli) and log in:

```bash
uv tool install veris-cli
veris login
```

Create an environment and set your LLM API key:

```bash
veris env create --name holmes-gpt-agent
veris env vars set ANTHROPIC_API_KEY=sk-ant-... --secret
# or: veris env vars set OPENAI_API_KEY=sk-... --secret
```

Build and push the sandbox image:

```bash
veris env push
```

Generate test scenarios:

```bash
veris scenarios create --num 25
```

Run the simulations:

```bash
veris run
```

## Project structure

```
holmes-gpt-agent/
├── app/
│   ├── __init__.py            # process_chat_streaming — fetch → investigate → write-back note
│   ├── main.py                # FastAPI app — /health, /chat (HTTP), /ws/chat (WebSocket)
│   └── investigator.py        # Config / PagerDutySource / ToolCallingLLM wiring
├── .holmes/
│   └── config.yaml            # Enables datadog/logs + datadog/metrics; disables everything else
├── .veris/
│   ├── veris.yaml             # Sandbox config (PagerDuty + Datadog mocks, WS channel)
│   ├── Dockerfile.sandbox
│   └── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | — | HolmesGPT LLM credentials (one required) |
| `MODEL` | `openai/gpt-5.4-mini` | LiteLLM model string |
| `PAGERDUTY_API_TOKEN` | — | PagerDuty REST API token |
| `PAGERDUTY_USER_EMAIL` | `sre-bot@holmesgpt.local` | `From` header for PagerDuty write ops |
| `DATADOG_API_KEY` | — | Datadog API key (toolset) |
| `DATADOG_APP_KEY` | — | Datadog application key (toolset) |
| `DATADOG_API_URL` | `https://api.datadoghq.com` | Datadog API base URL — DNS-aliased under Veris |
| `HOLMES_CONFIGPATH_DIR` | `~/.holmes` | Directory containing `config.yaml` (set to `/agent/.holmes` under Veris) |

## Example incidents

The agent expects realistic open incidents seeded in the PagerDuty mock. Good seeds:

- "payments-api: error rate ≥ 5% for 5m" (triggered, Datadog monitor)
- "checkout-service: p95 latency > 2s" (triggered after deploy `v2.41.0`)
- "auth-service: OOM kill on web-04" (restart visible in alert payload details)

For each, the LLM has the alert payload as text and can pivot into Datadog logs/metrics to confirm or expand the hypothesis.
