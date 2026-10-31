<div align="center">

<img src="./LM-Logo-Veris-Green.svg" alt="Veris" width="200">

# Cookbook

### Reference agents, tested before production

[![Docs](https://img.shields.io/badge/docs-veris.ai-047404)](https://docs.veris.ai)

</div>

---

This repository is a set of working AI agents, each built on a mainstream framework against real enterprise integrations, and tested the way [Veris](https://veris.ai) tests agents before production: on a **bench** of tasks in a simulated world, against **stateful twins** of the services the agent calls, with **synthetic users** on the other side of the conversation and **faults injected** on purpose, graded on what the agent did to those systems rather than on what it said.

Use the agents as starting points for your own, or as references for putting an agent on a Veris Bench. Each one runs standalone too.

## Examples

| Agent | What it does | Framework | Integrations | On a bench |
|-------|--------------|-----------|--------------|------------|
| **[Banker Connections Agent](./bca-agent)** | Helps retail bankers resolve customer record update errors (Clear CUID scenarios) in real time, instead of calling a specialist while the customer waits | Google ADK | Vertex AI, Hogan API | Ran on the retired simulation platform |
| **[Card Replacement Agent](./card-replacement-agent)** | A triage agent and three specialists that freeze cards, order replacements, track delivery and handle activation | OpenAI Agents SDK | PostgreSQL | **Nightly**, on the Card Service Desk bench ([chart](#the-nightly-benchmark)) |
| **[CRM Analyst Agent](./crm-analyst-agent)** | Answers PostHog product-analytics questions over Slack and drafts approval-gated outreach email, emitting OpenTelemetry traces to Langfuse | NemoClaw / OpenShell | PostHog, Slack, Langfuse | Nightly trace-grounded scenarios on the retired platform |
| **[HolmesGPT Agent](./holmes-gpt-agent)** | Investigates one PagerDuty incident per turn with Datadog logs and metrics and writes the root-cause analysis back as a note | HolmesGPT (CNCF) | PagerDuty, Datadog | Ran on the retired simulation platform |
| **[Medical Triage Agent](./medical-triage-agent)** | Looks up a patient's FHIR record, gathers symptoms over a multi-turn conversation, recommends a specialist and books the appointment | PydanticAI on Amazon Bedrock AgentCore | Epic FHIR R4 | Ran on the retired simulation platform |
| **[mini-bcs](./mini-bcs)** | A credit card support agent with switchable LLM providers; the shortest path from a working agent to scenario-based testing | OpenAI Agents SDK | Card operations backend | Ran on the retired simulation platform |
| **[PM Analyst](./pm-analyst)** | Turns meeting transcripts and notes into Epics, Features and User Stories and pushes them to Azure DevOps | Google ADK | Azure DevOps, Microsoft Teams | Ran on the retired simulation platform |
| **[Procurement Agent](./procurement-agent)** | Runs IT procurement end to end: sourcing against approved suppliers, RFQs, negotiation that spots hidden fees, PO finalisation | OpenAI Agents SDK | Oracle Fusion Cloud ERP, AgentMail | Ran on the retired simulation platform |
| **[Shopping Agent](./shopping-agent)** | A supervisor agent with catalog, account and checkout specialists, selling through Stripe payment links over WebSocket | LangGraph | Stripe MCP | Ran on the retired simulation platform |

Every example has its own README with setup, architecture and the integration notes.

## The nightly benchmark

![Nightly pass rate of the card-replacement agent](https://raw.githubusercontent.com/veris-ai/cookbook/bench-results/card-service-desk/chart.svg)

Every night [`card-replacement-bench-nightly.yaml`](.github/workflows/card-replacement-bench-nightly.yaml) builds the card-replacement agent from `main`, adds it as a new candidate to one long-lived trial on the Card Service Desk bench, waits for its 72 attempts (24 tasks, three repeats) and redraws this chart from the whole trial. Each dot is one night's pass rate; the bar is its 95% interval; a hollow dot is a night where some attempts did not count.

The bench's 24 tasks run against a Postgres twin of the bank's customers and cards, and the judge grades on the tool trace, the SQL ledger and the transcript, never on what the agent says it did. The agent's code only changes when this repository does, so night-to-night movement is mostly the models drifting. With 72 attempts a night the interval is about eleven points either way: read trends, not single nights. The details, the settings and how to reuse the workflow for your own agent are in the [card-replacement README](./card-replacement-agent/README.md#nightly-benchmark); the generic script is [`.github/bench/nightly.py`](.github/bench/nightly.py).

The pattern it follows, a small trial on every pull request and the full trial nightly with a floor on the pass rate's confidence interval, is written up at [veris.ai/guides/agent-regression-in-ci](https://veris.ai/guides/agent-regression-in-ci) and in the docs under [Regression testing in CI/CD](https://docs.veris.ai/regression-in-ci).

## Put an agent on a bench

Any of these agents, or your own, joins a bench in three steps from the [Veris Bench docs](https://docs.veris.ai):

1. **Get a bench into your workspace.** Fork a template or use one Veris built for you.
2. **[Add your agent](https://docs.veris.ai/add-your-agent).** Package it as a container (or point at a hosted endpoint), push it, and register it as a candidate. A `bench/candidate.json` like the [card-replacement one](./card-replacement-agent/bench/candidate.json) tells the bench how to talk to it: the port, the path and the health check. A coding agent can do this step for you with the add-your-agent skill.
3. **[Run a trial](https://docs.veris.ai/run-a-trial).** Start with a smoke trial on two tasks, then a full trial: every task, every archetype of simulated user, three repeats, with a pass rate and its 95% interval per candidate.

Then wire the trial into CI as above, so every version of the agent meets the same tasks.

## Run an agent standalone

Each agent can run on its own. Follow the README in its directory; you will typically need to:

1. Clone the repo and `cd` into the agent directory
2. Install dependencies (`uv sync` or `pip install`)
3. Set environment variables (API keys, etc.)
4. Start the server (`uvicorn` or `docker compose up`)

### Veris simulations (retired)

These examples used to run on the Veris simulation platform, which retired on **2026-10-15** and is replaced by [Veris Bench](https://benchmark.veris.ai). Environment images and data are kept until **2026-11-14**, then deleted. Questions or data requests: hello@veris.ai. Details: https://docs.veris.ai/deprecation

The `scenarios/` and `.veris/` directories in the older examples are that platform's format and are kept for reference.

## Project structure

```
cookbook/
  bca-agent/                Banker Connections Agent (Google ADK)
  card-replacement-agent/   Card Replacement Agent (OpenAI Agents SDK), nightly on a bench
  crm-analyst-agent/        CRM Analyst Agent (NemoClaw / OpenShell)
  holmes-gpt-agent/         HolmesGPT Agent (CNCF SRE agent)
  medical-triage-agent/     Medical Triage Agent (PydanticAI on Bedrock AgentCore)
  mini-bcs/                 Credit card support agent (OpenAI Agents SDK)
  pm-analyst/               PM Analyst (Google ADK)
  procurement-agent/        Procurement Agent (OpenAI Agents SDK)
  shopping-agent/           Shopping Agent (LangGraph, Stripe MCP)
  .github/workflows/        The nightly bench workflow and image retention
  .github/bench/            The generic nightly script and its tests
```

Each agent follows a consistent layout:

```
<agent>/
  app/              Application code and agent logic
  tests/            Unit and integration tests
  bench/            How a Veris Bench talks to this agent (candidate.json), where present
  scenarios/        Scenarios in the retired simulation format, where present
  README.md         Setup and usage instructions
```

## Contributing

To add a new cookbook example:

1. Create a new directory at the repo root
2. Include a `README.md` with setup instructions, an architecture overview and the integration notes
3. Add a `Dockerfile` and a `bench/candidate.json` so the agent can be registered on a bench
4. Optionally copy the nightly workflow and point it at your bench
5. Open a pull request

## Resources

- [Veris Bench documentation](https://docs.veris.ai): benches, worlds, candidates, trials
- [Regression testing in CI/CD](https://docs.veris.ai/regression-in-ci) and the [CI guide](https://veris.ai/guides/agent-regression-in-ci)
- [Veris for coding agents](https://docs.veris.ai/coding-agents): stateful twins your coding agent builds and tests against
- [The Veris leaderboard](https://veris.ai/leaderboard): public benchmarks run on the same infrastructure
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python), [Google ADK](https://google.github.io/adk-docs/), [LangGraph](https://langchain-ai.github.io/langgraph/), [PydanticAI](https://ai.pydantic.dev/)

---

<div align="center">
<sub>Built with <a href="https://veris.ai">Veris</a>. Break it in simulation, not in production.</sub>
</div>
