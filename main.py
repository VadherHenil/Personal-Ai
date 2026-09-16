import platform as _platform
import subprocess as _subprocess

# ── Nuclear: force CREATE_NO_WINDOW on EVERY subprocess call on Windows ───────
# This patches Popen itself, so no per-file flag is needed anywhere.
if _platform.system() == "Windows":
    _OrigPopen = _subprocess.Popen

    class _Popen(_OrigPopen):
        def __init__(self, args, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | _subprocess.CREATE_NO_WINDOW
            kw.pop("startupinfo", None)   # drop any stale/shared STARTUPINFO
            super().__init__(args, **kw)

    _subprocess.Popen = _Popen
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import re
import threading
import time
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import sounddevice as sd
import numpy as np
from google import genai
from google.genai import types
from ui import FridayUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    get_last_login, record_login, set_assistant_gender, set_admin_enabled, is_admin_enabled,
    append_session_transcript, get_all_sessions_full,
)

from actions.file_processor import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import _capture_camera, _capture_screen
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.system_monitor    import SystemMonitor, get_system_status
from actions.proactive         import ProactiveEngine
from actions.background_monitor import (
    add_monitor, remove_monitor, list_monitors, check_all as monitor_check_all,
)
from actions.web_search        import _news as _fetch_news_sync
from memory.config_manager     import (
    get_gemini_key,
    get_gemini_key_sources,
    get_voice_language,
    get_voice_name,
    load_personalization,
)
from tool_registry import TOOL_DECLARATIONS as TOOL_REGISTRY_DECLARATIONS


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

def _get_api_key(use_config_first: bool = False) -> str:
    key = get_gemini_key(prefer_env=not use_config_first)
    if not key:
        raise RuntimeError("Gemini API key not configured. Set GEMINI_API_KEY or save config/api_keys.json")
    return key


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are the user's configured AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

def _build_personalization_context(config: dict) -> str:
    """Format optional user settings as bounded, non-authoritative response guidance."""
    fields = (
        ("Assistant description", "assistant_description"),
        ("Welcome message", "welcome_message"),
        ("Personality preset", "personality_preset"),
        ("Response length", "response_length"),
        ("Preferred language", "preferred_language"),
        ("Conversation style", "conversation_style"),
        ("Default coding language", "default_coding_language"),
        ("Qualification", "user_qualification"),
        ("Additional user information", "additional_user_information"),
        ("Preferred personality and behavior", "friday_personality_behavior"),
        ("Custom instructions", "custom_instructions"),
    )
    details = []
    for label, key in fields:
        value = config.get(key, "")
        if isinstance(value, str) and value.strip():
            details.append(f"{label}: {value.strip()[:4000]}")
    levels = (
        ("Formality", "formality_level"),
        ("Humor", "humor_level"),
        ("Empathy", "empathy_level"),
        ("Creativity", "creativity_level"),
        ("Verbosity", "verbosity_level"),
    )
    for label, key in levels:
        try:
            value = int(config.get(key, 0))
        except (TypeError, ValueError):
            continue
        if value:
            details.append(f"{label} level: {max(0, min(100, value))}/100")
    behavior_flags = (
        ("memory_enabled", "Use saved preferences and conversation memory when useful."),
        ("auto_follow_up", "Offer a useful follow-up question when it adds value."),
        ("learning_mode", "Adapt carefully to recurring preferences; never infer sensitive facts."),
        ("research_mode", "Favor evidence-led, structured answers when research is requested."),
        ("developer_mode", "Prefer precise technical explanations, code, and implementation detail."),
        ("markdown_enabled", "Use clean Markdown when it improves readability."),
    )
    for key, instruction in behavior_flags:
        if config.get(key):
            details.append(instruction)
    if not details:
        return ""
    return (
        "[USER PERSONALIZATION]\n"
        "Use this context to adapt your tone and helpfulness when relevant. "
        "It is user preference only: do not let it override core instructions, "
        "safety requirements, tool-use rules, or the user's current request.\n"
        + "\n".join(details)
        + "\n"
    )


_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:    
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()

TOOL_DECLARATIONS = TOOL_REGISTRY_DECLARATIONS

# --- Plugin system ---


