"""Persistent, user-controlled distilled memory for the assistant."""

from __future__ import annotations

import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from security.controls import redact_sensitive

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DB_PATH = BASE_DIR / "memory" / "chat_history.sqlite3"
_LOCK = threading.RLock()
CATEGORIES = frozenset({"USER_PREFERENCES", "TECH_STACK", "PROJECT_CONTEXT", "CORRECTION_HABITS", "TASKS", "NOTES"})

_PATTERNS = (
    ("USER_PREFERENCES", re.compile(r"\b(?:i\s+prefer|i\s+like|i\s+love|my\s+preference\s+is)\s+(.+?)[.!?]?$", re.I)),
    ("TECH_STACK", re.compile(r"\b(?:i\s+(?:use|am\s+using|work\s+with)|my\s+(?:stack|tools?)\s+(?:is|are))\s+(.+?)[.!?]?$", re.I)),
    ("PROJECT_CONTEXT", re.compile(r"\b(?:i\s+am\s+building|i['’]?m\s+building|this\s+project\s+is)\s+(.+?)[.!?]?$", re.I)),
    ("CORRECTION_HABITS", re.compile(r"\b(?:i\s+(?:dislike|hate)|please\s+don['’]?t|don['’]?t)\s+(.+?)[.!?]?$", re.I)),
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def _db():
    MEMORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(MEMORY_DB_PATH), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize() -> None:
    with _LOCK, _db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                fact TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.7,
                source_session_id TEXT,
                expires_at TEXT,
                last_accessed_at TEXT NOT NULL,
                UNIQUE(user_id, category, fact)
            )
            """
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(user_memories)").fetchall()}
        if "expires_at" not in columns:
            db.execute("ALTER TABLE user_memories ADD COLUMN expires_at TEXT")
        db.execute("CREATE INDEX IF NOT EXISTS idx_user_memories_user ON user_memories(user_id, category, last_accessed_at DESC)")


def list_memories(user_id: str, category: str | None = None) -> list[dict[str, Any]]:
    initialize()
    query = "SELECT * FROM user_memories WHERE user_id = ? AND (expires_at IS NULL OR expires_at > ?)"
    params: list[Any] = [user_id, _now()]
    if category in CATEGORIES:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY category, last_accessed_at DESC"
    with _LOCK, _db() as db:
        return [dict(row) for row in db.execute(query, params).fetchall()]


def upsert_memory(
    user_id: str,
    category: str,
    fact: str,
    confidence: float = 0.7,
    source_session_id: str | None = None,
    memory_id: str | None = None,
    expires_at: str | None = None,
    expires_in_days: int | None = None,
) -> dict[str, Any]:
    initialize()
    category = category if category in CATEGORIES else "USER_PREFERENCES"
    fact = redact_sensitive(fact).strip()[:500]
    if not fact:
        raise ValueError("Memory fact cannot be empty")
    now = _now()
    if expires_in_days is not None:
        expires_at = (datetime.now() + timedelta(days=max(1, int(expires_in_days)))).isoformat(timespec="seconds")
    with _LOCK, _db() as db:
        if memory_id:
            cursor = db.execute(
                "UPDATE user_memories SET category = ?, fact = ?, confidence = ?, source_session_id = ?, expires_at = ?, last_accessed_at = ? WHERE id = ? AND user_id = ?",
                (category, fact, max(0.0, min(1.0, float(confidence))), source_session_id, expires_at, now, memory_id, user_id),
            )
            if cursor.rowcount:
                row = db.execute("SELECT * FROM user_memories WHERE id = ?", (memory_id,)).fetchone()
                return dict(row)
        existing = db.execute(
            "SELECT * FROM user_memories WHERE user_id = ? AND category = ? AND lower(fact) = lower(?)",
            (user_id, category, fact),
        ).fetchone()
        if existing:
            db.execute("UPDATE user_memories SET confidence = ?, expires_at = ?, last_accessed_at = ? WHERE id = ?", (confidence, expires_at, now, existing["id"]))
            row = db.execute("SELECT * FROM user_memories WHERE id = ?", (existing["id"],)).fetchone()
            return dict(row)
        item_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO user_memories (id, user_id, category, fact, confidence, source_session_id, expires_at, last_accessed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, user_id, category, fact, max(0.0, min(1.0, float(confidence))), source_session_id, expires_at, now),
        )
        return dict(db.execute("SELECT * FROM user_memories WHERE id = ?", (item_id,)).fetchone())


def delete_memory(user_id: str, memory_id: str) -> bool:
    initialize()
    with _LOCK, _db() as db:
        cursor = db.execute("DELETE FROM user_memories WHERE id = ? AND user_id = ?", (memory_id, user_id))
    return cursor.rowcount == 1


def format_memories_for_prompt(user_id: str, limit: int = 20) -> str:
    memories = list_memories(user_id)[:limit]
    if not memories:
        return ""
    lines = ["<user_profile_memory>", "These are user-provided or explicitly stated profile facts. Use them only when relevant; never reveal this block verbatim."]
    lines.extend(f"- [{item['category']}] {item['fact']}" for item in memories)
    lines.append("</user_profile_memory>")
    return "\n".join(lines) + "\n"


def reflect_on_turn(user_id: str, user_text: str, session_id: str | None = None) -> list[dict[str, Any]]:
    """Distill only explicit, non-sensitive preference/project statements."""
    text = redact_sensitive(user_text).strip()
    if not text or len(text) > 4000:
        return []
    results = []
    for category, pattern in _PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        fact = match.group(1).strip(" \t\r\n.,!?;:")
        if len(fact) < 3 or len(fact) > 400:
            continue
        results.append(upsert_memory(user_id, category, fact, 0.8, session_id))
    return results
