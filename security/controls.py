"""Dependency-free security controls used at assistant trust boundaries."""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Any

MAX_PROMPT_CHARS = 4000

_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I),
    re.compile(r"disregard\s+(all\s+)?prior\s+prompts?", re.I),
    re.compile(r"print\s+(the\s+)?system\s+prompt", re.I),
    re.compile(r"(?:dan|developer)\s+mode", re.I),
    re.compile(r"jailbreak", re.I),
)
_SECRET_PATTERNS = (
    (re.compile(r"[A-Z0-9_]*(?:API[_-]?KEY|SECRET|TOKEN)[A-Z0-9_]*\s*[=:]\s*[^\s,;]+", re.I), "[REDACTED_SECRET]"),
    (re.compile(r"\b(?:sk|AIza)[A-Za-z0-9_-]{16,}\b"), "[REDACTED_SECRET]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[REDACTED_CARD]"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[REDACTED_EMAIL]"),
)

# These operations can delete, execute, send, alter settings, or expose files.
_DESTRUCTIVE_TOOLS = frozenset({
    "code_helper", "computer_control", "computer_settings", "desktop_control",
    "dev_agent", "file_controller", "open_app", "reminder", "send_message",
})
_DESTRUCTIVE_ACTIONS = frozenset({
    "delete", "write", "edit", "run", "build", "shutdown", "restart", "reboot",
    "poweroff", "send", "type", "hotkey", "create_file", "create_folder", "move",
    "copy", "rename", "organize", "clean", "task", "install", "update",
})

TOOL_CAPABILITIES = {
    "screen_process": "screen",
    "close_camera": "camera",
    "file_controller": "files",
    "file_processor": "files",
    "browser_control": "browser",
    "open_app": "system",
    "computer_settings": "system",
    "computer_control": "system",
    "desktop_control": "system",
    "system_status": "system",
    "send_message": "messaging",
    "shutdown_friday": "power",
}


def redact_sensitive(value: Any) -> str:
    """Return bounded text safe for logs, transcripts, and model output display."""
    text = str(value or "")
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:MAX_PROMPT_CHARS]


def inspect_user_text(text: str) -> tuple[str, tuple[str, ...]]:
    """Redact PII and reject known instruction-boundary attacks."""
    sanitized = redact_sensitive(text).strip()
    if len(sanitized) > MAX_PROMPT_CHARS:
        raise ValueError(f"Prompt exceeds the {MAX_PROMPT_CHARS}-character limit.")
    reasons = tuple(pattern.pattern for pattern in _INJECTION_PATTERNS if pattern.search(sanitized))
    if reasons:
        raise ValueError("Prompt blocked by the instruction-boundary guardrail.")
    return sanitized, reasons


def sanitize_model_output(text: str) -> str:
    """Prevent provider secrets and PII from being displayed or persisted."""
    return redact_sensitive(text).strip()


def _schema_type_ok(value: Any, schema: dict[str, Any]) -> bool:
    kind = str(schema.get("type", "")).upper()
    return {
        "STRING": isinstance(value, str),
        "INTEGER": isinstance(value, int) and not isinstance(value, bool),
        "NUMBER": isinstance(value, (int, float)) and not isinstance(value, bool),
        "BOOLEAN": isinstance(value, bool),
        "ARRAY": isinstance(value, list),
        "OBJECT": isinstance(value, dict),
    }.get(kind, True)


def validate_tool_call(name: str, args: dict[str, Any], declarations: list[dict[str, Any]]) -> None:
    """Validate model tool arguments against the existing declaration schema."""
    declaration = next((item for item in declarations if item.get("name") == name), None)
    if declaration is None:
        raise ValueError(f"Unknown tool: {name}")
    schema = declaration.get("parameters") or {}
    properties = schema.get("properties") or {}
    missing = [key for key in schema.get("required", []) if key not in args]
    if missing:
        raise ValueError(f"Missing tool arguments: {', '.join(missing)}")
    unknown = set(args) - set(properties)
    if unknown:
        raise ValueError(f"Unexpected tool arguments: {', '.join(sorted(unknown))}")
    for key, value in args.items():
        if not _schema_type_ok(value, properties.get(key, {})):
            raise ValueError(f"Invalid type for tool argument: {key}")
    if name in _DESTRUCTIVE_TOOLS and str(args.get("action", "")).lower() in _DESTRUCTIVE_ACTIONS:
        raise PermissionError("Destructive tool calls require explicit human approval.")


def validate_runtime_tool_call(
    name: str,
    args: dict[str, Any],
    declarations: list[dict[str, Any]],
    *,
    enabled_plugins: dict[str, bool] | None = None,
    permissions: dict[str, bool] | None = None,
) -> None:
    """Apply declaration validation plus the user's plugin/capability policy."""
    validate_tool_call(name, args, declarations)
    if enabled_plugins is not None and not bool(enabled_plugins.get(name, True)):
        raise PermissionError(f"Plugin '{name}' is disabled in Settings.")
    capability = TOOL_CAPABILITIES.get(name)
    if capability and permissions is not None and not bool(permissions.get(capability, False)):
        raise PermissionError(f"Permission '{capability}' is required for tool '{name}'.")


class SlidingWindowLimiter:
    """Small in-process per-key limiter for the local dashboard."""

    def __init__(self, limit: int = 30, window_seconds: int = 600):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= self.window_seconds:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


def new_confirmation_token() -> str:
    return secrets.token_urlsafe(24)


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
