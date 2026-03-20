"""Gmail email backend."""

import base64
from datetime import datetime
from email.mime.text import MIMEText
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GmailClient:
    def __init__(self, user_id: str):
        self._user_id = user_id
        creds = Credentials(token="mock")
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def send_message(
        self, to: str, subject: str, body: str, in_reply_to: str | None = None
    ) -> dict[str, str]:
        msg = MIMEText(body, "plain")
        msg["To"] = to
        msg["Subject"] = subject
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        result = (
            self._service.users()
            .messages()
            .send(userId=self._user_id, body={"raw": raw})
            .execute()
        )
        return {
            "message_id": result.get("id", ""),
            "thread_id": result.get("threadId", ""),
        }

    def list_messages(
        self, limit: int = 50, after: datetime | None = None
    ) -> list[dict[str, Any]]:
        result = (
            self._service.users()
            .messages()
            .list(userId=self._user_id, maxResults=limit)
            .execute()
        )
        return [
            {"id": m["id"], "from": None, "timestamp": None}
            for m in result.get("messages", [])
        ]

    def get_message(self, message_id: str) -> dict[str, Any]:
        raw = (
            self._service.users()
            .messages()
            .get(userId=self._user_id, id=message_id)
            .execute()
        )
        headers = {
            h["name"].lower(): h["value"]
            for h in raw.get("payload", {}).get("headers", [])
        }

        body_data = raw.get("payload", {}).get("body", {}).get("data", "")
        if body_data:
            padded = body_data + "=" * (-len(body_data) % 4)
            text = base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
        else:
            text = ""

        return {
            "message_id": raw.get("id", ""),
            "thread_id": raw.get("threadId", ""),
            "from": headers.get("from", ""),
            "to": [a.strip() for a in headers.get("to", "").split(",") if a.strip()],
            "subject": headers.get("subject", ""),
            "text": text,
            "html": None,
            "timestamp": raw.get("internalDate"),
        }

    def get_message_headers(self, message_id: str) -> dict[str, str]:
        raw = (
            self._service.users()
            .messages()
            .get(userId=self._user_id, id=message_id, format="metadata")
            .execute()
        )
        return {
            h["name"]: h["value"]
            for h in raw.get("payload", {}).get("headers", [])
        }
