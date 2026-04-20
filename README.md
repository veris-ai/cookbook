<div align="center">

<img src="./LM-Logo-Veris-Green.svg" alt="Veris" width="200">

# Cookbook

### Build Reliable AI Agents With Simulated Environments

[![Docs](https://img.shields.io/badge/docs-veris.ai-047404)](https://docs.veris.ai)

</div>

---

A collection of reference agents demonstrating how to build, test, and deploy AI agents using the [Veris](https://veris.ai/sandbox) simulation platform — or run them standalone.

Each example is a complete, working agent with its own README, test suite, and Veris simulation scenarios. Use them as starting points for your own agents or as references for integrating with Veris.

## Examples

| Agent | Description | Framework | Integrations |
|-------|-------------|-----------|--------------|
| **[Banker Connections Agent](./bca-agent)** | Resolves customer record update errors for retail bankers in real time | Google ADK | Vertex AI, Hogan API |
| **[Card Replacement Agent](./card-replacement-agent)** | Handles card freeze, replacement, delivery tracking, and activation workflows | OpenAI Agents SDK | PostgreSQL |
| **[Mini BCS](./mini-bcs)** | Credit card support agent for common cardholder requests | OpenAI Agents SDK | PostgreSQL |
| **[PM Analyst](./pm-analyst)** | Converts meeting transcripts into structured Epics, Features, and User Stories | Google ADK | Azure DevOps, Microsoft Teams |
| **[Procurement Agent](./procurement-agent)** | Autonomous IT procurement sourcing, negotiation, and PO finalization | OpenAI Agents SDK | Oracle Fusion Cloud ERP, AgentMail |

## Getting Started

### Run standalone

Each agent can run independently — just follow the README in its directory. You'll typically need:

1. Clone the repo and `cd` into the agent directory
2. Install dependencies (`uv sync` or `pip install`)
3. Set environment variables (API keys, etc.)
4. Start the server (`uvicorn` or `docker compose up`)

### Run with Veris

[Veris](https://docs.veris.ai) provides sandboxed environments with simulated users and services so you can test your agent end-to-end before deploying to production.

**1. Install the Veris CLI**

```bash
uv tool install veris-cli
veris login
```

**2. Create an environment**

```bash
cd <agent-directory>
veris env create
```

**3. Configure and push**

Update `.veris/veris.yaml` with your environment variables, then:

```bash
veris env push
```

**4. Run simulations**

Generate test scenarios and run them:

```bash
veris scenarios create --num 25
veris run
```

Each agent includes pre-built scenarios in its `scenarios/` directory that you can also run directly.

For the full walkthrough, see the [Veris documentation](https://docs.veris.ai).

## Project Structure

```
cookbook/
  bca-agent/               Banker Connections Agent (Google ADK)
  card-replacement-agent/   Card Replacement Agent (OpenAI Agents SDK)
  mini-bcs/                 Mini BCS (OpenAI Agents SDK)
  pm-analyst/               PM Analyst (Google ADK)
  procurement-agent/        Procurement Agent (OpenAI Agents SDK)
```

Each agent follows a consistent layout:

```
<agent>/
  app/              Application code and agent logic
  tests/            Unit and integration tests
  scenarios/        Veris simulation scenarios
  .veris/           Veris sandbox configuration
  README.md         Setup and usage instructions
```

## Contributing

To add a new cookbook example:

1. Create a new directory at the repo root
2. Include a `README.md` with setup instructions, architecture overview, and Veris deployment steps
3. Add a `.veris/` directory with sandbox configuration
4. Include at least one scenario in `scenarios/`
5. Open a pull request

## Resources

- [Veris Documentation](https://docs.veris.ai) — Full platform docs, quickstart, and API reference
- [Veris CLI](https://docs.veris.ai) — CLI installation and commands
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) — Agent framework used by card-replacement and procurement agents
- [Google ADK](https://google.github.io/adk-docs/) — Agent framework used by BCA and PM Analyst

---

<div align="center">
<sub>Built with <a href="https://veris.ai">Veris</a> — the safest way to deploy your AI agents</sub>
</div>
