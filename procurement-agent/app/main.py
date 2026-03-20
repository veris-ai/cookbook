"""FastAPI application with configurable email backend."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from app.config import get_settings
from app.email_poller import start_poller, stop_poller


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_poller()
    yield
    stop_poller()


app = FastAPI(
    title="Procurement Agent",
    description="IT procurement sourcing & negotiation agent with Oracle Fusion Cloud ERP",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Webhook endpoint — only active when EMAIL_WEBHOOK_URL is set
_settings = get_settings()
if _settings.email_webhook_url:
    from app.agents.procurement_agent import process_email
    from app.schemas import EmailWebhookPayload

    _background_tasks: set[asyncio.Task] = set()

    @app.post("/webhooks/email", status_code=200)
    async def email_webhook(payload: EmailWebhookPayload) -> dict:
        task = asyncio.create_task(process_email(payload))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True}
