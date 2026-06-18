# crm-analyst Trace-Gen Nightly

A scheduled GitHub Action that grounds a fresh Veris scenario set on the last N
days (default **3**) of crm-analyst **production** Langfuse traces, then runs a
simulation + auto-evaluation against the prod env — closing a continuous-improvement
loop: **trace → generate → simulate → grade**, on a schedule.

Workflow: [`.github/workflows/crm-analyst-trace-gen-nightly.yaml`](../../.github/workflows/crm-analyst-trace-gen-nightly.yaml)

## How it works

1. `build_langfuse_curl.sh` turns "last `LOOKBACK_DAYS` days" into a time-ranged
   Langfuse query:
   `/api/public/traces?fromTimestamp=<FROM>&toTimestamp=<TO>&name=openclaw.run&limit=100`
   and prints it as a `curl … -u 'pk:sk'` command.
2. That curl is piped into `veris scenarios create --from-langfuse -` (veris-cli
   ≥ 2.30.0). The CLI parses the curl client-side into a `trace_blob` and posts a
   `kind=trace` scenario source — **keys never touch disk**.
3. The backend fetches the traces, distills intent, and generates the set.
4. `veris scenarios status --watch` blocks until ready; `veris run` simulates +
   auto-grades against the prod env. A markdown summary is uploaded as an artifact.

Each run's scenario set is titled `crm-analyst-trace-nightly-<N>d-<YYYYMMDD>` (UTC
date; `N` = lookback days) so it's easy to find in the console.

### Why `name=openclaw.run` and a time window

The crm-analyst agent emits several openclaw trace types — `openclaw.run`
(top-level agent turn), `openclaw.harness.run`, `openclaw.model.usage`,
`openclaw.exec`, `openclaw.liveness.warning`, `openclaw.message.processed`. Only
`openclaw.run` is a gradable conversation, so we filter to it. OTel export sets
no `sessionId`, so the **traces-list** endpoint (not `/sessions`) is the only
viable path. Unfiltered list queries time out on Langfuse Cloud; a tight
`fromTimestamp/toTimestamp` window is what makes the query reliable (a 7-day
window returns in ~11 s; 3 days is faster).

## Configuration

Per-agent values (`VERIS_ENV_ID`, `LANGFUSE_HOST`, the Secret-Manager secret
**names**) are hardcoded in the workflow `env:` block, so each agent gets its own
`*-trace-gen-nightly.yaml` (GitHub repo Variables are repo-global, so they can't
hold a different env per workflow). Only the shared GCP-WIF infra
(`GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`) is a
repo Variable. Credentials (the Veris key, Langfuse `pk`/`sk`) live in **GCP
Secret Manager** and are pulled at run time via Workload Identity Federation —
nothing secret is stored in the repo.

Tunables:

| Knob | Where | Default |
|------|-------|---------|
| Lookback window | `workflow_dispatch` input `lookback_days` / env `LOOKBACK_DAYS` | `3` |
| Scenario count | `workflow_dispatch` input `num_scenarios` / env `NUM_SCENARIOS` | `30` |
| Trace name filter | env `TRACE_NAME_FILTER` | `openclaw.run` |
| Focus prompt | env `FOCUS_PROMPT` | analytics/HogQL/email-approval steer |

## Run it manually

GitHub UI → Actions → "Veris: crm-analyst Trace-Gen Nightly" → Run workflow
(optionally override `lookback_days` / `num_scenarios`).

## Dry-run the curl-builder locally

```bash
LANGFUSE_HOST=https://us.cloud.langfuse.com \
LANGFUSE_PUBLIC_KEY=pk-lf-… LANGFUSE_SECRET_KEY=sk-lf-… \
LOOKBACK_DAYS=3 bash build_langfuse_curl.sh
# → curl 'https://us.cloud.langfuse.com/api/public/traces?fromTimestamp=…&toTimestamp=…&name=openclaw.run&limit=100' -u 'pk-lf-…:sk-lf-…'
bash test_build_langfuse_curl.sh   # → PASS (3 cases)
```

## Known limitations

- **No empty-night handling.** If the window has no `openclaw.run` traces,
  generation fails and the job fails (fail-loud). A configurable single-trace
  fallback or a clean skip is a follow-up.
- **No HTML report** (gen + sim + auto-grade only). Add `--report` to `veris run`
  and a `veris reports get` step to extend.
- **Admin gate.** Trace sources are admin-gated server-side, so the pulled Veris
  key must be an admin key for the backend hosting the env.
