"""Agent Service — runs the ADK agent pipeline for PM conversations."""

import logging
import os
from collections.abc import AsyncIterator

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

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.services.agents.pm_agent import pm_agent

APP_NAME = "pm-analyst"

_session_service = InMemorySessionService()

_runner = Runner(
    agent=pm_agent,
    app_name=APP_NAME,
    session_service=_session_service,
)

# Tools whose results should be sent as interactive select components
_INTERACTIVE_TOOLS = {
    "list_recent_meetings": "meeting",
    "list_onedrive_files": "file",
}


def _build_select_message(tool_name: str, tool_result: dict) -> dict | None:
    """Convert a tool result into a structured select message for the frontend."""
    select_type = _INTERACTIVE_TOOLS.get(tool_name)
    if not select_type:
        return None

    if select_type == "meeting":
        items = tool_result.get("meetings", [])
        return {
            "type": "select",
            "select_type": "meeting",
            "prompt": "Select a meeting to pull the transcript from:",
            "items": [
                {
                    "id": m["id"],
                    "label": m["subject"],
                    "description": m.get("start", ""),
                }
                for m in items
            ],
        }

    if select_type == "file":
        items = tool_result.get("items", [])
        return {
            "type": "select",
            "select_type": "file",
            "prompt": f"Contents of {tool_result.get('folder', '/')}:",
            "items": [
                {
                    "id": item["id"],
                    "label": item["name"],
                    "description": item.get("mime_type", item["type"]),
                    "item_type": item["type"],
                }
                for item in items
            ],
        }

    return None


async def get_or_create_session(session_id: str, state: dict | None = None):
    session = await _session_service.get_session(
        app_name=APP_NAME,
        user_id="pm",
        session_id=session_id,
    )
    if session is None:
        session = await _session_service.create_session(
            app_name=APP_NAME,
            user_id="pm",
            session_id=session_id,
            state=state or {},
        )
    return session


async def send_message(session_id: str, message: str) -> AsyncIterator[dict]:
    """Send a message to the agent and yield response messages.

    Yields structured messages:
    - {"type": "agent", "content": "...", "author": "..."} for text responses
    - {"type": "select", "select_type": "meeting"|"file", "items": [...]} for
      interactive selection prompts
    """
    session = await get_or_create_session(session_id)

    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )

    final_text = ""
    final_author = ""

    async for event in _runner.run_async(
        user_id="pm",
        session_id=session.id,
        new_message=user_content,
    ):
        if not event.content or not event.content.parts:
            continue

        for part in event.content.parts:
            if hasattr(part, "function_response") and part.function_response and not os.environ.get("SIMULATION_ID"):
                fn_name = part.function_response.name
                fn_result = part.function_response.response
                if fn_name in _INTERACTIVE_TOOLS and isinstance(fn_result, dict):
                    select_msg = _build_select_message(fn_name, fn_result)
                    if select_msg:
                        yield select_msg

            # Track the latest text for the final agent message
            if hasattr(part, "text") and part.text:
                final_text = part.text
                final_author = getattr(event, "author", "")

    if final_text:
        yield {
            "type": "agent",
            "content": final_text,
            "author": final_author,
        }
