# Shopping Agent

A multi-agent shopping assistant built with [LangGraph](https://langchain-ai.github.io/langgraph/) and [Stripe's MCP server](https://docs.stripe.com/mcp). Customers chat with the agent over WebSocket to browse products, manage their account, and check out via Stripe payment links.

## Agent Architecture

```
Browser (WebSocket) <---> Express Server <---> Supervisor Agent (LangGraph)
                                                   ├── Catalog Agent ──→ Stripe MCP
                                                   │   (products, prices, payment links,
                                                   │    charges, refunds)
                                                   └── Account Agent ──→ PostgreSQL
                                                       (customers, orders, profiles)
```

The system uses a **supervisor pattern** with two specialist agents:

- **Catalog Agent** (OpenAI `gpt-5-mini`) — owns the Stripe system. Lists products, creates payment links, looks up charges, processes refunds.
- **Account Agent** (Google Gemini `gemini-2.5-flash`) — owns the customer database. Looks up profiles, views order history, updates addresses, records orders.
- **Supervisor** (OpenAI `gpt-5-mini`) — breaks down customer requests and delegates to the right agent. Multi-step workflows (e.g. purchase) chain both agents.

### Key Files

- **`src/agent.js`** — LangGraph agent configuration. Supervisor prompt, sub-agent definitions, model selection.
- **`src/index.js`** — Express + WebSocket server. Streams agent responses as JSON messages.
- **`src/mcp.js`** — Stripe MCP client. Connects to Stripe's remote MCP server over HTTP.
- **`src/db.js`** — PostgreSQL tools for customer and order management.
- **`schemas/schema.sql`** — Database schema (customers, orders).
- **`public/index.html`** — Minimal chat UI.

## Prerequisites

- Node.js 18+
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A [Google AI API key](https://aistudio.google.com/apikey)
- A [Stripe secret key](https://dashboard.stripe.com/apikeys) (test mode)
- PostgreSQL (for local development)

## Quick Start

```bash
git clone <repo-url>
cd shopping-agent
npm install
```

Copy the env file and fill in your keys:

```bash
cp .env.example .env
```

```
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
STRIPE_SECRET_KEY=sk_test_...
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sandbox
PORT=8000
```

Seed the database and start the server:

```bash
psql $DATABASE_URL -f schemas/schema.sql
npm run dev
```

Open [http://localhost:8000](http://localhost:8000) and start chatting.

## Customizing

### Change models

Edit `src/agent.js`:

```js
const openaiModel = new ChatOpenAI({ model: "gpt-5-mini" });       // Supervisor + Catalog
const geminiModel = new ChatGoogleGenerativeAI({ model: "gemini-2.5-flash" }); // Account
```

### Change agent prompts

The `prompt` field on each agent in `src/agent.js` controls its behavior. Modify the supervisor prompt to change routing logic, or the sub-agent prompts to change how they interact with their tools.

### Add more tools

The Catalog Agent gets all its tools from Stripe's MCP server. The Account Agent uses custom PostgreSQL tools defined in `src/db.js`. Add new tools to either agent by extending the `tools` array in `src/agent.js`.

## Deploy on Veris

### 1. Install Veris CLI & login

```bash
uv tool install veris-cli
veris login
```

### 2. Clone the repo

```bash
git clone <repo-url>
cd shopping-agent
```

### 3. Create a Veris environment

```bash
veris env create
```

### 4. Configure environment variables

Set your API keys as secrets (not in `veris.yaml`):

```bash
veris env vars set OPENAI_API_KEY=sk-... --secret
veris env vars set GOOGLE_API_KEY=... --secret
```

> **Note:** `STRIPE_SECRET_KEY` and `DATABASE_URL` are automatically configured by the Veris sandbox (see `.veris/veris.yaml`). You don't need to set them manually.

### 5. Push and run

```bash
veris env push
```

### 6. Run simulations

```bash
veris scenarios create --num 25
veris run
```

## Veris Sandbox Configuration

The `.veris/veris.yaml` configures how the agent runs in the Veris sandbox:

- **Stripe mock** — DNS alias `mcp.stripe.com` maps to the sandbox's Stripe MCP mock. Products and prices are seeded per scenario.
- **PostgreSQL** — Provisioned automatically with the schema from `schemas/schema.sql`.
- **Persona channel** — WebSocket on `ws://localhost:8000`.
