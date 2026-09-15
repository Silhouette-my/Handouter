"""Manual/GUI Agent handoff bundle creation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .base import expected_outputs, read_handoff


@dataclass(frozen=True)
class ManualBundleResult:
    workspace: Path
    bundle: Path
    prompt: Path
    expected_outputs: dict[str, str]
    included_files: tuple[str, ...]


def _safe_relative(value: str) -> str:
    posix = PurePosixPath(value)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"unsafe handoff path: {value!r}")
    return posix.as_posix()


def _next_bundle_path(root: Path) -> Path:
    handoff = root / "handoff"
    for index in range(1, 10_000):
        target = handoff / f"gui-handoff-{index:03d}.zip"
        if not target.exists():
            return target
    raise RuntimeError("too many GUI handoff bundles")


def _add_file(root: Path, relative: str, files: dict[str, Path]) -> None:
    safe = _safe_relative(relative)
    path = root / safe
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(f"handoff file missing or unsafe: {safe}")
    files[safe] = path


def _publish_exclusive_file(source: Path, target: Path) -> None:
    """Publish a verified file without overwriting an existing destination."""
    try:
        os.link(source, target)
        return
    except FileExistsError:
        raise
    except OSError:
        pass

    created_stat = None
    try:
        with source.open("rb") as src, target.open("xb") as dst:
            created_stat = os.fstat(dst.fileno())
            shutil.copyfileobj(src, dst, length=1024 * 1024)
    except BaseException:
        if created_stat is not None:
            try:
                if os.path.samestat(created_stat, target.lstat()):
                    target.unlink()
            except FileNotFoundError:
                pass
        raise


def create_manual_bundle(workspace: str | Path, *, output: str | Path | None = None) -> ManualBundleResult:
    """Create a portable, credential-free bundle for GUI/Web agents.

    The archive mirrors workspace-relative paths so the same PROMPT.md works
    after upload/extraction. It intentionally excludes audio, raw ASR, private
    URLs, manifest/state, and any existing notes.
    """
    root, sources, _prompt_text = read_handoff(workspace)
    outputs = expected_outputs(sources)
    files: dict[str, Path] = {}

    _add_file(root, "handoff/PROMPT.md", files)
    sources_for_bundle = json.loads(json.dumps(sources))
    transcript_for_bundle = sources_for_bundle.get("transcript")
    if isinstance(transcript_for_bundle, dict):
        transcript_for_bundle["raw_asr_path"] = None

    skill = sources.get("skill") if isinstance(sources.get("skill"), dict) else {}
    entry = skill.get("entry")
    if not isinstance(entry, str) or not entry:
        raise ValueError("当前工作区是旧 handoff；请先运行 handouter prompt <workspace> 刷新 Prompt 后再生成 GUI bundle")
    _add_file(root, entry, files)
    modules = skill.get("modules") if isinstance(skill.get("modules"), list) else []
    for relative in modules:
        if isinstance(relative, str) and relative:
            _add_file(root, relative, files)

    transcript = sources.get("transcript") if isinstance(sources.get("transcript"), dict) else {}
    for key in ("path", "segments_path"):
        relative = transcript.get(key)
        if isinstance(relative, str) and relative:
            _add_file(root, relative, files)

    options = sources.get("options") if isinstance(sources.get("options"), dict) else {}
    if bool(options.get("use_slides_as_source")):
        slides = sources.get("slides") if isinstance(sources.get("slides"), dict) else {}
        for key in ("index_path", "alignment_path"):
            relative = slides.get(key)
            if isinstance(relative, str) and relative:
                _add_file(root, relative, files)
        index_path = slides.get("index_path")
        if isinstance(index_path, str) and index_path:
            events = json.loads((root / _safe_relative(index_path)).read_text(encoding="utf-8"))
            if isinstance(events, list):
                for event in events:
                    if isinstance(event, dict):
                        image = event.get("image_path")
                        if isinstance(image, str) and image:
                            _add_file(root, image, files)

    target = Path(output).expanduser().resolve() if output is not None else _next_bundle_path(root)
    if target.exists():
        raise FileExistsError(f"bundle already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    bundled_sources = (json.dumps(sources_for_bundle, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    readme = (
        "# Handouter GUI Agent handoff\n\n"
        "1. Upload this archive to the GUI/Web agent.\n"
        "2. Ask the agent to read `handoff/PROMPT.md` first.\n"
        "3. The prompt references only files included in this archive.\n"
        "4. Expected outputs: " + ", ".join(outputs.values()) + "\n"
        "5. This bundle intentionally excludes audio, private URLs/cookies, raw ASR, state, and old notes.\n"
    ).encode("utf-8")

    temporary = target.with_name(f".{target.name}.tmp-{uuid.uuid4().hex}")
    try:
        with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("BUNDLE_README.md", readme)
            archive.writestr("handoff/sources.json", bundled_sources)
            for relative, path in sorted(files.items()):
                archive.write(path, arcname=relative)
            checksums = {
                relative: hashlib.sha256(path.read_bytes()).hexdigest()
                for relative, path in sorted(files.items())
            }
            checksums["handoff/sources.json"] = hashlib.sha256(bundled_sources).hexdigest()
            archive.writestr(
                "BUNDLE_MANIFEST.json",
                json.dumps({"files": checksums, "expected_outputs": outputs}, ensure_ascii=False, indent=2) + "\n",
            )
        with zipfile.ZipFile(temporary, "r") as archive:
            broken = archive.testzip()
            if broken is not None:
                raise RuntimeError(f"GUI handoff bundle verification failed at: {broken}")
        # Publish only a verified archive, never overwriting an existing bundle.
        _publish_exclusive_file(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

    included = ("BUNDLE_README.md", "BUNDLE_MANIFEST.json", "handoff/sources.json", *sorted(files))
    return ManualBundleResult(root, target, root / "handoff" / "PROMPT.md", outputs, tuple(included))
