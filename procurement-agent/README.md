# Procurement Agent

IT procurement sourcing & negotiation agent with Oracle Fusion Cloud ERP integration, built with [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) and [Veris](https://veris.ai) simulation support.

## What This Agent Does

An autonomous **IT procurement agent** that manages the complete procurement lifecycle:
- **Sourcing** — Receives procurement requests, queries Oracle for approved suppliers, sends RFQs
- **Negotiation** — Collects vendor quotes, detects hidden fees and pressure tactics, counter-offers
- **Finalization** — Compares quotes, validates against procurement policies, creates POs in Oracle

### Key Capabilities

- **Conversation memory** — Maintains full thread context across email turns via `SQLiteSession`, preventing duplicate sourcing or PO creation
- **Per-thread state** — Tracks original requestor, budget ceiling, and cached approved supplier list per procurement thread via `ProcurementContext`
- **Policy enforcement** — Sub-agent validates budget ceiling, unit price caps, minimum quote requirements, and approved supplier list before any commitment
- **Phase awareness** — Instructions include explicit guards to execute sourcing and finalization only once per thread

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [Veris CLI](https://docs.veris.ai) (`uv tool install veris-cli`)
- API key: [OpenAI](https://platform.openai.com/api-keys)

## Quick Start (Local)

```bash
uv sync
cp .env.example .env
# Edit .env and set OPENAI_API_KEY, EMAIL_INBOX_ID, AGENTMAIL_API_KEY
uv run uvicorn app.main:app --host 0.0.0.0 --port 8008
```

## Deploy on Veris

### 1. Install Veris CLI & login

```bash
uv tool install veris-cli
veris login
```

### 2. Clone the repo

```bash
git clone <repo-url>
cd procurement-agent
```

### 3. Install dependencies

```bash
uv sync
```

> **Note:** `veris env push` requires `uv.lock` to exist. The Dockerfile uses `uv sync --frozen`. Run `uv sync` or `uv lock` first if the lockfile is missing.

### 4. Create a Veris environment

```bash
veris env create
```

### 5. Configure environment variables

Open `.veris/veris.yaml` and update the `agent.environment` section with your values:

```yaml
agent:
  environment:
    ORACLE_BASE_URL: https://oracle-fscm.oraclecloud.com/fscmRestApi/resources/11.13.18.05
    ORACLE_TOKEN_URL: https://oracle-fscm.oraclecloud.com/oauth2/v1/token
    ORACLE_CLIENT_ID: <your-oracle-client-id>
    ORACLE_CLIENT_SECRET: <your-oracle-client-secret>
    EMAIL_BACKEND: agentmail
    EMAIL_INBOX_ID: <your-inbox-id>
    AGENTMAIL_API_KEY: <your-agentmail-api-key>
```

Set your OpenAI API key as a secret (not in `veris.yaml`):

```bash
veris env vars set OPENAI_API_KEY=sk-... --secret
```

### 6. Push and run

```bash
veris env push
```

### 7. Run simulations

Generate test scenarios or use the pre-built ones in `scenarios/`:

```bash
veris scenarios create --num 25
veris run
```

## Veris Sandbox Configuration

The `.veris/veris.yaml` configures how the agent runs in the Veris sandbox:

- **Oracle mock service** — DNS alias `oracle-fscm.oraclecloud.com` maps to the sandbox's Oracle FSCM mock. The agent's `ORACLE_BASE_URL` and `ORACLE_TOKEN_URL` env vars are overridden to use this alias (the real Oracle hostname `efao.fa.us6.oraclecloud.com` has too many subdomain levels for the sandbox's TLS wildcard cert).
- **Email mock** — AgentMail is intercepted via DNS alias `api.agentmail.to`. No real AgentMail API key needed in sandbox mode.
- **Actor** — Email modality with 10-turn max and 3-second response interval.

## Project Structure

```
.
├── app/
│   ├── main.py                   # FastAPI app with polling + optional webhook
│   ├── config.py                 # Environment settings with backend validation
│   ├── email_poller.py           # Backend-agnostic email polling loop
│   ├── email/                    # Email backend abstraction
│   │   ├── __init__.py           # Factory: get_email_client()
│   │   ├── base.py               # EmailClient protocol
│   │   ├── agentmail_backend.py
│   │   └── gmail_backend.py
│   ├── agents/
│   │   ├── procurement_agent.py  # Agent orchestration, session memory, context wiring
│   │   ├── context.py            # ProcurementContext dataclass (per-thread state)
│   │   ├── instruction.md        # Agent system prompt (edit this!)
│   │   ├── policy_checker.py     # Procurement policy validation with ASL verification
│   │   └── tools.py              # oracle_connector, quote_tracker, send_email
│   └── schemas/                  # Pydantic models (EmailMessage, EmailWebhookPayload)
├── .veris/
│   ├── veris.yaml                # Sandbox service config and agent env overrides
│   └── Dockerfile.sandbox        # Sandbox container build
├── tests/                        # Test suite
└── pyproject.toml
```

## Customization

### Agent Behavior

Edit `app/agents/instruction.md` to customize the agent's system prompt.

### Adding Tools

Edit `app/agents/tools.py` and register in `app/agents/procurement_agent.py`.

### Procurement Policies

Edit `app/agents/policy_checker.py` to adjust policy rules (budget limits, quote minimums, deposit caps, etc.).
