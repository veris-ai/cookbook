# mini_bcs — Quickstart

A credit card support agent built with the OpenAI Agents SDK, supporting multiple LLM providers. This guide covers the agent setup first, then walks through integrating with [Veris](https://veris.ai) for scenario-based testing and evaluation.

## Agent Setup

### 1) Setup 

```bash
cd mini_bcs
uv venv && source .venv/bin/activate
uv sync
```

Copy and configure environment:

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 2) Run the API server

```bash
docker compose up
```

Health check:
```bash
curl -s http://127.0.0.1:8008/health
```

### 3) You can access the chat at

http://localhost:8008/


## LLM Providers

Mini BCS supports multiple LLM providers via the `LLM_PROVIDER` environment variable.

| Provider | `LLM_PROVIDER` | Model |
|----------|---------------|-------|
| DeepSeek | `baseten` | deepseek-ai/DeepSeek-V3.2 |
| GPT-OSS | `gptoss` | openai/gpt-oss-120b |
| Grok | `grok` | grok-3-fast |
| Azure OpenAI | `azure` | gpt-4o / gpt-5 |
| HuggingFace | `huggingface` | HuggingFaceTB/SmolLM3-3B |
| Kimi | `kimi` | moonshotai/Kimi-K2-Instruct-0905 |
| OpenAI | `openai` | gpt-4o (default) |


## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (required) |
| `LLM_PROVIDER` | LLM provider to use (default: openai) |
| `DATABASE_URL` | PostgreSQL connection string (default to Posgres in `docker-compose.yml`) |


# Veris Setup
a. Install Veris CLI and login:

```bash
uv tool install veris-cli
veris login # If personal
veris login --org <your org-id> # if part of an org
```

b. In mini-bcs folder, start a new Veris environment:

```bas
veris env create
```

Give your environment a name.

c. `veris.yaml` and `Dockerfile.sandbox` are configured for this agent. Only change them if you change agent's dependencies. 

d. Push you environment:

```bash
veris env push
```

e. Add required environment variables to Veris:

```bash
veris env vars set OPENAI_API_KEY=<your-oai-key> --secret # change this if using a different LLM provider
veris env vars set POSTGRES_PASSWORD=postgres
```

e. Login to [Veris Console](https://console.veris.ai) to generate scenarios, run simulations, evaluations and reports.

OR

```
veris scenarios create
veris run --scenario-set-id <from-last-step>
veris evaluations create --sim-run-id <from-last-step>
veris reports create --eval-run-id <from-last-step>
```