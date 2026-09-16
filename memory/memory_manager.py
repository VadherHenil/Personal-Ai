import json
from datetime import datetime
from threading import Lock
from pathlib import Path
import sys


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR         = get_base_dir()
MEMORY_PATH      = BASE_DIR / "memory" / "long_term.json"
_lock            = Lock()
MAX_VALUE_LENGTH = 380
MEMORY_MAX_CHARS = 2200
TRANSCRIPTS_DIR  = BASE_DIR / "memory" / "transcripts"


def _empty_memory() -> dict:
    return {
        "identity":      {},
        "preferences":   {},
        "projects":      {},
        "relationships": {},
        "wishes":        {},
        "notes":         {},
        "sessions":      [],
    }


def _normalize_memory(memory: dict) -> dict:
    if not isinstance(memory, dict):
        return _empty_memory()

    normalized = _empty_memory()
    for key, value in memory.items():
        if key == "sessions":
            normalized[key] = value if isinstance(value, list) else []
        elif isinstance(value, dict):
            normalized[key] = value
        else:
            normalized[key] = {}
    return normalized


def load_memory() -> dict:
    if not MEMORY_PATH.exists():
        return _empty_memory()
    with _lock:
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return _normalize_memory(data)
            return _empty_memory()
        except Exception as e:
            print(f"[Memory] ⚠️ Load error: {e}")
            return _empty_memory()

def _all_entries(memory: dict) -> list[tuple]:
    entries = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            if isinstance(entry, dict) and "value" in entry:
                entries.append((cat, key, entry))
    return entries


def _trim_to_limit(memory: dict) -> dict:
    if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
        return memory
    entries = _all_entries(memory)
    entries.sort(key=lambda t: t[2].get("updated", "0000-00-00"))
    for cat, key, _ in entries:
        if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
            break
        del memory[cat][key]
        print(f"[Memory] 🗑️  Trimmed {cat}/{key}")
    return memory

def save_memory(memory: dict) -> None:
    if not isinstance(memory, dict):
        return
    memory = _normalize_memory(memory)
    memory = _trim_to_limit(memory)
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _truncate_value(val: str) -> str:
    if isinstance(val, str) and len(val) > MAX_VALUE_LENGTH:
        return val[:MAX_VALUE_LENGTH].rstrip() + "…"
    return val


def _recursive_update(target: dict, updates: dict) -> bool:
    changed = False
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value):
                changed = True
        else:
            new_val  = _truncate_value(str(value["value"] if isinstance(value, dict) else value))
            entry    = {"value": new_val, "updated": datetime.now().strftime("%Y-%m-%d")}
            existing = target.get(key, {})
            if not isinstance(existing, dict) or existing.get("value") != new_val:
                target[key] = entry
                changed = True
    return changed


def update_memory(memory_update: dict) -> dict:
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory()
    memory = load_memory()
    if _recursive_update(memory, memory_update):
        save_memory(memory)
        print(f"[Memory] 💾 Saved: {list(memory_update.keys())}")
    return memory

