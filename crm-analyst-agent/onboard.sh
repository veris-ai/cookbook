#!/usr/bin/env bash
# onboard.sh — build + harness the native crm-analyst agent, end to end.
#
# Stage 1 (IMAGE):   `nemoclaw onboard` (interactive wizard) with OTel baked.
#                    Owns model / provider / Slack channel / allowlist / OTel-plugin.
# Stage 2 (HARNESS): layer skills + workspace/SOUL + PostHog secret + Langfuse
#                    header + egress presets onto the running sandbox.
#
# The non-state-dir harness bits (/sandbox/.secrets/posthog.env, the openclaw.json
# Langfuse/captureContent patch) and egress presets reset on every recreate, so
# Stage 2 must run after each onboard/rebuild.
#
# Run in a REAL terminal — the onboard wizard reads /dev/tty (cannot be piped).
# Re-apply harness only (skip the onboard) with:   onboard.sh --harness-only
set -euo pipefail

SANDBOX=crm-analyst
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECIPE_DIR="${RECIPE_DIR:-$SCRIPT_DIR}"                          # this cloned agent dir (skills/workspace/policies)
SECRETS_ENV="${SECRETS_ENV:-$RECIPE_DIR/crm-analyst-secrets.env}"  # real keys, git-ignored

# OTel is baked at onboard time: NEMOCLAW_OPENCLAW_OTEL=1 installs the diagnostics-otel
# plugin, patches the OTLP exporter to route via the egress proxy, and writes the
# diagnostics.otel block (endpoint/serviceName). onboard cannot bake the auth HEADER
# (no headers env) -> Stage 2 patches diagnostics.otel.headers in.
OTEL_ENDPOINT="https://us.cloud.langfuse.com/api/public/otel"
OTEL_SERVICE_NAME="crm-analyst"

SKIP_ONBOARD=0
[ "${1:-}" = "--harness-only" ] && SKIP_ONBOARD=1

# --- validate inputs up front (before the long onboard) ---
[ -d "$RECIPE_DIR" ]  || { echo "FATAL: recipe dir not found: $RECIPE_DIR" >&2; exit 1; }
[ -f "$SECRETS_ENV" ] || { echo "FATAL: secrets env not found: $SECRETS_ENV" >&2; exit 1; }
. "$SECRETS_ENV"
: "${POSTHOG_API_KEY:?}" "${POSTHOG_API_HOST:?}" "${POSTHOG_PROJECT_ID:?}" \
  "${LANGFUSE_PUBLIC_KEY:?}" "${LANGFUSE_SECRET_KEY:?}"

# ===========================================================================
# STAGE 1 — IMAGE via onboard (interactive)
# ===========================================================================
if [ "$SKIP_ONBOARD" = 0 ]; then
  echo ">> STAGE 1: nemoclaw onboard (interactive wizard; OTel baked)"
  echo "   answer: provider=openai  model=gpt-5.5  Messaging=Slack (your allowlist)"
  echo "           (any OpenAI-compatible endpoint works — e.g. Baseten Model APIs:"
  echo "            provider=compatible-endpoint, baseURL=https://inference.baseten.co/v1,"
  echo "            model=moonshotai/Kimi-K2.7-Code)"
  echo "           sandbox=$SANDBOX"
  NEMOCLAW_OPENCLAW_OTEL=1 \
  NEMOCLAW_OPENCLAW_OTEL_ENDPOINT="$OTEL_ENDPOINT" \
  NEMOCLAW_OPENCLAW_OTEL_SERVICE_NAME="$OTEL_SERVICE_NAME" \
  nemoclaw onboard
else
  echo ">> --harness-only: skipping onboard"
fi

# ===========================================================================
# STAGE 2 — HARNESS
# ===========================================================================
CID="$(docker ps --format '{{.Names}}' | grep -m1 "openshell-${SANDBOX}-" || true)"
[ -n "$CID" ] || { echo "FATAL: no running container openshell-${SANDBOX}-*" >&2; exit 1; }
echo ">> container: $CID  (image: $(docker inspect -f '{{.Config.Image}}' "$CID"))"

dex()  { docker exec -i -u sandbox "$CID" "$@"; }   # as sandbox user
dexr() { docker exec -i -u root    "$CID" "$@"; }   # as root (dirs/chown)

