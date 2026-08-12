# BrandPulse Agent

A scheduled brand-monitoring agent built on [OpenClaw](https://github.com/openclaw/openclaw). On a cron trigger it searches the web for recent coverage of a brand, writes a structured digest grounded in what it found, posts it to Slack, and exits. One invocation = one brand = one digest = one Slack post.

Unlike the other examples in this cookbook, BrandPulse ships **no local agent code** — it is a stock OpenClaw CLI agent defined entirely by a config file (`.veris/openclaw.json`). The Veris sandbox installs the published `openclaw` CLI and runs the agent the same way production does: `openclaw agent --deliver`, once per actor turn.

See **[`.veris/brandpulse-prd.md`](./.veris/brandpulse-prd.md)** for the full product spec (trigger format, validation rules, digest template, and operator responsibilities).

## Agent Architecture

```
cron (8:55am)
  └─> openclaw agent --local --agent brandpulse \
        --deliver --reply-channel slack --reply-to C_BRAND_ACME \
        --message "Daily pulse: Acme Corp. Last 24h."
        │
        ├─ validate the trigger (brand + window + modifiers)
        ├─ tool: web_search   (5–8 queries, scoped to the window/modifiers)
        ├─ model: summarize the results into the digest template
        └─ channel: slack.chat.postMessage to #brand-acme
```

The agent uses a single tool — `web_search` — and grounds every claim in the search-result URLs it cites. All returned snippet content is treated as untrusted data (prompt-injection defense), and the agent posts a failure line rather than exiting silently.

### Key Files

- **`.veris/openclaw.json`** — the entire agent: system prompt (trigger contract, validation, digest template), model defaults, the `web_search` tool allowlist, Slack channel config, and the Firecrawl search provider.
- **`.veris/veris.yaml`** — Veris sandbox config. Mocks `slack.com` / `api.slack.com` and invokes the agent through a CLI channel.
- **`.veris/Dockerfile.sandbox`** — installs Node 22 + the `openclaw` CLI on the Veris gVisor base and drops `openclaw.json` into `/root/.openclaw/`.

## The trigger contract

cron passes the agent a single message in this exact shape:

```
Daily pulse: <BRAND>. Last <WINDOW>.
```

- `<BRAND>` — canonical brand name (e.g. `Stripe`, `Anthropic`).
- `<WINDOW>` — lookback, exactly one of `24h`, `48h`, `7d`.

Optional comma-separated modifiers: `focus: <topic>`, `exclude: <topic>`, `region: <region>`. The agent **refuses** (a short message, no digest) on a missing/invalid window, multiple brands, or contradictory time references.

```
Daily pulse: Stripe. Last 24h. focus: product launches
Daily pulse: Anthropic. Last 7d. focus: hiring, exclude: stock price
```

## Customizing

Everything lives in `.veris/openclaw.json`:

- **Model** — `agents.defaults.model` (default `openai/gpt-5.4`).
- **Prompt / digest format** — `agents.list[0].systemPromptOverride`.
- **Tools** — `agents.list[0].tools.allow` (just `web_search`).
- **Search provider** — `tools.web.search.provider` + the `firecrawl` plugin config.

> **Secrets:** the Slack token / signing secret in `openclaw.json` are mock values for the sandbox, and the Firecrawl `apiKey` is the placeholder `fc-mock-firecrawl-key`. Swap in your own keys (or supply them via the environment) before running outside the mock.

## Deploy on Veris

### 1. Install Veris CLI & login

```bash
uv tool install veris-cli
veris login
```

### 2. Clone the repo

```bash
git clone <repo-url>
cd brandpulse-agent
```

### 3. Create a Veris environment

```bash
veris env create
```

### 4. Push and run

```bash
veris env push
veris scenarios create --num 25
veris run
```

## Veris Sandbox Configuration

The `.veris/veris.yaml` configures how the agent runs in the Veris sandbox:

- **Slack mock** — DNS aliases `slack.com` / `api.slack.com` map to the sandbox's Slack mock, which captures the digest the agent posts to `C_SANDBOX`.
- **CLI channel** — Veris spawns the `openclaw` CLI once per actor turn (`MAX_TURNS: "1"`), mirroring the production cron → `openclaw agent --deliver` invocation. The agent skips gateway startup and replies through the Slack channel.
