import asyncio
import logging
from pathlib import Path

from agents import Agent, Runner, SQLiteSession, set_default_openai_key
from pydantic import BaseModel

from app.agents.context import ProcurementContext
from app.config import get_settings
from app.email import get_email_client
from app.schemas import EmailWebhookPayload
from app.agents.policy_checker import check_policy
from app.agents.tools import oracle_connector, quote_tracker, send_email

logger = logging.getLogger(__name__)

set_default_openai_key(get_settings().openai_api_key)

_sessions: dict[str, SQLiteSession] = {}
_contexts: dict[str, ProcurementContext] = {}


def _get_session(thread_id: str) -> SQLiteSession:
    if thread_id not in _sessions:
        _sessions[thread_id] = SQLiteSession(session_id=thread_id, db_path=":memory:")
    return _sessions[thread_id]


def _get_context(thread_id: str, from_email: str) -> ProcurementContext:
    if thread_id not in _contexts:
        _contexts[thread_id] = ProcurementContext(
            thread_id=thread_id,
            from_email=from_email,
            original_requestor=from_email,
        )
    ctx = _contexts[thread_id]
    ctx.from_email = from_email
    return ctx


class EmailReply(BaseModel):
    to: str
    subject: str
    body: str
    in_reply_to: str | None = None


INSTRUCTION_FILE = Path("app/agents/instruction.md")
"""
The instruction file contains the system prompt that defines agent behavior.
Edit this file to customize how your agent responds to emails.
"""


def _load_instruction() -> str:
    return INSTRUCTION_FILE.read_text().strip()


def create_agent() -> Agent[ProcurementContext]:
    return Agent(
        name="procurement_agent",
        instructions=_load_instruction(),
        tools=[oracle_connector, quote_tracker, check_policy, send_email],
        output_type=EmailReply,
        model="gpt-4o",
    )


async def process_email(payload: EmailWebhookPayload) -> None:
    message = payload.message
    from_email = message.from_
    thread_id = message.thread_id
    subject = message.subject or "(no subject)"
    body = message.text or message.html or "(empty)"

    logger.info("Processing email from=%s, subject=%s, thread=%s", from_email, subject, thread_id)

    client = get_email_client()

    session = _get_session(thread_id)
    ctx = _get_context(thread_id, from_email)

    user_message = f"""Process this incoming email and send an appropriate reply.

From: {from_email}
Subject: {subject}
Message ID: {message.message_id}
Thread ID: {thread_id}

Email Body:
{body}
"""

    result = await Runner.run(create_agent(), user_message, context=ctx, session=session)
    reply: EmailReply = result.final_output

    await asyncio.to_thread(
        client.send_message,
        to=reply.to,
        subject=reply.subject,
        body=reply.body,
        in_reply_to=reply.in_reply_to,
    )

    logger.info("Sent reply to=%s, subject=%s", reply.to, reply.subject)
