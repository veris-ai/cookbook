# Card Replacement Agent

A multi-agent banking assistant built with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) that handles card replacement workflows: freezing cards, ordering replacements, tracking delivery status, and updating user information.

## Architecture

The agent system uses a **triage agent** that delegates to specialized sub-agents:

- **Card Replacement Agent** — handles freeze/replace requests, confirms delivery address
- **Replacement Status Update Agent** — tracks replacement status, handles activation and re-replacement
- **Out-of-Scope Agent** — catches unrelated questions and directs users to customer service

Data is stored in PostgreSQL with two tables: `users` and `cards`.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (for local or simulation runs)
- An OpenAI API key

## Quick start (Docker Compose)

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY

docker compose up --build
```

This starts PostgreSQL (with seed data) and the app on http://localhost:8008.

Health check:

```bash
curl -s http://127.0.0.1:8008/health
```

## Quick start (local)

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY

uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8008
```

> **Note:** You'll need a running PostgreSQL instance and `DATABASE_URL` set in `.env`.

## Running Veris simulations

Install the [Veris CLI](https://github.com/veris-ai/veris-cli) and log in:

```bash
uv tool install veris-cli
veris login
```

Create an environment and set your API key:

```bash
veris env create --name card-replacement-agent
veris env vars set OPENAI_API_KEY=sk-... --secret
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
