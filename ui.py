from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

if platform.system() == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QDragEnterEvent, QDropEvent, QFont,
    QFontDatabase, QKeySequence, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget, QProgressBar, QComboBox,
    QSlider, QCheckBox,
)

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"


def _read_full_config() -> dict:
    """Read api_keys.json config dict. Returns {} on any error."""
    try:
        return json.loads(API_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


_DEFAULT_W, _DEFAULT_H = 980, 700
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 148
_RIGHT_W = 340

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


class C:
    BG        = "#00060a"
    PANEL     = "#010d14"
    PANEL2    = "#010f18"
    BORDER    = "#0d3347"
    BORDER_B  = "#1a5c7a"
    BORDER_A  = "#0f4060"
    PRI       = "#00d4ff"
    PRI_DIM   = "#007a99"
    PRI_GHO   = "#001f2e"
    ACC       = "#ff6b00"
    ACC2      = "#ffcc00"
    GREEN     = "#00ff88"
    GREEN_D   = "#00aa55"
    RED       = "#ff3355"
    MUTED_C   = "#ff3366"
    TEXT      = "#8ffcff"
    TEXT_DIM  = "#3a8a9a"
    TEXT_MED  = "#5ab8cc"
    WHITE     = "#d8f8ff"
    DARK      = "#000d14"
    BAR_BG    = "#011520"


# Ana renge (accent) bağlı anahtarlar — durum renkleri (ACC, GREEN, RED…) sabit kalır
_HUE_LINKED = (
    "BG", "PANEL", "PANEL2", "BORDER", "BORDER_B", "BORDER_A",
    "PRI", "PRI_DIM", "PRI_GHO", "TEXT", "TEXT_DIM", "TEXT_MED",
    "WHITE", "DARK", "BAR_BG",
)
_PALETTE_DEFAULTS: dict[str, str] = {k: getattr(C, k) for k in _HUE_LINKED}

_THEME_COLOR_KEYS = (
    "BG", "PANEL", "PANEL2", "BORDER", "BORDER_B", "BORDER_A",
    "PRI", "PRI_DIM", "PRI_GHO", "ACC", "ACC2", "GREEN", "GREEN_D",
    "RED", "MUTED_C", "TEXT", "TEXT_DIM", "TEXT_MED", "WHITE", "DARK",
    "BAR_BG",
)

_THEMES: dict[str, dict[str, str]] = {
    "Dark": {key: getattr(C, key) for key in _THEME_COLOR_KEYS},
    "Light": {
        "BG": "#edf3f8", "PANEL": "#ffffff", "PANEL2": "#f5f8fb", "BORDER": "#c8d5e0", "BORDER_B": "#8aa6ba", "BORDER_A": "#a9bdcc", "PRI": "#0077b6", "PRI_DIM": "#4b7894", "PRI_GHO": "#dceef8", "ACC": "#c2410c", "ACC2": "#a16207", "GREEN": "#16803c", "GREEN_D": "#277a46", "RED": "#c62845", "MUTED_C": "#b4234b", "TEXT": "#15334a", "TEXT_DIM": "#5d7486", "TEXT_MED": "#365c75", "WHITE": "#0e2536", "DARK": "#e4edf4", "BAR_BG": "#d4e1eb",
    },
    "AMOLED": {
        "BG": "#000000", "PANEL": "#030303", "PANEL2": "#080808", "BORDER": "#202020", "BORDER_B": "#3c3c3c", "BORDER_A": "#292929", "PRI": "#38d9ff", "PRI_DIM": "#167a91", "PRI_GHO": "#07191f", "ACC": "#ff8a33", "ACC2": "#ffd166", "GREEN": "#45f5a1", "GREEN_D": "#158451", "RED": "#ff4968", "MUTED_C": "#ff4968", "TEXT": "#c9f8ff", "TEXT_DIM": "#5e8e99", "TEXT_MED": "#88c0cc", "WHITE": "#f2fcff", "DARK": "#000000", "BAR_BG": "#0b1114",
    },
    "Glassmorphism": {
        "BG": "#10182d", "PANEL": "#17223c", "PANEL2": "#202c49", "BORDER": "#53647f", "BORDER_B": "#8498b8", "BORDER_A": "#657795", "PRI": "#8dd8ff", "PRI_DIM": "#5f92b6", "PRI_GHO": "#273956", "ACC": "#ffad70", "ACC2": "#ffe18a", "GREEN": "#79edba", "GREEN_D": "#4aab80", "RED": "#ff7d98", "MUTED_C": "#ff7d98", "TEXT": "#d9ecff", "TEXT_DIM": "#93a8bf", "TEXT_MED": "#b3c8dd", "WHITE": "#ffffff", "DARK": "#121c31", "BAR_BG": "#1d2944",
    },
    "Minimal": {
        "BG": "#fafafa", "PANEL": "#ffffff", "PANEL2": "#f4f4f5", "BORDER": "#d4d4d8", "BORDER_B": "#a1a1aa", "BORDER_A": "#c4c4c8", "PRI": "#27272a", "PRI_DIM": "#71717a", "PRI_GHO": "#e4e4e7", "ACC": "#52525b", "ACC2": "#3f3f46", "GREEN": "#3f7d56", "GREEN_D": "#4b6b55", "RED": "#a8404e", "MUTED_C": "#a8404e", "TEXT": "#27272a", "TEXT_DIM": "#71717a", "TEXT_MED": "#52525b", "WHITE": "#18181b", "DARK": "#eeeeef", "BAR_BG": "#dedee0",
    },
    "Gradient": {
        "BG": "#18132f", "PANEL": "#211a42", "PANEL2": "#2b2353", "BORDER": "#514179", "BORDER_B": "#8067ad", "BORDER_A": "#64538c", "PRI": "#bb86fc", "PRI_DIM": "#8f6fbc", "PRI_GHO": "#38285f", "ACC": "#ff8bb7", "ACC2": "#ffd166", "GREEN": "#83efbb", "GREEN_D": "#479b74", "RED": "#ff6b93", "MUTED_C": "#ff6b93", "TEXT": "#e8dbff", "TEXT_DIM": "#a997c8", "TEXT_MED": "#c9b8e4", "WHITE": "#fbf6ff", "DARK": "#17112c", "BAR_BG": "#291f4d",
    },
    "Cyberpunk": {
        "BG": "#10051a", "PANEL": "#180927", "PANEL2": "#240d36", "BORDER": "#5b1f70", "BORDER_B": "#a332b5", "BORDER_A": "#742783", "PRI": "#00f5d4", "PRI_DIM": "#18a893", "PRI_GHO": "#083b39", "ACC": "#ff4da6", "ACC2": "#ffe66d", "GREEN": "#a7ff4f", "GREEN_D": "#67ad31", "RED": "#ff477e", "MUTED_C": "#ff477e", "TEXT": "#d9fff8", "TEXT_DIM": "#8cb8b3", "TEXT_MED": "#a7ddd5", "WHITE": "#ffffff", "DARK": "#12051d", "BAR_BG": "#220c33",
    },
    "Ultron": {
        "BG": "#030201", "PANEL": "#0d0803", "PANEL2": "#160c03", "BORDER": "#5a2d08", "BORDER_B": "#a85a12", "BORDER_A": "#7a3d0a", "PRI": "#ffaa30", "PRI_DIM": "#9b5515", "PRI_GHO": "#321704", "ACC": "#ff6f1a", "ACC2": "#ffcc66", "GREEN": "#ffd35a", "GREEN_D": "#a87824", "RED": "#ff5533", "MUTED_C": "#ff7043", "TEXT": "#ffd98a", "TEXT_DIM": "#9c7040", "TEXT_MED": "#c49755", "WHITE": "#fff0bd", "DARK": "#080402", "BAR_BG": "#1d0e03",
    },
}

# The native app also exposes the five visual identities from friday-ui.
# Their palettes reuse the native color contract so every existing widget can
# retheme without requiring a second stylesheet system.
_FRIDAY_THEME_PALETTES = {
    "Stark HUD": {"BG": "#060913", "PANEL": "#0b1220", "PANEL2": "#111c2e", "BORDER": "#164e63", "BORDER_B": "#00f0ff", "BORDER_A": "#16728a", "PRI": "#00f0ff", "PRI_DIM": "#168ca3", "PRI_GHO": "#082b3b", "ACC": "#ff9900", "ACC2": "#ffd166", "GREEN": "#52ffb8", "GREEN_D": "#24966d", "RED": "#ff5470", "MUTED_C": "#ff5470", "TEXT": "#d0f4ff", "TEXT_DIM": "#6d9aaa", "TEXT_MED": "#a3d3df", "WHITE": "#f5fdff", "DARK": "#050811", "BAR_BG": "#0d1a2b"},
    "Broadsheet Gazette": {"BG": "#faf6ed", "PANEL": "#fffdf7", "PANEL2": "#f1eadc", "BORDER": "#b7aa94", "BORDER_B": "#111111", "BORDER_A": "#8c7d68", "PRI": "#111111", "PRI_DIM": "#675d50", "PRI_GHO": "#e9dfcf", "ACC": "#c2410c", "ACC2": "#8b5e34", "GREEN": "#3f6b4f", "GREEN_D": "#31543e", "RED": "#a52f2f", "MUTED_C": "#8f3e3e", "TEXT": "#1c1917", "TEXT_DIM": "#756b5e", "TEXT_MED": "#50483e", "WHITE": "#171411", "DARK": "#eee5d6", "BAR_BG": "#e1d5c2"},
    "RetroOS 95": {"BG": "#008080", "PANEL": "#c0c0c0", "PANEL2": "#d8d8d8", "BORDER": "#808080", "BORDER_B": "#ffffff", "BORDER_A": "#000000", "PRI": "#000080", "PRI_DIM": "#004040", "PRI_GHO": "#a0a0a0", "ACC": "#800080", "ACC2": "#ffff00", "GREEN": "#008000", "GREEN_D": "#006000", "RED": "#800000", "MUTED_C": "#800000", "TEXT": "#000000", "TEXT_DIM": "#404040", "TEXT_MED": "#202020", "WHITE": "#ffffff", "DARK": "#000040", "BAR_BG": "#a0a0a0"},
    "Nordic Zen": {"BG": "#f7f7f3", "PANEL": "#ffffff", "PANEL2": "#eef0eb", "BORDER": "#d3d8cf", "BORDER_B": "#94a18e", "BORDER_A": "#b7c0b1", "PRI": "#334155", "PRI_DIM": "#64748b", "PRI_GHO": "#e3e8df", "ACC": "#4d7c0f", "ACC2": "#a16207", "GREEN": "#4d7c0f", "GREEN_D": "#52733a", "RED": "#a64b4b", "MUTED_C": "#a64b4b", "TEXT": "#1f2937", "TEXT_DIM": "#728073", "TEXT_MED": "#4b5563", "WHITE": "#17202a", "DARK": "#e9ece5", "BAR_BG": "#dce2d8"},
    "Neon Arcade 1984": {"BG": "#0d0221", "PANEL": "#170637", "PANEL2": "#25094f", "BORDER": "#63218e", "BORDER_B": "#ff007f", "BORDER_A": "#9e2dbe", "PRI": "#ff007f", "PRI_DIM": "#b82d79", "PRI_GHO": "#3d0d55", "ACC": "#00f2fe", "ACC2": "#ffe66d", "GREEN": "#70ffca", "GREEN_D": "#329b7b", "RED": "#ff477e", "MUTED_C": "#ff477e", "TEXT": "#fdf4ff", "TEXT_DIM": "#ad75bd", "TEXT_MED": "#ddaee8", "WHITE": "#ffffff", "DARK": "#0b011b", "BAR_BG": "#20084a"},
    "Astra CryoLab": {"BG": "#050c09", "PANEL": "#07130e", "PANEL2": "#0a1e15", "BORDER": "#164e3b", "BORDER_B": "#10b981", "BORDER_A": "#087f63", "PRI": "#10b981", "PRI_DIM": "#168c70", "PRI_GHO": "#092d22", "ACC": "#06b6d4", "ACC2": "#67e8f9", "GREEN": "#a3e635", "GREEN_D": "#4d8f2a", "RED": "#fb7185", "MUTED_C": "#fb7185", "TEXT": "#ecfdf5", "TEXT_DIM": "#6ee7b7", "TEXT_MED": "#a7f3d0", "WHITE": "#f0fdf4", "DARK": "#040e09", "BAR_BG": "#0b2117"},
    "Swiss Bauhaus Studio": {"BG": "#f4f4f5", "PANEL": "#ffffff", "PANEL2": "#e4e4e7", "BORDER": "#18181b", "BORDER_B": "#dc2626", "BORDER_A": "#52525b", "PRI": "#dc2626", "PRI_DIM": "#991b1b", "PRI_GHO": "#fee2e2", "ACC": "#facc15", "ACC2": "#fef08a", "GREEN": "#166534", "GREEN_D": "#15803d", "RED": "#b91c1c", "MUTED_C": "#991b1b", "TEXT": "#18181b", "TEXT_DIM": "#71717a", "TEXT_MED": "#52525b", "WHITE": "#18181b", "DARK": "#e4e4e7", "BAR_BG": "#d4d4d8"},
    "Arcane Grimoire": {"BG": "#1a110a", "PANEL": "#f5ecd8", "PANEL2": "#ebe0c7", "BORDER": "#855829", "BORDER_B": "#d4af37", "BORDER_A": "#a47b3e", "PRI": "#d4af37", "PRI_DIM": "#a47b3e", "PRI_GHO": "#4a2c16", "ACC": "#991b1b", "ACC2": "#fbbf24", "GREEN": "#52734a", "GREEN_D": "#3f5f38", "RED": "#991b1b", "MUTED_C": "#b91c1c", "TEXT": "#3e2c1e", "TEXT_DIM": "#78532f", "TEXT_MED": "#633a18", "WHITE": "#45260f", "DARK": "#160c05", "BAR_BG": "#d6be96"},
    "Apollo 11 Flight Deck": {"BG": "#12161c", "PANEL": "#171c23", "PANEL2": "#1e2632", "BORDER": "#374151", "BORDER_B": "#f59e0b", "BORDER_A": "#b45309", "PRI": "#f59e0b", "PRI_DIM": "#b7791f", "PRI_GHO": "#3b2910", "ACC": "#38bdf8", "ACC2": "#7dd3fc", "GREEN": "#22c55e", "GREEN_D": "#15803d", "RED": "#ef4444", "MUTED_C": "#f87171", "TEXT": "#f3f4f6", "TEXT_DIM": "#9ca3af", "TEXT_MED": "#cbd5e1", "WHITE": "#ffffff", "DARK": "#0f1318", "BAR_BG": "#1f2937"},
    "Neo Shibuya Manga": {"BG": "#0c0818", "PANEL": "#140b29", "PANEL2": "#25104d", "BORDER": "#000000", "BORDER_B": "#f72585", "BORDER_A": "#4cc9f0", "PRI": "#f72585", "PRI_DIM": "#b51763", "PRI_GHO": "#3b1455", "ACC": "#4cc9f0", "ACC2": "#fee440", "GREEN": "#70e000", "GREEN_D": "#38a300", "RED": "#ef233c", "MUTED_C": "#ef233c", "TEXT": "#f8fafc", "TEXT_DIM": "#94a3b8", "TEXT_MED": "#cbd5e1", "WHITE": "#fdf4ff", "DARK": "#0d071a", "BAR_BG": "#1f0e42"},
}
_THEMES.update(_FRIDAY_THEME_PALETTES)

_DESIGN_MODES = ("orb", "default", "radar", "reactor", "matrix", "constellation")
DEFAULT_DESIGN_MODE = "orb"

DEFAULT_UI_THEME = "Ultron"
_ACTIVE_UI_THEME = DEFAULT_UI_THEME

DEFAULT_UI_COLOR = _PALETTE_DEFAULTS["PRI"]


def apply_ui_accent(accent_hex: str) -> bool:
    """
    Seçilen accent rengine göre tüm turkuaz-ailesi paleti yeniden türetir
    (hue kaydırma — parlaklık/doygunluk oranları korunur, tasarım bozulmaz).
    Boyanan öğeler (HUD, dalga formu, metrikler) bir sonraki karede yeni
    rengi alır; stylesheet tabanlı paneller yeniden kurulduklarında alır.
    """
    import colorsys

    accent_hex = (accent_hex or "").strip().lower()
    if not (accent_hex.startswith("#") and len(accent_hex) == 7):
        return False
    try:
        int(accent_hex[1:], 16)
    except ValueError:
        return False

    def _hsv(h: str) -> tuple[float, float, float]:
        r = int(h[1:3], 16) / 255
        g = int(h[3:5], 16) / 255
        b = int(h[5:7], 16) / 255
        return colorsys.rgb_to_hsv(r, g, b)

    base_h            = _hsv(_PALETTE_DEFAULTS["PRI"])[0]
    acc_h, acc_s, _av = _hsv(accent_hex)
    dh   = acc_h - base_h
    grey = acc_s < 0.08   # griye yakın accent → tüm tema desaturize edilir

    for key, hex0 in _PALETTE_DEFAULTS.items():
        h, s, v = _hsv(hex0)
        if grey:
            s *= 0.15
        r, g, b = colorsys.hsv_to_rgb((h + dh) % 1.0, s, v)
        setattr(C, key, "#{:02x}{:02x}{:02x}".format(
            int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5)))
    return True


