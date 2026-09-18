"""Persistent proactive routines for briefings, alerts, weather, and automations."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "chat_history.sqlite3"


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def initialize() -> None:
    with _db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS routines (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
            kind TEXT NOT NULL, schedule TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER NOT NULL DEFAULT 1, last_run TEXT
        )""")


def create_routine(user_id: str, name: str, kind: str, schedule: str, payload: dict | None = None) -> dict:
    initialize()
    item_id = uuid.uuid4().hex
    with _db() as db:
        db.execute("INSERT INTO routines VALUES (?, ?, ?, ?, ?, ?, 1, NULL)", (item_id, user_id, name[:120], kind[:40], schedule[:80], json.dumps(payload or {})))
    return get_routine(user_id, item_id)


def list_routines(user_id: str) -> list[dict]:
    initialize()
    with _db() as db:
        rows = db.execute("SELECT * FROM routines WHERE user_id = ? ORDER BY name", (user_id,)).fetchall()
    return [_decode(row) for row in rows]


def get_routine(user_id: str, routine_id: str) -> dict | None:
    initialize()
    with _db() as db:
        row = db.execute("SELECT * FROM routines WHERE id = ? AND user_id = ?", (routine_id, user_id)).fetchone()
    return _decode(row) if row else None


def mark_due(user_id: str, now: datetime | None = None) -> list[dict]:
    """Return enabled routines whose simple HH:MM schedule matches the current minute."""
    current = (now or datetime.now()).strftime("%H:%M")
    due = []
    for routine in list_routines(user_id):
        if routine["enabled"] and routine["schedule"] == current and routine.get("last_run") != current:
            with _db() as db:
                db.execute("UPDATE routines SET last_run = ? WHERE id = ? AND user_id = ?", (current, routine["id"], user_id))
            due.append(routine)
    return due


def _decode(row) -> dict:
    item = dict(row)
    item["payload"] = json.loads(item.get("payload") or "{}")
    item["enabled"] = bool(item["enabled"])
    return item
