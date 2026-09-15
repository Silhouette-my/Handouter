"""Shared types/helpers for Agent interaction adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


@dataclass(frozen=True)
class AgentAvailability:
    name: str
    available: bool
    executable: str | None
    mode: str


@dataclass(frozen=True)
class AgentRunResult:
    agent: str
    returncode: int
    outputs: dict[str, str]
    validation_ok: bool
    validation_errors: tuple[str, ...]


def read_handoff(workspace: str | Path) -> tuple[Path, dict[str, Any], str]:
    root = Path(workspace).resolve()
    sources_path = root / "handoff" / "sources.json"
    prompt_path = root / "handoff" / "PROMPT.md"
    if not sources_path.is_file() or not prompt_path.is_file():
        raise FileNotFoundError("workspace does not contain a ready handoff")
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    if not isinstance(sources, dict):
        raise ValueError("handoff/sources.json must be an object")
    prompt = prompt_path.read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("handoff/PROMPT.md is empty")
    return root, sources, prompt


def expected_outputs(sources: dict[str, Any]) -> dict[str, str]:
    raw = sources.get("expected_outputs")
    if isinstance(raw, dict) and raw:
        items = raw.items()
    else:
        mode = str(sources.get("mode") or "deep")
        relative = sources.get("expected_output")
        items = [(mode, relative)]
    result: dict[str, str] = {}
    for mode, relative in items:
        if not isinstance(mode, str) or not isinstance(relative, str) or not relative:
            raise ValueError("invalid expected_outputs in sources.json")
        posix = PurePosixPath(relative)
        if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
            raise ValueError(f"unsafe expected output path: {relative!r}")
        if not posix.as_posix().startswith("notes/"):
            raise ValueError("Agent outputs must stay under notes/")
        result[mode] = posix.as_posix()
    if not result:
        raise ValueError("handoff has no expected outputs")
    return result
