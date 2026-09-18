import json
import os
import sys
import tempfile
import threading
from dataclasses import dataclass, asdict
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
    "ui_theme": "Ultron",
    "design_mode": "orb",
    "provider_mode": "auto",
    "offline_model": "rules",
    "enabled_plugins": {},
    "permissions": {},
    "theme_editor": {
        "font_family": "Courier New",
        "animations_enabled": True,
        "panel_visibility": {"left": True, "center": True, "right": True},
        "orb_sensitivity": 1.0,
        "orb_particle_density": 1.0,
    },
    "push_to_talk": False,
    "wake_word_enabled": False,
    "wake_word": "Friday",
    "audio_input_device": "default",
    "audio_output_device": "default",
    "voice_activity_visualization": True,
    "skill_profile": "general",
}

PLUGIN_NAMES = (
    "open_app", "web_search", "system_status", "weather_report", "send_message",
    "reminder", "youtube_video", "screen_process", "close_camera", "computer_settings",
    "browser_control", "file_controller", "desktop_control", "code_helper", "dev_agent",
    "computer_control", "game_updater", "flight_finder", "manage_monitor", "shutdown_friday",
    "file_processor",
    "plan_task", "manage_routine", "memory_control",
)

DEFAULT_PERMISSIONS = {
    "microphone": True,
    "camera": False,
    "screen": False,
    "files": False,
    "browser": False,
    "system": False,
    "messaging": False,
    "power": False,
}

@dataclass(frozen=True)
class AppSettings:
    """Validated application preferences shared by UI, runtime, and dashboard."""
    ui_theme: str = "Ultron"
    design_mode: str = "orb"
    voice_name: str = "Kore"
    voice_language: str = "en-US"
    provider_mode: str = "auto"
    offline_model: str = "rules"
    enabled_plugins: dict = None
    permissions: dict = None
    theme_editor: dict = None
    push_to_talk: bool = False
    wake_word_enabled: bool = False
    wake_word: str = "Friday"
    audio_input_device: str = "default"
    audio_output_device: str = "default"
    voice_activity_visualization: bool = True

    def __post_init__(self):
        object.__setattr__(self, "enabled_plugins", dict(self.enabled_plugins or {}))
        object.__setattr__(self, "permissions", dict(self.permissions or {}))


def validate_settings(values: dict | None = None) -> dict:
    """Return a normalized, bounded settings profile without exposing secrets."""
    raw = dict(PERSONALIZATION_DEFAULTS)
    raw.update(values or {})
    raw["ui_theme"] = str(raw.get("ui_theme") or "Ultron")[:80]
    raw["design_mode"] = str(raw.get("design_mode") or "orb").lower()
    if raw["design_mode"] not in {"orb", "default", "radar", "reactor", "matrix", "constellation"}:
        raw["design_mode"] = "orb"
    raw["provider_mode"] = str(raw.get("provider_mode") or "auto").lower()
    if raw["provider_mode"] not in {"auto", "online", "offline"}:
        raw["provider_mode"] = "auto"
    raw["offline_model"] = str(raw.get("offline_model") or "rules").lower()
    if raw["offline_model"] not in {"rules"}:
        raw["offline_model"] = "rules"
    enabled = raw.get("enabled_plugins") if isinstance(raw.get("enabled_plugins"), dict) else {}
    raw["enabled_plugins"] = {name: bool(enabled.get(name, True)) for name in PLUGIN_NAMES}
    permissions = raw.get("permissions") if isinstance(raw.get("permissions"), dict) else {}
    raw["permissions"] = {name: bool(permissions.get(name, default)) for name, default in DEFAULT_PERMISSIONS.items()}
    editor = raw.get("theme_editor") if isinstance(raw.get("theme_editor"), dict) else {}
    try:
        sensitivity = float(editor.get("orb_sensitivity", 1.0))
    except (TypeError, ValueError):
        sensitivity = 1.0
    try:
        density = float(editor.get("orb_particle_density", 1.0))
    except (TypeError, ValueError):
        density = 1.0
    raw["theme_editor"] = {
        "font_family": str(editor.get("font_family") or "Courier New")[:80],
        "animations_enabled": bool(editor.get("animations_enabled", True)),
        "panel_visibility": {
            name: bool((editor.get("panel_visibility") or {}).get(name, True))
            for name in ("left", "center", "right")
        },
        "orb_sensitivity": max(0.2, min(2.0, sensitivity)),
        "orb_particle_density": max(0.0, min(2.0, density)),
    }
    raw["push_to_talk"] = bool(raw.get("push_to_talk", False))
    raw["wake_word_enabled"] = bool(raw.get("wake_word_enabled", False))
    raw["wake_word"] = str(raw.get("wake_word") or "Friday")[:40]
    raw["audio_input_device"] = str(raw.get("audio_input_device") or "default")[:160]
    raw["audio_output_device"] = str(raw.get("audio_output_device") or "default")[:160]
    raw["voice_activity_visualization"] = bool(raw.get("voice_activity_visualization", True))
    raw["skill_profile"] = str(raw.get("skill_profile") or "general").lower()
    if raw["skill_profile"] not in {"general", "coding", "research", "household", "productivity"}:
        raw["skill_profile"] = "general"
    return raw


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
        data = validate_settings(data)
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
    return validate_settings(profile)


def load_settings() -> AppSettings:
    values = validate_settings(_load_config_file())
    return AppSettings(
        ui_theme=values["ui_theme"],
        design_mode=values["design_mode"],
        voice_name=str(values.get("voice_name") or "Kore"),
        voice_language=str(values.get("voice_language") or "en-US"),
        provider_mode=values["provider_mode"],
        offline_model=values["offline_model"],
        enabled_plugins=values["enabled_plugins"],
        permissions=values["permissions"],
        theme_editor=values["theme_editor"],
        push_to_talk=values["push_to_talk"],
        wake_word_enabled=values["wake_word_enabled"],
        wake_word=values["wake_word"],
        audio_input_device=values["audio_input_device"],
        audio_output_device=values["audio_output_device"],
        voice_activity_visualization=values["voice_activity_visualization"],
    )


def save_settings(settings: AppSettings | dict) -> dict:
    values = asdict(settings) if isinstance(settings, AppSettings) else dict(settings)
    return update_config(validate_settings(values))


def plugin_enabled(name: str) -> bool:
    return bool(load_personalization().get("enabled_plugins", {}).get(name, True))


def permission_granted(capability: str) -> bool:
    return bool(load_personalization().get("permissions", {}).get(capability, False))


def _get_env_api_key() -> str | None:
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = os.getenv(env_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _get_config_api_key() -> str | None:
    # Provider credentials must never be persisted in the desktop profile.
    return None


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
    raise RuntimeError(
        "Provider keys are environment-only. Set GEMINI_API_KEY or GOOGLE_API_KEY "
        "before starting Personal-Ai."
    )


def load_api_keys() -> dict:
    data = _load_config_file()
    gemini_key = get_gemini_key()
    if gemini_key:
        data["gemini_api_key"] = gemini_key
    return data


def get_gemini_key(prefer_env: bool = True) -> str | None:
    return _get_env_api_key()


def get_gemini_key_sources() -> tuple[str | None, str | None]:
    return _get_env_api_key(), None


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
