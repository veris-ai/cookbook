"""AgentMail email backend."""

from datetime import datetime
from email import message_from_bytes
from typing import Any

from agentmail import AgentMail


class AgentMailClient:
    def __init__(self, api_key: str, inbox_id: str):
        self._client = AgentMail(api_key=api_key)
        self._inbox_id = inbox_id

    def send_message(
        self, to: str, subject: str, body: str, in_reply_to: str | None = None
    ) -> dict[str, str]:
        headers = {"In-Reply-To": in_reply_to} if in_reply_to else None
        result = self._client.inboxes.messages.send(
            inbox_id=self._inbox_id,
            to=to,
            subject=subject,
            text=body,
            headers=headers,
        )
        return {"message_id": result.message_id, "thread_id": result.thread_id}

    def list_messages(
        self, limit: int = 50, after: datetime | None = None
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "inbox_id": self._inbox_id,
            "limit": limit,
            "ascending": True,
        }
        if after is not None:
            kwargs["after"] = after

        result = self._client.inboxes.messages.list(**kwargs)
        return [
            {
                "id": m.message_id,
                "from": m.from_,
                "timestamp": m.timestamp,
            }
            for m in result.messages
        ]

    def get_message(self, message_id: str) -> dict[str, Any]:
        msg = self._client.inboxes.messages.get(
            inbox_id=self._inbox_id,
            message_id=message_id,
        )
        return {
            "message_id": msg.message_id,
            "thread_id": msg.thread_id,
            "from": msg.from_,
            "to": msg.to or [],
            "subject": msg.subject or "",
            "text": msg.text,
            "html": msg.html,
            "timestamp": msg.timestamp,
        }

    def get_message_headers(self, message_id: str) -> dict[str, str]:
        raw_gen = self._client.inboxes.messages.get_raw(
            inbox_id=self._inbox_id,
            message_id=message_id,
        )
        raw_bytes = b"".join(raw_gen)
        email_msg = message_from_bytes(raw_bytes)
        return {k: v for k, v in email_msg.items()}