def format_memory_for_prompt(memory: dict | None) -> str:
    if not memory:
        return ""

    lines = []

    identity  = memory.get("identity", {})
    id_fields = ["name", "age", "birthday", "city", "job", "language", "school", "nationality"]
    for field in id_fields:
        entry = identity.get(field)
        if entry:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"{field.title()}: {val}")
    for key, entry in identity.items():
        if key in id_fields:
            continue
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val:
            lines.append(f"{key.replace('_', ' ').title()}: {val}")

    prefs = memory.get("preferences", {})
    if prefs:
        lines.append("")
        lines.append("Preferences:")
        for key, entry in list(prefs.items())[:15]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    projects = memory.get("projects", {})
    if projects:
        lines.append("")
        lines.append("Active Projects / Goals:")
        for key, entry in list(projects.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    rels = memory.get("relationships", {})
    if rels:
        lines.append("")
        lines.append("People in their life:")
        for key, entry in list(rels.items())[:10]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    wishes = memory.get("wishes", {})
    if wishes:
        lines.append("")
        lines.append("Wishes / Plans / Wants:")
        for key, entry in list(wishes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    notes = memory.get("notes", {})
    if notes:
        lines.append("")
        lines.append("Other notes:")
        for key, entry in list(notes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key}: {val}")

    if not lines:
        return ""

    header = "[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]\n"
    result = header + "\n".join(lines)
    if len(result) > 2000:
        result = result[:1997] + "…"

    return result + "\n"

def remember(key: str, value: str, category: str = "notes") -> str:
    valid = {"identity", "preferences", "projects", "relationships", "wishes", "notes"}
    if category not in valid:
        category = "notes"
    update_memory({category: {key: {"value": value}}})
    return f"Remembered: {category}/{key} = {value}"


def forget(key: str, category: str = "notes") -> str:
    memory = load_memory()
    cat    = memory.get(category, {})
    if key in cat:
        del cat[key]
        memory[category] = cat
        save_memory(memory)
        return f"Forgotten: {category}/{key}"
    return f"Not found: {category}/{key}"


forget_memory = forget


# ── Session memory ─────────────────────────────────────────────────────────────

_SESSION_MAX = 3   # safety cap — in practice 0-1 entries after pop


def save_session_summary(summary: str, language: str = "") -> None:
    """Append a 1-2 sentence session summary to long_term.json['sessions']."""
    summary = (summary or "").strip()
    if not summary:
        return
    memory   = load_memory()
    sessions = memory.get("sessions", [])
    if not isinstance(sessions, list):
        sessions = []
    now = datetime.now()
    entry: dict = {
        "date":      now.strftime("%Y-%m-%d"),
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "iso":       now.isoformat(),
        "summary":   summary[:280],
    }
    if language:
        entry["language"] = language
    sessions.append(entry)
    memory["sessions"] = sessions[-_SESSION_MAX:]
    with _lock:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _write_transcript_file(text: str) -> str:
    """Write full transcript to a file and return relative path."""
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    name = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = TRANSCRIPTS_DIR / f"session_{name}.txt"
    # ensure small size safety: limit to 1MB
    try:
        data = text if isinstance(text, str) else str(text)
        if len(data) > 1_000_000:
            data = data[:1_000_000]
        path.write_text(data, encoding="utf-8")
        # store relative path for portability
        return str(path.relative_to(BASE_DIR))
    except Exception as e:
        print(f"[Memory] ⚠️ Failed writing transcript file: {e}")
        return ""


def append_session_transcript(summary: str, transcript: str, language: str = "") -> None:
    """Append a session entry with summary and a transcript file reference."""
    if not transcript and not summary:
        return
    memory = load_memory()
    sessions = memory.get("sessions", [])
    if not isinstance(sessions, list):
        sessions = []

    tfile = _write_transcript_file(transcript)
    now = datetime.now()
    entry: dict = {
        "date":          now.strftime("%Y-%m-%d"),
        "timestamp":     now.strftime("%Y-%m-%d %H:%M:%S"),
        "iso":           now.isoformat(),
        "summary":       (summary or "").strip()[:280],
        "transcript_file": tfile,
    }
    if language:
        entry["language"] = language

    sessions.append(entry)
    # keep up to _SESSION_MAX full entries to avoid unbounded growth
    memory["sessions"] = sessions[-_SESSION_MAX:]
    with _lock:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def get_all_sessions_full(limit: int = 10) -> list[dict]:
    """Return recent session entries including full transcript text when available."""
    res = []
    memory = load_memory()
    sessions = memory.get("sessions", [])
    seen_files = set()
    # First, include entries explicitly recorded in memory (most recent last)
    if isinstance(sessions, list) and sessions:
        for entry in sessions[-limit:]:
            e = dict(entry)
            tfile = e.get("transcript_file")
            if tfile:
                seen_files.add(str(Path(tfile).name))
                try:
                    p = BASE_DIR / tfile
                    if p.exists():
                        e["transcript"] = p.read_text(encoding="utf-8")
                    else:
                        e["transcript"] = ""
                except Exception:
                    e["transcript"] = ""
            else:
                e["transcript"] = ""
            res.append(e)

    # If we still need more entries, scan transcript files directory for recent files
    if len(res) < limit:
        try:
            if TRANSCRIPTS_DIR.exists():
                files = sorted(
                    [p for p in TRANSCRIPTS_DIR.iterdir() if p.is_file() and p.name.startswith("session_")],
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                for p in files:
                    if len(res) >= limit:
                        break
                    if p.name in seen_files:
                        continue
                    try:
                        txt = p.read_text(encoding="utf-8")
                    except Exception:
                        txt = ""
                    # derive a reasonable date/timestamp from filename when possible
                    # filename format: session_YYYYMMDD_HHMMSS.txt
                    name = p.stem
                    parts = name.split("_")
                    date_str = ""
                    ts_str = ""
                    iso = None
                    if len(parts) >= 3:
                        ymd = parts[1]
                        hms = parts[2]
                        try:
                            date_str = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
                            ts_str = f"{hms[:2]}:{hms[2:4]}:{hms[4:6]}"
                            iso = f"{date_str}T{ts_str}"
                        except Exception:
                            date_str = ""
                    entry = {
                        "date": date_str or datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d"),
                        "timestamp": f"{date_str} {ts_str}" if date_str and ts_str else datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "iso": iso or datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                        "summary": "Transcript file",
                        "transcript_file": str(p.relative_to(BASE_DIR)),
                        "transcript": txt,
                    }
                    res.append(entry)
        except Exception as e:
            print(f"[Memory] ⚠️ scanning transcripts failed: {e}")

    return res[:limit]


def record_login() -> None:
    """Record a login timestamp in long_term memory under preferences.last_login."""
    memory = load_memory()
    last = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefs = memory.get("preferences", {})
    prefs["last_login"] = {"value": last, "updated": datetime.now().strftime("%Y-%m-%d")}
    memory["preferences"] = prefs
    save_memory(memory)


def get_last_login() -> str | None:
    memory = load_memory()
    prefs = memory.get("preferences", {})
    last = prefs.get("last_login")
    if isinstance(last, dict):
        return last.get("value")
    return None


def set_assistant_gender(gender: str = "female") -> None:
    memory = load_memory()
    prefs = memory.get("preferences", {})
    prefs["assistant_gender"] = {"value": str(gender), "updated": datetime.now().strftime("%Y-%m-%d")}
    memory["preferences"] = prefs
    save_memory(memory)


def set_admin_enabled(enabled: bool = True) -> None:
    memory = load_memory()
    prefs = memory.get("preferences", {})
    prefs["admin_enabled"] = {"value": str(bool(enabled)), "updated": datetime.now().strftime("%Y-%m-%d")}
    memory["preferences"] = prefs
    save_memory(memory)


def is_admin_enabled() -> bool:
    memory = load_memory()
    prefs = memory.get("preferences", {})
    val = prefs.get("admin_enabled")
    if isinstance(val, dict):
        return str(val.get("value", "False")).lower() in ("1", "true", "yes")
    return str(val).lower() in ("1", "true", "yes")


def pop_last_session() -> dict | None:
    """
    Return AND remove the most recent session entry.
    Calling this consumes the entry so it is never repeated in future briefings.
    """
    with _lock:
        if not MEMORY_PATH.exists():
            return None
        try:
            memory   = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            sessions = memory.get("sessions", [])
            if not isinstance(sessions, list) or not sessions:
                return None
            entry = sessions.pop()          # remove the last entry
            memory["sessions"] = sessions
            MEMORY_PATH.write_text(
                json.dumps(memory, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return entry
        except Exception as e:
            print(f"[Memory] ⚠️ pop_last_session error: {e}")
            return None


def get_last_session() -> dict | None:
    """Return the most recent session entry without removing it."""
    try:
        if not MEMORY_PATH.exists():
            return None
        memory = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        sessions = memory.get("sessions", [])
        if not isinstance(sessions, list) or not sessions:
            return None
        return sessions[-1]
    except Exception as e:
        print(f"[Memory] ⚠️ get_last_session error: {e}")
        return None