"""Application service for the M1: existing materials -> workspace -> handoff."""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ProgressCallback = Callable[[str, int, str], None]


def _progress(callback: ProgressCallback | None, stage: str, percent: int, detail: str = "") -> None:
    if callback is not None:
        callback(stage, percent, detail)

from .asr import ASRResult, transcribe_sensevoice
from .handoff import HandoffSummary, create_handoff
from .importers import import_slides_zip, read_private_media_source
from .media import AudioExtractResult, extract_audio
from .validation import ValidationReport, validate_workspace
from .workspace import WorkspaceSummary, create_workspace, read_json, validate_lecture_id


@dataclass(frozen=True)
class PrepareResult:
    workspace: Path
    materials: WorkspaceSummary
    handoff: HandoffSummary
    validation: ValidationReport


@dataclass(frozen=True)
class RefreshHandoffResult:
    workspace: Path
    handoff: HandoffSummary
    validation: ValidationReport
    archived_prompt: Path


@dataclass(frozen=True)
class BuildResult:
    prepare: PrepareResult
    asr: ASRResult
    media: AudioExtractResult | None


def prepare_lecture(
    workspace_root: str | Path,
    *,
    lecture_id: str,
    course_title: str,
    transcript: str | Path,
    segments: str | Path | None = None,
    raw_asr: str | Path | None = None,
    audio: str | Path | None = None,
    slides_dir: str | Path | None = None,
    slides_meta: str | Path | None = None,
    slides_zip: str | Path | None = None,
    mode: str = "deep",
    modes: tuple[str, ...] | list[str] | None = None,
    use_slides_as_source: bool | None = None,
    embed_slides: bool = False,
    allow_web: bool = False,
    format_profile: str = "clean",
    skill_path: str | Path | None = None,
    source_type: str = "local_existing_materials",
) -> PrepareResult:
    """Atomically prepare one new lecture workspace and validated handoff bundle."""

    lecture_id = validate_lecture_id(lecture_id)
    root = Path(workspace_root)
    if root.exists() and not root.is_dir():
        raise NotADirectoryError(f"workspace_root 不是目录: {root}")
    root.mkdir(parents=True, exist_ok=True)
    target = root / lecture_id
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"讲次工作区已存在，拒绝覆盖: {target}")
    if embed_slides and use_slides_as_source is False:
        raise ValueError("正文嵌图时不能禁用 PPT 来源")
    if slides_zip is not None and (slides_dir is not None or slides_meta is not None):
        raise ValueError("slides_zip 不能与 slides_dir/slides_meta 同时使用")

    imported_slides: Path | None = None
    if slides_zip is not None:
        imported_slides = root / f".{lecture_id}.slides-{uuid.uuid4().hex}"
        import_slides_zip(slides_zip, imported_slides)
        slides_dir = imported_slides
        slides_meta = imported_slides / "slides_meta.json"

    staging = root / f".{lecture_id}.tmp-{uuid.uuid4().hex}"
    try:
        materials = create_workspace(
            staging,
            lecture_id=lecture_id,
            course_title=course_title,
            transcript=transcript,
            segments=segments,
            raw_asr=raw_asr,
            audio=audio,
            slides_dir=slides_dir,
            slides_meta=slides_meta,
            source_type=source_type,
        )
        manifest = read_json(staging / "manifest.json")
        has_slides = int(manifest.get("slides", {}).get("image_count", 0)) > 0
        resolved_use_slides = has_slides if use_slides_as_source is None else bool(use_slides_as_source)
        if embed_slides:
            resolved_use_slides = True

        handoff = create_handoff(
            staging,
            mode=mode,
            modes=modes,
            use_slides_as_source=resolved_use_slides,
            embed_slides=embed_slides,
            allow_web=allow_web,
            format_profile=format_profile,
            skill_path=skill_path,
        )
        validation = validate_workspace(staging, update_state=True)
        if not validation.ok:
            details = "; ".join(validation.errors)
            raise RuntimeError(f"交接工作区验证失败: {details}")
        staging.rename(target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        if imported_slides is not None:
            shutil.rmtree(imported_slides, ignore_errors=True)

    materials = WorkspaceSummary(
        lecture_id=materials.lecture_id,
        course_title=materials.course_title,
        workspace=target,
        transcript_path=materials.transcript_path,
        slide_event_count=materials.slide_event_count,
        slide_image_count=materials.slide_image_count,
        slide_missing_count=materials.slide_missing_count,
        slide_unknown_time_count=materials.slide_unknown_time_count,
    )
    return PrepareResult(target, materials, handoff, validation)


def refresh_handoff(
    workspace: str | Path,
    *,
    mode: str | None = None,
    modes: tuple[str, ...] | list[str] | None = None,
    use_slides_as_source: bool | None = None,
    embed_slides: bool | None = None,
    allow_web: bool | None = None,
    format_profile: str | None = None,
    skill_path: str | Path | None = None,
) -> RefreshHandoffResult:
    """Create a new Prompt for an existing lecture without rerunning media/ASR.

    The previous Prompt and sources index are archived under ``handoff/history``.
    If regeneration fails, the previous handoff/state are restored.
    """
    root = Path(workspace)
    if not root.is_dir():
        raise NotADirectoryError(f"讲次工作区不存在: {root}")
    prompt = root / "handoff" / "PROMPT.md"
    sources_path = root / "handoff" / "sources.json"
    state_path = root / "state.json"
    if not prompt.is_file() or not sources_path.is_file() or not state_path.is_file():
        raise FileNotFoundError("工作区缺少现有 handoff/state，无法刷新 Prompt")

    current = read_json(sources_path)
    options = current.get("options", {}) if isinstance(current, dict) else {}
    current_modes = current.get("modes") if isinstance(current.get("modes"), list) else None
    if modes is not None:
        resolved_modes = list(modes)
    elif mode is not None:
        resolved_modes = [mode]
    else:
        resolved_modes = current_modes or [str(current.get("mode") or "deep")]
    resolved_mode = resolved_modes[0]
    resolved_use_slides = bool(options.get("use_slides_as_source")) if use_slides_as_source is None else bool(use_slides_as_source)
    resolved_embed = bool(options.get("embed_slides")) if embed_slides is None else bool(embed_slides)
    resolved_web = bool(options.get("allow_web")) if allow_web is None else bool(allow_web)
    resolved_format = format_profile or str(options.get("format_profile") or "clean")
    if resolved_embed:
        resolved_use_slides = True

    history = root / "handoff" / "history"
    history.mkdir(exist_ok=True)
    index = 1
    while (history / f"task-{index:03d}-PROMPT.md").exists() or (history / f"task-{index:03d}-sources.json").exists():
        index += 1
    archived_prompt = history / f"task-{index:03d}-PROMPT.md"
    archived_sources = history / f"task-{index:03d}-sources.json"
    current_skill = root / "handoff" / "skill"
    archived_skill = history / f"task-{index:03d}-skill"
    previous_state = state_path.read_bytes()
    prompt.replace(archived_prompt)
    sources_path.replace(archived_sources)
    if current_skill.is_dir():
        current_skill.replace(archived_skill)

    try:
        handoff = create_handoff(
            root,
            mode=resolved_mode,
            modes=resolved_modes,
            use_slides_as_source=resolved_use_slides,
            embed_slides=resolved_embed,
            allow_web=resolved_web,
            format_profile=resolved_format,
            skill_path=skill_path,
        )
        validation = validate_workspace(root, update_state=True)
        if not validation.ok:
            raise RuntimeError("刷新 Prompt 后工作区验证失败: " + "; ".join(validation.errors))
    except BaseException:
        try:
            (root / "handoff" / "PROMPT.md").unlink()
        except FileNotFoundError:
            pass
        try:
            (root / "handoff" / "sources.json").unlink()
        except FileNotFoundError:
            pass
        if current_skill.is_dir():
            shutil.rmtree(current_skill, ignore_errors=True)
        archived_prompt.replace(prompt)
        archived_sources.replace(sources_path)
        if archived_skill.is_dir():
            archived_skill.replace(current_skill)
        state_path.write_bytes(previous_state)
        raise

    return RefreshHandoffResult(root, handoff, validation, archived_prompt)


def build_from_audio(
    workspace_root: str | Path,
    *,
    lecture_id: str,
    course_title: str,
    audio: str | Path,
    slides_dir: str | Path | None = None,
    slides_meta: str | Path | None = None,
    slides_zip: str | Path | None = None,
    mode: str = "deep",
    modes: tuple[str, ...] | list[str] | None = None,
    use_slides_as_source: bool | None = None,
    embed_slides: bool = False,
    allow_web: bool = False,
    format_profile: str = "clean",
    skill_path: str | Path | None = None,
    device: str = "auto",
    language: str = "auto",
    model_path: str | None = None,
    progress: ProgressCallback | None = None,
) -> BuildResult:
    """ASR an existing local audio file, then prepare a validated handoff workspace."""
    lecture_id = validate_lecture_id(lecture_id)
    root = Path(workspace_root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / lecture_id
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"讲次工作区已存在，拒绝覆盖: {target}")
    scratch = root / f".{lecture_id}.asr-{uuid.uuid4().hex}"
    try:
        _progress(progress, "ASR 转写", 0, "正在加载 SenseVoice")
        asr = transcribe_sensevoice(
            audio,
            scratch,
            device=device,
            language=language,
            model_path=model_path,
        )
        _progress(progress, "ASR 转写", 100, f"完成（{asr.segment_count} 个片段）")
        _progress(progress, "生成工作区", 0, "正在导入材料并生成 handoff")
        prepared = prepare_lecture(
            root,
            lecture_id=lecture_id,
            course_title=course_title,
            transcript=asr.transcript_path,
            segments=asr.segments_path,
            raw_asr=asr.raw_path,
            audio=audio,
            slides_dir=slides_dir,
            slides_meta=slides_meta,
            slides_zip=slides_zip,
            mode=mode,
            modes=modes,
            use_slides_as_source=use_slides_as_source,
            embed_slides=embed_slides,
            allow_web=allow_web,
            format_profile=format_profile,
            skill_path=skill_path,
            source_type="local_audio_asr",
        )
        _progress(progress, "生成工作区", 100, "完成")
        persisted_asr = ASRResult(
            output_dir=prepared.workspace / "transcript",
            raw_path=prepared.workspace / "transcript" / "raw.json",
            segments_path=prepared.workspace / "transcript" / "segments.json",
            transcript_path=prepared.workspace / "transcript" / "transcript.txt",
            segment_count=asr.segment_count,
            timestamp_kind=asr.timestamp_kind,
            device=asr.device,
            elapsed_seconds=asr.elapsed_seconds,
        )
        return BuildResult(prepare=prepared, asr=persisted_asr, media=None)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def build_from_asset_zip(
    workspace_root: str | Path,
    *,
    lecture_id: str,
    course_title: str,
    asset_zip: str | Path,
    mode: str = "deep",
    modes: tuple[str, ...] | list[str] | None = None,
    use_slides_as_source: bool | None = None,
    embed_slides: bool = False,
    allow_web: bool = False,
    format_profile: str = "clean",
    skill_path: str | Path | None = None,
    device: str = "auto",
    language: str = "auto",
    model_path: str | None = None,
    progress: ProgressCallback | None = None,
) -> BuildResult:
    """Browser asset ZIP -> private signed media URL in memory -> full local preparation."""
    _progress(progress, "读取课程资产", 0, "正在读取 ZIP 元数据")
    media_source = read_private_media_source(asset_zip)
    _progress(progress, "读取课程资产", 100, "完成")
    return build_from_media(
        workspace_root,
        lecture_id=lecture_id,
        course_title=course_title,
        media_source=media_source,
        slides_zip=asset_zip,
        mode=mode,
        modes=modes,
        use_slides_as_source=use_slides_as_source,
        embed_slides=embed_slides,
        allow_web=allow_web,
        format_profile=format_profile,
        skill_path=skill_path,
        device=device,
        language=language,
        model_path=model_path,
        source_type="zhiyun_asset_zip",
        progress=progress,
    )


def build_from_media(
    workspace_root: str | Path,
    *,
    lecture_id: str,
    course_title: str,
    media_source: str | Path,
    slides_dir: str | Path | None = None,
    slides_meta: str | Path | None = None,
    slides_zip: str | Path | None = None,
    mode: str = "deep",
    modes: tuple[str, ...] | list[str] | None = None,
    use_slides_as_source: bool | None = None,
    embed_slides: bool = False,
    allow_web: bool = False,
    format_profile: str = "clean",
    skill_path: str | Path | None = None,
    device: str = "auto",
    language: str = "auto",
    model_path: str | None = None,
    source_type: str = "media_asr",
    progress: ProgressCallback | None = None,
) -> BuildResult:
    """Extract audio from local/authorized media, transcribe it, then prepare handoff."""
    lecture_id = validate_lecture_id(lecture_id)
    root = Path(workspace_root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / lecture_id
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"讲次工作区已存在，拒绝覆盖: {target}")
    scratch_root = root / f".{lecture_id}.media-{uuid.uuid4().hex}"
    scratch_root.mkdir(parents=True, exist_ok=False)
    audio_path = scratch_root / "audio.m4a"
    asr_dir = scratch_root / "asr"
    try:
        _progress(progress, "提取音频", 0, "正在调用 ffmpeg")
        media = extract_audio(media_source, audio_path)
        _progress(progress, "提取音频", 100, "完成")
        _progress(progress, "ASR 转写", 0, "正在加载 SenseVoice")
        asr = transcribe_sensevoice(
            audio_path,
            asr_dir,
            device=device,
            language=language,
            model_path=model_path,
        )
        _progress(progress, "ASR 转写", 100, f"完成（{asr.segment_count} 个片段）")
        _progress(progress, "生成工作区", 0, "正在导入 PPT 并生成 handoff")
        prepared = prepare_lecture(
            root,
            lecture_id=lecture_id,
            course_title=course_title,
            transcript=asr.transcript_path,
            segments=asr.segments_path,
            raw_asr=asr.raw_path,
            audio=audio_path,
            slides_dir=slides_dir,
            slides_meta=slides_meta,
            slides_zip=slides_zip,
            mode=mode,
            modes=modes,
            use_slides_as_source=use_slides_as_source,
            embed_slides=embed_slides,
            allow_web=allow_web,
            format_profile=format_profile,
            skill_path=skill_path,
            source_type=source_type,
        )
        _progress(progress, "生成工作区", 100, "完成")
        persisted_asr = ASRResult(
            output_dir=prepared.workspace / "transcript",
            raw_path=prepared.workspace / "transcript" / "raw.json",
            segments_path=prepared.workspace / "transcript" / "segments.json",
            transcript_path=prepared.workspace / "transcript" / "transcript.txt",
            segment_count=asr.segment_count,
            timestamp_kind=asr.timestamp_kind,
            device=asr.device,
            elapsed_seconds=asr.elapsed_seconds,
        )
        persisted_media = AudioExtractResult(
            output=prepared.workspace / "audio" / "source.m4a",
            duration_ms=media.duration_ms,
            bytes=(prepared.workspace / "audio" / "source.m4a").stat().st_size,
            mode=media.mode,
        )
        return BuildResult(prepare=prepared, asr=persisted_asr, media=persisted_media)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)
