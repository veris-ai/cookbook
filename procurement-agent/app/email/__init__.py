"""Configurable email backend. Set EMAIL_BACKEND env var to 'agentmail' or 'gmail'."""

from functools import lru_cache

from app.email.base import EmailClient


@lru_cache
def get_email_client() -> EmailClient:
    from app.config import get_settings

    settings = get_settings()
    if settings.email_backend == "gmail":
        from app.email.gmail_backend import GmailClient

        return GmailClient(user_id=settings.email_inbox_id)
    else:
        from app.email.agentmail_backend import AgentMailClient

        return AgentMailClient(
            api_key=settings.agentmail_api_key,
            inbox_id=settings.email_inbox_id,
        )


__all__ = ["EmailClient", "get_email_client"]
