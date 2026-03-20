"""Email client protocol defining the backend contract."""

from datetime import datetime
from typing import Any, Protocol


class EmailClient(Protocol):
    def send_message(
        self, to: str, subject: str, body: str, in_reply_to: str | None = None
    ) -> dict[str, str]:
        """Send email. Returns {"message_id": ..., "thread_id": ...}."""
        ...

    def list_messages(
        self, limit: int = 50, after: datetime | None = None
    ) -> list[dict[str, Any]]:
        """List recent messages. Returns list of dicts with at least 'id' and 'from' keys."""
        ...

    def get_message(self, message_id: str) -> dict[str, Any]:
        """Get full message. Returns normalized dict with message_id, thread_id, from, to, subject, text, html, timestamp."""
        ...

    def get_message_headers(self, message_id: str) -> dict[str, str]:
        """Get email headers as {name: value} dict. Used for Veris session extraction."""
        ...
