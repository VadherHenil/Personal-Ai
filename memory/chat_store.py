"""SQLite-backed chat sessions, messages, and safe continuation helpers."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
CHAT_DB_PATH = BASE_DIR / "memory" / "chat_history.sqlite3"
_DB_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    CHAT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(CHAT_DB_PATH), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def _database():
    connection = _connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize() -> None:
    with _DB_LOCK, _database() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT 'New conversation',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'general',
                pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1))
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                metadata TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user_updated
                ON sessions(user_id, pinned DESC, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_session_time
                ON messages(session_id, timestamp);
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                message_id UNINDEXED, session_id UNINDEXED, user_id UNINDEXED,
                content
            );
            """
        )
        db.execute(
            """
            INSERT INTO messages_fts (message_id, session_id, user_id, content)
            SELECT m.id, m.session_id, s.user_id, m.content
            FROM messages m JOIN sessions s ON s.id = m.session_id
            WHERE NOT EXISTS (SELECT 1 FROM messages_fts f WHERE f.message_id = m.id)
            """
        )


def _row_session(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["pinned"] = bool(item["pinned"])
    return item


def create_session(
    user_id: str,
    title: str = "New conversation",
    category: str = "general",
) -> str:
    initialize()
    session_id = uuid.uuid4().hex
    now = _now()
    with _DB_LOCK, _database() as db:
        db.execute(
            "INSERT INTO sessions (id, user_id, title, created_at, updated_at, category) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, user_id, (title or "New conversation")[:160], now, now, category[:80]),
        )
    return session_id


def ensure_session(user_id: str, session_id: str | None = None) -> str:
    initialize()
    if session_id:
        with _DB_LOCK, _database() as db:
            row = db.execute(
                "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if row:
                return session_id
    return create_session(user_id)


def append_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    tokens_used: int = 0,
    metadata: dict[str, Any] | None = None,
) -> str:
    initialize()
    if role not in {"system", "user", "assistant", "tool"}:
        raise ValueError("Unsupported message role")
    message_id = uuid.uuid4().hex
    now = _now()
    with _DB_LOCK, _database() as db:
        owned = db.execute(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not owned:
            raise PermissionError("Session does not belong to the authenticated user")
        db.execute(
            "INSERT INTO messages (id, session_id, role, content, timestamp, tokens_used, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (message_id, session_id, role, content, now, max(0, int(tokens_used)), json.dumps(metadata or {}, ensure_ascii=False)),
        )
        db.execute(
            "INSERT INTO messages_fts (message_id, session_id, user_id, content) SELECT ?, ?, user_id, ? FROM sessions WHERE id = ?",
            (message_id, session_id, content, session_id),
        )
        db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    return message_id


def list_sessions(user_id: str, query: str = "", limit: int = 100) -> list[dict[str, Any]]:
    initialize()
    query = (query or "").strip()
    like = f"%{query}%"
    with _DB_LOCK, _database() as db:
        rows = db.execute(
            """
            SELECT DISTINCT s.*
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            WHERE s.user_id = ?
              AND (? = '' OR s.title LIKE ? OR s.summary LIKE ? OR m.content LIKE ?)
            ORDER BY s.pinned DESC, s.updated_at DESC
            LIMIT ?
            """,
            (user_id, query, like, like, like, max(1, min(int(limit), 500))),
        ).fetchall()
    return [_row_session(row) for row in rows]


def search_conversations(
    user_id: str,
    query: str,
    *,
    category: str = "",
    role: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Search owned messages with FTS5 and optional metadata filters."""
    initialize()
    query = " ".join(part for part in str(query or "").split() if part.replace("_", "").isalnum())
    if not query:
        return []
    clauses = ["f.user_id = ?", "f.content MATCH ?"]
    values: list[Any] = [user_id, query]
    if category:
        clauses.append("s.category = ?")
        values.append(category[:80])
    if role in {"system", "user", "assistant", "tool"}:
        clauses.append("m.role = ?")
        values.append(role)
    if date_from:
        clauses.append("m.timestamp >= ?")
        values.append(date_from)
    if date_to:
        clauses.append("m.timestamp <= ?")
        values.append(date_to)
    values.append(max(1, min(int(limit), 500)))
    with _DB_LOCK, _database() as db:
        rows = db.execute(
            f"""
            SELECT m.id, m.session_id, s.title, s.category, m.role,
                   snippet(messages_fts, 3, '<mark>', '</mark>', '...', 18) AS snippet,
                   m.timestamp
            FROM messages_fts f
            JOIN messages m ON m.id = f.message_id
            JOIN sessions s ON s.id = m.session_id
            WHERE {' AND '.join(clauses)}
            ORDER BY m.timestamp DESC LIMIT ?
            """,
            values,
        ).fetchall()
    return [dict(row) for row in rows]


def get_session(session_id: str, user_id: str, include_messages: bool = True) -> dict[str, Any] | None:
    initialize()
    with _DB_LOCK, _database() as db:
        row = db.execute(
            "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not row:
            return None
        result = _row_session(row)
        if include_messages:
            messages = db.execute(
                "SELECT id, role, content, timestamp, tokens_used, metadata FROM messages WHERE session_id = ? ORDER BY timestamp, rowid",
                (session_id,),
            ).fetchall()
            result["messages"] = []
            for message in messages:
                item = dict(message)
                try:
                    item["metadata"] = json.loads(item["metadata"] or "{}")
                except json.JSONDecodeError:
                    item["metadata"] = {}
                result["messages"].append(item)
        return result


def update_session(
    session_id: str,
    user_id: str,
    *,
    title: str | None = None,
    pinned: bool | None = None,
    category: str | None = None,
    summary: str | None = None,
) -> bool:
    initialize()
    updates: list[str] = []
    values: list[Any] = []
    for column, value in (("title", title), ("pinned", pinned), ("category", category), ("summary", summary)):
        if value is not None:
            updates.append(f"{column} = ?")
            values.append(int(value) if column == "pinned" else str(value)[:4000])
    if not updates:
        return False
    updates.append("updated_at = ?")
    values.extend([_now(), session_id, user_id])
    with _DB_LOCK, _database() as db:
        cursor = db.execute(
            f"UPDATE sessions SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
            values,
        )
    return cursor.rowcount == 1


def update_message(message_id: str, user_id: str, content: str) -> bool:
    """Replace a message owned by the user and remove its later continuation."""
    initialize()
    content = str(content).strip()
    if not content:
        return False
    now = _now()
    with _DB_LOCK, _database() as db:
        message = db.execute(
            """
            SELECT m.session_id, m.timestamp, m.rowid
            FROM messages m JOIN sessions s ON s.id = m.session_id
            WHERE m.id = ? AND s.user_id = ? AND m.role = 'user'
            """,
            (message_id, user_id),
        ).fetchone()
        if not message:
            return False
        db.execute(
            """
            DELETE FROM messages
            WHERE session_id = ? AND (timestamp > ? OR (timestamp = ? AND rowid > ?))
            """,
            (message["session_id"], message["timestamp"], message["timestamp"], message["rowid"]),
        )
        db.execute("UPDATE messages SET content = ?, timestamp = ? WHERE id = ?", (content, now, message_id))
        db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, message["session_id"]))
    return True


def prepare_regeneration(message_id: str, user_id: str) -> tuple[str, str] | None:
    """Remove an assistant reply and return its preceding user prompt."""
    initialize()
    with _DB_LOCK, _database() as db:
        target = db.execute(
            """
            SELECT m.session_id, m.timestamp, m.rowid
            FROM messages m JOIN sessions s ON s.id = m.session_id
            WHERE m.id = ? AND s.user_id = ? AND m.role = 'assistant'
            """,
            (message_id, user_id),
        ).fetchone()
        if not target:
            return None
        prompt = db.execute(
            """
            SELECT content FROM messages
            WHERE session_id = ? AND role = 'user'
              AND (timestamp < ? OR (timestamp = ? AND rowid < ?))
            ORDER BY timestamp DESC, rowid DESC LIMIT 1
            """,
            (target["session_id"], target["timestamp"], target["timestamp"], target["rowid"]),
        ).fetchone()
        if not prompt:
            return None
        db.execute(
            "DELETE FROM messages WHERE session_id = ? AND (timestamp > ? OR (timestamp = ? AND rowid >= ?))",
            (target["session_id"], target["timestamp"], target["timestamp"], target["rowid"]),
        )
        db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), target["session_id"]))
    return target["session_id"], prompt["content"]


def fork_session(session_id: str, user_id: str) -> str:
    """Create an independent copy of the entire owned conversation."""
    initialize()
    with _DB_LOCK, _database() as db:
        source = db.execute(
            "SELECT * FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id)
        ).fetchone()
        if not source:
            raise PermissionError("Session does not belong to the authenticated user")
        new_id = uuid.uuid4().hex
        now = _now()
        db.execute(
            """
            INSERT INTO sessions (id, user_id, title, created_at, updated_at, summary, category, pinned)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (new_id, user_id, f"Fork of {source['title']}"[:160], now, now, source["summary"], source["category"]),
        )
        copied = db.execute(
            "SELECT role, content, timestamp, tokens_used, metadata FROM messages WHERE session_id = ? ORDER BY timestamp, rowid",
            (session_id,),
        ).fetchall()
        db.executemany(
            "INSERT INTO messages (id, session_id, role, content, timestamp, tokens_used, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(uuid.uuid4().hex, new_id, row["role"], row["content"], row["timestamp"], row["tokens_used"], row["metadata"]) for row in copied],
        )
    return new_id


def delete_session(session_id: str, user_id: str) -> bool:
    initialize()
    with _DB_LOCK, _database() as db:
        cursor = db.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
    return cursor.rowcount == 1


def branch_session(session_id: str, message_id: str, user_id: str) -> str:
    """Fork a session at a message while enforcing ownership on both records."""
    initialize()
    with _DB_LOCK, _database() as db:
        source = db.execute(
            "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not source:
            raise PermissionError("Session does not belong to the authenticated user")
        cutoff = db.execute(
            "SELECT timestamp, rowid FROM messages WHERE id = ? AND session_id = ?",
            (message_id, session_id),
        ).fetchone()
        if not cutoff:
            raise ValueError("Message does not belong to the session")
        new_id = uuid.uuid4().hex
        now = _now()
        db.execute(
            "INSERT INTO sessions (id, user_id, title, created_at, updated_at, summary, category, pinned) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (new_id, user_id, f"Branch of {source['title']}"[:160], now, now, source["summary"], source["category"]),
        )
        copied = db.execute(
            """
            SELECT role, content, timestamp, tokens_used, metadata
            FROM messages
            WHERE session_id = ? AND (timestamp < ? OR (timestamp = ? AND rowid <= ?))
            ORDER BY timestamp, rowid
            """,
            (session_id, cutoff["timestamp"], cutoff["timestamp"], cutoff["rowid"]),
        ).fetchall()
        db.executemany(
            "INSERT INTO messages (id, session_id, role, content, timestamp, tokens_used, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (uuid.uuid4().hex, new_id, row["role"], row["content"], row["timestamp"], row["tokens_used"], row["metadata"])
                for row in copied
            ],
        )
    return new_id


def group_sessions_by_timeframe(sessions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    today = datetime.now().date()
    groups = {"Today": [], "Yesterday": [], "Previous 7 Days": [], "Previous 30 Days": [], "Older History": []}
    for session in sessions:
        try:
            date = datetime.fromisoformat(session["updated_at"]).date()
        except (KeyError, ValueError):
            groups["Older History"].append(session)
            continue
        age = (today - date).days
        group = (
            "Today" if age == 0 else "Yesterday" if age == 1
            else "Previous 7 Days" if age <= 7
            else "Previous 30 Days" if age <= 30
            else "Older History"
        )
        groups[group].append(session)
    return groups
