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

### Veris simulations (retired)

These examples used to run on the Veris simulation platform. That platform retires on **2026-10-31** (writes close **2026-10-05**). The example agents live on as public benches at [benchmark.veris.ai](https://benchmark.veris.ai); service mocking for your own code is now [Veris Twins](https://studio.veris.ai). Dates and export steps: https://docs.veris.ai/deprecation

## POC Scope

This POC includes only the Clear CUID sub-agent. The full system would add ~15–20 additional sub-agents (trust accounts, wire transfers, etc.), real database connectivity, and production auth.
