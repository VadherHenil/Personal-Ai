"""Opt-in release manifest checker for packaged builds."""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen

from version import __version__


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for part in str(value).lstrip("v").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple((parts + [0, 0, 0])[:3])


def check_for_update(url: str | None = None, timeout: float = 3.0) -> dict | None:
    manifest_url = url or os.getenv("PERSONAL_AI_UPDATE_URL")
    if not manifest_url:
        return None
    request = Request(manifest_url, headers={"User-Agent": "Personal-AI-Update-Checker"})
    with urlopen(request, timeout=timeout) as response:
        manifest = json.loads(response.read().decode("utf-8"))
    latest = str(manifest.get("version") or "")
    if not latest or _version_tuple(latest) <= _version_tuple(__version__):
        return None
    return {"current": __version__, "latest": latest, "url": manifest.get("url"), "notes": manifest.get("notes", "")}
