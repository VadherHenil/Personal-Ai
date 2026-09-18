"""Structured, redacted application logging and crash capture."""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from security.controls import redact_sensitive

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "friday.jsonl"


class RedactedJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive(record.getMessage()),
        }
        if record.exc_info:
            payload["exception"] = redact_sensitive("".join(traceback.format_exception(*record.exc_info)))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("friday")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(RedactedJsonFormatter())
        logger.addHandler(handler)
    return logger


def install_crash_handler(logger: logging.Logger | None = None) -> None:
    target = logger or configure_logging()

    def handle_uncaught(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        target.critical("Uncaught application exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_uncaught
