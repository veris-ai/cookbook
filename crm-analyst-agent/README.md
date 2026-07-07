# crm-analyst-agent

A **NemoClaw / OpenShell** agent: a CRM/PM **analytics assistant** that answers PostHog
product-analytics questions over Slack and drafts approval-gated outreach email, while emitting
OpenTelemetry traces to Langfuse. It's a worked example of an agent built on the native `nemoclaw`
CLI (OpenShell runtime sandbox), not the `veris env push` / Dockerfile flow.

This directory has everything to stand it up: the build+harness script (`onboard.sh`), the harness
itself (the SOUL workspace + two skills), the egress policy presets, and a nightly
**trace → scenario** loop under [`trace-gen/`](trace-gen/).

## What it is

| Aspect | Value |
|---|---|
| Runtime | OpenClaw inside OpenShell (docker driver) |
| Model | any **OpenAI-compatible** endpoint — default `gpt-5.5`; also works with Baseten Model APIs (e.g. `moonshotai/Kimi-K2.7-Code`) |
| Channel | Slack (native, Socket Mode), `contextVisibility: allowlist` |
| Analytics | PostHog HogQL query API, read-only, via the `exec` tool; internal-team activity (`INTERNAL_EMAIL_DOMAIN`, default `veris.ai`) excluded by default |
| Tracing | OpenClaw `diagnostics-otel` plugin → OTLP → Langfuse Cloud, with content capture |
| Skills | `crm-analyst-query` (PostHog), `nemo-sales-crm-approval` (email send, approval-gated) |

## Why two stages

`nemoclaw onboard` **≠** `docker build`. A Dockerfile produces an *image*; the running agent also
needs the OpenShell runtime sandbox (supervisor / netns / OPA / gateway) that onboard provisions.
And onboard's standard build owns the **deployable config** — model, provider, Slack channel,
allowlist, OTel plugin — baked from your wizard answers (the image *is* the deployable unit). So the
split is structural:

1. **Image** = `nemoclaw onboard` (standard build). Owns model / provider / Slack channel /
   allowlist / OTel plugin.
2. **Harness** = `onboard.sh` Stage 2. Layers the bits onboard can't bake — skills, the SOUL
   workspace, the PostHog secret file, the Langfuse OTLP auth header, and the egress presets — onto
   the running sandbox.

The harness's non-state-dir bits (`/sandbox/.secrets/posthog.env`, the `openclaw.json` Langfuse /
captureContent patch) and the custom egress presets **reset on every recreate**, so Stage 2 must
re-run after each onboard/rebuild. `onboard.sh` does both stages; `--harness-only` re-applies Stage 2.

## Files

```
onboard.sh                       # Stage 1 (nemoclaw onboard, OTel baked) + Stage 2 (harness). --harness-only skips Stage 1.
workspace/                       # the SOUL framework (maps to /sandbox/.openclaw/workspace/)
  SOUL.md IDENTITY.md AGENTS.md TOOLS.md POLICY.md USER.md HEARTBEAT.md
skills/
  crm-analyst-query/SKILL.md     # PostHog HogQL via exec; reads creds from /sandbox/.secrets/posthog.env
  nemo-sales-crm-approval/SKILL.md
policies/
  posthog.yaml                   # egress preset: PostHog, scoped to python3*/node binaries
  langfuse.yaml                  # egress preset: Langfuse OTLP, node binary
trace-gen/                       # nightly: ground a scenario set on production Langfuse traces (see its README)
crm-analyst-secrets.env.example  # template; copy to crm-analyst-secrets.env (git-ignored) to build
```

## Set it up

You need the `nemoclaw` CLI and accounts for your model provider, PostHog, Langfuse, and a Slack
app. `onboard.sh` wraps the whole flow; run it in a **real terminal** (the onboard wizard reads
`/dev/tty`).

1. **Secrets**: `cp crm-analyst-secrets.env.example crm-analyst-secrets.env` and fill in real keys
   (PostHog personal key with `query:read`+`person:read`; Langfuse public/secret keypair; your
   PostHog project id). The filled file is git-ignored; `onboard.sh` reads it from `$SECRETS_ENV`
   (defaults to this directory).