# --- 1. skills (durable native install) ---
for sk in crm-analyst-query nemo-sales-crm-approval; do
  echo ">> skill install: $sk"
  nemoclaw "$SANDBOX" skill install "$RECIPE_DIR/skills/$sk"
done

# --- 2. workspace / SOUL framework ---
echo ">> workspace sync -> /sandbox/.openclaw/workspace/"
docker cp "$RECIPE_DIR/workspace/." "$CID:/sandbox/.openclaw/workspace/"
dexr chown -R sandbox:sandbox /sandbox/.openclaw/workspace

# --- 3. PostHog creds in a NON-state-dir path (survives state-restore redaction) ---
echo ">> posthog secret -> /sandbox/.secrets/posthog.env"
dexr sh -c 'mkdir -p /sandbox/.secrets && chown sandbox:sandbox /sandbox/.secrets && chmod 700 /sandbox/.secrets'
dex sh -c 'cat > /sandbox/.secrets/posthog.env && chmod 600 /sandbox/.secrets/posthog.env' <<EOF
POSTHOG_API_KEY=${POSTHOG_API_KEY}
POSTHOG_API_HOST=${POSTHOG_API_HOST}
POSTHOG_PROJECT_ID=${POSTHOG_PROJECT_ID}
EOF

# --- 4. Langfuse OTLP header + captureContent + GenAI semconv + timeout -> openclaw.json ---
echo ">> openclaw.json patch (otel header + captureContent + semconv + timeout)"
AUTH="$(printf '%s:%s' "$LANGFUSE_PUBLIC_KEY" "$LANGFUSE_SECRET_KEY" | base64 -w0)"
dex env AUTH="$AUTH" node - <<'NODE'
const fs=require("fs");
const p="/sandbox/.openclaw/openclaw.json";
const c=JSON.parse(fs.readFileSync(p,"utf8"));
c.diagnostics=c.diagnostics||{}; c.diagnostics.otel=c.diagnostics.otel||{};
c.diagnostics.otel.headers={"Authorization":"Basic "+process.env.AUTH,"x-langfuse-ingestion-version":"4"};
c.diagnostics.otel.captureContent={enabled:true,inputMessages:true,outputMessages:true,toolInputs:true,toolOutputs:true,toolDefinitions:true};
c.env=c.env||{}; c.env.vars=c.env.vars||{};
c.env.vars.OTEL_SEMCONV_STABILITY_OPT_IN="gen_ai_latest_experimental";
c.agents=c.agents||{}; c.agents.defaults=c.agents.defaults||{}; c.agents.defaults.timeoutSeconds=180;
fs.writeFileSync(p,JSON.stringify(c,null,2));
process.stderr.write("patched diagnostics.otel.headers + captureContent + OTEL_SEMCONV + timeoutSeconds\n");
NODE

# --- 5. egress presets (reset on recreate) ---
for pol in posthog langfuse; do
  echo ">> policy-add: $pol"
  nemoclaw "$SANDBOX" policy-add --from-file "$RECIPE_DIR/policies/$pol.yaml" --yes
done

# --- 6. full process restart so OTel re-preloads captureContent ---
echo ">> full restart (OTel re-preload)"
docker restart "$CID"
nemoclaw "$SANDBOX" connect --probe-only

# --- verify ---
echo ">> VERIFY"
dex node -e 'const c=JSON.parse(require("fs").readFileSync("/sandbox/.openclaw/openclaw.json","utf8"));
const a=(((c.channels||{}).slack||{}).accounts||{}).default||{};
console.log("model.primary :", (((c.agents||{}).defaults||{}).model||{}).primary);
console.log("allowFrom     :", (a.allowFrom||[]).length, "ids", JSON.stringify(a.allowFrom));
console.log("otel.headers  :", Object.keys(((c.diagnostics||{}).otel||{}).headers||{}));
console.log("captureContent:", !!((c.diagnostics||{}).otel||{}).captureContent);
console.log("timeoutSeconds:", ((c.agents||{}).defaults||{}).timeoutSeconds);'
dex sh -c 'echo "posthog.env   : $(test -f /sandbox/.secrets/posthog.env && echo present || echo MISSING)"; ls /sandbox/.openclaw/skills'
echo ">> done."
