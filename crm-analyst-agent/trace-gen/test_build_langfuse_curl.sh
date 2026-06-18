#!/usr/bin/env bash
# Networkless unit test for build_langfuse_curl.sh. Deterministic via NOW_OVERRIDE.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

fail() { echo "FAIL: $1"; echo "  got:  $2"; echo "  want: $3"; exit 1; }

# Case 1: default 3-day window, default name filter.
OUT="$(LANGFUSE_HOST='https://us.cloud.langfuse.com' \
       LANGFUSE_PUBLIC_KEY='pk-lf-TEST' \
       LANGFUSE_SECRET_KEY='sk-lf-TEST' \
       LOOKBACK_DAYS='3' \
       NOW_OVERRIDE='2026-06-17T00:00:00Z' \
       bash "$DIR/build_langfuse_curl.sh")"
WANT="curl 'https://us.cloud.langfuse.com/api/public/traces?fromTimestamp=2026-06-14T00:00:00Z&toTimestamp=2026-06-17T00:00:00Z&name=openclaw.run&limit=100' -u 'pk-lf-TEST:sk-lf-TEST'"
[ "$OUT" = "$WANT" ] || fail "default window" "$OUT" "$WANT"

# Case 2: custom lookback + empty name filter drops the &name= clause.
OUT="$(LANGFUSE_HOST='https://us.cloud.langfuse.com/' \
       LANGFUSE_PUBLIC_KEY='pk' LANGFUSE_SECRET_KEY='sk' \
       LOOKBACK_DAYS='7' TRACE_NAME_FILTER='' LIMIT='50' \
       NOW_OVERRIDE='2026-06-17T12:00:00Z' \
       bash "$DIR/build_langfuse_curl.sh")"
WANT="curl 'https://us.cloud.langfuse.com/api/public/traces?fromTimestamp=2026-06-10T12:00:00Z&toTimestamp=2026-06-17T12:00:00Z&limit=50' -u 'pk:sk'"
[ "$OUT" = "$WANT" ] || fail "no-name 7d" "$OUT" "$WANT"

# Case 3: missing required env fails loudly (non-zero exit).
if LANGFUSE_PUBLIC_KEY='pk' LANGFUSE_SECRET_KEY='sk' bash "$DIR/build_langfuse_curl.sh" 2>/dev/null; then
  echo "FAIL: expected non-zero exit when LANGFUSE_HOST unset"; exit 1
fi

echo "PASS (3 cases)"
