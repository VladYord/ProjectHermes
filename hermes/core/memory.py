"""Conversation memory — session history with optional SQLite persistence.

When the environment variable ``HERMES_PACKAGED=1`` is set (Tauri sidecar
mode) sessions are written through to ``{app_data_dir}/sessions.db`` so they
survive server restarts.  In development / tests the in-memory store is used
exclusively, keeping tests fast and stateless.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from hermes.log_setup import get_logger

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


# ---------------------------------------------------------------------------
# SQLite-backed session (used only when HERMES_PACKAGED=1)
# ---------------------------------------------------------------------------

class _SQLiteSession(Session):
    """Session that writes through to SQLite on every mutation."""

    def __init__(self, session_id: str, db: sqlite3.Connection) -> None:
        super().__init__(session_id=session_id)
        self._db = db

    def add(self, role: str, content: str) -> None:
        super().add(role, content)
        self._sync_to_db()

    def clear(self) -> None:
        super().clear()
        self._db.execute(
            "DELETE FROM sessions WHERE session_id = ?", (self.session_id,)
        )
        self._db.commit()

    def _sync_to_db(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            "DELETE FROM sessions WHERE session_id = ?", (self.session_id,)
        )
        self._db.executemany(
            "INSERT INTO sessions (session_id, message_index, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (self.session_id, i, m.role, m.content, now)
                for i, m in enumerate(self.messages)
            ],
        )
        self._db.commit()


# ---------------------------------------------------------------------------
# ConversationMemory
# ---------------------------------------------------------------------------

class ConversationMemory:
    """In-memory conversation session manager with optional SQLite persistence.

    - Development / tests (``HERMES_PACKAGED`` not set): pure in-memory, no I/O.
    - Packaged desktop app (``HERMES_PACKAGED=1``): sessions written through to
      ``sessions.db`` in the OS app-data directory and reloaded on startup.
    """

    _CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id    TEXT    NOT NULL,
            message_index INTEGER NOT NULL,
            role          TEXT    NOT NULL,
            content       TEXT    NOT NULL,
            created_at    TEXT    NOT NULL,
            PRIMARY KEY (session_id, message_index)
        )
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._db: sqlite3.Connection | None = None

        if os.environ.get("HERMES_PACKAGED") == "1":
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        from hermes.config_manager import get_app_data_dir
        db_path = get_app_data_dir() / "sessions.db"
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.execute(self._CREATE_TABLE)
        self._db.commit()
        self._load_from_sqlite()
        logger.info("SQLite session store opened: %s", db_path)

    def _load_from_sqlite(self) -> None:
        rows = self._db.execute(
            "SELECT session_id, role, content "
            "FROM sessions ORDER BY session_id, message_index"
        ).fetchall()
        for session_id, role, content in rows:
            if session_id not in self._sessions:
                self._sessions[session_id] = _SQLiteSession(session_id, self._db)
            self._sessions[session_id].messages.append(Message(role=role, content=content))
        logger.info("Loaded %d sessions from SQLite", len(self._sessions))

    def get_or_create_session(self, session_id: str | None = None) -> Session:
        """Get an existing session or create a new one."""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]

        sid = session_id or uuid.uuid4().hex[:12]
        session: Session = (
            _SQLiteSession(session_id=sid, db=self._db)
            if self._db is not None
            else Session(session_id=sid)
        )
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
            if self._db is not None:
                self._db.execute(
                    "DELETE FROM sessions WHERE session_id = ?", (session_id,)
                )
                self._db.commit()
            return True
        return False

    def list_sessions(self) -> list[str]:
        """Return all active session IDs."""
        return list(self._sessions.keys())
