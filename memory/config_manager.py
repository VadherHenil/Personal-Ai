import json
import os
import sys
import tempfile
import threading
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"
_CONFIG_LOCK = threading.RLock()

PERSONALIZATION_DEFAULTS = {
    "assistant_name": "Friday",
    "assistant_description": "A helpful personal AI assistant.",
    "welcome_message": "How can I help you today?",
    "personality_preset": "Friendly",
    "custom_instructions": "",
    "response_length": "Balanced",
    "preferred_language": "Auto",
    "conversation_style": "Conversational",
    "formality_level": 50,
    "humor_level": 50,
    "empathy_level": 70,
    "creativity_level": 60,
    "verbosity_level": 50,
    "default_coding_language": "Python",
    "markdown_enabled": True,
    "memory_enabled": True,
    "context_retention": "Session",
    "auto_follow_up": True,
    "learning_mode": False,
    "research_mode": False,
    "developer_mode": False,
}


def _load_config_file() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Failed to load api_keys.json: {e}")
        return {}


def update_config(values: dict) -> dict:
    """Atomically merge validated preferences into the local profile.

    The desktop app is single-user, so this file is the durable profile shared
    by the desktop UI, the live assistant, and the paired-phone dashboard.
    Atomic replacement prevents a partial write if the app closes mid-update.
    """
    ensure_config_dir()
    with _CONFIG_LOCK:
        data = _load_config_file()
        data.update({key: value for key, value in values.items() if value is not None})
        fd, temp_name = tempfile.mkstemp(prefix="friday-config-", suffix=".json", dir=str(CONFIG_DIR))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, CONFIG_FILE)
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise
        return data


def load_personalization() -> dict:
    """Return a complete, backwards-compatible personalization profile."""
    profile = dict(PERSONALIZATION_DEFAULTS)
    profile.update(_load_config_file())
    return profile


def _get_env_api_key() -> str | None:
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = os.getenv(env_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _get_config_api_key() -> str | None:
    value = _load_config_file().get("gemini_api_key")
    return value.strip() if isinstance(value, str) and value.strip() else None


def get_config_value(key: str, default=None, env_var_names: tuple[str, ...] | None = None) -> object:
    env_names = tuple(env_var_names or ())
    for env_name in env_names:
        if env_name:
            value = os.getenv(env_name)
            if value is not None and str(value).strip():
                return value.strip()

    fallback = os.getenv(key.upper())
    if fallback is not None and str(fallback).strip():
        return fallback.strip()

    return _load_config_file().get(key, default)


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists()

def save_api_keys(gemini_api_key: str) -> None:
    ensure_config_dir()

    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data["gemini_api_key"] = gemini_api_key.strip()

    CONFIG_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )


def load_api_keys() -> dict:
    data = _load_config_file()
    gemini_key = get_gemini_key()
    if gemini_key:
        data["gemini_api_key"] = gemini_key
    return data


def get_gemini_key(prefer_env: bool = True) -> str | None:
    env_key = _get_env_api_key()
    config_key = _get_config_api_key()
    if prefer_env:
        return env_key or config_key
    return config_key or env_key


def get_gemini_key_sources() -> tuple[str | None, str | None]:
    return _get_env_api_key(), _get_config_api_key()


def get_voice_name() -> str | None:
    value = get_config_value(
        "voice_name",
        default=None,
        env_var_names=("VOICE_NAME",),
    )
    return value if isinstance(value, str) and value.strip() else None


def get_voice_language() -> str | None:
    value = get_config_value(
        "voice_language",
        default=None,
        env_var_names=("VOICE_LANGUAGE",),
    )
    return value if isinstance(value, str) and value.strip() else None


def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)


def get_assistant_name() -> str:
    """Return the configured assistant name, or 'Friday' if not set."""
    return str(load_personalization().get("assistant_name") or "Friday").strip() or "Friday"


def get_user_name() -> str:
    """Return the configured user name for addressing."""
    return load_api_keys().get("user_name", "")


def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to config."""
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["assistant_name"] = assistant_name.strip() or "Friday"
    data["user_name"] = user_name.strip()
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)


def save_brief_enabled(enabled: bool) -> None:
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["morning_brief_enabled"] = enabled
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
