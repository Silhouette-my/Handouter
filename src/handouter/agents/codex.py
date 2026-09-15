"""Codex CLI adapter."""

from __future__ import annotations

import shutil
from pathlib import Path

from .base import AgentAvailability

NAME = "codex"


def availability() -> AgentAvailability:
    executable = shutil.which("codex")
    return AgentAvailability(NAME, bool(executable), executable, "cli")


def build_command(workspace: str | Path, *, model: str | None = None) -> list[str]:
    info = availability()
    if not info.executable:
        raise FileNotFoundError("Codex CLI not found on PATH")
    command = [
        info.executable,
        "exec",
        "-C",
        str(Path(workspace).resolve()),
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--ephemeral",
        "--color",
        "never",
    ]
    if model:
        command += ["--model", model]
    command.append("-")
    return command
