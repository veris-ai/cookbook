import asyncio
import logging
import uuid
from datetime import datetime, timezone

from app.config import get_settings
from app.email import get_email_client
from app.schemas import EmailMessage, EmailWebhookPayload

logger = logging.getLogger(__name__)

_poller_task: asyncio.Task | None = None


async def _poll_loop() -> None:
    settings = get_settings()
    inbox_id = settings.email_inbox_id
    interval = settings.email_poll_interval

    if not inbox_id:
        logger.error("[Poller] Inbox ID not set, cannot poll")
        return

    client = get_email_client()
    last_timestamp: datetime = datetime.now(timezone.utc)
    processed_ids: set[str] = set()

    logger.info("[Poller] Started polling %s every %ds", inbox_id, interval)

    from app.agents.procurement_agent import process_email

    while True:
        try:
            stubs = await asyncio.to_thread(
                client.list_messages, limit=50, after=last_timestamp
            )

            for stub in stubs:
                msg_id = stub["id"]

                # Skip outbound messages
                if inbox_id in (stub.get("from") or ""):
                    continue
                if msg_id in processed_ids:
                    continue

                full_msg = await asyncio.to_thread(client.get_message, msg_id)

                payload = EmailWebhookPayload(
                    event_type="message.received",
                    event_id=str(uuid.uuid4()),
                    message=EmailMessage(
                        message_id=full_msg["message_id"],
                        thread_id=full_msg["thread_id"],
                        inbox_id=inbox_id,
                        to=full_msg["to"] if isinstance(full_msg["to"], list) else [full_msg["to"]],
                        subject=full_msg["subject"],
                        text=full_msg.get("text"),
                        html=full_msg.get("html"),
                        **{"from": full_msg["from"]},
                    ),
                )

                logger.info(
                    "[Poller] New email from=%s subject=%s",
                    full_msg["from"],
                    full_msg["subject"],
                )
                processed_ids.add(msg_id)

                ts = full_msg.get("timestamp")
                if ts is not None:
                    last_timestamp = ts if isinstance(ts, datetime) else datetime.now(timezone.utc)

                await process_email(payload)

        except Exception as e:
            logger.error("[Poller] Error: %s", e)

        await asyncio.sleep(interval)


def start_poller() -> None:
    global _poller_task
    settings = get_settings()
    # Skip polling if agent uses webhook mode
    if settings.email_webhook_url:
        return
    if settings.email_poll_interval <= 0:
        return
    _poller_task = asyncio.create_task(_poll_loop())


def stop_poller() -> None:
    global _poller_task
    if _poller_task:
        _poller_task.cancel()
        _poller_task = None