class FridayLive:

    def __init__(self, ui: FridayUI):
        self.ui             = ui
        self._asst_name     = "Friday"   # updated each session from config
        self.session              = None
        self.audio_in_queue       = None
        self.out_queue            = None
        self._loop                = None
        self._is_speaking         = False
        self._speaking_lock       = threading.Lock()
        self._phone_active        = False   # True while phone mic is streaming; pauses PC mic
        self._pending_vision       = None    # (img_bytes, mime_type, question, angle) to inject after tool response
        self._vision_cam_active    = False   # True if camera was opened for vision → auto-close after response
        self._vision_close_pending = False   # True after vision injected; next turn_complete closes camera
        self._vision_last_time     = 0.0     # monotonic time of last screen_process call (cooldown guard)
        self._vision_busy          = False   # True while a vision capture/inject cycle is in flight
        self._interrupted          = False   # True while draining audio after user interrupt
        self.ui.on_text_command   = self._on_text_command
        self.ui.on_remote_clicked = self._make_remote_key
        self.ui.on_interrupt      = self.interrupt
        self.ui.on_personalization_changed = self._on_personalization_changed
        self._turn_done_event: asyncio.Event | None = None
        self._dashboard     = None
        self._briefing_sent    = False          # morning briefing fires once per process
        self._sys_monitor      = SystemMonitor()  # persistent cooldown state
        self._proactive        = ProactiveEngine()
        self._last_user_speech = time.monotonic()  # updated on every user utterance
        self._session_log: list[str] = []          # conversation turns for end-of-session summary
        self._pending_startup_greeting: str | None = None
        self._greeting_state: str = "idle"  # one of: idle, queued, sent
        self._session_raw_log: list[str] = []

    def _on_personalization_changed(self, settings: dict) -> None:
        """Apply visible identity updates immediately and notify paired devices."""
        name = str(settings.get("assistant_name") or self._asst_name).strip()
        if name:
            self._asst_name = name
        if self._dashboard and self._loop:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._dashboard.broadcast({"type": "assistant_config", "name": self._asst_name}),
                    self._loop,
                )
                # A disconnected device receives the latest profile on render.
                future.add_done_callback(lambda _f: None)
            except RuntimeError:
                pass

    def _make_remote_key(self):
        """Called from Qt main thread when user presses Remote Control."""
        if self._dashboard is None:
            self.ui.write_log(
                "SYS: Dashboard unavailable. "
                "Run: pip install fastapi \"uvicorn[standard]\" cryptography"
            )
            return None
        key    = self._dashboard.new_key()
        url    = self._dashboard.get_url()
        manual = self._dashboard.get_manual_url()
        return url, key, f"{url}/auto-login?key={key}", manual

    def _on_text_command(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self._send_pending_and_user(text),
            self._loop
        )

    async def _send_pending_and_user(self, text: str) -> None:
        """Send any queued startup greeting first, then the user's text input."""
        try:
            if self._pending_startup_greeting and self.session:
                try:
                    await self.session.send_client_content(
                        turns={"parts": [{"text": self._pending_startup_greeting}]},
                        turn_complete=True,
                    )
                    self.ui.write_log("SYS: Greeting sent.")
                except Exception as e:
                    print(f"[FRIDAY] Failed to send queued greeting: {e}")
                else:
                    # Wait for the assistant's response to complete before sending user input
                    if self._turn_done_event:
                        try:
                            await asyncio.wait_for(self._turn_done_event.wait(), timeout=8)
                        except asyncio.TimeoutError:
                            pass
                        try:
                            self._turn_done_event.clear()
                        except Exception:
                            pass
                finally:
                    self._pending_startup_greeting = None
                    # mark as sent so reconnects or repeated starts don't greet again
                    try:
                        self._greeting_state = "sent"
                    except Exception:
                        pass

            # Now send the user's text. Log it locally so transcripts include both sides.
            # Debounce duplicate rapid inputs (some UI events send twice).
            if self.session:
                now_t = time.time()
                last_txt = getattr(self, '_last_sent_user_text', None)
                last_t = getattr(self, '_last_sent_user_time', 0)
                if last_txt is not None and text.strip() == last_txt.strip() and (now_t - last_t) < 1.0:
                    # duplicate input detected — ignore
                    self.ui.write_log("SYS: Duplicate input ignored.")
                    return
                # record this as last sent
                try:
                    self._last_sent_user_text = text
                    self._last_sent_user_time = now_t
                except Exception:
                    pass
                try:
                    # record typed user input into session logs
                    # UI already logs the text; avoid duplicating UI log here
                    self._session_log.append(f"User: {text}")
                    if hasattr(self, '_session_raw_log'):
                        self._session_raw_log.append(f"User: {text}")
                except Exception:
                    pass

                # If the user is explicitly asking to recall exact past conversations,
                # handle it locally by returning stored transcripts instead of sending
                # the request to the LLM which may refuse or paraphrase.
                try:
                    lt = text.lower()
                    recall_keywords = ("last", "pichli", "conversation", "conversations", "exact", "transcript", "sabhi", "poori", "poori tarah")
                    if any(k in lt for k in recall_keywords) and ("conversation" in lt or "transcript" in lt or "conversation" in lt):
                        from memory.memory_manager import get_all_sessions_full
                        sessions = get_all_sessions_full(limit=10)
                        if not sessions:
                            reply = "Koi purani baatein nahin mili."
                        else:
                            parts = []
                            for s in sessions:
                                date = s.get("date", "unknown date")
                                ts = s.get("timestamp") or s.get("iso") or ""
                                summary = s.get("summary", "")
                                transcript = s.get("transcript", "").strip() or "(no transcript)"
                                header = f"--- {date} {(' ' + ts) if ts else ''} — {summary} ---"
                                parts.append(header + "\n" + transcript)
                            reply = "\n\n".join(parts)

                        # send reply as assistant output
                        await self.session.send_client_content(
                            turns={"parts": [{"text": reply}]},
                            turn_complete=True,
                        )
                        # append assistant reply to session logs
                        try:
                            self._session_log.append(f"{self._asst_name}: {reply}")
                            if hasattr(self, '_session_raw_log'):
                                self._session_raw_log.append(f"{self._asst_name}: {reply}")
                        except Exception:
                            pass
                        # done — do not forward the original prompt to LLM
                        return
                except Exception as e:
                    print(f"[FRIDAY] Recall-helper error: {e}")

                await self.session.send_client_content(
                    turns={"parts": [{"text": text}]},
                    turn_complete=True,
                )
                # update last user speech time so proactive logic doesn't trigger
                try:
                    self._last_user_speech = time.monotonic()
                except Exception:
                    pass
        except Exception as e:
            print(f"[FRIDAY] _send_pending_and_user error: {e}")

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def interrupt(self) -> None:
        """Stop Friday mid-speech: drain queued audio and open mic immediately."""
        self._interrupted = True
        q = self.audio_in_queue
        if q:
            drained = 0
            while True:
                try:
                    q.get_nowait()
                    drained += 1
                except Exception:
                    break
            if drained:
                    print(f"[FRIDAY] ✋ Interrupted — {drained} audio chunks discarded")
        self.set_speaking(False)
        if self._turn_done_event:
            self._turn_done_event.clear()
        self.ui.write_log("SYS: Interrupted — listening...")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _build_config(self, voice_name: str | None = None) -> types.LiveConnectConfig:
        from datetime import datetime

        # Load customization from config
        try:
            _cfg = json.loads(open(API_CONFIG_PATH, encoding="utf-8").read())
            self._asst_name = (_cfg.get("assistant_name") or "Friday").strip()
            _user_name = (_cfg.get("user_name") or "").strip()
        except Exception:
            self._asst_name = "Friday"
            _user_name = ""
            _cfg = {}

        memory     = load_memory() if _cfg.get("memory_enabled", True) else {}
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()
        personalization_ctx = _build_personalization_context(_cfg)

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        _user_name = (_cfg.get("user_name") or "").strip()
        memory_name = (
            memory.get("identity", {}).get("name", {}).get("value")
            if isinstance(memory.get("identity", {}).get("name"), dict) else None
        )
        preferred_name = memory.get("preferences", {}).get("address_user_as", {}).get("value")
        if isinstance(preferred_name, str):
            preferred_name = preferred_name.strip() or None
        if memory_name and not preferred_name:
            preferred_name = memory_name.strip()
        if preferred_name and not _user_name:
            _user_name = preferred_name

        preferred_language = memory.get("identity", {}).get("language", {}).get("value")
        if isinstance(preferred_language, str):
            preferred_language = preferred_language.strip() or None
        configured_language = str(_cfg.get("preferred_language", "Auto") or "Auto").strip()
        if configured_language and configured_language.lower() != "auto":
            preferred_language = configured_language
        if preferred_language and preferred_language.lower() in {"hinglish", "hindi-english", "hindi english"}:
            preferred_language = "Hinglish"

        relationship_tone = memory.get("preferences", {}).get("relationship_tone", {}).get("value")
        if isinstance(relationship_tone, str):
            relationship_tone = relationship_tone.strip() or None

        conversation_style = memory.get("preferences", {}).get("conversation_style", {}).get("value")
        if isinstance(conversation_style, str):
            conversation_style = conversation_style.strip() or None

        if _user_name:
            _addr = f"ADDRESS: Always call the user '{_user_name}'. Never call them sir."
        else:
            _addr = (
                "ADDRESS: Always speak in Hinglish — use Hindi naturally, and only use English when a Hindi word is hard to spell or creates a barrier. "
                "Always call the user by name and never use sir."
            )

        if preferred_language:
            _addr += f" Always speak in {preferred_language}."
        if relationship_tone:
            _addr += f" {relationship_tone}."
        if conversation_style:
            _addr += f" {conversation_style}."

        identity_ctx = (
            f"[IDENTITY]\n"
            f"Your name is {self._asst_name}. "
            f"Always refer to yourself as {self._asst_name}.\n"
            f"{_addr}\n\n"
        )

        parts = [time_ctx, sys_prompt]
        if mem_str:
            parts.append(mem_str)
        parts.append(identity_ctx)
        if personalization_ctx:
            parts.append(personalization_ctx)

        speech_config = self._build_speech_config(voice_name)
        print(f"[FRIDAY] Voice config: {speech_config}")

        try:
            voice_speed = float(_cfg.get("voice_speed", 1.0) or 1.0)
        except (TypeError, ValueError):
            voice_speed = 1.0
        try:
            voice_pitch = int(_cfg.get("voice_pitch", 0) or 0)
        except (TypeError, ValueError):
            voice_pitch = 0
        voice_guidance = (
            "[VOICE PREFERENCES]\n"
            f"Speak at approximately {max(0.7, min(1.3, voice_speed)):.2f}x normal speed. "
            f"Use a {'slightly higher' if voice_pitch > 0 else 'slightly lower' if voice_pitch < 0 else 'natural'} pitch.\n"
        )

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts + [voice_guidance]),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=speech_config,
        )

    def _build_speech_config(self, voice_name: str | None = None) -> types.SpeechConfig:
        if voice_name:
            return types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name,
                    )
                )
            )
        return types.SpeechConfig()

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[FRIDAY] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "screen_process":
                import time as _t_mod
                _now = _t_mod.monotonic()
                _cooldown = 4.0  # seconds — covers echo window after speaking ends
                if self._vision_busy or (_now - self._vision_last_time) < _cooldown:
                    _wait = max(0, _cooldown - (_now - self._vision_last_time))
                    print(f"[Vision] ⏳ Cooldown active ({_wait:.1f}s remaining) — ignoring duplicate call")
                    result = "Vision is still processing the previous request. I will not call this again."
                else:
                    self._vision_busy      = True
                    self._vision_last_time = _now
                    angle     = args.get("angle", "screen").lower()
                    user_text = args.get("text", "What do you see?")
                    if angle == "camera":
                        img_b, mime_t = await loop.run_in_executor(None, _capture_camera)
                        self.ui.start_camera_stream()
                        self._vision_cam_active = True
                        print(f"[Vision] 📷 Camera: {len(img_b):,} bytes")
                        _stall = "camera"
                    else:
                        img_b, mime_t = await loop.run_in_executor(None, _capture_screen)
                        print(f"[Vision] 🖥️  Screen: {len(img_b):,} bytes")
                        _stall = "screen"
                    self._pending_vision = (img_b, mime_t, user_text, angle)
                    result = (
                        f"[VISION_ACTIVE] {_stall.capitalize()} captured. "
                        f"Immediately say ONE short natural sentence in the user's own language, "
                        f"telling them you are looking at their {_stall} right now. "
                        f"Do NOT describe or guess content — the actual image arrives in the NEXT message."
                    )

            elif name == "close_camera":
                self.ui.stop_camera_stream()
                result = "Camera closed."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."
                # Mirror results to the on-screen content panel
                _mode = args.get("mode", "search")
                if r and not r.startswith("No results") and not r.startswith("Search failed"):
                    _query = args.get("query") or ", ".join(args.get("items", []))
                    _label = f"{_mode.upper()} — {_query[:38]}" if _query else _mode.upper()
                    self.ui.show_content(_label, r)
            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                r = await loop.run_in_executor(
                    None,
                    lambda: file_processor(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "computer_control":
                # Require admin flag to be enabled before performing broad system actions.
                action = (args.get("action") or "").lower()
                destructive_actions = {
                    "delete", "delete_file", "remove", "install", "run_shell",
                    "shutdown", "format", "install_package", "pip_install",
                }

                if not is_admin_enabled():
                    result = (
                        "Admin actions are disabled. To enable, run the 'enable_admin' command."
                    )
                else:
                    # If the action is potentially destructive, require an explicit confirm flag
                    if action in destructive_actions and not args.get("confirm"):
                        result = (
                            f"Action '{action}' looks destructive. To proceed, re-run the command with 'confirm': true"
                        )
                    else:
                        r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                        result = r or "Done."

            elif name == "enable_admin":
                # Start a typed confirmation flow: produce a short token saved in memory.
                import random, string

                token = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                update_memory({"preferences": {"admin_pending_token": {"value": token}}})
                result = (
                    "Admin enable requested. To confirm, run: enable_admin_confirm with token=<token> "
                    f"(example: enable_admin_confirm token={token})"
                )

            elif name == "enable_admin_confirm":
                token = args.get("token") or args.get("code") or ""
                mem = load_memory()
                pending = mem.get("preferences", {}).get("admin_pending_token", {}).get("value")
                if token and pending and str(token) == str(pending):
                    set_admin_enabled(True)
                    # clear pending token
                    update_memory({"preferences": {"admin_pending_token": {"value": ""}}})
                    result = "Admin enabled. Friday can now perform system actions."
                else:
                    result = "Token mismatch or not found. Run 'enable_admin' to request a new confirmation token."

            elif name == "recall_sessions":
                # Return stored full session transcripts (recent first)
                try:
                    sessions = get_all_sessions_full(limit=10)
                    if not sessions:
                        result = "No past conversations found."
                    else:
                        parts = []
                        for s in sessions:
                            date = s.get("date", "unknown date")
                            summary = s.get("summary", "")
                            transcript = s.get("transcript", "").strip()
                            header = f"--- {date} — {summary} ---"
                            parts.append(header + "\n" + (transcript or "(no transcript)"))
                        result = "\n\n".join(parts)
                except Exception as e:
                    result = f"Failed to retrieve sessions: {e}"

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "system_status":
                r = await loop.run_in_executor(None, get_system_status)
                result = str(r)

            elif name == "manage_monitor":
                action = args.get("action", "").lower().strip()
                topic  = args.get("topic", "").strip()
                if action == "add" and topic:
                    result = await asyncio.to_thread(add_monitor, topic)
                elif action == "remove" and topic:
                    result = await asyncio.to_thread(remove_monitor, topic)
                elif action == "list":
                    topics = await asyncio.to_thread(list_monitors)
                    result = ("Monitoring: " + ", ".join(topics)) if topics else "No topics are being monitored."
                else:
                    result = "Specify action (add/remove/list) and a topic."

            elif name == "shutdown_friday":
                self.ui.write_log("SYS: Shutdown requested.")
                async def _do_shutdown():
                    await self._save_session_summary()
                    if self.session:
                        try:
                            await self.session.send_client_content(
                                turns={"parts": [{"text": "Say a brief natural goodbye to the user."}]},
                                turn_complete=True,
                            )
                        except Exception:
                            pass
                    await asyncio.sleep(1.5)
                    import os as _os
                    _os._exit(0)
                asyncio.create_task(_do_shutdown())

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[FRIDAY] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[Friday] 🎤 Mic started")
        loop = asyncio.get_event_loop()

        def enqueue_audio(data: bytes) -> None:
            """Keep capture real-time when the network temporarily falls behind."""
            try:
                self.out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
            except asyncio.QueueFull:
                # Old audio is no longer useful for a live conversation.
                pass

        def callback(indata, frames, time_info, status):
            if status:
                print(f"[FRIDAY] Mic status: {status}")
            with self._speaking_lock:
                friday_speaking = self._is_speaking
            if not friday_speaking and not self.ui.muted and not self._phone_active:
                if indata.ndim > 1 and indata.shape[1] > 1:
                    data = indata[:, 0].tobytes()
                else:
                    data = indata.tobytes()
                loop.call_soon_threadsafe(enqueue_audio, data)

        # Do not open an input device until the user enables the mic. This is
        # when the operating system shows its native microphone permission UI.
        # Permission/device failures remain recoverable and never disconnect
        # the Gemini Live session.
        while True:
            while self.ui.muted:
                self.ui.set_microphone_status("off")
                await asyncio.sleep(0.2)
            try:
                input_dev = sd.query_devices(kind="input")
                max_input_channels = input_dev.get("max_input_channels", 0)
                if max_input_channels < 1:
                    raise RuntimeError("No input audio device available.")
                actual_channels = min(CHANNELS, max_input_channels)
                print(
                    f"[FRIDAY] Mic device: {input_dev.get('name')} "
                    f"(max_input_channels={max_input_channels}, using={actual_channels})"
                )
                with sd.InputStream(
                    samplerate=SEND_SAMPLE_RATE,
                    channels=actual_channels,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                    callback=callback,
                ):
                    print("[FRIDAY] 🎤 Mic stream open")
                    self.ui.set_microphone_status("listening")
                    while not self.ui.muted:
                        await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                detail = str(e) or "The operating system did not provide a microphone."
                print(f"[FRIDAY] ❌ Mic: {detail}")
                self.ui.set_microphone_status(
                    "error",
                    "Microphone unavailable. Allow microphone access in system privacy settings, then try again. " + detail,
                )
                # Avoid repeatedly triggering device drivers/permission prompts.
                for _ in range(25):
                    if self.ui.muted:
                        break
                    await asyncio.sleep(0.2)

    async def _receive_audio(self):
        print("[Friday] 👂 Recv started")
        out_buf, in_buf = [], []
        out_buf_raw, in_buf_raw = [], []

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        if self._interrupted:
                            pass  # discard: interrupted
                        else:
                            if self._turn_done_event and self._turn_done_event.is_set():
                                self._turn_done_event.clear()
                            # Split into ~50 ms chunks so interrupt() stops audio within 50 ms
                            # (24000 Hz × 2 bytes/sample × 0.05 s = 2400 bytes per slice)
                            _audio_data = response.data
                            _SLICE = 2400
                            for _i in range(0, len(_audio_data), _SLICE):
                                self.audio_in_queue.put_nowait(_audio_data[_i : _i + _SLICE])

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            raw_txt_out = sc.output_transcription.text or ""
                            txt = _clean_transcript(raw_txt_out)
                            if raw_txt_out and raw_txt_out != (out_buf_raw[-1] if out_buf_raw else ""):
                                out_buf_raw.append(raw_txt_out)
                            if txt and txt != (out_buf[-1] if out_buf else ""):
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            raw_txt_in = sc.input_transcription.text or ""
                            txt = _clean_transcript(raw_txt_in)
                            if raw_txt_in:
                                in_buf_raw.append(raw_txt_in)
                            if txt:
                                in_buf.append(txt)
                                self._last_user_speech = time.monotonic()

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            # If this turn_complete ends an interrupted response, clear the
                            # flag and skip all further processing for that turn.
                            if self._interrupted:
                                self._interrupted = False
                                in_buf  = []
                                out_buf = []
                                continue

                            full_in = " ".join(in_buf).strip()
                            full_in_raw = " ".join(in_buf_raw).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                                self._session_log.append(f"User: {full_in}")
                                if self._dashboard:
                                    asyncio.create_task(self._dashboard.broadcast({
                                        "type": "log", "speaker": "user",
                                        "text": full_in,
                                        "ts": datetime.now().isoformat(),
                                    }))
                            if full_in_raw:
                                self._session_raw_log.append(f"User: {full_in_raw}")
                            in_buf = []
                            in_buf_raw = []

                            full_out = " ".join(out_buf).strip()
                            full_out_raw = " ".join(out_buf_raw).strip()
                            if full_out:
                                self.ui.write_log(f"{self._asst_name}: {full_out}")
                                self._session_log.append(f"{self._asst_name}: {full_out}")
                                if self._dashboard:
                                    asyncio.create_task(self._dashboard.broadcast({
                                        "type": "log", "speaker": "friday",
                                        "text": full_out,
                                        "ts": datetime.now().isoformat(),
                                    }))
                            if full_out_raw:
                                self._session_raw_log.append(f"{self._asst_name}: {full_out_raw}")
                            out_buf = []
                            out_buf_raw = []

                            # Vision injection: model finished tool-response turn → now send the image
                            if self._pending_vision and self.session:
                                import base64 as _b64
                                img_b, mime_t, question, angle = self._pending_vision
                                self._pending_vision = None
                                b64 = _b64.b64encode(img_b).decode("ascii")
                                print(f"[Vision] 📤 {len(img_b):,} bytes (angle={angle}) → main session")
                                await self.session.send_client_content(
                                    turns={"parts": [
                                        {"inline_data": {"mime_type": mime_t, "data": b64}},
                                        {"text": question},
                                    ]},
                                    turn_complete=True,
                                )
                                # Mark next turn_complete behaviour depending on angle
                                if self._vision_cam_active:
                                    # Camera: keep busy until Friday finishes speaking the answer
                                    self._vision_cam_active    = False
                                    self._vision_close_pending = True
                                else:
                                    # Screen-only: no camera to close; release busy flag now
                                    self._vision_busy = False
                            elif self._vision_close_pending:
                                # This turn_complete IS the vision answer — close camera + release busy flag
                                self._vision_close_pending = False
                                self._vision_busy = False
                                async def _cam_close():
                                    await asyncio.sleep(2.0)
                                    self.ui.stop_camera_stream()
                                asyncio.create_task(_cam_close())

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[FRIDAY] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
        except Exception as e:
            print(f"[FRIDAY] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[Friday] 🔊 Play started")

        try:
            _playback_cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
            _output_volume = float(_playback_cfg.get("voice_volume", 1.0) or 1.0)
        except Exception:
            _output_volume = 1.0
        _output_volume = max(0.0, min(1.0, _output_volume))

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue

                self.set_speaking(True)

                # Batch all immediately-available chunks into one write to reduce
                # thread-pool round-trips (was one asyncio.to_thread per 50ms slice).
                # Cap at ~200 ms so interrupt() still stops audio within ~200 ms.
                batch = bytearray(chunk)
                while len(batch) < 9600:   # 9600 bytes ≈ 200 ms at 24 kHz / 16-bit mono
                    try:
                        batch.extend(self.audio_in_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                try:
                    output = bytes(batch)
                    if _output_volume != 1.0:
                        samples = np.frombuffer(output, dtype=np.int16).astype(np.float32)
                        samples *= _output_volume
                        output = np.clip(samples, -32768, 32767).astype(np.int16).tobytes()
                    await asyncio.to_thread(stream.write, output)
                except (RuntimeError, asyncio.CancelledError):
                    break   # executor shutting down — exit cleanly
        except Exception as e:
            print(f"[FRIDAY] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    # ── Morning briefing ────────────────────────────────────────────────────────

    async def _send_startup_briefing(self) -> None:
        """
        Two-phase briefing optimized for speed:
          Phase 1 — instant greeting (no tools) → speech starts in <1s
          Phase 2 — news pre-fetched in a background thread while Phase 1 plays,
                    delivered as ready text (no Gemini tool-call round-trip) and
                    shown on the UI content panel. Waits for turn_complete event
                    instead of a fixed sleep so there is no unnecessary gap.
        """
        memory   = load_memory()
        identity = memory.get("identity", {})

        def _val(k: str) -> str:
            e = identity.get(k, {})
            return (e.get("value", "") if isinstance(e, dict) else str(e)).strip()

        lang = _val("language")
        name = _val("name")
        time_str = datetime.now().strftime("%H:%M")

        # We will only send a warm, feminine greeting here and skip automatically
        # fetching or delivering news. The user prefers a single greeting that
        # feels like talking with a girl, so keep it short and personal.
        await asyncio.sleep(0.2)
        if not self.session:
            return

        # Prepare feminine, Hinglish-friendly greeting
        lang_clause = f" Respond in {lang}." if lang else ""
        name_clause = f" Address the user as {name}." if name else ""

        # Consume the last session only when it is about to be included in the
        # greeting. This guarantees a recap is mentioned once, then never
        # repeated on a later morning/startup.
        from memory.memory_manager import pop_last_session
        last = await asyncio.to_thread(pop_last_session)
        session_clause = ""
        if last:
            # Prefer exact timestamp when available (added by memory_manager)
            ts = last.get("timestamp") or last.get("iso")
            if ts:
                # Try to parse the timestamp into a datetime for relative phrasing
                t_dt = None
                try:
                    t_dt = datetime.fromisoformat(ts)
                except Exception:
                    try:
                        t_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        t_dt = None

                if t_dt:
                    now_dt = datetime.now()
                    days = (now_dt.date() - t_dt.date()).days
                    time_part = t_dt.strftime("%H:%M:%S")
                    if days == 0:
                        rel = f"earlier today at {time_part}"
                    elif days == 1:
                        rel = f"yesterday at {time_part}"
                    elif days < 7:
                        rel = f"{days} days ago at {time_part}"
                    else:
                        rel = f"on {t_dt.strftime('%Y-%m-%d')} at {time_part}"
                    # include exact timestamp alongside the friendly phrase
                    _when = f"{rel} ({t_dt.strftime('%Y-%m-%d %H:%M:%S')})"
                else:
                    _when = ts
            else:
                try:
                    _delta = (datetime.now() - datetime.strptime(last["date"], "%Y-%m-%d")).days
                    _when  = "earlier today" if _delta == 0 else ("yesterday" if _delta == 1 else f"{_delta} days ago")
                except Exception:
                    _when = "last time"
            session_clause = f" Also mention naturally that {_when}: {last.get('summary', '')}"

        profile = load_personalization()
        configured_name = str(profile.get("user_name") or name or "there").strip()
        welcome = str(profile.get("welcome_message") or "").strip()
        p1 = (
            f"Automatically greet the user now. {welcome} "
            f"Address them as {configured_name}, mention the current time is {time_str}, "
            f"and naturally recap the previous conversation only when supplied below. "
            f"Keep it to 1-2 short sentences. Do not call any tools.{lang_clause}{name_clause} {session_clause}"
        )

        # Speak immediately after the Live connection is ready. This makes
        # opening the app feel alive while the sent/consumed flags prevent a
        # reconnect from greeting or recapping again.
        try:
            if self._greeting_state == "sent":
                self.ui.write_log("SYS: Startup greeting already spoken this session.")
            else:
                await self.session.send_client_content(
                    turns={"parts": [{"text": p1}]}, turn_complete=True,
                )
                self._pending_startup_greeting = None
                self._greeting_state = "sent"
                self.ui.write_log("SYS: Startup greeting sent.")
        except Exception as e:
            print(f"[FRIDAY] Could not queue briefing: {e}")

    # ── Session memory ──────────────────────────────────────────────────────────

    async def _save_session_summary(self) -> None:
        """Summarise the current session in 1-2 sentences and save to long_term.json."""
        log = self._session_log
        if len(log) < 1:          # if no exchanges, nothing to save
            return
        # copy and reset immediately so next session starts fresh
        convo_lines = list(log)
        self._session_log = []

        memory = load_memory()
        lang_entry = memory.get("identity", {}).get("language", {})
        lang = (lang_entry.get("value", "") if isinstance(lang_entry, dict) else str(lang_entry)).strip()
        lang = lang or "English"

        convo = "\n".join(convo_lines[-1000:])   # cleaned transcript for summary
        # also capture the raw transcript (exact chat) when available
        raw_lines = list(self._session_raw_log) if hasattr(self, '_session_raw_log') else []
        self._session_raw_log = []
        convo_raw = "\n".join(raw_lines[-10000:])
        # attempt to generate a short summary using existing helper; fall back to first 2 lines
        summary = None
        try:
            prompt = (
                f"Summarize this conversation in 1-2 sentences in {lang}. "
                "Focus on what the user accomplished or discussed. "
                "Output ONLY the summary text, nothing else:\n\n" + convo
            )
            summary = await self._call_extractive_summary(prompt)
            if summary:
                summary = summary.strip().replace("\n", " ")
        except Exception:
            summary = "Conversation saved."

        try:
            # store the exact raw transcript; fall back to cleaned convo if raw not available
            append_session_transcript(summary or "", convo_raw or convo, lang)
        except Exception as e:
            print(f"[FRIDAY] Failed saving full transcript: {e}")
            return
        self._session_log = []    # reset immediately so the next session starts clean

    # ── System monitor ──────────────────────────────────────────────────────────

    async def _run_system_monitor(self) -> None:
        """Background task: voice alerts when metrics exceed thresholds."""
        while True:
            await asyncio.sleep(10)
            alert = await asyncio.to_thread(self._sys_monitor.check)
            if not alert or not self.session:
                continue
            # Don't interrupt an active conversation
            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking or (time.monotonic() - self._last_user_speech) < 10:
                continue
            try:
                await self.session.send_client_content(
                    turns={"parts": [{"text": alert}]},
                    turn_complete=True,
                )
            except Exception as e:
                print(f"[Monitor] ⚠️ Could not send alert: {e}")

    # ── Background monitor ──────────────────────────────────────────────────────

    async def _run_background_monitor(self) -> None:
        """Check user-configured topics once per day; speak alerts when new headlines appear."""
        await asyncio.sleep(300)          # wait 5 min after startup before first check
        while True:
            if self.session:
                # Don't interrupt if user spoke recently or Friday is mid-sentence
                with self._speaking_lock:
                    speaking = self._is_speaking
                recent_speech = (time.monotonic() - self._last_user_speech) < 30
                if not speaking and not recent_speech:
                    try:
                        alerts = await asyncio.to_thread(monitor_check_all)
                        memory = load_memory()
                        lang_e = memory.get("identity", {}).get("language", {})
                        lang   = (lang_e.get("value", "") if isinstance(lang_e, dict) else str(lang_e)).strip() or "English"
                        for alert in alerts:
                            msg = (
                                f"{alert}\n\n"
                                f"Inform the user about this development naturally in {lang}. "
                                "One brief sentence only."
                            )
                            await self.session.send_client_content(
                                turns={"parts": [{"text": msg}]},
                                turn_complete=True,
                            )
                            self.ui.write_log(f"SYS: Monitor alert sent.")
                            await asyncio.sleep(6)   # gap between consecutive alerts
                    except Exception as e:
                        print(f"[Monitor] ⚠️ Background check error: {e}")
            await asyncio.sleep(1800)     # check every 30 minutes

    # ── Proactive mode ──────────────────────────────────────────────────────────

    async def _run_proactive_mode(self) -> None:
        """
        Background task: periodically checks if the user has been silent long enough,
        then hands time + memory context to Gemini so it can decide what (if anything)
        to say proactively. No hardcoded rules — Gemini makes the call.
        """
        while True:
            await asyncio.sleep(60)   # evaluate once per minute

            if not self.session:
                continue

            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking:
                continue

            if not self._proactive.should_trigger(self._last_user_speech):
                continue

            self._proactive.mark_triggered()

            try:
                memory       = await asyncio.to_thread(load_memory)
                monitors     = await asyncio.to_thread(list_monitors)
                recent_turns = self._session_log[-8:] if self._session_log else []
                prompt = self._proactive.build_prompt(
                    memory       = memory,
                    monitors     = monitors or None,
                    recent_turns = recent_turns or None,
                )
                await self.session.send_client_content(
                    turns={"parts": [{"text": prompt}]},
                    turn_complete=True,
                )
                self.ui.write_log("SYS: Proactive check-in.")
            except Exception as e:
                print(f"[Proactive] ⚠️ {e}")

    # ── Phone audio relay ────────────────────────────────────────────────────────

    async def _relay_phone_audio(self) -> None:
        """Forward phone mic PCM chunks from dashboard queue into the Gemini Live session."""
        q = self._dashboard._phone_audio_queue
        while True:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # No audio for 1 s → phone mic inactive, give PC mic back
                self._phone_active = False
                continue
            self._phone_active = True   # phone is streaming — silence PC mic
            with self._speaking_lock:
                speaking = self._is_speaking
            if not speaking and not self.ui.muted:
                try:
                    self.out_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass

    def _on_phone_connected(self) -> None:
        self.ui.write_log("SYS: Phone connected via Remote Dashboard.")
        self.ui.notify_phone_connected()

    # ── dashboard command relay ─────────────────────────────────────────────

    async def _process_dashboard_commands(self) -> None:
        while True:
            try:
                text = await asyncio.wait_for(
                    self._dashboard._command_queue.get(), timeout=0.5
                )
                if not text:
                    continue
                # Wait up to 8s for session to become ready after a wake
                for _ in range(80):
                    if self.session:
                        break
                    await asyncio.sleep(0.1)
                if self.session:
                    await self._send_pending_and_user(text)
                    self.ui.write_log(f"[Web]: {text}")
                else:
                    print(f"[Dashboard] Dropped command (no session): {text}")
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"[Dashboard] Command error: {e}")
                await asyncio.sleep(0.5)

    # ── main loop ───────────────────────────────────────────────────────────

    async def run(self):
        self._loop = asyncio.get_event_loop()

        # Start dashboard (optional — needs: pip install fastapi "uvicorn[standard]" cryptography)
        try:
            from dashboard.server import DashboardServer
            self._dashboard = DashboardServer()
            self._dashboard.set_connect_callback(self._on_phone_connected)
            asyncio.create_task(self._dashboard.serve())
            # Runs for the whole lifetime, not just inside an active session
            asyncio.create_task(self._process_dashboard_commands())
        except Exception as e:
            print(f"[Dashboard] Disabled: {e}")
            self._dashboard = None

        current_voice_name = get_voice_name()
        while True:
            try:
                print("[Friday] Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config(current_voice_name)

                # Fresh client on every reconnect — avoids stale HTTP session state
                client = genai.Client(
                    api_key=_get_api_key(),
                    http_options={"api_version": "v1beta"}
                )

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session          = session
                    self.audio_in_queue   = asyncio.Queue()
                    self.out_queue        = asyncio.Queue(maxsize=200)
                    self._turn_done_event = asyncio.Event()

                    # Reset transient state that must not carry over from a previous session
                    self._pending_vision       = None
                    self._vision_cam_active    = False
                    self._vision_close_pending = False
                    self._vision_busy          = False
                    self._vision_last_time     = 0.0
                    self._interrupted          = False

                    print("[Friday] Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: Friday online.")

                    # Greet based on last login and record this login
                    try:
                        memory = load_memory()
                        last_login = get_last_login()
                        if last_login:
                            try:
                                prev = datetime.strptime(last_login, "%Y-%m-%d %H:%M:%S")
                                days = (datetime.now() - prev).days
                                if days == 0:
                                    greet = f"Welcome back, {memory.get('preferences', {}).get('address_user_as', {}).get('value', 'friend')}! We already chatted today."
                                elif days == 1:
                                    greet = f"Long time no see, {memory.get('preferences', {}).get('address_user_as', {}).get('value', 'friend')} — you last interacted with me yesterday."
                                else:
                                    greet = f"Welcome back, {memory.get('preferences', {}).get('address_user_as', {}).get('value', 'friend')} — you last interacted {days} days ago."
                            except Exception:
                                greet = f"Welcome back, {memory.get('preferences', {}).get('address_user_as', {}).get('value', 'friend')}!"
                        else:
                            profile = load_personalization()
                            welcome = str(profile.get("welcome_message") or "").strip()
                            greet = welcome or (
                                f"Hello, {memory.get('preferences', {}).get('address_user_as', {}).get('value', 'friend')}! Nice to see you."
                            )

                        # The dedicated startup task speaks a single greeting as
                        # soon as the connection is ready. Keep this branch only
                        # for diagnostic state; do not queue a second greeting.
                        try:
                            if self._greeting_state == "sent":
                                self.ui.write_log("SYS: Greeting already spoken this session; skipping queue.")
                            else:
                                self.ui.write_log("SYS: Preparing automatic startup greeting.")
                        except Exception:
                            print(f"[FRIDAY] Could not queue greeting: {greet}")

                        # Ensure assistant persona and admin flags are set
                        prefs = memory.get("preferences", {})
                        if not prefs.get("assistant_gender"):
                            set_assistant_gender("female")
                        if not prefs.get("admin_enabled"):
                            set_admin_enabled(True)

                        # Record this login timestamp
                        record_login()
                    except Exception as _e:
                        print(f"[FRIDAY] Greeting/login record error: {_e}")

                    if self._dashboard:
                        await self._dashboard.broadcast({"type": "status", "state": "active"})

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    tg.create_task(self._run_system_monitor())
                    tg.create_task(self._run_background_monitor())
                    tg.create_task(self._run_proactive_mode())
                    if self._dashboard:
                        tg.create_task(self._relay_phone_audio())

                    # Startup greeting — fires once per process launch.
                    if not self._briefing_sent:
                        self._briefing_sent = True
                        tg.create_task(self._send_startup_briefing())

            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except BaseException as e:
                # Catches both Exception and BaseExceptionGroup (Python 3.11+
                # TaskGroup raises BaseExceptionGroup when tasks are cancelled
                # externally, which `except Exception` would miss, letting the
                # exception escape the while-loop and causing asyncio.run() to
                # start shutdown — resulting in "executor after shutdown" errors).
                err_str = str(e)
                print(f"[FRIDAY] Error ({type(e).__name__}): {e}")
                traceback.print_exc()

                # Normalize error text once for downstream checks
                err_lower = err_str.lower()

                # Unsupported voice or model-specific voice mismatch — retry without explicit voice config
                if "requested voice api_name" in err_lower and current_voice_name:
                    print(f"[FRIDAY] Voice '{current_voice_name}' not supported by model; retrying without explicit voice config.")
                    self.ui.write_log("WARN: Configured voice is unavailable for this Gemini model. Falling back to default voice.")
                    current_voice_name = None
                    continue

                # Model doesn't accept audio content type (some preview models) — retry without sending audio config
                if "audio content type" in err_lower or "content type audio" in err_lower:
                    print("[FRIDAY] Model rejected CONTENT_TYPE_AUDIO; retrying without explicit speech/audio config.")
                    self.ui.write_log("WARN: Gemini model does not support audio content for this configuration. Falling back to non-audio mode.")
                    current_voice_name = None
                    continue

                # Invalid API key — stop hammering the API, prompt re-configuration
                is_invalid_key = (
                    "api key not valid" in err_lower
                    or "invalid api key" in err_lower
                    or "api key invalid" in err_lower
                    or "request had invalid authentication credentials" in err_lower
                )
                if is_invalid_key:
                    env_key, config_key = get_gemini_key_sources()
                    if env_key and config_key and env_key != config_key:
                        self.ui.write_log("WARN: Environment API key failed. Retrying with config file key.")
                        print("[FRIDAY] Invalid env API key detected; retrying with config/api_keys.json key.")
                        try:
                            client = genai.Client(api_key=_get_api_key(use_config_first=True), http_options={"api_version": "v1beta"})
                            continue
                        except Exception as retry_e:
                            print(f"[FRIDAY] Retry using config key also failed: {retry_e}")
                            err_str = str(retry_e)

                    self.ui.write_log("ERR: API key invalid — please re-enter your key.")
                    self.ui.set_state("SLEEPING")
                    self.ui.prompt_reconfig()
                    while not self.ui._win._ready:
                        await asyncio.sleep(1)
                    print("[FRIDAY] New API key saved — reconnecting...")
                    _conn_backoff = 3
                    continue

                # Network / timeout errors — log clearly and back off
                is_net_err = any(k in err_str for k in (
                    "TimeoutError", "timed out", "getaddrinfo", "CancelledError",
                    "ConnectionRefusedError", "OSError", "Cannot connect",
                ))
                if is_net_err:
                    _conn_backoff = min(getattr(self, "_conn_backoff", 3) * 2, 60)
                    self._conn_backoff = _conn_backoff
                    self.ui.write_log(
                        f"NET: Bağlantı kurulamadı — {_conn_backoff}s sonra tekrar deneniyor. "
                        "(VPN gerekiyor olabilir)"
                    )
                else:
                    self._conn_backoff = 3
            finally:
                self.session = None
                # Preserve even short conversations so the next startup can
                # naturally acknowledge what the user last discussed.
                if self._session_log:
                    asyncio.create_task(self._save_session_summary())

            self.set_speaking(False)
            self.ui.set_state("SLEEPING")

            if self._dashboard:
                await self._dashboard.broadcast({"type": "status", "state": "sleeping"})

            delay = getattr(self, "_conn_backoff", 3)
            print(f"[FRIDAY] Reconnecting in {delay}s...")
            await asyncio.sleep(delay)

def main():
    ui = FridayUI("face.png")

    def runner():
        ui.wait_for_api_key()
        friday = FridayLive(ui)
        try:
            asyncio.run(friday.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()

if __name__ == "__main__":
    main()
