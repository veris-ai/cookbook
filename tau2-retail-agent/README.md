# tau2-retail-agent

A retail customer service chatbot built on the [tau2-bench](https://github.com/sierra-research/tau2-bench) benchmark from Sierra Research. Handles order management via chat: cancel, modify, return, and exchange orders, authenticate customers, and look up products.

## Architecture

- `agent/server.py` — FastAPI app with `/chat` endpoint (sandbox entry point)
- `agent/tau2_agent.py` — `RetailAgent(LLMAgent)` wired into tau2's framework
- `agent/tools.py` — 15 retail tools (6 read, 7 write, 2 utility) operating on tau2's `RetailDB`
- `agent/core.py` — System prompt assembly from `agent_desc.txt` + domain policy
- `scripts/run_tau2.py` — CLI benchmark runner (standalone evaluation, not the sandbox entry point)

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- `OPENAI_API_KEY` environment variable set

## Quick Start

### Run locally

```bash
uv sync
OPENAI_API_KEY=sk-... uv run uvicorn agent.server:app --host 0.0.0.0 --port 8080
```

### Run with Veris Sandbox

```bash
# Initialize environment
veris env create --name tau2-retail-agent

# Push to sandbox
veris env push

# Run a simulation
veris run start
```

### Run tau2-bench evaluation (standalone)

```bash
uv sync
OPENAI_API_KEY=sk-... uv run python scripts/run_tau2.py \
  --agent-llm gpt-4.1-mini \
  --user-llm gpt-4.1-mini \
  --num-tasks 10 \
  --max-concurrency 5
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `AGENT_LLM` | `gpt-4.1-mini` | LLM model for the agent |
| `OPENAI_API_KEY` | — | OpenAI API key (required) |
| `LLM_PROVIDER` | `openai` | LLM provider (set in veris.yaml) |

