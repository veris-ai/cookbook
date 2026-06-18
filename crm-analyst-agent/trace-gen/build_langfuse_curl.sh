#!/usr/bin/env bash
# Build a time-ranged Langfuse /api/public/traces curl for
# `veris scenarios create --from-langfuse -`. Prints the curl to stdout.
# No network, no disk. Timestamp math in python3 for Mac+Linux portability.
set -euo pipefail

: "${LANGFUSE_HOST:?set LANGFUSE_HOST}"
: "${LANGFUSE_PUBLIC_KEY:?set LANGFUSE_PUBLIC_KEY}"
: "${LANGFUSE_SECRET_KEY:?set LANGFUSE_SECRET_KEY}"
LOOKBACK_DAYS="${LOOKBACK_DAYS:-3}"
TRACE_NAME_FILTER="${TRACE_NAME_FILTER-openclaw.run}"
LIMIT="${LIMIT:-100}"

read -r FROM TO < <(python3 - "$LOOKBACK_DAYS" "${NOW_OVERRIDE:-}" <<'PY'
import sys, datetime
days = int(sys.argv[1])
now_arg = sys.argv[2]
if now_arg:
    now = datetime.datetime.fromisoformat(now_arg.replace("Z", "+00:00"))
else:
    now = datetime.datetime.now(datetime.timezone.utc)
frm = now - datetime.timedelta(days=days)
fmt = "%Y-%m-%dT%H:%M:%SZ"
print(frm.strftime(fmt), now.strftime(fmt))
PY
)

name_q=""
[ -n "$TRACE_NAME_FILTER" ] && name_q="&name=${TRACE_NAME_FILTER}"
url="${LANGFUSE_HOST%/}/api/public/traces?fromTimestamp=${FROM}&toTimestamp=${TO}${name_q}&limit=${LIMIT}"

printf "curl '%s' -u '%s:%s'\n" "$url" "$LANGFUSE_PUBLIC_KEY" "$LANGFUSE_SECRET_KEY"
