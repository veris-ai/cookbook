FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md uv.lock ./

RUN uv sync --frozen --no-dev

COPY src/ ./src/

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8088/ping || exit 1

ENV PORT=8088
CMD ["uv", "run", "python", "src/main.py"]
