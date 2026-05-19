"""HolmesGPT PagerDuty agent — investigate one incident per turn."""

import logging
from typing import AsyncGenerator, Optional

import anyio
from pydantic import BaseModel, Field

from .investigator import (
    build_config,
    build_source,
    investigate,
    make_toolcalling_llm,
    parse_incident_id,
    pick_incident,
)

logger = logging.getLogger(__name__)


class StreamEventMessage(BaseModel):
    type: str = Field(
        ...,
        description="Type of event: 'message', 'tool_call', 'tool_output', 'done', 'error'",
    )
    content: str = Field(default="")
    metadata: dict = Field(default_factory=dict)


async def process_chat_streaming(message: str) -> AsyncGenerator[StreamEventMessage, None]:
    """One investigation per message — terminal action is the PagerDuty note write-back."""
    logger.info("Processing message: %s", message[:120])

    try:
        config = build_config()
    except Exception as e:
        yield StreamEventMessage(type="error", content=str(e))
        return

    incident_id: Optional[str] = parse_incident_id(message)

    yield StreamEventMessage(
        type="tool_call",
        content=("Fetching incident " + incident_id) if incident_id else "Listing open incidents",
        metadata={"tool_name": "pagerduty.fetch", "incident_id": incident_id or ""},
    )

    source = build_source(config, incident_key=None)
    try:
        issue = await anyio.to_thread.run_sync(pick_incident, source, incident_id)
    except Exception as e:
        logger.exception("PagerDuty fetch failed")
        yield StreamEventMessage(type="error", content=f"PagerDuty fetch failed: {e}")
        return

    if issue is None:
        yield StreamEventMessage(
            type="message",
            content="No open PagerDuty incidents found.",
        )
        yield StreamEventMessage(type="done", content="no_incident")
        return

    yield StreamEventMessage(
        type="tool_output",
        content=f"Found incident {issue.id}: {issue.name}",
        metadata={"incident_id": issue.id, "url": issue.url},
    )

    yield StreamEventMessage(
        type="tool_call",
        content="Running HolmesGPT investigation",
        metadata={"tool_name": "holmes.investigate"},
    )

    try:
        ai = await anyio.to_thread.run_sync(make_toolcalling_llm, config)
        result = await anyio.to_thread.run_sync(investigate, ai, issue, config)
    except Exception as e:
        logger.exception("Investigation failed")
        yield StreamEventMessage(type="error", content=f"Investigation failed: {e}")
        return

    analysis = result.result or "(no analysis produced)"
    yield StreamEventMessage(
        type="message",
        content=analysis,
        metadata={"incident_id": issue.id},
    )

    yield StreamEventMessage(
        type="tool_call",
        content=f"Writing analysis note to incident {issue.id}",
        metadata={"tool_name": "pagerduty.write_back"},
    )
    try:
        await anyio.to_thread.run_sync(source.write_back_result, issue.id, result)
    except Exception as e:
        logger.exception("Write-back failed")
        yield StreamEventMessage(type="error", content=f"Write-back failed: {e}")
        return

    yield StreamEventMessage(
        type="done",
        content=f"Wrote analysis note to {issue.id}",
        metadata={"incident_id": issue.id, "analysis": analysis},
    )
