"""Progressive-disclosure Skill planning and materialization.

The built-in lecture-note Skill is modular. A handoff only exposes modules that
are relevant to the selected deliverables/options. Custom single-file Skills
remain supported and simply produce an empty module list.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


COMMON_MODULES = (
    "references/common/evidence.md",
    "references/common/writing.md",
    "references/common/presentation.md",
    "references/common/completion.md",
)
MODE_MODULES = {
    "verbatim": "references/modes/verbatim.md",
    "full": "references/modes/full.md",
    "deep": "references/modes/deep.md",
    "summary": "references/modes/summary.md",
}
FORMAT_MODULES = {
    "clean": "references/formats/clean.md",
    "traceable": "references/formats/traceable.md",
}
SLIDE_MODULES = {
    "ignore": "references/slides/ignore.md",
    "source-only": "references/slides/source-only.md",
    "embed": "references/slides/embed.md",
}
MULTI_OUTPUT_MODULE = "references/execution/multi-output.md"
LONG_COURSE_MODULE = "references/execution/long-course.md"


@dataclass(frozen=True)
class SkillPlan:
    source_entry: Path
    entry_path: str
    modules: tuple[str, ...]


def _safe_relative(relative: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"invalid Skill module path: {relative!r}")
    return Path(*posix.parts)


def plan_modules(
    skill_entry: str | Path,
    *,
    modes: Iterable[str],
    format_profile: str,
    use_slides_as_source: bool,
    embed_slides: bool,
    segment_count: int = 0,
    transcript_bytes: int = 0,
) -> tuple[str, ...]:
    """Return the built-in Skill modules needed for this handoff.

    A custom standalone Skill may not have the built-in reference tree; in that
    case we intentionally return no modules rather than inventing requirements.
    """
    entry = Path(skill_entry).resolve()
    root = entry.parent
    sentinel = root / COMMON_MODULES[0]
    if not sentinel.is_file():
        return ()

    requested = [str(mode).strip().lower() for mode in modes]
    modules: list[str] = list(COMMON_MODULES)
    for mode in ("deep", "summary", "full", "verbatim"):
        if mode in requested:
            modules.append(MODE_MODULES[mode])
    modules.append(FORMAT_MODULES[format_profile])

    if not use_slides_as_source:
        modules.append(SLIDE_MODULES["ignore"])
    elif embed_slides:
        modules.append(SLIDE_MODULES["embed"])
    else:
        modules.append(SLIDE_MODULES["source-only"])

    if len(set(requested)) > 1:
        modules.append(MULTI_OUTPUT_MODULE)
    if int(segment_count) >= 100 or int(transcript_bytes) >= 20_000:
        modules.append(LONG_COURSE_MODULE)

    # Preserve deterministic order and reject plans whose source files vanished.
    result: list[str] = []
    seen: set[str] = set()
    for relative in modules:
        if relative in seen:
            continue
        source = root / _safe_relative(relative)
        if not source.is_file():
            raise FileNotFoundError(f"Skill module missing: {source}")
        seen.add(relative)
        result.append(relative)
    return tuple(result)


def materialize_skill_plan(
    workspace: str | Path,
    skill_entry: str | Path,
    modules: Iterable[str],
) -> SkillPlan:
    """Copy the Skill entry and selected modules into the handoff directory."""
    workspace = Path(workspace)
    source_entry = Path(skill_entry).resolve()
    if not source_entry.is_file():
        raise FileNotFoundError(f"Skill entry missing: {source_entry}")
    source_root = source_entry.parent
    target_root = workspace / "handoff" / "skill"
    if target_root.exists():
        raise FileExistsError(f"handoff Skill already exists: {target_root}")
    target_root.mkdir(parents=True)
    copied: list[str] = []
    try:
        shutil.copyfile(source_entry, target_root / "SKILL.md")
        for relative in modules:
            safe = _safe_relative(relative)
            source = source_root / safe
            if not source.is_file():
                raise FileNotFoundError(f"Skill module missing: {source}")
            target = target_root / safe
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append((Path("handoff") / "skill" / safe).as_posix())
    except BaseException:
        shutil.rmtree(target_root, ignore_errors=True)
        raise

    return SkillPlan(
        source_entry=source_entry,
        entry_path="handoff/skill/SKILL.md",
        modules=tuple(copied),
    )
