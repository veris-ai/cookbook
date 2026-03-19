"""BCA Service — runs the agent pipeline for banker conversations."""

import json
import logging
import os
import tempfile

from app.config import get_settings

logger = logging.getLogger(__name__)

# Configure Google GenAI env vars BEFORE importing ADK
settings = get_settings()
if settings.google_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
elif settings.gcp_project:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
    os.environ["GOOGLE_CLOUD_PROJECT"] = settings.gcp_project
    os.environ["GOOGLE_CLOUD_LOCATION"] = settings.gcp_location

    # If SA key JSON is provided as a string, write it to a temp file
    # so ADC can pick it up via GOOGLE_APPLICATION_CREDENTIALS.
    if settings.gcp_service_account_json and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        sa_info = json.loads(settings.gcp_service_account_json)
        _sa_tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", prefix="gcp-sa-", delete=False,
        )
        json.dump(sa_info, _sa_tmpfile)
        _sa_tmpfile.flush()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _sa_tmpfile.name

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.services.agents.supervisor_agent import supervisor_agent

APP_NAME = "bca"

_session_service = InMemorySessionService()

_runner = Runner(
    agent=supervisor_agent,
    app_name=APP_NAME,
    session_service=_session_service,
)


async def get_or_create_session(session_id: str, state: dict | None = None):
    """Get an existing session or create a new one."""
    session = await _session_service.get_session(
        app_name=APP_NAME,
        user_id="banker",
        session_id=session_id,
    )
    if session is None:
        session = await _session_service.create_session(
            app_name=APP_NAME,
            user_id="banker",
            session_id=session_id,
            state=state or {},
        )
    return session


async def send_message(session_id: str, message: str) -> dict:
    """Send a message to the agent and return the final response.

    Args:
        session_id: Conversation session ID.
        message: The banker's message text.

    Returns:
        Dict with the agent's response text and metadata.
    """
    session = await get_or_create_session(session_id)

    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )

    final_text = ""
    final_author = ""

    async for event in _runner.run_async(
        user_id="banker",
        session_id=session.id,
        new_message=user_content,
    ):
        # Collect the final agent response text
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text = part.text
                    final_author = getattr(event, "author", "")

        # Log tool calls and responses
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    logger.info(f"[{session_id}] TOOL CALL: {fc.name}({fc.args})")
                if hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    resp_preview = str(fr.response)[:300]
                    logger.info(f"[{session_id}] TOOL RESPONSE: {fr.name} → {resp_preview}")

    # Determine action_required based on response content
    action_required = "none"
    if "[ESCALATE" in final_text:
        action_required = "escalated"
    elif "confirm" in final_text.lower() and "?" in final_text:
        action_required = "confirm_action"
    elif "?" in final_text:
        action_required = "provide_info"

    return {
        "content": final_text,
        "author": final_author,
        "action_required": action_required,
    }
