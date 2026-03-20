#!/bin/bash
set -e

export PORT="${PORT:-8080}"
uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
