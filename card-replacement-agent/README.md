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

Install the [Veris Sim CLI](https://docs.veris.ai/reference/cli/installation) and log in:

```bash
uv tool install veris-sim-cli
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

## Nightly benchmark

![Nightly pass rate](https://raw.githubusercontent.com/veris-ai/cookbook/bench-results/card-replacement/chart.svg)

Every night [`card-replacement-bench-nightly.yaml`](../.github/workflows/card-replacement-bench-nightly.yaml)
builds this agent from `main`, adds it as a new candidate to one long-lived Veris bench trial, waits
for its 25 tasks to finish, and redraws this chart from the whole trial. Each dot is one night's pass
rate; the bar is its 95% interval. A hollow dot is a night where some attempts did not count (a
Veris-side failure, or still running after 3 hours).

**What it measures.** The agent's code only changes when this repo does, so night-to-night movement
is mostly the models drifting — the agent's (the openai-agents default), the simulated customer's,
and the judge's. With 25 attempts a night the interval is about ±18 points: read trends, not single
nights. Four tasks (the replacement-status inquiries) fail until
the agent can read a card's replacement status (its `Card` model has no such field, and
`update_card_replacement_status` calls a method `BCSAPI` does not define); that fix will
show as a step up.

### How it works

- [`.github/bench/nightly.py`](../.github/bench/nightly.py) is generic: register the image as a candidate,
  find or create the trial named by `--trial`, poll until its attempts finish, exclude Veris-side
  failures, write `results.json` and `chart.svg`.
- [`bench/candidate.json`](bench/candidate.json) is the only agent-specific input: how bench talks to
  this agent (HTTP `POST /chat` on port 8008, health check `/health`).
- The trial must stay unchanged while it runs. Editing the bench's world or judge, removing a task,
  or editing a task or archetype stops the job with a message. To start a new series on purpose,
  change `SERIES` in the workflow.
- Never delete a candidate that is in the trial: bench then refuses every later addition to it.
- Each candidate is named `card-replacement <date> (<commit>, <image digest>)`.
  [`card-replacement-image-retention.yaml`](../.github/workflows/card-replacement-image-retention.yaml)
  keeps the newest images in GHCR when run (by hand for now); an older night keeps its results on
  bench but can no longer be re-run.

### Settings

Optional repository variables (Settings → Secrets and variables → Actions → Variables); each has a
default, so none is required.

| Variable | Default | What it sets |
|---|---|---|
| `CARD_REPLACEMENT_ENVIRONMENT` | `bench-dev` | Which GitHub environment the nightly uses — and so which bench endpoint, bench and API key |
| `CARD_REPLACEMENT_WAIT_MINUTES` | `180` | How long the job waits for the night's attempts before charting what finished; keep it under 330 (GitHub stops a job at 6 h) |
| `CARD_REPLACEMENT_IMAGES_TO_KEEP` | `30` | How many of the newest images the retention workflow keeps |

A manual run (Actions → Run workflow) can also name a different trial, to try a change without
adding a point to the `nightly` series; its result stays in the run's summary and on bench, and
the published chart is left alone. The schedule itself is the `cron` line in each workflow:
GitHub does not read it from a variable.

### One-time setup (per environment)

The nightly job needs a bench that already exists; it only adds candidates to it.

1. **Twin world.** With the `veris` CLI, create an environment with the twins the agent uses (here a
   Postgres twin), boot it, load the customers and cards the tasks talk about, and save it as a
   snapshot (`veris env create`, `veris up`, `veris snapshot create`).
2. **Bench.** In the bench console, create a bench with an exam of tasks, a world bound to that
   snapshot, and the agent's secrets as candidate environment (here `OPENAI_API_KEY`).
3. **GitHub.** In a GitHub environment (`bench-dev` or `bench-prod`), set the variables `BENCH_API`,
   `BENCH_CONSOLE` and `CARD_REPLACEMENT_BENCH_ID`, and the secret `BENCH_API_KEY` (a workspace API
   key from the bench console).
4. **Image access.** The image lands in GHCR as `card-replacement-agent`. A package pushed from a
   public repo is public, which bench needs: it pulls without credentials. From a private repo, save a
   registry login in the bench console instead.

### Use it for your own agent

Set up a bench as above, write a `candidate.json` for your agent, copy the workflow (change `IMAGE`,
`LABEL`, the build `context`, `--candidate`, the bench variable), and set the four GitHub values.
