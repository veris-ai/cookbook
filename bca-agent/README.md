# Banker Connections Agent (BCA)

AI agent that helps retail bankers resolve customer record update errors in real time, eliminating the need to call a specialist and wait 12–15 minutes while the customer stands at the counter.

This POC handles **Clear CUID scenarios** — errors when updating customer phone numbers and identification documents.

## How It Works

```
Banker Chat UI
      │
Supervisor Agent  ──→  Clear CUID Agent  ──→  Simulated Hogan API
      │                       │
 (routes/escalates)    (lookup_procedure)  ──→  Vertex AI RAG
```

1. Banker describes the error in chat
2. **Supervisor Agent** classifies the query and routes to the Clear CUID Agent (or escalates to a live specialist)
3. **Clear CUID Agent** identifies the error type, looks up the remediation procedure via RAG, retrieves the customer profile, proposes a fix, and executes it after banker confirmation

## Tech Stack

| Component | Technology |
|-----------|------------|
| Agent Framework | Google ADK |
| LLM | Vertex AI (Gemini) |
| Knowledge Base | Vertex AI RAG Engine |
| API | REST (JSON over HTTPS) |

## Tools

| Tool | Description |
|------|-------------|
| `lookup_procedure` | RAG retrieval against the procedure document |
| `hogan_get_customer` | `GET /customers/{inputKey}` — retrieve customer profile |
| `hogan_update_customer` | `PATCH /customers/{inputKey}` — clear phone/ID fields |

## Covered Error Types

| Code | Description |
|------|-------------|
| CUID-PH-001 | International to domestic phone conversion |
| CUID-PH-002 | Duplicate phone number |
| CUID-PH-003 | Corrupted ECN phone link |
| CUID-ID-001 | Primary ID update blocked |
| CUID-ID-002 | Secondary ID add conflict |

## API

```bash
# Start conversation
curl -X POST http://localhost:8000/api/v1/conversations \
  -H "Content-Type: application/json" \
  -d '{"banker_id": "B123", "branch_id": "BR01", "customer_ecn": "1001"}'

# Send message
curl -X POST http://localhost:8000/api/v1/conversations/{id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "I cant update the customers phone number, getting a format error"}'

# Confirm action
curl -X POST http://localhost:8000/api/v1/conversations/{id}/confirm \
  -H "Content-Type: application/json" \
  -d '{"action_id": "...", "confirmed": true}'
```

## Deploy on Veris

### Prerequisites

- A GCP project with **Vertex AI** enabled
- A GCP service account key (JSON) with Vertex AI permissions
- A **Vertex AI RAG corpus** set up with the procedure document

### 1. Install Veris CLI & login

```bash
uv tool install veris-cli
veris login
```

### 2. Clone the repo

```bash
git clone <repo-url>
cd bca-agent
```

### 3. Create a Veris environment

```bash
veris env create
```

### 4. Configure environment variables

Open `.veris/veris.yaml` and update the `agent.environment` section with your values:

```yaml
agent:
  environment:
    HOGAN_API_BASE_URL: https://api.hogan.dxc.com
    ADK_MODEL: gemini-2.5-flash
    GCP_PROJECT: <your-gcp-project-id>
    GCP_LOCATION: global
    RAG_CORPUS_ID: <your-rag-corpus-id>
    RAG_LOCATION: europe-west4
```

### 5. Add the GCP service account key in Veris console

The agent needs GCP credentials to call Vertex AI. Since the key is sensitive, add it as a secret through the Veris console — not in `veris.yaml`.

1. Go to the [Veris console](https://console.veris.ai)
2. Navigate to your environment's **Secrets** section
3. Add a new secret with key name: `GCP_SERVICE_ACCOUNT_JSON`
4. Paste the full contents of your GCP service account JSON key file as the value

### 6. Push and run

```bash
veris env push
```

## POC Scope

This POC includes only the Clear CUID sub-agent. The full system would add ~15–20 additional sub-agents (trust accounts, wire transfers, etc.), real database connectivity, and production auth.