def current_palette() -> dict[str, str]:
    """C sınıfındaki accent'e bağlı renklerin anlık kopyası."""
    return {k: getattr(C, k) for k in _THEME_COLOR_KEYS}


def apply_ui_theme(theme_name: str) -> str:
    """Apply a named complete UI palette and return the resolved theme name."""
    global _ACTIVE_UI_THEME
    resolved = theme_name if theme_name in _THEMES else DEFAULT_UI_THEME
    for key, value in _THEMES[resolved].items():
        setattr(C, key, value)
    _ACTIVE_UI_THEME = resolved
    return resolved


def retheme_all_widgets(old: dict[str, str], new: dict[str, str]) -> None:
    """
    CANLI tam tema değişimi. Uygulamadaki HER widget'ın stylesheet'inde eski
    palet renklerini yenileriyle değiştirir ve yeniden çizdirir. Böylece renk
    değişimi yalnızca boyanan öğelerde değil, panel/buton/kenarlık dahil tüm
    arayüzde ANINDA uygulanır — yeniden başlatma gerekmez.
    """
    mapping = {old[k].lower(): new[k].lower()
               for k in old if old[k].lower() != new.get(k, old[k]).lower()}
    if not mapping:
        return
    app = QApplication.instance()
    if app is None:
        return
    for w in app.allWidgets():
        try:
            ss = w.styleSheet()
            if ss:
                s2 = ss
                for o, n in mapping.items():
                    if o in s2:
                        s2 = s2.replace(o, n)
                if s2 != ss:
                    w.setStyleSheet(s2)
            w.update()
        except Exception:
            pass


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


# ── Windows GPU via NVML DLL (no subprocess, no console window) ──────────────
_nvml_lib: object = None   # cached ctypes DLL
_nvml_ok:  object = None   # None=untested, True=works, False=unavailable


def _nvml_gpu_windows() -> float:
    """Return NVIDIA GPU utilisation % using nvml.dll directly — zero subprocess."""
    global _nvml_lib, _nvml_ok
    if _nvml_ok is False:
        return -1.0
    try:
        import ctypes

        class _Util(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        if _nvml_lib is None:
            for dll_name in ("nvml", r"C:\Windows\System32\nvml.dll"):
                try:
                    lib = ctypes.WinDLL(dll_name)
                    lib.nvmlInit_v2()
                    _nvml_lib = lib
                    break
                except Exception:
                    continue

        if _nvml_lib is None:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            _nvml_ok = True
            return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)

        dev = ctypes.c_void_p()
        _nvml_lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
        util = _Util()
        _nvml_lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(util))
        _nvml_ok = True
        return float(util.gpu)
    except Exception:
        _nvml_ok = False
        return -1.0


