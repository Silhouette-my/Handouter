"""Claude Code CLI adapter."""

from __future__ import annotations

import shutil
from pathlib import Path

from .base import AgentAvailability

NAME = "claude"


def availability() -> AgentAvailability:
    executable = shutil.which("claude")
    return AgentAvailability(NAME, bool(executable), executable, "cli")


def build_command(workspace: str | Path, *, model: str | None = None) -> list[str]:
    info = availability()
    if not info.executable:
        raise FileNotFoundError("Claude Code CLI not found on PATH")
    command = [
        info.executable,
        "--print",
        "--permission-mode",
        "acceptEdits",
        "--output-format",
        "text",
    ]
    if model:
        command += ["--model", model]
    # Claude Code uses the subprocess cwd as its local project root. The runner
    # sends the Prompt through stdin to avoid Windows command-length/quoting issues.
    return command
