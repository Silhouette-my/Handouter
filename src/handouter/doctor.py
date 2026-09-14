"""Environment diagnostics without installing or modifying dependencies."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import platform
import shutil
import sys
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required_for: str


def _version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def run_doctor() -> dict:
    checks: list[Check] = []
    checks.append(Check("python", sys.version_info >= (3, 11), platform.python_version(), "core"))
    for command in ("ffmpeg", "ffprobe"):
        path = shutil.which(command)
        checks.append(Check(command, bool(path), path or "not found", "media"))
    for module, package, purpose in (
        ("funasr", "funasr", "asr"),
        ("torch", "torch", "asr"),
    ):
        present = importlib.util.find_spec(module) is not None
        version = _version(package) if present else None
        checks.append(Check(module, present, version or "not installed", purpose))
    textual_present = importlib.util.find_spec("textual") is not None
    curses_present = importlib.util.find_spec("curses") is not None
    checks.append(Check("textual", textual_present, _version("textual") or "not installed (optional)", "tui_optional"))
    checks.append(Check("curses", curses_present, "stdlib" if curses_present else "not available", "tui_fallback"))
    ok_core = all(check.ok for check in checks if check.required_for == "core")
    return {
        "ok_core": ok_core,
        "ok_media": ok_core and all(check.ok for check in checks if check.required_for == "media"),
        "ok_asr": ok_core and all(check.ok for check in checks if check.required_for == "asr"),
        "ok_tui": ok_core and (textual_present or curses_present),
        "tui_backend": "textual" if textual_present else ("curses" if curses_present else None),
        "checks": [asdict(check) for check in checks],
    }
