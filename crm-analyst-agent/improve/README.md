# crm-analyst improvement loop

A self-closing nightly loop that turns Veris simulation **reports** into agent
improvements, gated by a human-reviewed draft PR.

```
 nightly  ──►  rebuild prod env from repo HEAD
          ──►  generate scenarios from fresh prod traces (Langfuse, openclaw.run)
          ──►  run + grade  ──►  report  ──►  ingest agent-fixes  ──►  DRAFT PR
                                                                         │
                                              you review + merge ◄───────┘
          ──►  NEXT nightly rebuilds from the merged HEAD on fresh scenarios …
```

There is **no separate verify job / pinned regression set**: each night re-grounds
on the latest production traces and rebuilds the agent from repo HEAD, so the next
run *is* the verification. Improvement is tracked as the pass-rate trend over nights.

## Pieces

| File | Role |
|---|---|
| [`ingest_report.py`](ingest_report.py) | Apply a report's agent-fixes to the agent source, emit a PR body. |
| [`../../.github/workflows/crm-analyst-improve-nightly.yaml`](../../.github/workflows/crm-analyst-improve-nightly.yaml) | The nightly loop (cron + `workflow_dispatch`). |
| [`fixtures/agent_fixes_example.json`](fixtures/agent_fixes_example.json) | A real `/agent-fixes` payload (test + reference). |

## `ingest_report.py`

Input is the JSON from `veris reports get <rpt_id> --format json`:

```json
{"report_id": "...", "status": "completed",
 "fixes": [{"route": "skill", "confidence": "medium",
            "target_path": "skills/.../SKILL.md",
            "diff": "diff --git a/skills/... b/skills/...\n@@ ...",
            "title": "...", "description": "...", "simulations_affected": [...]}]}
```

Only **agent-fixable** routes are applied — `skill`, `system_prompt`, `tool_schema`
(the endpoint already filters; the script re-checks). `bad_scenario` / `capability`
findings are parked. Each `diff` is a git diff whose paths are relative to the agent
root, so it is applied with `git apply --directory=crm-analyst-agent -p1 --recount`.
Fixes that don't apply cleanly (baseline drift) are **listed for manual fixing**, not
force-patched. Exit codes let the caller tell a clean run from a drifted one: **0** if
≥1 fix applied (open a draft PR), **2** if agent-fixable fixes were found but all failed
to apply (baseline drift — the workflow surfaces the PR body as an artifact instead of
calling it clean), **1** if there was nothing agent-fixable (a genuinely clean run).

```bash
veris reports get rpt_xxx --format json -o fixes.json
python improve/ingest_report.py --fixes fixes.json --agent-dir crm-analyst-agent
```

Tests: `pytest improve/test_ingest_report.py`.

## Required infra (already wired for prod, except where noted)

- **Env**: `VERIS_ENV_ID=env_5e5n3vezipnngaqvygtki` (prod crm-analyst).
- **GCP WIF**: repo Variables `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`,
  `GCP_SERVICE_ACCOUNT`; the SA needs Secret Manager access + scenario/report perms.
- **Secrets (GCP Secret Manager)**: `veris-cookbook-nightly-admin-key` (is_admin
  automation key — trace sources are admin-gated), `crm-analyst-langfuse-{public,secret}-key`.
- **Repo setting**: *Actions → General → Allow GitHub Actions to create and approve
  pull requests* (the draft-PR step uses the default `GITHUB_TOKEN`).

## Prerequisites to validate before trusting the cron

1. **Token fix in prod** — prod `env_5e5n3` must run the gateway with `--token`
   (veris-sandbox recipe `3.2.0`, PR #1955) or the agent hits `token_mismatch` and
   the report grades empty. Rebuilt automatically by the loop's `env push` once the
   recipe is live.
2. **B0 baseline** — the repo's `crm-analyst-agent/` must be the source the env is
   built from, so the report's diffs `git apply` on a byte-identical baseline. The
   `env push --no-snapshot` step needs an env-push-able layout (`user-state/`).
3. Dry-run once via **`workflow_dispatch`** before enabling the schedule.