2. **Build + harness** in one shot:
   ```bash
   ./onboard.sh
   ```
   - **Stage 1** runs `nemoclaw onboard` with OTel baked. Answer the wizard:
     `provider=openai`, `model=gpt-5.5`, web search=no, **Messaging=Slack with your allowlist**,
     `sandbox=crm-analyst`. (Any OpenAI-compatible endpoint works — e.g. Baseten Model APIs:
     `provider=compatible-endpoint`, `baseURL=https://inference.baseten.co/v1`,
     `model=moonshotai/Kimi-K2.7-Code`.) The standard build bakes model/provider/channel/`allowFrom`/OTel plugin.
   - **Stage 2** auto-applies the harness: installs the two skills, syncs `workspace/`, writes
     `/sandbox/.secrets/posthog.env`, patches `openclaw.json` (Langfuse auth header + captureContent
     + `OTEL_SEMCONV_STABILITY_OPT_IN` + `timeoutSeconds`), re-applies the egress presets, then does
     a full process restart so the OTel exporter re-preloads. Ends with a VERIFY block.

3. **Re-apply harness only** (after a separate `nemoclaw <name> rebuild`, which resets the
   non-state-dir bits and egress presets):
   ```bash
   ./onboard.sh --harness-only
   ```

### Updating the Slack allowlist

The allowlist materializes from `SLACK_ALLOWED_USERS` into `channels.slack…allowFrom` at **onboard
time**. Stage the IDs with `nemoclaw crm-analyst channels` (control-plane), then re-run `./onboard.sh`
to materialize them — the `channels` command only *stages*; the onboard *applies*.

## Model

The agent uses any **OpenAI-compatible** chat endpoint; the default here is `gpt-5.5`. Skill
invocation is the bar to clear: weaker models can fail to invoke file-based skills (they search for a
*skill name* as if it were a tool id and loop on the resulting error). The SOUL is hardened for this
("skills are files — use `read`+`exec`", plus a hard give-up rule) and `timeoutSeconds` is bounded,
but a hardened prompt doesn't fix a weak model — pick a model with solid tool/function calling. Swap
models live with `nemoclaw inference set` (hot-reload, no rebuild).

## Continuous improvement (`trace-gen/`)

Once the agent is live and emitting Langfuse traces, [`trace-gen/`](trace-gen/) is a nightly GitHub
Action that grounds a fresh Veris scenario set on the last N days of **production** traces, then runs
a simulation + evaluation against it — closing a trace → generate → simulate → grade loop. See
[`trace-gen/README.md`](trace-gen/README.md).

The workflow YAML in this repo is a **reference copy** (`workflow_dispatch` only). We run the real
loop against our production agent from a private mirror, because its outputs — reports, sim
transcripts, fix diffs, logs — quote production data; sanitized improvements are cherry-picked back
into this copy.

## Hard-won gotchas (why the harness/policies look the way they do)

- **State-restore redacts secrets in `state_dirs`.** On a rebuild/recreate, OpenShell replaces
  secret-looking values inside restored `state_dirs` (`skills/`, `workspace/`, …) with a placeholder.
  So the PostHog key **cannot** live in `skills/…/posthog.env`. `onboard.sh` writes it to
  **`/sandbox/.secrets/`** (not a state_dir → never restored-over). `openclaw.json` (Langfuse auth
  header) is the config file, not a state_dir, so it's patched the same way.
- **Per-binary egress.** A preset with no `binaries:` field denies *everything* (OPA matches no
  binary → CONNECT 403). The exec'd `python3` resolves to a real interpreter path (kernel
  `/proc/<pid>/exe`), so the PostHog preset scopes `/usr/bin/python3*` + node; Langfuse (gateway node
  exporter) scopes node.
- **Egress presets reset on rebuild** to the onboard defaults — `onboard.sh` (or `--harness-only`)
  re-applies them.
- **OTel → Langfuse.** `diagnostics.otel` has no headers env var; the auth must be
  `diagnostics.otel.headers.Authorization = Basic base64(pk:sk)` patched into `openclaw.json`
  (`onboard.sh` does this). `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` makes spans
  render natively in Langfuse, and `diagnostics.otel.captureContent` records LLM input/output.
- **captureContent needs a full restart.** Editing `captureContent` live triggers an *in-process*
  gateway restart that silently breaks the preloaded OTel exporter (turns run, nothing exports). So
  `onboard.sh` ends with a real `docker restart` + `connect --probe-only`, not a hot-reload.
- **Version coupling.** OpenClaw's wire protocol is coupled to the OpenShell supervisor version —
  pin OpenClaw + supervisor as a set; never freeze the supervisor independently.
