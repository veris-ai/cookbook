"""In-memory async session management compatible with OpenAI Agents."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field
from agents.items import TResponseInputItem

# from .agent_setup.workflow import BCSRunContext

class BCSRunContext(BaseModel):
    """Per-run context for capturing tool calls and structured outputs."""

    tool_calls: List[Dict] = Field(default_factory=list)
    data: Dict = Field(default_factory=dict)

    # For strict tool schemas in OpenAI Agents SDK
    model_config = {"extra": "forbid"}


class _InMemoryAgentSession:
    """Adapter that fulfils the Agents SDK ``Session`` protocol."""

    def __init__(self, state: "SessionState") -> None:
        self._state = state

    @property
    def session_id(self) -> str:
        return self._state.session_id

    async def get_items(self, limit: int | None = None) -> List[TResponseInputItem]:
        async with self._state.memory_lock:
            items = list(self._state.items)
        if limit is None or limit >= len(items):
            return items
        return items[-limit:]

    async def add_items(self, items: List[TResponseInputItem]) -> None:
        if not items:
            return
        async with self._state.memory_lock:
            self._state.items.extend(items)
        self._state.touch()

    async def pop_item(self) -> TResponseInputItem | None:
        async with self._state.memory_lock:
            if not self._state.items:
                return None
            item = self._state.items.pop()
        self._state.touch()
        return item

    async def clear_session(self) -> None:
        async with self._state.memory_lock:
            self._state.items.clear()


@dataclass
class SessionState:
    """Container for a single chat session."""

    session_id: str
    run_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_active: datetime = field(default_factory=datetime.utcnow)
    items: List[TResponseInputItem] = field(default_factory=list)
    memory_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    context: BCSRunContext = field(default_factory=BCSRunContext)
    _agent_session: _InMemoryAgentSession = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._agent_session = _InMemoryAgentSession(self)

    @property
    def agent_session(self) -> _InMemoryAgentSession:
        return self._agent_session

    def touch(self) -> None:
        """Update last-active timestamp when the session is used."""

        self.last_active = datetime.utcnow()


class SessionManager:
    """Manage chat sessions for FastAPI endpoints."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def get_session(self, session_id: Optional[str] = None) -> SessionState:
        """Return an existing session or create a new one."""

        if session_id is None:
            session_id = uuid4().hex
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = SessionState(session_id=session_id)
                self._sessions[session_id] = session
            session.touch()
            return session

    async def remove_session(self, session_id: str) -> None:
        """Remove a session, allowing clients to opt out early."""

        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.agent_session.clear_session()

    async def close(self) -> None:
        """Best-effort cleanup hook for FastAPI lifespan events."""

        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            await session.agent_session.clear_session()


__all__ = ["SessionManager", "SessionState"]
