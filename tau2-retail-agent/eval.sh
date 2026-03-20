#!/bin/bash
set -e

ITER_DIR=${1:?Usage: eval.sh <iter-dir>}

SNAPSHOT=$(mktemp -d)
cp agent_desc.txt "$SNAPSHOT/agent_desc.txt"
trap "rm -rf $SNAPSHOT" EXIT

echo "=== tau2-bench Retail Evaluation ==="

AGENT_DESC_PATH="$SNAPSHOT/agent_desc.txt" \
uv run python scripts/run_tau2.py \
  --task-split-name test \
  --agent-llm gpt-5-mini \
  --user-llm gpt-5-mini \
  --num-trials 1 \
  --max-concurrency 10 \
  --save-to "ralph_$(basename "$(dirname "$ITER_DIR")")_iter_$(basename "$ITER_DIR")"
