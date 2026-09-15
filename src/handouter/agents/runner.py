"""Run supported CLI agents and validate their outputs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import claude, codex
from .base import AgentAvailability, AgentRunResult, expected_outputs, read_handoff
from ..validation import validate_note_output, validate_workspace
from ..workspace import read_json, sha256_file


_ADAPTERS = {
    "codex": codex,
    "claude": claude,
}


def available_cli_agents() -> list[AgentAvailability]:
    return [adapter.availability() for adapter in _ADAPTERS.values()]


def run_cli_agent(
    workspace: str | Path,
    *,
    agent: str,
    model: str | None = None,
) -> AgentRunResult:
    """Run one CLI agent non-interactively against a prepared workspace.

    Child output is forwarded to stderr so Handouter's stdout can remain a
    machine-readable JSON result when called through the CLI.
    """
    name = agent.strip().lower()
    adapter = _ADAPTERS.get(name)
    if adapter is None:
        raise ValueError(f"unsupported CLI agent: {agent}")

    root, sources, prompt = read_handoff(workspace)
    outputs = expected_outputs(sources)
    for relative in outputs.values():
        if (root / relative).exists():
            raise FileExistsError(f"expected Agent output already exists: {relative}")
    protected_notes = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in (root / "notes").glob("*.md")
        if path.is_file() and not path.is_symlink()
    }
    protected_control: dict[str, str] = {}
    for path in [root / "manifest.json", root / "state.json", *sorted((root / "handoff").rglob("*"))]:
        if not path.is_file() or path.is_symlink() or path.suffix.lower() == ".zip":
            continue
        relative = path.relative_to(root).as_posix()
        protected_control[relative] = sha256_file(path)
    info = adapter.availability()
    if not info.available:
        raise FileNotFoundError(f"{name} CLI is not available on PATH")

    command = adapter.build_command(root, model=model)
    if name == "codex":
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            cwd=root,
            stdout=sys.stderr,
            stderr=sys.stderr,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    elif name == "claude":
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            cwd=root,
            stdout=sys.stderr,
            stderr=sys.stderr,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    else:  # pragma: no cover - guarded by registry
        raise AssertionError(name)

    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"{name} exited with code {completed.returncode}")

    workspace_report = validate_workspace(root, update_state=False)
    if not workspace_report.ok:
        errors.extend(f"workspace: {message}" for message in workspace_report.errors)

    for relative, expected_hash in protected_control.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            errors.append(f"handoff/control file was removed or replaced: {relative}")
        elif sha256_file(path) != expected_hash:
            errors.append(f"handoff/control file was modified: {relative}")

    for relative, expected_hash in protected_notes.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            errors.append(f"existing note was removed or replaced: {relative}")
        elif sha256_file(path) != expected_hash:
            errors.append(f"existing note was modified: {relative}")

    for mode, relative in outputs.items():
        report = validate_note_output(root, output=relative, update_state=False)
        if not report.ok:
            errors.extend(f"{mode}: {message}" for message in report.errors)

    state_path = root / "state.json"
    try:
        state: dict[str, Any] = read_json(state_path)
        state["agent_output"] = {
            "status": "validated" if not errors else "failed",
            "agent": name,
            "returncode": completed.returncode,
            "outputs": outputs,
            "errors": errors,
            "semantic_review": "required",
        }
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError):
        pass

    return AgentRunResult(
        agent=name,
        returncode=completed.returncode,
        outputs=outputs,
        validation_ok=not errors,
        validation_errors=tuple(errors),
    )
