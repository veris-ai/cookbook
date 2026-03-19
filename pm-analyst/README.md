# PM Analyst

AI assistant that converts meeting transcripts and notes into structured project management artifacts (Epics, Features, User Stories) and pushes them to Azure DevOps.

## Prerequisites

- Python 3.11+
- Node.js 18+
- A Google AI API key **or** GCP project with Vertex AI enabled

## Project Structure

```
backend/          FastAPI + Google ADK agent
pm-assistant/     Next.js frontend
```

## Local Setup

### 1. Backend

```bash
cd backend
cp .env.example .env          # then edit .env with your values
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Key env vars in `backend/.env`:

| Variable | Required | Description |
|---|---|---|
| `PORT` | No | Server port (default `8000`) — also sets the OAuth redirect URI automatically |
| `GOOGLE_API_KEY` | Yes* | Google AI Studio key (*or use Vertex AI below) |
| `GCP_PROJECT` | Yes* | Vertex AI project (*or use API key above) |
| `GCP_LOCATION` | No | Vertex AI region (default `global`) |
| `ADK_MODEL` | No | LLM model (default `gemini-2.5-flash`) |
| `MS_CLIENT_ID` | No | Entra ID app client ID (for Teams/OneDrive) |
| `MS_CLIENT_SECRET` | No | Entra ID app client secret |
| `MS_TENANT_ID` | No | Entra ID tenant ID |
| `ADO_ORG` | No | Azure DevOps organization (for work items) |
| `ADO_PROJECT` | No | Azure DevOps project |

Start the backend:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port $PORT
```

Or simply use the default port:

```bash
uvicorn app.main:app --reload
```

### 2. Frontend

```bash
cd pm-assistant
npm install
```

Create `pm-assistant/.env.local` to point at the backend:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

If you changed `PORT` in the backend, update this to match (e.g. `http://localhost:8001`).

Start the frontend:

```bash
npm run dev -- --port 3000
```

Or on a custom port:

```bash
npm run dev -- --port 3001
```

### 3. Open the app

Visit `http://localhost:3000` (or whichever port you chose for the frontend).

## Optional: Microsoft Integration

To enable Teams transcript pulling and OneDrive file access:

1. Register an app in [Entra ID](https://entra.microsoft.com) with redirect URI `http://localhost:<PORT>/auth/microsoft/callback`
2. Set `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, and `MS_TENANT_ID` in `backend/.env`
3. Sign in via the app's Microsoft login button

## Optional: Azure DevOps Integration

To enable creating/managing work items in ADO:

1. Ensure the Entra ID app registration above has the `Azure DevOps (user_impersonation)` API permission
2. Set `ADO_ORG` and `ADO_PROJECT` in `backend/.env`
3. Re-authenticate to consent to the new scope
4. Ask the agent to create work items — it will push Epics, Features, and User Stories with proper hierarchy
