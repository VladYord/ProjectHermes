"""Conversation memory — in-memory session history manager."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from hermes.logging import get_logger

logger = get_logger("memory")

_MAX_HISTORY = 20  # Default: keep last N messages per session


@dataclass
class Message:
    role: str  # "human" or "ai"
    content: str


@dataclass
class Session:
    session_id: str
    messages: list[Message] = field(default_factory=list)
    max_history: int = _MAX_HISTORY

    def add(self, role: str, content: str) -> None:
        self.messages.append(Message(role=role, content=content))
        # Trim to max history (keep pairs if possible)
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]

    def get_history(self) -> list[tuple[str, str]]:
        """Return history as list of (role, content) tuples."""
        return [(m.role, m.content) for m in self.messages]

    def clear(self) -> None:
        self.messages.clear()


class ConversationMemory:
    """In-memory conversation session manager.

    Stores message history per session ID. No persistence — sessions are lost
    on server restart (persistence planned for Phase 2).
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create_session(self, session_id: str | None = None) -> Session:
        """Get an existing session or create a new one."""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]

        sid = session_id or uuid.uuid4().hex[:12]
        session = Session(session_id=sid)
        self._sessions[sid] = session
        logger.debug("Created new session: %s", sid)
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID, or None if not found."""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if it existed."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[str]:
        """Return all active session IDs."""
        return list(self._sessions.keys())