class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        gpu = self._get_gpu()

        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        # pynvml — subprocess-free, works on all platforms if installed
        try:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
        except Exception:
            pass

        # Windows: nvml.dll via ctypes (already cached in _nvml_gpu_windows)
        if _OS == "Windows":
            return _nvml_gpu_windows()

        # Linux / macOS: libnvidia-ml shared lib via ctypes
        try:
            import ctypes
            _lib = "libnvidia-ml.so.1" if _OS == "Linux" else "libnvidia-ml.dylib"

            class _Util(ctypes.Structure):
                _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

            nv = ctypes.CDLL(_lib)
            nv.nvmlInit_v2()
            dev = ctypes.c_void_p()
            nv.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
            u = _Util()
            nv.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
            return float(u.gpu)
        except Exception:
            pass

        return -1.0   # N/A — zero subprocess on all platforms

    def _get_temp(self) -> float:
        # psutil — works on Linux; occasionally Windows with driver support
        try:
            temps = psutil.sensors_temperatures()
            for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                         "cpu-thermal", "zenpower", "it8688"]:
                if name in temps and temps[name]:
                    return temps[name][0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass

        # Windows: wmi module (pure Python COM, zero subprocess)
        if _OS == "Windows":
            try:
                import wmi  # type: ignore
                w = wmi.WMI(namespace="root/wmi")
                tz = w.MSAcpi_ThermalZoneTemperature()
                if tz:
                    return (tz[0].CurrentTemperature / 10.0) - 273.15
            except Exception:
                pass

        return -1.0   # N/A — zero subprocess on all platforms

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()

class HudCanvas(QWidget):
    def __init__(self, face_path: str, assistant_name: str = "Friday", design_mode: str = DEFAULT_DESIGN_MODE, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"
        self._assistant_name = assistant_name
        self._design_mode = design_mode if design_mode in _DESIGN_MODES else DEFAULT_DESIGN_MODE

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._scan       = 0.0
        self._scan2      = 180.0
        self._rings      = [0.0, 120.0, 240.0]
        self._pulses: list[float] = [0.0, 50.0, 100.0]
        self._blink      = True
        self._blink_tick = 0
        self._particles: list[list[float]] = []
        self._face_px: QPixmap | None = None
        self._load_face(face_path)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def set_design_mode(self, design_mode: str):
        self._design_mode = design_mode if design_mode in _DESIGN_MODES else DEFAULT_DESIGN_MODE
        self.update()

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz  = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk  = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    def _step(self):
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.06, 1.14)
                self._tgt_halo  = random.uniform(145, 190)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(15, 28)
            else:
                self._tgt_scale = random.uniform(1.001, 1.008)
                self._tgt_halo  = random.uniform(48, 68)
            self._last_t = now

        sp = 0.38 if self.speaking else 0.15
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        speeds = [1.3, -0.9, 2.0] if self.speaking else [0.55, -0.35, 0.9]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360

        self._scan  = (self._scan  + (3.0 if self.speaking else 1.3)) % 360
        self._scan2 = (self._scan2 + (-2.0 if self.speaking else -0.75)) % 360

        fw  = min(self.width(), self.height())
        lim = fw * 0.74
        spd = 4.2 if self.speaking else 2.0
        self._pulses = [r + spd for r in self._pulses if r + spd < lim]
        if len(self._pulses) < 3 and random.random() < (0.07 if self.speaking else 0.025):
            self._pulses.append(0.0)

        if self.speaking and random.random() < 0.28:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.28
            self._particles.append([
                cx + math.cos(ang) * r_s, cy + math.sin(ang) * r_s,
                math.cos(ang) * random.uniform(0.9, 2.4),
                math.sin(ang) * random.uniform(0.9, 2.4) - 0.4, 1.0,
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2]*0.97, p[3]*0.97, p[4]-0.028]
            for p in self._particles if p[4] > 0
        ]

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self.update()

    def _paint_ultron_orb(self, p: QPainter, cx: float, cy: float, fw: float):
        radius = fw * 0.235 * self._scale
        glow = QRadialGradient(QPointF(cx, cy), radius * 1.8)
        glow.setColorAt(0.0, qcol(C.WHITE, 235))
        glow.setColorAt(0.16, qcol(C.ACC2, 220))
        glow.setColorAt(0.42, qcol(C.ACC, 120))
        glow.setColorAt(0.72, qcol(C.PRI, 36))
        glow.setColorAt(1.0, qcol(C.PRI, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QRectF(cx - radius * 1.8, cy - radius * 1.8, radius * 3.6, radius * 3.6))

        core = QRadialGradient(QPointF(cx - radius * 0.2, cy - radius * 0.2), radius)
        core.setColorAt(0.0, qcol(C.WHITE, 255))
        core.setColorAt(0.3, qcol(C.ACC2, 245))
        core.setColorAt(0.78, qcol(C.ACC, 190))
        core.setColorAt(1.0, qcol(C.DARK, 210))
        p.setBrush(QBrush(core))
        p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        p.setBrush(Qt.BrushStyle.NoBrush)
        for width, height, alpha in (
            (2.0, 0.42, 190), (1.45, 0.72, 155), (0.72, 1.0, 135),
        ):
            p.setPen(QPen(qcol(C.ACC2, alpha), width))
            p.drawEllipse(QRectF(cx - radius * height, cy - radius * 0.34, radius * height * 2, radius * 0.68))
            p.drawEllipse(QRectF(cx - radius * 0.34, cy - radius * height, radius * 0.68, radius * height * 2))

        p.setPen(QPen(qcol(C.ACC2, 90), 1))
        for offset in range(-6, 7):
            y = cy + offset * radius * 0.115
            half = radius * math.sqrt(max(0.0, 1.0 - (offset / 8.0) ** 2))
            p.drawLine(QPointF(cx - half, y), QPointF(cx + half, y))

        p.setPen(QPen(qcol(C.ACC2, 220), 2))
        p.drawArc(QRectF(cx - radius * 1.18, cy - radius * 1.18, radius * 2.36, radius * 2.36), int(self._rings[0] * 16), 125 * 16)
        p.setPen(QPen(qcol(C.ACC, 170), 1.4))
        p.drawArc(QRectF(cx - radius * 1.32, cy - radius * 1.32, radius * 2.64, radius * 2.64), int(self._rings[1] * 16), 80 * 16)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcol(C.WHITE, 255)))
        p.drawEllipse(QRectF(cx - radius * 0.12, cy - radius * 0.12, radius * 0.24, radius * 0.24))

    def _paint_default_design(self, p: QPainter, cx: float, cy: float, fw: float):
        radius = fw * 0.24
        p.setPen(QPen(qcol(C.PRI, 210), 2))
        p.setBrush(QBrush(qcol(C.PANEL2, 230)))
        p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        if self._face_px and not self._face_px.isNull():
            face = self._face_px.scaled(int(radius * 1.72), int(radius * 1.72), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(cx - face.width() / 2), int(cy - face.height() / 2), face)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(qcol(C.PRI, 130), 1.5))
        p.drawEllipse(QRectF(cx - radius * 1.18, cy - radius * 1.18, radius * 2.36, radius * 2.36))
        p.setPen(QPen(qcol(C.ACC, 180), 2))
        p.drawArc(QRectF(cx - radius * 1.32, cy - radius * 1.32, radius * 2.64, radius * 2.64), int(self._rings[0] * 16), 100 * 16)

    def _paint_radar_design(self, p: QPainter, cx: float, cy: float, fw: float):
        radius = fw * 0.36
        p.setBrush(Qt.BrushStyle.NoBrush)
        for fraction in (0.42, 0.70, 1.0):
            p.setPen(QPen(qcol(C.PRI, 105), 1))
            r = radius * fraction
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        p.setPen(QPen(qcol(C.PRI, 95), 1))
        p.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))
        p.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))
        sweep = math.radians(self._scan)
        p.setPen(QPen(qcol(C.ACC, 220), 2))
        p.drawLine(QPointF(cx, cy), QPointF(cx + math.cos(sweep) * radius, cy - math.sin(sweep) * radius))
        for index in range(7):
            angle = math.radians(index * 51 + 18)
            distance = radius * (0.35 + (index % 3) * 0.19)
            x = cx + math.cos(angle) * distance
            y = cy - math.sin(angle) * distance
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(C.GREEN if index % 2 else C.ACC2, 220)))
            p.drawEllipse(QPointF(x, y), 3.5 if index % 3 == 0 else 2, 3.5 if index % 3 == 0 else 2)
        p.setPen(QPen(qcol(C.PRI, 180), 1))
        p.drawText(QRectF(cx - radius, cy + radius + 10, radius * 2, 20), Qt.AlignmentFlag.AlignCenter, "ACTIVE SCAN // 360 DEG")

    def _paint_reactor_design(self, p: QPainter, cx: float, cy: float, fw: float):
        radius = fw * 0.27 * self._scale
        glow = QRadialGradient(QPointF(cx, cy), radius * 1.9)
        glow.setColorAt(0.0, qcol(C.WHITE, 230))
        glow.setColorAt(0.22, qcol(C.ACC2, 210))
        glow.setColorAt(0.55, qcol(C.ACC, 85))
        glow.setColorAt(1.0, qcol(C.PRI, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QRectF(cx - radius * 1.9, cy - radius * 1.9, radius * 3.8, radius * 3.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for index, scale in enumerate((1.0, 1.22, 1.46)):
            p.setPen(QPen(qcol(C.ACC if index == 0 else C.PRI, 220 - index * 35), 2 if index == 0 else 1))
            r = radius * scale
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        for index in range(8):
            angle = math.radians(self._rings[0] + index * 45)
            inner = radius * 1.05
            outer = radius * (1.28 + 0.08 * (index % 2))
            p.setPen(QPen(qcol(C.ACC2, 200), 2))
            p.drawLine(QPointF(cx + math.cos(angle) * inner, cy + math.sin(angle) * inner), QPointF(cx + math.cos(angle) * outer, cy + math.sin(angle) * outer))
        p.setPen(QPen(qcol(C.WHITE, 220), 1))
        p.drawText(QRectF(cx - radius * 1.4, cy - 12, radius * 2.8, 24), Qt.AlignmentFlag.AlignCenter, "ARC // CORE")

    def _paint_matrix_design(self, p: QPainter, cx: float, cy: float, fw: float):
        columns = max(12, int(fw / 22))
        for index in range(columns):
            x = (index + 0.5) * self.width() / columns
            height = fw * (0.18 + ((index * 37 + self._tick * (2 if self.speaking else 1)) % 100) / 150)
            p.setPen(QPen(qcol(C.GREEN, 150 if index % 3 else 220), 2))
            p.drawLine(QPointF(x, cy - height), QPointF(x, cy + height))
            if index % 2 == 0:
                p.setPen(QPen(qcol(C.PRI, 115), 1))
                p.drawLine(QPointF(x, cy - height - 12), QPointF(x, cy - height))
        scan_y = (self._tick * (2 if self.speaking else 1)) % max(1, self.height())
        p.setPen(QPen(qcol(C.ACC, 210), 2))
        p.drawLine(QPointF(0, scan_y), QPointF(self.width(), scan_y))
        side = fw * 0.28
        p.setPen(QPen(qcol(C.PRI, 220), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(cx - side, cy - side, side * 2, side * 2))
        p.setPen(QPen(qcol(C.ACC2, 220), 1))
        p.drawText(QRectF(cx - side, cy - 10, side * 2, 20), Qt.AlignmentFlag.AlignCenter, "NEURAL LINK")

    def _paint_constellation_design(self, p: QPainter, cx: float, cy: float, fw: float):
        points = []
        for index in range(13):
            angle = math.radians(index * 137.5 + self._scan * 0.15)
            distance = fw * (0.12 + (index % 5) * 0.075)
            point = (cx + math.cos(angle) * distance, cy + math.sin(angle) * distance)
            points.append(point)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for first, second in zip(points, points[1:]):
            p.setPen(QPen(qcol(C.PRI, 105), 1))
            p.drawLine(QPointF(*first), QPointF(*second))
        for index, (x, y) in enumerate(points):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(C.ACC2 if index % 3 == 0 else C.PRI, 220)))
            size = 3.5 if index % 3 == 0 else 2.2
            p.drawEllipse(QPointF(x, y), size, size)
        p.setPen(QPen(qcol(C.PRI, 180), 1))
        p.drawEllipse(QRectF(cx - fw * 0.34, cy - fw * 0.34, fw * 0.68, fw * 0.68))
        p.setPen(QPen(qcol(C.TEXT, 190), 1))
        p.drawText(QRectF(cx - fw * 0.28, cy + fw * 0.37, fw * 0.56, 20), Qt.AlignmentFlag.AlignCenter, "COGNITIVE CONSTELLATION")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        if self._design_mode == "orb":
            p.setPen(QPen(qcol(C.PRI_GHO), 1))
            for x in range(0, W, 48):
                for y in range(0, H, 48):
                    p.drawPoint(x, y)

        r_face = fw * 0.31

        if self._design_mode == "orb":
            for i in range(10):
                r   = r_face * (1.8 - i * 0.08)
                frc = 1.0 - i / 10
                a   = max(0, min(255, int(self._halo * 0.085 * frc)))
                col = qcol(C.MUTED_C if self.muted else C.PRI, a)
                p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        if self._design_mode == "orb":
            # Pulse and telemetry layers belong to the orb presentation.
            for pr in self._pulses:
                a = max(0, int(230 * (1.0 - pr / (fw * 0.74))))
                col = qcol(C.MUTED_C if self.muted else C.PRI, a)
                p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

            for idx, (r_frac, w_r, arc_l, gap) in enumerate(
                [(0.48, 3, 115, 78), (0.40, 2, 78, 55), (0.32, 1, 56, 40)]
            ):
                ring_r = fw * r_frac
                base = self._rings[idx]
                a_val = max(0, min(255, int(self._halo * (1.0 - idx * 0.18))))
                col = qcol(C.MUTED_C if self.muted else C.PRI, a_val)
                p.setPen(QPen(col, w_r)); p.setBrush(Qt.BrushStyle.NoBrush)
                angle = base
                rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
                while angle < base + 360:
                    p.drawArc(rect, int(angle * 16), int(arc_l * 16))
                    angle += arc_l + gap

            sr = fw * 0.50
            sa = min(255, int(self._halo * 1.5))
            ex = 75 if self.speaking else 44
            p.setPen(QPen(qcol(C.MUTED_C if self.muted else C.PRI, sa), 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            srect = QRectF(cx - sr, cy - sr, sr * 2, sr * 2)
            p.drawArc(srect, int(self._scan * 16), int(ex * 16))
            p.setPen(QPen(qcol(C.ACC, sa // 2), 1.5))
            p.drawArc(srect, int(self._scan2 * 16), int(ex * 16))

            t_out, t_in = fw * 0.497, fw * 0.474
            p.setPen(QPen(qcol(C.PRI, 140), 1))
            for deg in range(0, 360, 10):
                rad = math.radians(deg)
                inn = t_in if deg % 30 == 0 else t_in + 6
                p.drawLine(
                    QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                    QPointF(cx + inn * math.cos(rad), cy - inn * math.sin(rad)),
                )

            ch_r, gap_h = fw * 0.51, fw * 0.16
            p.setPen(QPen(qcol(C.PRI, int(self._halo * 0.5)), 1))
            p.drawLine(QPointF(cx - ch_r, cy), QPointF(cx - gap_h, cy))
            p.drawLine(QPointF(cx + gap_h, cy), QPointF(cx + ch_r, cy))
            p.drawLine(QPointF(cx, cy - ch_r), QPointF(cx, cy - gap_h))
            p.drawLine(QPointF(cx, cy + gap_h), QPointF(cx, cy + ch_r))

            bl = 24
            bc = qcol(C.PRI, 210)
            hl, hr = cx - fw // 2, cx + fw // 2
            ht, hb = cy - fw // 2, cy + fw // 2
            p.setPen(QPen(bc, 2))
            for bx, by, dx, dy in [(hl, ht, 1, 1), (hr, ht, -1, 1), (hl, hb, 1, -1), (hr, hb, -1, -1)]:
                p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
                p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))

            self._paint_ultron_orb(p, cx, cy, fw)
        elif self._design_mode == "radar":
            self._paint_radar_design(p, cx, cy, fw)
        elif self._design_mode == "reactor":
            self._paint_reactor_design(p, cx, cy, fw)
        elif self._design_mode == "matrix":
            self._paint_matrix_design(p, cx, cy, fw)
        elif self._design_mode == "constellation":
            self._paint_constellation_design(p, cx, cy, fw)
        else:
            self._paint_default_design(p, cx, cy, fw)

        if self._design_mode == "orb":
            for pt in self._particles:
                a = max(0, min(255, int(pt[4] * 255)))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(qcol(C.PRI, a)))
                p.drawEllipse(QPointF(pt[0], pt[1]), 2.5, 2.5)

        # status text
        sy = cy + fw * 0.40
        if self.muted:
            txt, col = "⊘  MUTED",     qcol(C.MUTED_C)
        elif self.speaking:
            txt, col = "●  SPEAKING",  qcol(C.ACC)
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  THINKING",   qcol(C.ACC2)
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym}  PROCESSING", qcol(C.ACC2)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  LISTENING",  qcol(C.GREEN)
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  {self.state}", qcol(C.PRI)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 26), Qt.AlignmentFlag.AlignCenter, txt)

        # waveform
        wy = sy + 30
        N, bw = 36, 8
        wx0 = (W - N * bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.MUTED_C)
            elif self.speaking:
                hgt = random.randint(3, 20)
                cl  = qcol(C.PRI) if hgt > 12 else qcol(C.PRI_DIM)
            else:
                hgt = int(3 + 2 * math.sin(self._tick * 0.09 + i * 0.6))
                cl  = qcol(C.BORDER_B)
            p.fillRect(QRectF(wx0 + i * bw, wy + 20 - hgt, bw - 1, hgt), cl)

class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0–100
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        bar_h   = 4
        bar_y   = H - bar_h - 5
        bar_w   = W - 12
        bar_x   = 6
        fill_w  = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.ACC)
        else:
            bar_col = qcol(self._color)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)

class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 6px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG};
                width: 8px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 4px;
                min-height: 20px;
            }}
        """)
        self._queue: list[str] = []
        self._typing  = False
        self._text    = ""
        self._pos     = 0
        self._tag     = "sys"
        self._ai_name_lc = "friday"   # updated when assistant name changes
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)
        self._last_user_sent_text: str | None = None
        self._last_user_sent_time: float = 0.0

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        _ai_pfx = f"{self._ai_name_lc}:"
        if   tl.startswith("you:"):                              self._tag = "you"
        elif tl.startswith(_ai_pfx) or tl.startswith("friday:"): self._tag = "ai"
        elif tl.startswith("file:"):                             self._tag = "file"
        elif "err" in tl:                                        self._tag = "err"
        else:                                                    self._tag = "sys"
        self._tmr.start(6)

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":  qcol(C.WHITE),
                "ai":   qcol(C.PRI),
                "err":  qcol(C.RED),
                "file": qcol(C.GREEN),
                "sys":  qcol(C.ACC2),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)

_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#ff6b00"),
    "audio":   ("🎵", "#cc44ff"), "pdf":     ("📄", "#ff4444"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#44bb44"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for Friday", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class _CameraPreview(QWidget):
    """Floating overlay that briefly shows what the camera captured."""

    _W, _H = 244, 188

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            _CameraPreview {{
                background: rgba(0, 6, 10, 242);
                border: 1px solid {C.PRI};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._W)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 5, 6, 6)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        title = QLabel("◈  VISUAL INPUT")
        title.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(16, 16)
        close_btn.setFont(QFont("Courier New", 8))
        close_btn.setStyleSheet(
            f"color: {C.TEXT_DIM}; background: transparent; border: none;"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        hdr.addWidget(close_btn)
        lay.addLayout(hdr)

        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(self._img_lbl)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self.hide()

    def show_frame(self, img_bytes: bytes) -> None:
        px = QPixmap()
        px.loadFromData(img_bytes)
        if not px.isNull():
            max_w = self._W - 12
            scaled = px.scaled(
                max_w, 160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._img_lbl.setPixmap(scaled)
            self._img_lbl.setFixedSize(scaled.width(), scaled.height())
            self.adjustSize()
        self.show()
        self.raise_()
        self._timer.start(6_000)   # auto-dismiss after 6 s


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure Friday before first boot.", 9, color=C.PRI_DIM))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("YOUR GEMINI API KEY", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Courier New", 10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addWidget(_lbl(
            "Stored only in this device's ignored local config. You can also use GEMINI_API_KEY.",
            7, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft,
        ))
        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,"#001a22"),"mac":(C.ACC2,"#1a1400"),"linux":(C.GREEN,"#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 3px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #000d12; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return
        self.done.emit(key, self._sel_os)


class HueWheel(QWidget):
    """
    Dairesel renk seçici. Kullanıcı tutamacı (küçük beyaz daire) çarkın
    çevresinde sürükleyerek TÜM renk tonları arasından seçim yapar.
    Merkezdeki dolu daire seçilen rengin canlı önizlemesidir.
    """

    hue_picked    = pyqtSignal(str)   # sürükleme sırasında (canlı)
    hue_committed = pyqtSignal(str)   # tutamaç bırakıldığında

    _RING = 16   # halka kalınlığı (px)

    def __init__(self, initial_hex: str = DEFAULT_UI_COLOR, parent=None):
        super().__init__(parent)
        self.setFixedSize(148, 148)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hue  = 0.53
        self._drag = False
        self.set_color(initial_hex)

    # ── API ──────────────────────────────────────────────────────────────────
    def color(self) -> str:
        return QColor.fromHsvF(self._hue, 1.0, 1.0).name()

    def set_color(self, hex_str: str):
        c = QColor((hex_str or "").strip())
        if c.isValid() and c.hsvHueF() >= 0:
            self._hue = c.hsvHueF()
            self.update()

    # ── geometri yardımcıları ────────────────────────────────────────────────
    def _ring_rect(self) -> QRectF:
        m = self._RING / 2 + 3
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _hue_from_pos(self, pos: QPointF) -> float:
        c  = QRectF(self.rect()).center()
        dx = pos.x() - c.x()
        dy = c.y() - pos.y()          # ekran y'si aşağı — matematiksel eksene çevir
        ang = math.atan2(dy, dx)      # [-π, π], saat yönünün tersi
        return (ang / (2 * math.pi)) % 1.0

    # ── çizim ────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect   = self._ring_rect()
        center = rect.center()

        grad = QConicalGradient(center, 0)
        for i in range(0, 361, 20):
            grad.setColorAt(i / 360.0, QColor.fromHsvF((i % 360) / 360.0, 1.0, 1.0))
        p.setPen(QPen(QBrush(grad), self._RING))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # merkez önizleme dairesi
        preview = QColor.fromHsvF(self._hue, 1.0, 1.0)
        inner   = rect.adjusted(30, 30, -30, -30)
        p.setPen(QPen(qcol(C.BORDER_B), 1))
        p.setBrush(QBrush(preview))
        p.drawEllipse(inner)

        # sürüklenen tutamaç
        r   = rect.width() / 2
        ang = self._hue * 2 * math.pi
        hx  = center.x() + r * math.cos(ang)
        hy  = center.y() - r * math.sin(ang)
        p.setPen(QPen(QColor("#00060a"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QPointF(hx, hy), 7.5, 7.5)

    # ── fare ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        self._drag = True
        self._hue  = self._hue_from_pos(e.position())
        self.update()
        self.hue_picked.emit(self.color())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._hue = self._hue_from_pos(e.position())
            self.update()
            self.hue_picked.emit(self.color())

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self.hue_committed.emit(self.color())


class CustomizeOverlay(QWidget):
    """Floating overlay — change assistant name, user name and UI colour."""

    saved = pyqtSignal(str, str, str)   # assistant_name, user_name, ui_color
    _OW, _OH = 400, 500

    def __init__(self, assistant_name="Friday", user_name="",
                 ui_color=DEFAULT_UI_COLOR, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            CustomizeOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(8)

        def _lbl(txt, fs=9, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Courier New", fs,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        _fs = (f"QLineEdit {{ background: #000d12; color: {C.TEXT}; "
               f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
               f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        lay.addWidget(_lbl("⚙  CUSTOMISE ASSISTANT", 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_lbl("ASSISTANT NAME", 8, color=C.TEXT_DIM,
                            align=Qt.AlignmentFlag.AlignLeft))
        self._name_input = QLineEdit(assistant_name)
        self._name_input.setFont(QFont("Courier New", 10))
        self._name_input.setFixedHeight(32)
        self._name_input.setStyleSheet(_fs)
        lay.addWidget(self._name_input)

        lay.addSpacing(4)
        lay.addWidget(_lbl("YOUR NAME  (leave blank for default sir / efendim)", 8,
                            color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._user_input = QLineEdit(user_name)
        self._user_input.setPlaceholderText("e.g.  Tony   (leave blank for auto)")
        self._user_input.setFont(QFont("Courier New", 10))
        self._user_input.setFixedHeight(32)
        self._user_input.setStyleSheet(_fs)
        lay.addWidget(self._user_input)

        # ── UI colour — renk çarkı ───────────────────────────────────────────
        lay.addSpacing(4)
        clr_hdr = QHBoxLayout()
        clr_hdr.addWidget(_lbl("UI COLOUR  —  drag the handle", 8,
                               color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        clr_hdr.addStretch()
        df_btn = QPushButton("DEFAULT")
        df_btn.setFixedSize(64, 20)
        df_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        df_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        df_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        df_btn.clicked.connect(lambda: self._set_color(DEFAULT_UI_COLOR))
        clr_hdr.addWidget(df_btn)
        lay.addLayout(clr_hdr)

        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._sel_color     = self._initial_color
        self.on_preview     = None   # callable(hex) — canlı önizleme; MainWindow bağlar

        self._wheel = HueWheel(self._sel_color)
        wheel_row = QHBoxLayout()
        wheel_row.addStretch(); wheel_row.addWidget(self._wheel); wheel_row.addStretch()
        lay.addLayout(wheel_row)
        self._wheel.hue_picked.connect(self._on_wheel_pick)
        self._wheel.hue_committed.connect(self._on_wheel_commit)

        self._hex_input = QLineEdit(self._sel_color)
        self._hex_input.setPlaceholderText("#00d4ff   (custom hex colour)")
        self._hex_input.setFont(QFont("Courier New", 10))
        self._hex_input.setFixedHeight(28)
        self._hex_input.setStyleSheet(_fs)
        self._hex_input.textEdited.connect(self._on_hex_edited)
        lay.addWidget(self._hex_input)

        lay.addSpacing(6)
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        save_btn = QPushButton("▸  APPLY CHANGES")
        save_btn.setFixedHeight(34)
        save_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setFont(QFont("Courier New", 9))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

    # ── renk akışı ───────────────────────────────────────────────────────────
    def _set_color(self, hx: str, update_wheel: bool = True, preview: bool = True):
        """Seçili rengi günceller; hex kutusu + çark senkron kalır, tema canlı önizlenir."""
        self._sel_color = hx.strip().lower()
        self._hex_input.blockSignals(True)
        self._hex_input.setText(self._sel_color)
        self._hex_input.blockSignals(False)
        if update_wheel:
            self._wheel.set_color(self._sel_color)
        if preview and self.on_preview:
            self.on_preview(self._sel_color)

    def _on_wheel_pick(self, hx: str):
        # Sürükleme sırasında: hex kutusunu güncelle, temayı henüz uygulama
        self._sel_color = hx
        self._hex_input.blockSignals(True)
        self._hex_input.setText(hx)
        self._hex_input.blockSignals(False)

    def _on_wheel_commit(self, hx: str):
        # Tutamaç bırakıldı → tüm arayüzü canlı önizle
        self._set_color(hx, update_wheel=False)

    def _on_hex_edited(self, text: str):
        t = text.strip().lower()
        if t.startswith("#") and len(t) == 7:
            try:
                int(t[1:], 16)
            except ValueError:
                return
            self._set_color(t, update_wheel=True, preview=True)

    def _cancel(self):
        # Önizleme uygulandıysa açılıştaki renge geri dön
        if self.on_preview and self._sel_color != self._initial_color:
            self.on_preview(self._initial_color)
        self.hide()

    def _save(self):
        name = self._name_input.text().strip() or "Friday"
        user = self._user_input.text().strip()
        self.saved.emit(name, user, self._sel_color or DEFAULT_UI_COLOR)
        self.hide()


class ThemeOverlay(QWidget):
    """Floating settings section for previewing and selecting complete palettes."""

    saved = pyqtSignal(str, str, str)  # theme_name, primary_colour, design_mode
    _OW, _OH = 510, 570

    def __init__(self, theme_name: str, ui_color: str, design_mode: str = DEFAULT_DESIGN_MODE, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ThemeOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B}; border-radius: 6px;
            }}
        """)
        self._initial_theme = theme_name if theme_name in _THEMES else "Custom"
        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._initial_design = design_mode if design_mode in _DESIGN_MODES else DEFAULT_DESIGN_MODE
        self._selected_theme = self._initial_theme
        self._selected_color = self._initial_color
        self._selected_design = self._initial_design
        self.on_preview = None
        self._theme_buttons: dict[str, QPushButton] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(8)

        title = QLabel("THEMES")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(title)
        intro = QLabel("Select a theme to preview it across Friday. Apply saves your choice.")
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro.setFont(QFont("Courier New", 8))
        intro.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(intro)

        grid = QVBoxLayout()
        grid.setSpacing(7)
        names = list(_THEMES)
        for row_start in range(0, len(names), 2):
            row = QHBoxLayout()
            row.setSpacing(7)
            for name in names[row_start:row_start + 2]:
                palette = _THEMES[name]
                button = QPushButton(f"{name.upper()}\n{palette['PRI']}  {palette['BG']}")
                button.setMinimumHeight(54)
                button.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(lambda _, selected=name: self._select_theme(selected))
                self._theme_buttons[name] = button
                row.addWidget(button)
            if row_start + 1 >= len(names):
                row.addStretch()
            grid.addLayout(row)
        lay.addLayout(grid)

        design_title = QLabel("DESIGN")
        design_title.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        design_title.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; padding-top: 6px;")
        lay.addWidget(design_title)
        self._design_combo = QComboBox()
        self._design_combo.addItem("Orb - animated tactical visualization", "orb")
        self._design_combo.addItem("Default - clean assistant portrait", "default")
        self._design_combo.addItem("Radar Grid - scanning sensor array", "radar")
        self._design_combo.addItem("Reactor Core - energized power cell", "reactor")
        self._design_combo.addItem("Matrix Scan - neural data field", "matrix")
        self._design_combo.addItem("Constellation - cognitive star map", "constellation")
        selected_index = self._design_combo.findData(self._selected_design)
        self._design_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self._design_combo.setFont(QFont("Courier New", 8))
        self._design_combo.setFixedHeight(30)
        self._design_combo.setStyleSheet(f"QComboBox {{ color: {C.TEXT}; background: {C.PANEL}; border: 1px solid {C.BORDER}; padding: 3px 7px; }} QComboBox QAbstractItemView {{ color: {C.TEXT}; background: {C.PANEL}; selection-background-color: {C.PRI_GHO}; }}")
        self._design_combo.currentIndexChanged.connect(self._select_design)
        lay.addWidget(self._design_combo)

        note = QLabel("Custom accent colours remain available under Customise Assistant.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setFont(QFont("Courier New", 7))
        note.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(note)
        lay.addStretch()

        row = QHBoxLayout()
        apply = QPushButton("APPLY THEME")
        cancel = QPushButton("CANCEL")
        for button in (apply, cancel):
            button.setFixedHeight(32)
            button.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        apply.setStyleSheet(f"QPushButton {{ color: {C.PRI}; border: 1px solid {C.PRI_DIM}; border-radius: 3px; background: transparent; }} QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}")
        cancel.setStyleSheet(f"QPushButton {{ color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px; background: transparent; }} QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}")
        apply.clicked.connect(self._save)
        cancel.clicked.connect(self._cancel)
        row.addWidget(apply)
        row.addWidget(cancel)
        lay.addLayout(row)
        self._style_theme_buttons()

    def _style_theme_buttons(self):
        for name, button in self._theme_buttons.items():
            palette = _THEMES[name]
            selected = name == self._selected_theme
            border = C.PRI if selected else palette["BORDER_B"]
            button.setStyleSheet(
                f"QPushButton {{ background: {palette['PANEL']}; color: {palette['TEXT']}; "
                f"border: 2px solid {border}; border-radius: 4px; text-align: left; padding: 7px; }} "
                f"QPushButton:hover {{ border-color: {palette['PRI']}; }}"
            )

    def _select_theme(self, theme_name: str):
        self._selected_theme = theme_name
        self._selected_color = _THEMES[theme_name]["PRI"]
        self._style_theme_buttons()
        if self.on_preview:
            self.on_preview(theme_name, self._selected_design)

    def _select_design(self, _index: int):
        self._selected_design = str(self._design_combo.currentData() or DEFAULT_DESIGN_MODE)
        if self.on_preview:
            self.on_preview(self._selected_theme, self._selected_design)

    def _cancel(self):
        if self.on_preview:
            if self._initial_theme in _THEMES:
                self.on_preview(self._initial_theme, self._initial_design)
            else:
                self.on_preview("Custom", self._initial_design, self._initial_color)
        self.hide()

    def _save(self):
        self.saved.emit(self._selected_theme, self._selected_color, self._selected_design)
        self.hide()


class PersonalizationOverlay(QWidget):
    """Auto-saving profile, behavior, and communication preferences."""

    saved = pyqtSignal(dict)
    _OW, _OH = 560, 720

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PersonalizationOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B}; border-radius: 6px;
            }}
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(8)

        title = QLabel("PERSONALIZATION ENGINE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(7)
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        field_style = (
            f"background: {C.PANEL2}; color: {C.TEXT}; border: 1px solid {C.BORDER}; "
            f"border-radius: 3px; padding: 5px 7px;"
        )

        def label(text: str, hint: str = ""):
            item = QLabel(text)
            item.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            item.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(item)
            if hint:
                detail = QLabel(hint)
                detail.setWordWrap(True)
                detail.setFont(QFont("Courier New", 7))
                detail.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
                lay.addWidget(detail)

        label("AI NAME", "Updates the desktop title, HUD, prompts, and paired dashboard immediately.")
        self._assistant_name = QLineEdit(str(config.get("assistant_name", "Friday")))
        self._assistant_name.setStyleSheet(f"QLineEdit {{ {field_style} }} QLineEdit:focus {{ border-color: {C.PRI}; }}")
        self._assistant_name.setFixedHeight(31)
        lay.addWidget(self._assistant_name)

        label("AI DESCRIPTION")
        self._assistant_description = QLineEdit(str(config.get("assistant_description", "")))
        self._assistant_description.setStyleSheet(f"QLineEdit {{ {field_style} }} QLineEdit:focus {{ border-color: {C.PRI}; }}")
        self._assistant_description.setFixedHeight(31)
        lay.addWidget(self._assistant_description)

        label("WELCOME MESSAGE")
        self._welcome_message = QLineEdit(str(config.get("welcome_message", "")))
        self._welcome_message.setStyleSheet(f"QLineEdit {{ {field_style} }} QLineEdit:focus {{ border-color: {C.PRI}; }}")
        self._welcome_message.setFixedHeight(31)
        lay.addWidget(self._welcome_message)

        label("USER NAME", "The name Friday should use when addressing you.")
        self._name = QLineEdit(str(config.get("user_name", "")))
        self._name.setStyleSheet(f"QLineEdit {{ {field_style} }} QLineEdit:focus {{ border-color: {C.PRI}; }}")
        self._name.setFixedHeight(31)
        lay.addWidget(self._name)

        label("QUALIFICATION", "Your educational background or profession.")
        self._qualification = QLineEdit(str(config.get("user_qualification", "")))
        self._qualification.setStyleSheet(f"QLineEdit {{ {field_style} }} QLineEdit:focus {{ border-color: {C.PRI}; }}")
        self._qualification.setFixedHeight(31)
        lay.addWidget(self._qualification)

        label("ADDITIONAL USER INFORMATION", "Optional occupation, interests, preferences, goals, or other useful context.")
        self._additional = QTextEdit(str(config.get("additional_user_information", "")))
        self._additional.setAcceptRichText(False)
        self._additional.setFixedHeight(72)
        self._additional.setStyleSheet(f"QTextEdit {{ {field_style} }} QTextEdit:focus {{ border-color: {C.PRI}; }}")
        lay.addWidget(self._additional)

        label("FRIDAY'S PERSONALITY & BEHAVIOR", "For example: professional, friendly, mentor-like, concise, humorous, or motivational.")
        self._personality = QTextEdit(str(config.get("friday_personality_behavior", "")))
        self._personality.setAcceptRichText(False)
        self._personality.setFixedHeight(72)
        self._personality.setStyleSheet(f"QTextEdit {{ {field_style} }} QTextEdit:focus {{ border-color: {C.PRI}; }}")
        lay.addWidget(self._personality)

        label("CUSTOM INSTRUCTIONS", "Additional guidance for how Friday should respond. Core capabilities and safety remain unchanged.")
        self._instructions = QTextEdit(str(config.get("custom_instructions", "")))
        self._instructions.setAcceptRichText(False)
        self._instructions.setFixedHeight(94)
        self._instructions.setStyleSheet(f"QTextEdit {{ {field_style} }} QTextEdit:focus {{ border-color: {C.PRI}; }}")
        lay.addWidget(self._instructions)

        label("ASSISTANT STYLE", "These preferences guide every new conversation and can be changed at any time.")
        self._personality_preset = QComboBox()
        self._personality_preset.addItems(["Professional", "Friendly", "Mentor", "Technical", "Creative", "Funny", "Researcher"])
        self._personality_preset.setCurrentText(str(config.get("personality_preset", "Friendly")))
        self._response_length = QComboBox()
        self._response_length.addItems(["Concise", "Balanced", "Detailed"])
        self._response_length.setCurrentText(str(config.get("response_length", "Balanced")))
        self._language = QComboBox()
        self._language.addItems(["Auto", "English", "Hindi", "Hinglish", "Spanish", "French", "German", "Japanese"])
        self._language.setCurrentText(str(config.get("preferred_language", "Auto")))
        self._coding_language = QComboBox()
        self._coding_language.addItems(["Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "Go", "Rust"])
        self._coding_language.setCurrentText(str(config.get("default_coding_language", "Python")))
        self._skill_profile = QComboBox()
        self._skill_profile.addItems(["General", "Coding", "Research", "Household", "Productivity"])
        self._skill_profile.setCurrentText(str(config.get("skill_profile", "general")).title())
        for title, control in (("Personality", self._personality_preset), ("Response length", self._response_length), ("Language", self._language), ("Coding language", self._coding_language), ("Skill profile", self._skill_profile)):
            row = QHBoxLayout(); item = QLabel(title.upper()); item.setFixedWidth(132)
            item.setFont(QFont("Courier New", 8, QFont.Weight.Bold)); item.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            control.setFont(QFont("Courier New", 8)); control.setStyleSheet(f"QComboBox {{ {field_style} }} QComboBox::drop-down {{ border: none; }}")
            row.addWidget(item); row.addWidget(control, stretch=1); lay.addLayout(row)

        self._preference_sliders = {}
        for key, title, default in (
            ("formality_level", "Formality", 50),
            ("humor_level", "Humor", 50),
            ("empathy_level", "Empathy", 70),
            ("creativity_level", "Creativity", 60),
            ("verbosity_level", "Verbosity", 50),
        ):
            row = QHBoxLayout(); item = QLabel(title.upper()); item.setFixedWidth(132)
            item.setFont(QFont("Courier New", 8, QFont.Weight.Bold)); item.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            slider = QSlider(Qt.Orientation.Horizontal); slider.setRange(0, 100)
            try: slider.setValue(max(0, min(100, int(config.get(key, default)))) )
            except (TypeError, ValueError): slider.setValue(default)
            slider.setStyleSheet(f"QSlider::groove:horizontal {{ height: 4px; background: {C.BORDER}; }} QSlider::handle:horizontal {{ width: 11px; margin: -4px 0; background: {C.PRI}; border-radius: 5px; }}")
            value = QLabel(f"{slider.value()}% "); value.setFixedWidth(34); value.setFont(QFont("Courier New", 7)); value.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
            slider.valueChanged.connect(lambda current, label=value: label.setText(f"{current}%"))
            self._preference_sliders[key] = slider
            row.addWidget(item); row.addWidget(slider, stretch=1); row.addWidget(value); lay.addLayout(row)

        label("BEHAVIOR")
        self._behavior = {}
        for key, title, default in (
            ("memory_enabled", "Use preference memory", True),
            ("auto_follow_up", "Offer helpful follow-ups", True),
            ("learning_mode", "Learning mode", False),
            ("research_mode", "Research mode", False),
            ("developer_mode", "Developer mode", False),
            ("markdown_enabled", "Use Markdown", True),
        ):
            check = QCheckBox(title)
            check.setChecked(bool(config.get(key, default)))
            check.setFont(QFont("Courier New", 8))
            check.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            self._behavior[key] = check
            lay.addWidget(check)
        lay.addStretch()

        self._sync_status = QLabel("Changes save automatically")
        self._sync_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sync_status.setFont(QFont("Courier New", 7))
        self._sync_status.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        outer.addWidget(self._sync_status)

        row = QHBoxLayout()
        save = QPushButton("SAVE PERSONALIZATION")
        cancel = QPushButton("CANCEL")
        for button in (save, cancel):
            button.setFixedHeight(32)
            button.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setStyleSheet(f"QPushButton {{ color: {C.PRI}; border: 1px solid {C.PRI_DIM}; border-radius: 3px; background: transparent; }} QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}")
        cancel.setStyleSheet(f"QPushButton {{ color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px; background: transparent; }} QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}")
        save.clicked.connect(self._save)
        cancel.clicked.connect(self.hide)
        row.addWidget(save)
        row.addWidget(cancel)
        outer.addLayout(row)

        self._autosave = QTimer(self)
        self._autosave.setSingleShot(True)
        self._autosave.timeout.connect(self._save)
        for control in (self._assistant_name, self._assistant_description, self._welcome_message,
                        self._name, self._qualification, self._additional, self._personality,
                        self._instructions):
            signal = control.textChanged if isinstance(control, (QLineEdit, QTextEdit)) else None
            if signal:
                signal.connect(self._schedule_save)
        for control in (self._personality_preset, self._response_length, self._language, self._coding_language, self._skill_profile):
            control.currentTextChanged.connect(self._schedule_save)
        for control in self._behavior.values():
            control.toggled.connect(self._schedule_save)
        for control in self._preference_sliders.values():
            control.valueChanged.connect(self._schedule_save)

    def _schedule_save(self, *_):
        self._sync_status.setText("Saving…")
        self._sync_status.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        self._autosave.start(450)

    def _save(self):
        settings = {
            "assistant_name": self._assistant_name.text().strip() or "Friday",
            "assistant_description": self._assistant_description.text().strip()[:280],
            "welcome_message": self._welcome_message.text().strip()[:500],
            "user_name": self._name.text().strip()[:120],
            "user_qualification": self._qualification.text().strip()[:280],
            "additional_user_information": self._additional.toPlainText().strip()[:4000],
            "friday_personality_behavior": self._personality.toPlainText().strip()[:4000],
            "custom_instructions": self._instructions.toPlainText().strip()[:4000],
            "personality_preset": self._personality_preset.currentText(),
            "response_length": self._response_length.currentText(),
            "preferred_language": self._language.currentText(),
            "default_coding_language": self._coding_language.currentText(),
            "skill_profile": self._skill_profile.currentText().lower(),
        }
        settings.update({key: control.isChecked() for key, control in self._behavior.items()})
        settings.update({key: control.value() for key, control in self._preference_sliders.items()})
        self.saved.emit(settings)
        self._sync_status.setText("Saved locally • applied to new responses")
        self._sync_status.setStyleSheet(f"color: {C.GREEN}; background: transparent;")


class VoiceSettingsOverlay(QWidget):
    """Persistent voice controls for the Gemini Live session."""

    saved = pyqtSignal(str, float, int, int)  # voice, speed, pitch, volume
    preview_requested = pyqtSignal(str, float, int, int)
    _OW, _OH = 470, 420

    _VOICES = (
        ("Default", "Default", "Use Gemini's selected voice"),
        ("Puck", "Male", "Warm and conversational"),
        ("Charon", "Male", "Deep and measured"),
        ("Kore", "Female", "Clear and expressive"),
        ("Aoede", "Female", "Bright and friendly"),
        ("Fenrir", "Neutral", "Calm and balanced"),
    )

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            VoiceSettingsOverlay {{
                background: rgba(0, 6, 10, 248);
                border: 1px solid {C.BORDER_B}; border-radius: 6px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 17, 20, 17)
        lay.setSpacing(9)

        title = QLabel("VOICE SETTINGS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(title)

        note = QLabel(
            "Choose how Friday speaks. Voice changes take effect on the next "
            "live connection; volume applies immediately to new responses."
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setFont(QFont("Courier New", 7))
        note.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(note)

        field_style = (
            f"background: {C.PANEL2}; color: {C.TEXT}; border: 1px solid {C.BORDER}; "
            f"border-radius: 3px; padding: 4px 6px;"
        )
        label = QLabel("VOICE")
        label.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(label)
        self._voice = QComboBox()
        self._voice.setFixedHeight(31)
        self._voice.setFont(QFont("Courier New", 8))
        self._voice.setStyleSheet(f"QComboBox {{ {field_style} }} QComboBox::drop-down {{ border: none; }}")
        selected = str(config.get("voice_name", "") or "Default")
        for name, profile, description in self._VOICES:
            self._voice.addItem(f"{name}  —  {profile}", (name, description))
        for index, (name, _profile, _description) in enumerate(self._VOICES):
            if name.lower() == selected.lower():
                self._voice.setCurrentIndex(index)
                break
        lay.addWidget(self._voice)
        self._voice_hint = QLabel()
        self._voice_hint.setFont(QFont("Courier New", 7))
        self._voice_hint.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(self._voice_hint)
        self._voice.currentIndexChanged.connect(self._update_voice_hint)
        self._update_voice_hint()

        self._speed, self._speed_value = self._add_slider(
            lay, "SPEAKING SPEED", 70, 130,
            int(float(config.get("voice_speed", 1.0) or 1.0) * 100), "%"
        )
        self._pitch, self._pitch_value = self._add_slider(
            lay, "PITCH", -6, 6, int(config.get("voice_pitch", 0) or 0), " st"
        )
        self._volume, self._volume_value = self._add_slider(
            lay, "VOLUME", 0, 100, int(config.get("voice_volume", 1.0) * 100), "%"
        )
        self._speed.valueChanged.connect(lambda value: self._speed_value.setText(f"{value}%"))
        self._pitch.valueChanged.connect(lambda value: self._pitch_value.setText(f"{value:+d} st"))
        self._volume.valueChanged.connect(lambda value: self._volume_value.setText(f"{value}%"))

        controls = QHBoxLayout()
        preview = QPushButton("PREVIEW VOICE")
        save = QPushButton("SAVE SETTINGS")
        cancel = QPushButton("CANCEL")
        for button in (preview, save, cancel):
            button.setFixedHeight(32)
            button.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        preview.setStyleSheet(f"QPushButton {{ color: {C.ACC2}; border: 1px solid {C.ACC2}; border-radius: 3px; background: transparent; }} QPushButton:hover {{ background: {C.PRI_GHO}; }}")
        save.setStyleSheet(f"QPushButton {{ color: {C.PRI}; border: 1px solid {C.PRI_DIM}; border-radius: 3px; background: transparent; }} QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}")
        cancel.setStyleSheet(f"QPushButton {{ color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px; background: transparent; }}")
        preview.clicked.connect(self._preview)
        save.clicked.connect(self._save)
        cancel.clicked.connect(self.hide)
        controls.addWidget(preview)
        controls.addWidget(save)
        controls.addWidget(cancel)
        lay.addStretch()
        lay.addLayout(controls)

    def _add_slider(self, layout, title, minimum, maximum, value, suffix):
        row = QHBoxLayout()
        label = QLabel(title)
        label.setFixedWidth(125)
        label.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(max(minimum, min(maximum, value)))
        slider.setStyleSheet(f"QSlider::groove:horizontal {{ height: 4px; background: {C.BORDER}; }} QSlider::handle:horizontal {{ width: 12px; margin: -5px 0; background: {C.PRI}; border-radius: 6px; }}")
        display = QLabel(f"{slider.value()}{suffix}" if minimum >= 0 else f"{slider.value():+d}{suffix}")
        display.setFixedWidth(42)
        display.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        display.setFont(QFont("Courier New", 8))
        display.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        row.addWidget(label)
        row.addWidget(slider, stretch=1)
        row.addWidget(display)
        layout.addLayout(row)
        return slider, display

    def _settings(self):
        voice, _description = self._voice.currentData()
        return voice, self._speed.value() / 100, self._pitch.value(), self._volume.value()

    def _update_voice_hint(self):
        _voice, description = self._voice.currentData()
        self._voice_hint.setText(description)

    def _preview(self):
        self.preview_requested.emit(*self._settings())

    def _save(self):
        self.saved.emit(*self._settings())
        self.hide()


class ClipboardPanel(QWidget):
    """Floating panel shown when text is copied — offers quick Friday actions."""

    action_requested = pyqtSignal(str)
    _W, _H = 326, 112

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ClipboardPanel {{
                background: rgba(0, 8, 14, 248);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._W)
        self._clip_text = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 7)
        lay.setSpacing(4)

        hdr = QHBoxLayout(); hdr.setSpacing(4)
        icon_lbl = QLabel("◈  CLIPBOARD DETECTED")
        icon_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        hdr.addWidget(icon_lbl); hdr.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(16, 16)
        x_btn.setFont(QFont("Courier New", 8))
        x_btn.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.clicked.connect(self.hide)
        hdr.addWidget(x_btn)
        lay.addLayout(hdr)

        self._preview = QLabel()
        self._preview.setFont(QFont("Courier New", 8))
        self._preview.setStyleSheet(f"""
            color: {C.TEXT}; background: {C.PANEL2};
            border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 6px;
        """)
        self._preview.setWordWrap(False)
        self._preview.setFixedHeight(28)
        lay.addWidget(self._preview)

        btn_row = QHBoxLayout(); btn_row.setSpacing(4)
        _bs = (f"QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED}; "
               f"border: 1px solid {C.BORDER}; border-radius: 2px; }}"
               f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}")
        for label, cmd_fmt in [
            ("TRANSLATE", "Translate this text to English: {text}"),
            ("SUMMARISE", "Summarise this: {text}"),
            ("EXPLAIN",   "Explain this: {text}"),
            ("FIX",       "Fix grammar and spelling: {text}"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(22)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_bs)
            b.clicked.connect(lambda _, c=cmd_fmt: self._trigger(c))
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.hide)
        self.hide()

    def _trigger(self, cmd_fmt: str):
        if self._clip_text:
            self.action_requested.emit(cmd_fmt.format(text=self._clip_text[:800]))
        self.hide()

    def show_clipboard(self, text: str):
        self._clip_text = text
        preview = text[:58].replace('\n', ' ')
        if len(text) > 58:
            preview += "…"
        self._preview.setText(f'"{preview}"')
        self.show(); self.raise_()
        self._dismiss_timer.start(8000)


class RemoteKeyOverlay(QWidget):
    """Floating overlay — QR code for instant phone pairing + manual key fallback."""

    closed = pyqtSignal()

    _OW, _OH = 400, 465

    def __init__(self, url: str, key: str, auto_login_url: str = "",
                 manual_url: str = "", expiry_secs: int = 600, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            RemoteKeyOverlay {{
                background: rgba(0, 4, 12, 0.95);
                border: 1px solid {C.BORDER_B};
                border-radius: 14px;
            }}
        """)
        self._expiry          = time.time() + expiry_secs
        self._on_new_key      = None
        self._auto_login_url  = auto_login_url
        self._manual_url      = manual_url or url

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(5)

        def _lbl(txt, fs=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", fs,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            w.setWordWrap(True)
            return w

        lay.addWidget(_lbl("◈  REMOTE ACCESS", 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 1px 0;")
        lay.addWidget(sep)

        # ── QR code ───────────────────────────────────────────────────────────
        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(176, 176)
        self._qr_label.setStyleSheet(
            "background: white; border-radius: 10px; padding: 4px;"
        )
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self._qr_label)
        qr_row.addStretch()
        lay.addLayout(qr_row)

        self._update_qr(auto_login_url)

        lay.addWidget(_lbl("Scan with phone camera to connect instantly", 8, color=C.TEXT_DIM))

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 1px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_lbl("Or enter manually:", 7, color=C.TEXT_DIM,
                           align=Qt.AlignmentFlag.AlignLeft))

        self._url_lbl = QLabel(self._manual_url)
        self._url_lbl.setFont(QFont("Courier New", 8))
        self._url_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        self._url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._url_lbl)

        self._key_lbl = QLabel(key)
        self._key_lbl.setFont(QFont("Courier New", 28, QFont.Weight.Bold))
        self._key_lbl.setStyleSheet(f"""
            color: {C.ACC};
            background: {C.PANEL2};
            border: 1px solid {C.BORDER_B};
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 10px;
        """)
        self._key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._key_lbl)

        self._timer_lbl = QLabel()
        self._timer_lbl.setFont(QFont("Courier New", 8))
        self._timer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._timer_lbl)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        new_btn = QPushButton("NEW KEY")
        new_btn.setFixedHeight(32)
        new_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 5px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        new_btn.clicked.connect(self._refresh_key)
        btn_row.addWidget(new_btn)

        close_btn = QPushButton("DISMISS")
        close_btn.setFixedHeight(32)
        close_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 5px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self._do_close)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._ctimer = QTimer(self)
        self._ctimer.timeout.connect(self._tick)
        self._ctimer.start(1000)
        self._tick()

    def set_new_key_callback(self, fn) -> None:
        self._on_new_key = fn

    def _update_qr(self, url: str) -> None:
        if not url:
            self._qr_label.setText("—")
            return
        try:
            import qrcode as _qrmod
            from io import BytesIO
            qr = _qrmod.QRCode(
                box_size=5, border=2,
                error_correction=_qrmod.constants.ERROR_CORRECT_M,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(
                px.scaled(170, 170,
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )
        except ImportError:
            self._qr_label.setText("pip install\nqrcode[pil]")
            self._qr_label.setFont(QFont("Courier New", 8))
            self._qr_label.setStyleSheet(
                "color: #888; background: white; border-radius: 10px; padding: 4px;"
            )
        except Exception:
            self._qr_label.setText(url[:28])
            self._qr_label.setFont(QFont("Courier New", 7))
            self._qr_label.setStyleSheet(
                f"color: {C.PRI}; background: white; border-radius: 10px; padding: 4px;"
            )

    def _tick(self):
        remaining = max(0, int(self._expiry - time.time()))
        m, s = divmod(remaining, 60)
        self._timer_lbl.setText(f"Key expires in  {m:02d}:{s:02d}")
        if remaining == 0:
            self._do_close()

    def mark_connected(self) -> None:
        """Call from any thread when a phone successfully connects."""
        self._ctimer.stop()
        self._key_lbl.setText("CONNECTED")
        self._key_lbl.setStyleSheet(f"""
            color: {C.GREEN};
            background: rgba(34,197,94,0.08);
            border: 2px solid rgba(34,197,94,0.4);
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 4px;
        """)
        self._qr_label.setText("✓")
        self._qr_label.setFont(QFont("Courier New", 54, QFont.Weight.Bold))
        self._qr_label.setStyleSheet(
            "color: #00ff88; background: #001a0d; border-radius: 10px;"
        )
        self._timer_lbl.setText("Phone connected — Friday ready")
        self._timer_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")

    def _refresh_key(self):
        if self._on_new_key:
            result = self._on_new_key()
            if result:
                url    = result[0]
                key    = result[1]
                auto   = result[2] if len(result) >= 3 else ""
                manual = result[3] if len(result) >= 4 else url
                self._manual_url     = manual or url
                self._url_lbl.setText(self._manual_url)
                self._key_lbl.setText(key)
                self._auto_login_url = auto
                self._update_qr(auto or url)
                self._expiry = time.time() + 600
                self._key_lbl.setStyleSheet(f"""
                    color: {C.ACC};
                    background: {C.PANEL2};
                    border: 1px solid {C.BORDER_B};
                    border-radius: 8px;
                    padding: 6px 4px;
                    letter-spacing: 10px;
                """)
                self._timer_lbl.setStyleSheet(
                    f"color: {C.TEXT_MED}; background: transparent;"
                )
                self._ctimer.start(1000)
                self._tick()

    def _do_close(self):
        self._ctimer.stop()
        self.hide()
        self.closed.emit()


class MainWindow(QMainWindow):
    _log_sig        = pyqtSignal(str)
    _state_sig      = pyqtSignal(str)
    _content_sig    = pyqtSignal(str, str)   # (title, text) — thread-safe content display
    _reconfig_sig   = pyqtSignal()           # trigger setup overlay from any thread
    _camera_sig     = pyqtSignal(bytes)      # show camera frame preview (small overlay)
    _cam_stream_sig = pyqtSignal(bool)       # True=start live stream, False=stop
    _cam_frame_sig  = pyqtSignal(bytes)      # live camera frame → HUD area
    _cam_request_sig = pyqtSignal(bool)      # explicit camera on/off request
    _cam_status_sig = pyqtSignal(str, str)   # state, diagnostic
    _mic_status_sig = pyqtSignal(str, str)   # state, diagnostic
    _clipboard_sig  = pyqtSignal(str)        # clipboard text changed (thread-safe)

    def __init__(self, face_path: str):
        super().__init__()
        self._face_path = face_path

        # Load customization from config
        _cfg = _read_full_config()
        self._assistant_name: str = (_cfg.get("assistant_name") or "Friday").strip()
        _display = self._assistant_name.upper()

        # Kayıtlı UI rengini panel/stylesheet'ler kurulmadan ÖNCE uygula
        _ui_theme = (_cfg.get("ui_theme") or "").strip()
        _ui_color = (_cfg.get("ui_color") or "").strip()
        self._design_mode = (_cfg.get("design_mode") or DEFAULT_DESIGN_MODE).strip()
        if self._design_mode not in _DESIGN_MODES:
            self._design_mode = DEFAULT_DESIGN_MODE
        if _ui_theme in _THEMES:
            apply_ui_theme(_ui_theme)
        elif _ui_color and _ui_color.lower() != DEFAULT_UI_COLOR:
            # Backward compatibility for existing accent-only configurations.
            apply_ui_accent(_ui_color)

        self.setWindowTitle(f"{self._assistant_name} — Personal AI Assistant")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command   = None
        self.on_remote_clicked = None   # callable: () -> (url, key) | None
        self.on_interrupt      = None   # callable: () -> None — stop Friday mid-speech
        self.on_personalization_changed = None
        # Start with the microphone off unless the user explicitly enabled it.
        # This keeps the OS permission request tied to a deliberate mic action.
        self._muted            = not bool(_cfg.get("microphone_enabled", False))
        # track last sent user text to debounce duplicate sends
        self._last_user_sent_text: str | None = None
        self._last_user_sent_time: float = 0.0
        self._current_file: str | None = None
        self._remote_overlay: RemoteKeyOverlay | None = None
        self._customize_overlay: CustomizeOverlay | None = None
        self._theme_overlay: ThemeOverlay | None = None
        self._personalization_overlay: PersonalizationOverlay | None = None
        self._voice_settings_overlay: VoiceSettingsOverlay | None = None
        self.on_voice_preview = None

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel, stretch=0)

        # Center column: HUD + resizable content panel via QSplitter
        self.hud = HudCanvas(face_path, _display, self._design_mode)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._content_panel = self._build_content_panel()

        # Live camera container — replaces HUD when camera stream is active
        _cam_cont = QWidget()
        _cam_cont.setStyleSheet("background: #000308;")
        _cam_v = QVBoxLayout(_cam_cont)
        _cam_v.setContentsMargins(0, 0, 0, 0)
        _cam_v.setSpacing(0)
        _cam_hdr = QHBoxLayout()
        _cam_hdr.setContentsMargins(8, 5, 8, 5)
        _cam_title = QLabel("◈  CAMERA FEED")
        _cam_title.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        _cam_title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        _cam_hdr.addWidget(_cam_title)
        _cam_hdr.addStretch()
        _cam_x = QPushButton("✕  CLOSE")
        _cam_x.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        _cam_x.setCursor(Qt.CursorShape.PointingHandCursor)
        _cam_x.setStyleSheet(f"""
            QPushButton {{
                color: {C.TEXT_DIM}; background: transparent;
                border: none; padding: 2px 6px;
            }}
            QPushButton:hover {{ color: {C.PRI}; }}
        """)
        _cam_x.clicked.connect(self.stop_camera_stream)
        _cam_hdr.addWidget(_cam_x)
        _cam_v.addLayout(_cam_hdr)
        self._cam_live_lbl = QLabel()
        self._cam_live_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cam_live_lbl.setStyleSheet("background: transparent;")
        self._cam_live_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        _cam_v.addWidget(self._cam_live_lbl, stretch=1)

        # Stack: 0 = animated HUD, 1 = live camera
        self._hud_cam_stack = QStackedWidget()
        self._hud_cam_stack.addWidget(self.hud)
        self._hud_cam_stack.addWidget(_cam_cont)

        self._center_split = QSplitter(Qt.Orientation.Vertical)
        self._center_split.setStyleSheet(f"""
            QSplitter::handle {{
                background: {C.BORDER};
                height: 4px;
            }}
            QSplitter::handle:hover {{
                background: {C.PRI_DIM};
            }}
        """)
        self._center_split.addWidget(self._hud_cam_stack)
        self._center_split.addWidget(self._content_panel)
        self._center_split.setStretchFactor(0, 3)
        self._center_split.setStretchFactor(1, 1)
        self._center_split.setCollapsible(0, False)
        body.addWidget(self._center_split, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=0)

        root.addLayout(body, stretch=1)
        root.addWidget(self._build_footer())

        # Quick-access drawer (floating overlay, built after central widget layout is done)
        self._quick_drawer = self._build_quick_drawer()
        self._update_autostart_btn(self._check_autostart())
        from memory.config_manager import get_brief_enabled as _gbe
        self._update_brief_btn(_gbe())

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Metrik güncelleme timer'ı
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)
        self._content_sig.connect(self._show_content)
        self._reconfig_sig.connect(self._show_setup)
        self._camera_sig.connect(self._show_camera_frame)
        self._cam_stream_sig.connect(self._on_cam_stream)
        self._cam_frame_sig.connect(self._on_cam_frame)
        self._cam_request_sig.connect(self._set_camera_requested)
        self._cam_status_sig.connect(self._set_camera_status)
        self._mic_status_sig.connect(self._set_microphone_status)
        self._clipboard_sig.connect(self._show_clipboard_panel)
        self._cam_stop = threading.Event()
        self._cam_thread: threading.Thread | None = None
        self._camera_active = False

        # Camera preview overlay (child of central widget, positioned in resizeEvent)
        self._cam_preview = _CameraPreview(self.centralWidget())

        # Clipboard panel (child of central widget, bottom-center)
        self._clipboard_panel = ClipboardPanel(self.centralWidget())
        self._clipboard_panel.action_requested.connect(self._on_clipboard_action)
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)
        sc_intr = QShortcut(QKeySequence("Escape"), self)
        sc_intr.activated.connect(self._do_interrupt)

    def _show_camera_frame(self, img_bytes: bytes):
        """Slot — display camera preview overlay (main thread)."""
        self._cam_preview.show_frame(img_bytes)
        cw = self.centralWidget()
        pw = _CameraPreview._W
        ph = self._cam_preview.height()
        self._cam_preview.setGeometry(
            cw.width() - _RIGHT_W - pw - 12,
            cw.height() - ph - 28,
            pw, ph,
        )

    # --- Live camera stream in HUD area ------------------------------------
    def _on_cam_stream(self, start: bool) -> None:
        if start:
            self._hud_cam_stack.setCurrentIndex(1)
        else:
            self._hud_cam_stack.setCurrentIndex(0)
            self._cam_live_lbl.clear()

    def _on_cam_frame(self, data: bytes) -> None:
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            w, h = self._cam_live_lbl.width(), self._cam_live_lbl.height()
            if w > 1 and h > 1:
                self._cam_live_lbl.setPixmap(
                    px.scaled(w, h,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
                )

    def start_camera_stream(self) -> None:
        """Request camera access from any thread; the UI thread owns the stream."""
        self._cam_request_sig.emit(True)

    def _set_camera_requested(self, enabled: bool) -> None:
        if not enabled:
            self._cam_stop.set()
            return
        if self._cam_thread and self._cam_thread.is_alive():
            return
        self._cam_stop.clear()
        self._set_camera_status("requesting", "Requesting camera access…")
        self._cam_thread = threading.Thread(target=self._cam_loop, daemon=True, name="cam-stream")
        self._cam_thread.start()

    def _cam_loop(self) -> None:
        failed = False
        try:
            import cv2
            # Reuse camera index detected by screen_processor (cached in api_keys.json)
            cam_idx = 0
            try:
                import json as _j
                cfg = _j.loads((CONFIG_DIR / "api_keys.json").read_text())
                cam_idx = int(cfg.get("camera_index", 0))
            except Exception:
                pass
            try:
                backend = cv2.CAP_DSHOW if _OS == "Windows" else cv2.CAP_ANY
            except AttributeError:
                backend = 0
            cap = cv2.VideoCapture(cam_idx, backend)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                failed = True
                self._cam_status_sig.emit("error", "Camera unavailable. Check its privacy permission or close another app using it.")
                return
            # warm-up frames
            for _ in range(5):
                cap.read()
            self._cam_status_sig.emit("on", "Camera is on")
            self._cam_stream_sig.emit(True)
            while not self._cam_stop.wait(0.033) and cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                    self._cam_frame_sig.emit(buf.tobytes())
            cap.release()
        except Exception as e:
            failed = True
            print(f"[Camera] Stream error: {e}")
            self._cam_status_sig.emit("error", f"Camera error: {str(e)[:110]}")
        finally:
            self._cam_stream_sig.emit(False)
            if not failed:
                self._cam_status_sig.emit("off", "Camera off")

    def stop_camera_stream(self) -> None:
        self._cam_request_sig.emit(False)

    def _set_camera_status(self, status: str, message: str = "") -> None:
        self._camera_active = status == "on"
        if not hasattr(self, "_camera_btn"):
            return
        if status == "on":
            self._camera_btn.setText("CAMERA ON  •  CLICK TO TURN OFF")
            self._camera_btn.setStyleSheet(f"QPushButton {{ background: #001a08; color: {C.GREEN}; border: 1px solid {C.GREEN}; border-radius: 3px; }} QPushButton:hover {{ background: #002010; }}")
            self._camera_status.setText("CAMERA: ON  •  LIVE PREVIEW")
            self._camera_status.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        elif status == "requesting":
            self._camera_btn.setText("CAMERA: REQUESTING ACCESS…")
            self._camera_btn.setStyleSheet(f"QPushButton {{ color: {C.ACC2}; border: 1px solid {C.ACC2}; border-radius: 3px; background: transparent; }}")
            self._camera_status.setText("CAMERA: REQUESTING PERMISSION")
            self._camera_status.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        elif status == "error":
            self._camera_btn.setText("CAMERA OFF  •  RETRY")
            self._camera_btn.setStyleSheet(f"QPushButton {{ color: {C.RED}; border: 1px solid {C.RED}; border-radius: 3px; background: transparent; }}")
            self._camera_status.setText("CAMERA: UNAVAILABLE")
            self._camera_status.setStyleSheet(f"color: {C.RED}; background: transparent;")
            self._log.append_log(f"ERR: {message}")
        else:
            self._camera_btn.setText("CAMERA OFF  •  CLICK TO TURN ON")
            self._camera_btn.setStyleSheet(f"QPushButton {{ color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px; background: transparent; }} QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}")
            self._camera_status.setText("CAMERA: OFF")
            self._camera_status.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

    def _toggle_camera(self) -> None:
        if self._camera_active or (self._cam_thread and self._cam_thread.is_alive()):
            self.stop_camera_stream()
        else:
            self.start_camera_stream()

    def _set_microphone_status(self, status: str, message: str = "") -> None:
        if not hasattr(self, "_mic_status"):
            return
        if status == "listening":
            self._mic_status.setText("MIC: LISTENING  •  CONTINUOUS VOICE")
            self._mic_status.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        elif status == "error":
            self._mic_status.setText("MIC: UNAVAILABLE  •  CHECK PERMISSION")
            self._mic_status.setStyleSheet(f"color: {C.RED}; background: transparent;")
            self._log.append_log(f"ERR: {message}")
        else:
            self._mic_status.setText("MIC: OFF")
            self._mic_status.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

    # ------------------------------------------------------------------
    # Icon generation — arc-reactor style, rendered with Pillow
    # ------------------------------------------------------------------
    @staticmethod
    def _build_friday_icon(out_path: Path) -> bool:
        """
        Render a FRIDAY arc-reactor icon at 4× resolution and downsample
        for crisp results at all sizes. Saves a multi-res .ico to out_path.
        Returns True on success.
        """
        try:
            import math
            import PIL.Image
            import PIL.ImageDraw
            import PIL.ImageFilter
        except ImportError:
            return False

        CYAN   = (0, 212, 255)
        DIM    = (0, 100, 140)
        DARK   = (0, 6, 10)
        GLOW   = (0, 160, 200)
        WHITE  = (220, 240, 255)

        def _render(sz: int) -> PIL.Image.Image:
            S  = sz * 4                     # draw at 4× then downscale
            img = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
            d   = PIL.ImageDraw.Draw(img)
            cx = cy = S // 2

            # ── filled background circle ──────────────────────────────────
            R = S // 2 - 2
            d.ellipse([cx-R, cy-R, cx+R, cy+R], fill=(*DARK, 255))

            # ── outer border ring ─────────────────────────────────────────
            lw = max(2, S // 40)
            d.ellipse([cx-R, cy-R, cx+R, cy+R],
                      outline=(*CYAN, 220), width=lw)

            # ── mid decorative ring ───────────────────────────────────────
            R2 = int(R * 0.72)
            d.ellipse([cx-R2, cy-R2, cx+R2, cy+R2],
                      outline=(*DIM, 180), width=max(1, lw // 2))

            # ── 6 radial spokes (hex bolt) ────────────────────────────────
            R_inner = int(R * 0.30)
            R_outer = int(R * 0.62)
            spoke_w = max(1, S // 80)
            for i in range(6):
                angle = math.radians(i * 60 - 30)
                x1 = cx + int(R_inner * math.cos(angle))
                y1 = cy + int(R_inner * math.sin(angle))
                x2 = cx + int(R_outer * math.cos(angle))
                y2 = cy + int(R_outer * math.sin(angle))
                d.line([x1, y1, x2, y2], fill=(*GLOW, 200), width=spoke_w)

            # ── 6 tick marks on outer ring ────────────────────────────────
            for i in range(6):
                angle = math.radians(i * 60)
                for dr in range(lw * 2):
                    rx = (R - lw - dr)
                    d.point(
                        [cx + int(rx * math.cos(angle)),
                         cy + int(rx * math.sin(angle))],
                        fill=(*WHITE, 220),
                    )

            # ── inner glowing ring ────────────────────────────────────────
            Ri = int(R * 0.26)
            d.ellipse([cx-Ri, cy-Ri, cx+Ri, cy+Ri],
                      outline=(*CYAN, 255), width=max(2, lw))

            # ── bright glow soft blur applied before core ─────────────────
            # (draw a slightly larger cyan circle on a separate layer)
            glow_layer = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
            gd = PIL.ImageDraw.Draw(glow_layer)
            Rc = int(R * 0.13)
            gd.ellipse([cx-Rc*2, cy-Rc*2, cx+Rc*2, cy+Rc*2],
                       fill=(*CYAN, 110))
            glow_layer = glow_layer.filter(PIL.ImageFilter.GaussianBlur(S // 14))
            img = PIL.Image.alpha_composite(img, glow_layer)
            d   = PIL.ImageDraw.Draw(img)

            # ── core dot ──────────────────────────────────────────────────
            d.ellipse([cx-Rc, cy-Rc, cx+Rc, cy+Rc], fill=(*WHITE, 255))

            # ── downscale to target size ──────────────────────────────────
            return img.resize((sz, sz), PIL.Image.LANCZOS)

        try:
            sizes  = [256, 128, 64, 48, 32, 16]
            frames = [_render(s) for s in sizes]
            frames[0].save(
                out_path,
                format="ICO",
                append_images=frames[1:],
                sizes=[(s, s) for s in sizes],
            )
            return True
        except Exception as e:
            print(f"[Shortcut] ⚠️  Icon generation failed: {e}")
            return False

    @staticmethod
    def _create_lnk_windows(lnk: str, target: str, args: str,
                             work_dir: str, icon_loc: str) -> None:
        """
        Create a Windows .lnk shortcut WITHOUT launching PowerShell or cmd.
        Tries win32com (pywin32) first; falls back to wscript.exe + VBScript.
        wscript.exe is a GUI-mode host — it never opens a console window.
        """
        # ── Option 1: pywin32 (pure Python COM, zero subprocess) ──────────
        try:
            from win32com.client import Dispatch   # type: ignore
            sh = Dispatch("WScript.Shell")
            sc = sh.CreateShortCut(lnk)
            sc.TargetPath       = target
            sc.Arguments        = f'"{args}"'
            sc.WorkingDirectory = work_dir
            sc.Description      = "J.A.R.V.I.S AI Assistant"
            sc.IconLocation     = icon_loc
            sc.save()
            return
        except ImportError:
            pass

        # ── Option 2: wscript.exe + VBScript (always available on Windows,
        #    GUI-mode executable — never opens a console window) ────────────
        vbs = "\n".join([
            'Set ws = CreateObject("WScript.Shell")',
            f'Set sc = ws.CreateShortcut("{lnk}")',
            f'sc.TargetPath = "{target}"',
            f'sc.Arguments = Chr(34) & "{args}" & Chr(34)',
            f'sc.WorkingDirectory = "{work_dir}"',
            'sc.Description = "J.A.R.V.I.S AI Assistant"',
            f'sc.IconLocation = "{icon_loc}"',
            'sc.Save',
        ])
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".vbs")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(vbs)
            proc = subprocess.Popen(
                ["wscript.exe", "/nologo", tmp],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
            proc.wait(timeout=10)
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    @staticmethod
    def _get_desktop_dir() -> Path:
        """
        Resolve the user's REAL desktop directory instead of assuming
        ~/Desktop, which breaks when:
          • OneDrive "Known Folder Move" relocates the desktop
            (C:/Users/x/OneDrive/Desktop) — very common on Win 10/11;
          • the XDG desktop is localized on Linux (~/Masaüstü,
            ~/Schreibtisch, ~/Bureau, …).
        Falls back to ~/Desktop only as a last resort.
        """
        home = Path.home()
        _os = platform.system()

        if _os == "Windows":
            # ── 1) SHGetKnownFolderPath(FOLDERID_Desktop) — the canonical
            #       answer; follows OneDrive redirection. No dependencies. ──
            try:
                import ctypes
                from ctypes import wintypes

                class _GUID(ctypes.Structure):
                    _fields_ = [("Data1", wintypes.DWORD),
                                ("Data2", wintypes.WORD),
                                ("Data3", wintypes.WORD),
                                ("Data4", ctypes.c_ubyte * 8)]

                # FOLDERID_Desktop {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}
                fid = _GUID(0xB4BFCC3A, 0xDB2C, 0x424C,
                            (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9,
                                                 0x9A, 0x87, 0xC6, 0x41))
                buf = ctypes.c_wchar_p()
                if ctypes.windll.shell32.SHGetKnownFolderPath(
                        ctypes.byref(fid), 0, None, ctypes.byref(buf)) == 0:
                    p = Path(buf.value)
                    ctypes.windll.ole32.CoTaskMemFree(buf)
                    if p.is_dir():
                        return p
            except Exception:
                pass

            # ── 2) Registry: User Shell Folders (may contain %VARS%) ──────
            try:
                import winreg
                with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion"
                        r"\Explorer\User Shell Folders") as key:
                    val, _t = winreg.QueryValueEx(key, "Desktop")
                p = Path(os.path.expandvars(val))
                if p.is_dir():
                    return p
            except Exception:
                pass

        elif _os == "Linux":
            # ── xdg-user-dir honours localized names (~/Masaüstü, …) ──────
            try:
                out = subprocess.run(["xdg-user-dir", "DESKTOP"],
                                     capture_output=True, text=True, timeout=5)
                p = Path(out.stdout.strip())
                if out.stdout.strip() and p != home and p.is_dir():
                    return p
            except Exception:
                pass
            try:
                cfg = home / ".config" / "user-dirs.dirs"
                for line in cfg.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("XDG_DESKTOP_DIR"):
                        val = line.split("=", 1)[1].strip().strip('"')
                        p = Path(val.replace("$HOME", str(home)))
                        if p != home and p.is_dir():
                            return p
            except Exception:
                pass

        # macOS: ~/Desktop is always the real path (localization is
        # display-only). Everything else lands here as a last resort.
        return home / "Desktop"

    def _create_desktop_shortcut(self):
        """
        Create a desktop shortcut on Windows / macOS / Linux.
        Never opens a terminal, console, or PowerShell window on any platform.
        """
        import stat as _stat
        script  = Path(__file__).resolve().parent / "main.py"
        python  = Path(sys.executable)
        desktop = self._get_desktop_dir()

        # Arc-reactor icon (.ico — also exported as .png for Linux/macOS)
        ico_path = Path(__file__).resolve().parent / "config" / "friday.ico"
        if not ico_path.exists():
            self._build_friday_icon(ico_path)

        try:
            _os = platform.system()

            # ── Windows ───────────────────────────────────────────────────────
            if _os == "Windows":
                pythonw  = python.parent / "pythonw.exe"
                target   = str(pythonw if pythonw.exists() else python)
                lnk      = str(desktop / "Friday.lnk")
                icon_loc = str(ico_path) if ico_path.exists() else f"{target},0"
                self._create_lnk_windows(lnk, target, str(script),
                                         str(script.parent), icon_loc)

            # ── macOS — proper .app bundle (no Terminal window) ───────────────
            elif _os == "Darwin":
                app     = desktop / "Friday.app"
                mac_dir = app / "Contents" / "MacOS"
                res_dir = app / "Contents" / "Resources"
                mac_dir.mkdir(parents=True, exist_ok=True)
                res_dir.mkdir(exist_ok=True)

                # Launcher executable (bash — runs as background process,
                # macOS does NOT open Terminal for executables inside .app bundles)
                launcher = mac_dir / "Friday"
                launcher.write_text(
                    "#!/usr/bin/env bash\n"
                    f'cd "{script.parent}"\n'
                    f'exec "{python}" "{script}"\n'
                )
                launcher.chmod(launcher.stat().st_mode
                               | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH)

                # Minimal Info.plist (required for .app recognition)
                (app / "Contents" / "Info.plist").write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                    '<plist version="1.0"><dict>\n'
                    '  <key>CFBundleExecutable</key><string>FRIDAY</string>\n'
                    '  <key>CFBundleIdentifier</key>'
                    '<string>com.friday.assistant</string>\n'
                    '  <key>CFBundleName</key><string>Friday</string>\n'
                    '  <key>CFBundlePackageType</key><string>APPL</string>\n'
                    '  <key>CFBundleVersion</key><string>1.0</string>\n'
                    '</dict></plist>\n'
                )

                # Optional: copy icon as .icns (skip silently if Pillow is missing)
                try:
                    import PIL.Image
                    icns = res_dir / "AppIcon.icns"
                    PIL.Image.open(ico_path).save(icns, format="ICNS")
                    # Inject icon reference into plist
                    plist = app / "Contents" / "Info.plist"
                    txt = plist.read_text()
                    plist.write_text(
                        txt.replace(
                            '</dict></plist>',
                            '  <key>CFBundleIconFile</key>'
                            '<string>AppIcon</string>\n</dict></plist>\n',
                        )
                    )
                except Exception:
                    pass  # icon is optional

            # ── Linux — .desktop file (Terminal=false, no console) ────────────
            else:
                # Export .ico → .png for better desktop integration
                png_path = ico_path.with_suffix(".png")
                if not png_path.exists() and ico_path.exists():
                    try:
                        import PIL.Image
                        PIL.Image.open(ico_path).resize(
                            (256, 256), PIL.Image.LANCZOS
                        ).save(png_path, format="PNG")
                    except Exception:
                        png_path = ico_path  # fallback to .ico

                icon_line = f"Icon={png_path}\n" if png_path.exists() else ""
                desk = desktop / "friday.desktop"
                desk.write_text(
                    "[Desktop Entry]\n"
                    "Name=Friday\n"
                    f"Exec={python} {script}\n"
                    f"Path={script.parent}\n"
                    "Type=Application\n"
                    "Terminal=false\n"
                    "Categories=Utility;\n"
                    + icon_line
                )
                desk.chmod(desk.stat().st_mode | 0o755)

            self._log.append_log("SYS: Desktop shortcut created.")
        except Exception as e:
            self._log.append_log(f"ERR: Shortcut failed — {e}")

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cw = self.centralWidget()
        if self._overlay and self._overlay.isVisible():
            ow, oh = 460, 390
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._remote_overlay and self._remote_overlay.isVisible():
            ow, oh = RemoteKeyOverlay._OW, RemoteKeyOverlay._OH
            self._remote_overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._customize_overlay and self._customize_overlay.isVisible():
            ow, oh = CustomizeOverlay._OW, CustomizeOverlay._OH
            self._customize_overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        for overlay, overlay_type in (
            (self._theme_overlay, ThemeOverlay),
            (self._personalization_overlay, PersonalizationOverlay),
        ):
            if overlay and overlay.isVisible():
                ow = min(overlay_type._OW, cw.width() - 16)
                oh = min(overlay_type._OH, cw.height() - 16)
                overlay.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        # Camera preview — bottom-right corner of the center/HUD area
        pw = _CameraPreview._W
        ph = self._cam_preview.height() or _CameraPreview._H
        self._cam_preview.setGeometry(
            cw.width() - _RIGHT_W - pw - 12,
            cw.height() - ph - 28,
            pw, ph,
        )
        # Clipboard panel — bottom-center
        if hasattr(self, '_clipboard_panel') and self._clipboard_panel.isVisible():
            self._position_clipboard_panel()
        # Quick drawer — reposition if open
        if hasattr(self, '_quick_drawer') and self._quick_drawer.isVisible():
            self._position_quick_drawer()

    def _update_metrics(self):
        snap = _metrics.snapshot()

        # CPU
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")

        # MEM
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")

        # NET
        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)  # 10 MB/s = %100
        self._bar_net.set_value(net_pct, net_str)

        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
        else:
            self._bar_tmp.set_value(0, "N/A")

        try:
            boot_t  = psutil.boot_time()
            elapsed = time.time() - boot_t
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
        except Exception:
            self._uptime_lbl.setText("UP  --:--")

        try:
            proc_count = len(psutil.pids())
            self._proc_lbl.setText(f"PROC  {proc_count}")
        except Exception:
            self._proc_lbl.setText("PROC  --")


    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(54)
        w.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER_B};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 0, 16, 0)

        def _badge(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addSpacing(8)
        self._drawer_btn = QPushButton("⚙")
        self._drawer_btn.setFixedSize(26, 26)
        self._drawer_btn.setFont(QFont("Courier New", 11))
        self._drawer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drawer_btn.setToolTip("Settings & Controls")
        self._drawer_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 4px;
            }}
            QPushButton:hover {{ color: {C.PRI}; border-color: {C.PRI_DIM}; }}
            QPushButton:checked {{ color: {C.PRI}; border-color: {C.PRI}; background: {C.PRI_GHO}; }}
        """)
        self._drawer_btn.setCheckable(True)
        self._drawer_btn.clicked.connect(self._toggle_drawer)
        lay.addWidget(self._drawer_btn)
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(1)
        _disp = self._assistant_name.upper()
        self._title_lbl = QLabel(_disp)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setFont(QFont("Courier New", 17, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        mid.addWidget(self._title_lbl)
        _sub_text = ("Just A Rather Very Intelligent System"
                 if _disp in ("FRIDAY", "J.A.R.V.I.S")
                 else "Personal AI Assistant")
        self._sub_lbl = QLabel(_sub_text)
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_lbl.setFont(QFont("Courier New", 7))
        self._sub_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        mid.addWidget(self._sub_lbl)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)

        hdr = QLabel("◈ SYS MONITOR")
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)
        lay.addSpacing(2)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff6688")

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net,
                    self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(4)

        info_panel = QWidget()
        info_panel.setStyleSheet(
            f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;"
        )
        ip_lay = QVBoxLayout(info_panel)
        ip_lay.setContentsMargins(6, 5, 6, 5)
        ip_lay.setSpacing(3)

        self._uptime_lbl = QLabel("UP  --:--")
        self._uptime_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        ip_lay.addWidget(self._uptime_lbl)

        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(QFont("Courier New", 8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        ip_lay.addWidget(self._proc_lbl)

        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS  {os_name}")
        os_lbl.setFont(QFont("Courier New", 8))
        os_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        ip_lay.addWidget(os_lbl)

        lay.addWidget(info_panel)
        lay.addSpacing(4)

        lay.addStretch()

        for txt, col in [
            ("AI CORE\nACTIVE",  C.GREEN),
            ("SEC\nCLEARED",     C.PRI),
            ("PROTOCOL\nXLIX",   C.TEXT_DIM),
        ]:
            lbl = QLabel(txt)
            lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {col}; background: {C.PANEL2};"
                f"border: 1px solid {C.BORDER_A}; border-radius: 3px; padding: 4px;"
            )
            lay.addWidget(lbl)

        return w
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        def _sec(txt):
            l = QLabel(f"▸ {txt}")
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            return l

        lay.addWidget(_sec("ACTIVITY LOG"))
        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_sec("FILE UPLOAD"))
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("No file loaded — drop or click above to upload")
        self._file_hint.setFont(QFont("Courier New", 7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_sec("COMMAND INPUT"))
        lay.addLayout(self._build_input_row())

        self._interrupt_btn = QPushButton("✋  INTERRUPT  [ESC]")
        self._interrupt_btn.setFixedHeight(34)
        self._interrupt_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._interrupt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._interrupt_btn.setStyleSheet(f"""
            QPushButton {{
                background: #140008; color: {C.MUTED_C};
                border: 1px solid {C.MUTED_C}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: #200010; border: 1px solid #ff6688;
            }}
            QPushButton:pressed {{
                background: #300018;
            }}
        """)
        self._interrupt_btn.clicked.connect(self._do_interrupt)
        lay.addWidget(self._interrupt_btn)

        self._mute_btn = QPushButton("🎙  MICROPHONE ACTIVE")
        self._mute_btn.setFixedHeight(30)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        self._mic_status = QLabel()
        self._mic_status.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._mic_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_microphone_status("off" if self._muted else "listening")
        lay.addWidget(self._mic_status)

        self._camera_btn = QPushButton("CAMERA OFF  •  CLICK TO TURN ON")
        self._camera_btn.setFixedHeight(30)
        self._camera_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._camera_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._camera_btn.clicked.connect(self._toggle_camera)
        lay.addWidget(self._camera_btn)
        self._camera_status = QLabel("CAMERA: OFF")
        self._camera_status.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._camera_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._camera_status)
        self._set_camera_status("off")

        return w

    def _build_quick_drawer(self) -> QWidget:
        """Floating overlay panel shown when the ⚙ header button is toggled."""
        _BTN_STYLE_PRI = f"""
            QPushButton {{
                background: #00091a; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
                text-align: left; padding: 0 8px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """
        _BTN_STYLE_DIM = f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
                text-align: left; padding: 0 8px;
            }}
            QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}
        """

        w = QWidget(self.centralWidget())
        w.setObjectName("QuickDrawer")
        w.setStyleSheet(f"""
            QWidget#QuickDrawer {{
                background: {C.DARK};
                border: 1px solid {C.BORDER_B};
                border-top: none;
                border-radius: 0 0 6px 6px;
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(5)

        hdr = QLabel("◈ CONTROLS")
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)

        remote_btn = QPushButton("◉  REMOTE CONTROL")
        remote_btn.setFixedHeight(30)
        remote_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        remote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remote_btn.setStyleSheet(_BTN_STYLE_PRI)
        remote_btn.clicked.connect(self._open_remote)
        lay.addWidget(remote_btn)

        fs_btn = QPushButton("⛶  FULLSCREEN  [F11]")
        fs_btn.setFixedHeight(26)
        fs_btn.setFont(QFont("Courier New", 7))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(_BTN_STYLE_DIM)
        fs_btn.clicked.connect(self._toggle_fullscreen)
        lay.addWidget(fs_btn)

        sc_btn = QPushButton("⊞  CREATE DESKTOP SHORTCUT")
        sc_btn.setFixedHeight(26)
        sc_btn.setFont(QFont("Courier New", 7))
        sc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sc_btn.setStyleSheet(_BTN_STYLE_DIM)
        sc_btn.clicked.connect(self._create_desktop_shortcut)
        lay.addWidget(sc_btn)

        self._autostart_btn = QPushButton("◉  AUTO-START: OFF")
        self._autostart_btn.setFixedHeight(26)
        self._autostart_btn.setFont(QFont("Courier New", 7))
        self._autostart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._autostart_btn.clicked.connect(self._toggle_autostart)
        lay.addWidget(self._autostart_btn)

        cust_btn = QPushButton("⚙  CUSTOMISE ASSISTANT")
        cust_btn.setFixedHeight(26)
        cust_btn.setFont(QFont("Courier New", 7))
        cust_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cust_btn.setStyleSheet(_BTN_STYLE_DIM)
        cust_btn.clicked.connect(self._open_customize)
        lay.addWidget(cust_btn)

        themes_hdr = QLabel("THEMES")
        themes_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        themes_hdr.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; padding-top: 4px;")
        lay.addWidget(themes_hdr)
        themes_btn = QPushButton("◈  THEMES & APPEARANCE")
        themes_btn.setFixedHeight(26)
        themes_btn.setFont(QFont("Courier New", 7))
        themes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        themes_btn.setStyleSheet(_BTN_STYLE_DIM)
        themes_btn.clicked.connect(self._open_themes)
        lay.addWidget(themes_btn)

        personalization_hdr = QLabel("PERSONALIZATION")
        personalization_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        personalization_hdr.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; padding-top: 4px;")
        lay.addWidget(personalization_hdr)
        personalization_btn = QPushButton("◈  PERSONALIZATION")
        personalization_btn.setFixedHeight(26)
        personalization_btn.setFont(QFont("Courier New", 7))
        personalization_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        personalization_btn.setStyleSheet(_BTN_STYLE_DIM)
        personalization_btn.clicked.connect(self._open_personalization)
        lay.addWidget(personalization_btn)

        voice_hdr = QLabel("VOICE")
        voice_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        voice_hdr.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; padding-top: 4px;")
        lay.addWidget(voice_hdr)
        voice_btn = QPushButton("◈  VOICE SETTINGS")
        voice_btn.setFixedHeight(26)
        voice_btn.setFont(QFont("Courier New", 7))
        voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        voice_btn.setStyleSheet(_BTN_STYLE_DIM)
        voice_btn.clicked.connect(self._open_voice_settings)
        lay.addWidget(voice_btn)

        self._brief_btn = QPushButton()
        self._brief_btn.setFixedHeight(26)
        self._brief_btn.setFont(QFont("Courier New", 7))
        self._brief_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._brief_btn.clicked.connect(self._toggle_brief)
        lay.addWidget(self._brief_btn)

        w.adjustSize()
        return w

    def _toggle_drawer(self, checked: bool):
        if checked:
            self._position_quick_drawer()
            self._quick_drawer.show()
            self._quick_drawer.raise_()
        else:
            self._quick_drawer.hide()

    def _position_quick_drawer(self):
        if not hasattr(self, '_quick_drawer'):
            return
        _W = 220
        self._quick_drawer.setFixedWidth(_W)
        self._quick_drawer.adjustSize()
        self._quick_drawer.setGeometry(12, 54, _W, self._quick_drawer.sizeHint().height())

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(5)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or question…")
        self._input.setFont(QFont("Courier New", 9))
        self._input.setFixedHeight(30)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d14; color: {C.WHITE};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 3px 7px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("▸")
        send.setFixedSize(30, 30)
        send.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_content_panel(self) -> QWidget:
        """
        Collapsible panel below the HUD — shows search results, news, briefings.
        Hidden by default; appears when show_content() is called.
        """
        w = QWidget()
        w.setObjectName("ContentPanel")
        w.setStyleSheet(f"""
            QWidget#ContentPanel {{
                background: {C.PANEL};
                border-top: 1px solid {C.BORDER_B};
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 7, 12, 8)
        lay.setSpacing(5)

        # ── header row ───────────────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(6)

        dot = QLabel("◈")
        dot.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        dot.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(dot)

        self._content_title_lbl = QLabel("BRIEFING")
        self._content_title_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._content_title_lbl.setStyleSheet(
            f"color: {C.PRI}; background: transparent; letter-spacing: 1px;"
        )
        hdr.addWidget(self._content_title_lbl)
        hdr.addStretch()

        self._content_ts_lbl = QLabel("")
        self._content_ts_lbl.setFont(QFont("Courier New", 7))
        self._content_ts_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hdr.addWidget(self._content_ts_lbl)

        dismiss = QPushButton("DISMISS  ✕")
        dismiss.setFont(QFont("Courier New", 7))
        dismiss.setFixedHeight(18)
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 2px; padding: 0 5px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        dismiss.clicked.connect(w.hide)
        hdr.addWidget(dismiss)
        lay.addLayout(hdr)

        # ── separator ─────────────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); lay.addWidget(sep)

        # ── text display ──────────────────────────────────────────────────────
        self._content_display = QTextEdit()
        self._content_display.setReadOnly(True)
        self._content_display.setFont(QFont("Courier New", 8))
        self._content_display.setMinimumHeight(60)
        self._content_display.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._content_display.setStyleSheet(f"""
            QTextEdit {{
                background: {C.DARK};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 3px;
                padding: 6px 8px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG}; width: 6px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B}; border-radius: 3px; min-height: 16px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0; border: none;
            }}
        """)
        lay.addWidget(self._content_display)

        return w

    def _show_content(self, title: str, text: str):
        """Slot — runs on Qt main thread. Updates and shows the content panel."""
        import time as _time
        self._content_title_lbl.setText(title.upper()[:48])
        self._content_ts_lbl.setText(_time.strftime("%H:%M:%S"))
        self._content_display.setPlainText(text)
        self._content_display.moveCursor(
            self._content_display.textCursor().MoveOperation.Start
        )
        first_show = not self._content_panel.isVisible()
        self._content_panel.show()
        if first_show:
            total = self._center_split.height()
            self._center_split.setSizes([max(total - 220, 120), 220])

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("[F4] Mute  ·  [F11] Fullscreen"))
        lay.addStretch()
        lay.addWidget(_fl("By Henil", C.PRI_DIM))
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p    = Path(path)
        cat  = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon}  {p.name}  ·  {size}  ·  Tell {self._assistant_name} what to do with it")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def notify_phone_connected(self) -> None:
        if self._remote_overlay and self._remote_overlay.isVisible():
            self._remote_overlay.mark_connected()

    def _open_remote(self):
        if not self.on_remote_clicked:
            self._log.append_log("SYS: Dashboard not running — remote unavailable.")
            return
        result = self.on_remote_clicked()
        if not result:
            self._log.append_log("SYS: Could not generate remote key.")
            return
        url    = result[0]
        key    = result[1]
        auto   = result[2] if len(result) >= 3 else ""
        manual = result[3] if len(result) >= 4 else url
        if self._remote_overlay:
            self._remote_overlay._do_close()
        cw  = self.centralWidget()
        ow, oh = RemoteKeyOverlay._OW, RemoteKeyOverlay._OH
        ov  = RemoteKeyOverlay(url, key, auto_login_url=auto, manual_url=manual,
                               expiry_secs=600, parent=cw)
        ov.set_new_key_callback(self.on_remote_clicked)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.closed.connect(lambda: setattr(self, '_remote_overlay', None))
        ov.show()
        self._remote_overlay = ov
        self._log.append_log(f"SYS: Remote key generated — manual: {manual or url}")

    # ── Auto-start ──────────────────────────────────────────────────────────────

    def _check_autostart(self) -> bool:
        """Returns True if auto-start is currently registered on this OS."""
        try:
            if _OS == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
                try:
                    winreg.QueryValueEx(key, "FRIDAY_AI")
                    return True
                except FileNotFoundError:
                    return False
                finally:
                    winreg.CloseKey(key)
            elif _OS == "Darwin":
                return (Path.home() / "Library" / "LaunchAgents"
                    / "com.friday.assistant.plist").exists()
            else:
                return (Path.home() / ".config" / "autostart" / "friday.desktop").exists()
        except Exception:
            return False

    def _toggle_autostart(self):
        currently_on = self._check_autostart()
        try:
            script = str(Path(__file__).resolve().parent / "main.py")
            if _OS == "Windows":
                import winreg
                reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
                if currently_on:
                    winreg.DeleteValue(reg, "FRIDAY_AI")
                else:
                    pythonw = Path(sys.executable).parent / "pythonw.exe"
                    exe = str(pythonw if pythonw.exists() else sys.executable)
                    winreg.SetValueEx(reg, "FRIDAY_AI", 0, winreg.REG_SZ,
                                      f'"{exe}" "{script}"')
                winreg.CloseKey(reg)
            elif _OS == "Darwin":
                plist_dir = Path.home() / "Library" / "LaunchAgents"
                plist_dir.mkdir(parents=True, exist_ok=True)
                plist = plist_dir / "com.friday.assistant.plist"
                if currently_on:
                    plist.unlink(missing_ok=True)
                else:
                    plist.write_text(
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                        '<plist version="1.0"><dict>\n'
                        '  <key>Label</key><string>com.friday.assistant</string>\n'
                        '  <key>ProgramArguments</key><array>\n'
                        f'    <string>{sys.executable}</string>\n'
                        f'    <string>{script}</string>\n'
                        '  </array>\n'
                        '  <key>RunAtLoad</key><true/>\n'
                        '</dict></plist>\n'
                    )
            else:
                desk_dir = Path.home() / ".config" / "autostart"
                desk_dir.mkdir(parents=True, exist_ok=True)
                desk = desk_dir / "Friday.desktop"
                if currently_on:
                    desk.unlink(missing_ok=True)
                else:
                    desk.write_text(
                        "[Desktop Entry]\n"
                        f"Name={self._assistant_name}\n"
                        f"Exec={sys.executable} {script}\n"
                        "Type=Application\nTerminal=false\n"
                        "X-GNOME-Autostart-enabled=true\n"
                    )
            enabled = not currently_on
            self._update_autostart_btn(enabled)
            self._log.append_log(
                f"SYS: Auto-start {'enabled' if enabled else 'disabled'}.")
        except Exception as e:
            self._log.append_log(f"ERR: Auto-start failed — {e}")

    def _update_autostart_btn(self, enabled: bool):
        if not hasattr(self, '_autostart_btn'):
            return
        if enabled:
            self._autostart_btn.setText("◉  AUTO-START: ON")
            self._autostart_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #001a08; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #002010; }}
            """)
        else:
            self._autostart_btn.setText("◉  AUTO-START: OFF")
            self._autostart_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
            """)

    def _toggle_brief(self):
        from memory.config_manager import get_brief_enabled, save_brief_enabled
        new_val = not get_brief_enabled()
        save_brief_enabled(new_val)
        self._update_brief_btn(new_val)

    def _update_brief_btn(self, enabled: bool):
        if not hasattr(self, '_brief_btn'):
            return
        if enabled:
            self._brief_btn.setText("☀  MORNING BRIEF: ON")
            self._brief_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #001a08; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 3px;
                    text-align: left; padding: 0 8px;
                }}
                QPushButton:hover {{ background: #002010; }}
            """)
        else:
            self._brief_btn.setText("☀  MORNING BRIEF: OFF")
            self._brief_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                    text-align: left; padding: 0 8px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
            """)

    # ── Customization ────────────────────────────────────────────────────────────

    def _open_themes(self):
        cfg = _read_full_config()
        theme = (cfg.get("ui_theme") or "").strip()
        color = (cfg.get("ui_color") or C.PRI).strip()
        design_mode = (cfg.get("design_mode") or DEFAULT_DESIGN_MODE).strip()
        if design_mode not in _DESIGN_MODES:
            design_mode = DEFAULT_DESIGN_MODE
        if theme not in _THEMES:
            theme = "Custom" if color.lower() != DEFAULT_UI_COLOR else DEFAULT_UI_THEME
        if self._theme_overlay:
            self._theme_overlay.hide()
        cw = self.centralWidget()
        overlay = ThemeOverlay(theme, color, design_mode, parent=cw)
        ow = min(ThemeOverlay._OW, cw.width() - 16)
        oh = min(ThemeOverlay._OH, cw.height() - 16)
        overlay.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        overlay.on_preview = self._preview_theme
        overlay.saved.connect(self._apply_theme_update)
        overlay.show()
        overlay.raise_()
        self._theme_overlay = overlay

    def _preview_theme(self, theme_name: str, design_mode: str = DEFAULT_DESIGN_MODE, custom_color: str = ""):
        old = current_palette()
        if theme_name in _THEMES:
            apply_ui_theme(theme_name)
        elif theme_name == "Custom":
            apply_ui_accent(custom_color)
        retheme_all_widgets(old, current_palette())
        self.hud.set_design_mode(design_mode)

    def _apply_theme_update(self, theme_name: str, primary_color: str, design_mode: str):
        if theme_name not in _THEMES:
            return
        old = current_palette()
        apply_ui_theme(theme_name)
        retheme_all_widgets(old, current_palette())
        self._design_mode = design_mode if design_mode in _DESIGN_MODES else DEFAULT_DESIGN_MODE
        self.hud.set_design_mode(self._design_mode)
        try:
            data = _read_full_config()
            data["ui_theme"] = theme_name
            data["ui_color"] = primary_color.lower()
            data["design_mode"] = self._design_mode
            API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
            self._log.append_log(f"SYS: Theme applied — {theme_name}")
        except Exception as e:
            self._log.append_log(f"ERR: Theme save failed — {e}")

    def _open_personalization(self):
        if self._personalization_overlay:
            self._personalization_overlay.hide()
        cw = self.centralWidget()
        overlay = PersonalizationOverlay(_read_full_config(), parent=cw)
        ow = min(PersonalizationOverlay._OW, cw.width() - 16)
        oh = min(PersonalizationOverlay._OH, cw.height() - 16)
        overlay.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        overlay.saved.connect(self._apply_personalization_update)
        overlay.show()
        overlay.raise_()
        self._personalization_overlay = overlay

    def _apply_personalization_update(self, settings: dict):
        try:
            from memory.config_manager import update_config
            new_name = str(settings.get("assistant_name") or "Friday").strip()
            if new_name != self._assistant_name:
                self._apply_name_update(new_name, str(settings.get("user_name") or ""))
            update_config(settings)
            if self.on_personalization_changed:
                self.on_personalization_changed(dict(settings))
            self._log.append_log("SYS: Personalization synchronized.")
        except Exception as e:
            self._log.append_log(f"ERR: Personalization save failed — {e}")

    def _open_voice_settings(self):
        if self._voice_settings_overlay:
            self._voice_settings_overlay.hide()
        cw = self.centralWidget()
        overlay = VoiceSettingsOverlay(_read_full_config(), parent=cw)
        ow = min(VoiceSettingsOverlay._OW, cw.width() - 16)
        oh = min(VoiceSettingsOverlay._OH, cw.height() - 16)
        overlay.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        overlay.saved.connect(self._apply_voice_settings)
        overlay.preview_requested.connect(self._preview_voice)
        overlay.show()
        overlay.raise_()
        self._voice_settings_overlay = overlay

    def _apply_voice_settings(self, voice: str, speed: float, pitch: int, volume: int):
        try:
            data = _read_full_config()
            data["voice_name"] = "" if voice == "Default" else voice
            data["voice_speed"] = round(max(0.7, min(1.3, speed)), 2)
            data["voice_pitch"] = max(-6, min(6, int(pitch)))
            data["voice_volume"] = round(max(0, min(100, int(volume))) / 100, 2)
            API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
            self._log.append_log("SYS: Voice settings saved. They apply on the next live connection.")
        except Exception as e:
            self._log.append_log(f"ERR: Voice settings save failed — {e}")

    def _preview_voice(self, voice: str, speed: float, pitch: int, volume: int):
        """Speak a short local preview without interrupting the active Live session."""
        self._log.append_log(f"SYS: Playing {voice} voice preview.")

        def play_preview():
            text = "Hello. This is how your assistant voice will sound."
            try:
                if _OS == "Windows":
                    import pythoncom
                    from win32com.client import Dispatch
                    pythoncom.CoInitialize()
                    try:
                        speaker = Dispatch("SAPI.SpVoice")
                        speaker.Rate = max(-3, min(3, round((speed - 1.0) * 10)))
                        speaker.Volume = max(0, min(100, int(volume)))
                        preferred = {
                            "Puck": ("david", "mark", "male"),
                            "Charon": ("david", "mark", "male"),
                            "Kore": ("zira", "hazel", "female"),
                            "Aoede": ("zira", "hazel", "female"),
                            "Fenrir": (),
                        }.get(voice, ())
                        for token in speaker.GetVoices():
                            if any(name in token.GetDescription().lower() for name in preferred):
                                speaker.Voice = token
                                break
                        xml = f"<pitch absmiddle='{max(-6, min(6, int(pitch)))}'>{text}</pitch>"
                        speaker.Speak(xml, 8)  # SVSFIsXML
                    finally:
                        pythoncom.CoUninitialize()
                elif _OS == "Darwin":
                    subprocess.run(["say", "-r", str(int(180 * speed)), text], **_WIN_HIDE)
                else:
                    subprocess.run(["espeak", "-s", str(int(175 * speed)), "-p", str(50 + pitch * 5), text], **_WIN_HIDE)
            except Exception as exc:
                self._log_sig.emit(f"ERR: Voice preview unavailable — {exc}")

        threading.Thread(target=play_preview, daemon=True, name="voice-preview").start()

    def _open_customize(self):
        cfg = _read_full_config()
        if self._customize_overlay:
            self._customize_overlay.hide()
        cw = self.centralWidget()
        ov = CustomizeOverlay(
            cfg.get("assistant_name", "Friday") or "Friday",
            cfg.get("user_name", ""),
            cfg.get("ui_color", "") or DEFAULT_UI_COLOR,
            parent=cw,
        )
        ow, oh = CustomizeOverlay._OW, CustomizeOverlay._OH
        oh = min(oh, cw.height() - 16)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.on_preview = self._preview_ui_color
        ov.saved.connect(self._apply_name_update)
        ov.show()
        self._customize_overlay = ov

    def _preview_ui_color(self, hex_color: str):
        """Canlı önizleme — tüm arayüzü yeni renge boyar (config'e YAZMAZ)."""
        old = current_palette()
        if apply_ui_accent(hex_color):
            retheme_all_widgets(old, current_palette())

    def _apply_name_update(self, name: str, user_name: str, ui_color: str = ""):
        """Update all name/theme-dependent UI elements and persist to config."""
        self._assistant_name = name.strip() or "Friday"
        display = self._assistant_name.upper()
        self.setWindowTitle(f"{self._assistant_name} — Personal AI Assistant")
        self._title_lbl.setText(display)
        if display in ("FRIDAY", "Friday"):
            self._sub_lbl.setText("Just A Rather Very Intelligent System")
        else:
            self._sub_lbl.setText("Personal AI Assistant")
        self._log._ai_name_lc = self._assistant_name.lower()
        self.hud._assistant_name = display

        color_changed = False
        if ui_color:
            old = current_palette()
            if apply_ui_accent(ui_color):
                # Tüm arayüzü (paneller, butonlar, kenarlıklar, HUD) canlı boya
                retheme_all_widgets(old, current_palette())
                color_changed = old["PRI"] != C.PRI

        try:
            data = _read_full_config()
            data["assistant_name"] = self._assistant_name
            data["user_name"] = user_name.strip()
            if ui_color:
                data["ui_color"] = ui_color.strip().lower()
                saved_theme = data.get("ui_theme")
                if saved_theme in _THEMES:
                    if ui_color.strip().lower() != _THEMES[saved_theme]["PRI"].lower():
                        data["ui_theme"] = "Custom"
                elif ui_color.strip().lower() != DEFAULT_UI_COLOR:
                    data["ui_theme"] = "Custom"
            API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
            self._log.append_log(f"SYS: Identity updated — {display}")
            if color_changed:
                self._log.append_log(f"SYS: UI colour applied — {ui_color}")
        except Exception as e:
            self._log.append_log(f"ERR: Config save failed — {e}")

    # ── Clipboard intelligence ───────────────────────────────────────────────────

    def _on_clipboard_changed(self):
        try:
            text = QApplication.clipboard().text().strip()
            if len(text) >= 10:
                self._clipboard_sig.emit(text)
        except Exception:
            pass

    def _show_clipboard_panel(self, text: str):
        self._clipboard_panel.show_clipboard(text)
        self._position_clipboard_panel()

    def _position_clipboard_panel(self):
        cw = self.centralWidget()
        pw = ClipboardPanel._W
        ph = self._clipboard_panel.sizeHint().height() or ClipboardPanel._H
        x = (cw.width() - pw) // 2
        y = cw.height() - ph - 6
        self._clipboard_panel.setGeometry(x, y, pw, ph)
        self._clipboard_panel.raise_()

    def _on_clipboard_action(self, cmd: str):
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(cmd,), daemon=True).start()

    # ────────────────────────────────────────────────────────────────────────────

    def _do_interrupt(self):
        if self.on_interrupt:
            self.on_interrupt()

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        try:
            data = _read_full_config()
            data["microphone_enabled"] = not self._muted
            API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
        except Exception as e:
            self._log.append_log(f"ERR: Could not save microphone preference — {e}")
        if self._muted:
            self._apply_state("MUTED")
            self._set_microphone_status("off")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._set_microphone_status("listening")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("🔇  MICROPHONE MUTED")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #140006; color: {C.MUTED_C};
                    border: 1px solid {C.MUTED_C}; border-radius: 3px;
                }}
            """)
        else:
            self._mute_btn.setText("🎙  MICROPHONE ACTIVE")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #00140a; color: {C.GREEN};
                    border: 1px solid {C.GREEN}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #001f10; }}
            """)

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        # Debounce duplicate sends from the UI (some key handlers fire twice)
        now = time.time()
        if self._last_user_sent_text is not None and txt == self._last_user_sent_text and (now - self._last_user_sent_time) < 1.0:
            return
        self._last_user_sent_text = txt
        self._last_user_sent_time = now
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")

    def _check_config(self) -> bool:
        from memory.config_manager import get_gemini_key
        return bool(get_gemini_key())

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 390
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = _read_full_config()
        data.update({"gemini_api_key": key, "os_system": os_name})
        API_FILE.write_text(
            json.dumps(data, indent=4),
            encoding="utf-8",
        )
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._assistant_name = _read_full_config().get("assistant_name", "Friday") or "Friday"
        self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. {self._assistant_name} online.")

    def closeEvent(self, event):
        """Release the camera immediately when the assistant window closes."""
        self._cam_stop.set()
        super().closeEvent(event)

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class FridayUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_remote_clicked(self):
        return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, cb):
        self._win.on_remote_clicked = cb

    @property
    def on_interrupt(self):
        return self._win.on_interrupt

    @on_interrupt.setter
    def on_interrupt(self, cb):
        self._win.on_interrupt = cb

    @property
    def on_personalization_changed(self):
        return self._win.on_personalization_changed

    @on_personalization_changed.setter
    def on_personalization_changed(self, cb):
        self._win.on_personalization_changed = cb

    def notify_phone_connected(self) -> None:
        self._win.notify_phone_connected()

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def set_microphone_status(self, status: str, message: str = ""):
        """Thread-safe microphone status update from the audio worker."""
        self._win._mic_status_sig.emit(status, message)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def show_content(self, title: str, text: str):
        """Thread-safe: display content in the panel below the HUD."""
        self._win._content_sig.emit(title[:48], text[:4000])

    def prompt_reconfig(self):
        """Thread-safe: show the API key setup overlay (e.g. after an auth error)."""
        self._win._ready = False
        self._win._reconfig_sig.emit()

    def show_camera_frame(self, img_bytes: bytes):
        """Thread-safe: show a webcam frame in the small overlay (screen captures)."""
        self._win._camera_sig.emit(img_bytes)

    def start_camera_stream(self) -> None:
        """Thread-safe: start live camera feed in the full HUD area."""
        self._win.start_camera_stream()

    def stop_camera_stream(self) -> None:
        """Thread-safe: stop the live camera feed."""
        self._win.stop_camera_stream()

    @property
    def assistant_name(self) -> str:
        return self._win._assistant_name

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")
