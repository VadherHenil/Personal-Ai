"""Persistent action history for dashboard audit, retry, and undo workflows."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ACTION_DB_PATH = BASE_DIR / "memory" / "chat_history.sqlite3"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    ACTION_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(ACTION_DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    return db


def initialize() -> None:
    with _connect() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS action_history (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, tool TEXT NOT NULL,
                arguments TEXT NOT NULL DEFAULT '{}', result TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'completed', undoable INTEGER NOT NULL DEFAULT 0,
                undone INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            )"""
        )


def record_action(user_id: str, tool: str, arguments: dict, result: str, *, undoable: bool = False, status: str = "completed") -> str:
    initialize()
    action_id = uuid.uuid4().hex
    with _connect() as db:
        db.execute(
            "INSERT INTO action_history (id,user_id,tool,arguments,result,status,undoable,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (action_id, user_id, tool, json.dumps(arguments or {}, ensure_ascii=False), str(result)[:4000], status, int(undoable), _now()),
        )
    return action_id


def list_actions(user_id: str, limit: int = 100) -> list[dict]:
    initialize()
    with _connect() as db:
        rows = db.execute(
            "SELECT * FROM action_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, max(1, min(int(limit), 500))),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["arguments"] = json.loads(item["arguments"] or "{}")
        item["undoable"] = bool(item["undoable"])
        item["undone"] = bool(item["undone"])
        items.append(item)
    return items


def mark_undone(action_id: str, user_id: str) -> bool:
    initialize()
    with _connect() as db:
        cursor = db.execute(
            "UPDATE action_history SET undone = 1, status = 'undone' WHERE id = ? AND user_id = ? AND undoable = 1 AND undone = 0",
            (action_id, user_id),
        )
    return cursor.rowcount == 1
