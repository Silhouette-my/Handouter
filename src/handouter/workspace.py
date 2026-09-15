"""Create a self-contained lecture workspace from existing local materials.

This module is intentionally deterministic: it copies a transcript and optional
slide assets, records hashes and known limitations, and never invokes a model or
network service.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .platform_support import is_portable_path_component

SCHEMA_VERSION = "1"
SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class WorkspaceSummary:
    lecture_id: str
    course_title: str
    workspace: Path
    transcript_path: str
    slide_event_count: int
    slide_image_count: int
    slide_missing_count: int
    slide_unknown_time_count: int


def _json_dump(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_lecture_id(lecture_id: str) -> str:
    value = lecture_id.strip()
    if len(value) > 120 or not is_portable_path_component(value):
        raise ValueError("lecture_id 必须是 1-120 个字符且可作为 macOS/Windows/Linux 目录名")
    return value


def _seconds_to_ms(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("seconds 必须是有限的非负秒数")
    try:
        seconds = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("seconds 不是有效数字") from exc
    if not seconds.is_finite() or seconds < 0:
        raise ValueError("seconds 必须是有限的非负秒数")
    milliseconds = seconds * 1000
    if milliseconds != milliseconds.to_integral_value():
        raise ValueError("时间精度小于 1ms，拒绝静默舍入")
    return int(milliseconds)


def _clock_to_ms(value: str) -> int:
    if not isinstance(value, str):
        raise ValueError("时间必须是 HH:MM:SS 或 MM:SS 字符串")
    parts = value.strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"无效时间字符串: {value!r}")
    if not all(re.fullmatch(r"\d+", part) for part in parts[:-1]):
        raise ValueError(f"无效时间字符串: {value!r}")
    if not re.fullmatch(r"\d{1,2}(?:\.\d{1,3})?", parts[-1]):
        raise ValueError(f"无效时间字符串: {value!r}")
    second_ms = _seconds_to_ms(parts[-1])
    if second_ms >= 60_000:
        raise ValueError(f"秒字段越界: {value!r}")
    if len(parts) == 3:
        if int(parts[1]) >= 60:
            raise ValueError(f"分钟字段越界: {value!r}")
        minutes = int(parts[0]) * 60 + int(parts[1])
    else:
        minutes = int(parts[0])
    return minutes * 60_000 + second_ms


def _record_start_ms(item: dict[str, Any]) -> int | None:
    values: list[int] = []
    if item.get("start_ms") is not None:
        raw = item["start_ms"]
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise ValueError("start_ms 必须是非负整数毫秒或 null")
        values.append(raw)
    if item.get("seconds") is not None and item.get("seconds") != "":
        values.append(_seconds_to_ms(item["seconds"]))
    for key in ("timestamp", "time", "switchTime"):
        if item.get(key) is not None and item.get(key) != "":
            values.append(_clock_to_ms(item[key]))
    if len(set(values)) > 1:
        raise ValueError("同一条 PPT 记录的时间字段互相矛盾")
    return values[0] if values else None


def _record_end_ms(item: dict[str, Any], start_ms: int | None) -> int | None:
    raw = item.get("end_ms")
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise ValueError("end_ms 必须是非负整数毫秒或 null")
    if start_ms is not None and raw < start_ms:
        raise ValueError("end_ms 不能早于 start_ms")
    return raw


def _safe_image_name(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("PPT filename 必须是文件名或 null")
    if not is_portable_path_component(value):
        raise ValueError("PPT filename 必须是跨平台可移植的单个文件名")
    name = Path(value)
    if name.name != value:
        raise ValueError("PPT filename 只能是当前 slides 目录中的文件名")
    if name.suffix.lower() not in SUPPORTED_IMAGES:
        raise ValueError(f"不支持的 PPT 图片类型: {value}")
    return value


def _load_slide_records(
    slides_dir: Path, metadata_path: Path | None = None
) -> tuple[list[dict[str, Any]], list[Path]]:
    if not slides_dir.is_dir():
        raise FileNotFoundError(f"PPT 目录不存在: {slides_dir}")
    if slides_dir.is_symlink():
        raise ValueError("PPT 目录不能是符号链接")

    images = sorted(
        (
            path
            for path in slides_dir.iterdir()
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in SUPPORTED_IMAGES
        ),
        key=lambda path: path.name.casefold(),
    )
    image_by_name = {path.name: path for path in images}
    metadata_path = metadata_path if metadata_path is not None else slides_dir / "slides_meta.json"
    if metadata_path.exists():
        if not metadata_path.is_file() or metadata_path.is_symlink():
            raise ValueError("PPT 元数据必须是普通 JSON 文件")
        raw = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, list):
            raise ValueError("slides_meta.json 必须是对象列表")
        records = raw
    else:
        records = [{"filename": path.name} for path in images]

    normalized: list[dict[str, Any]] = []
    referenced: set[str] = set()
    for idx, item in enumerate(records, 1):
        if not isinstance(item, dict):
            raise ValueError("slides_meta.json 中每条记录都必须是对象")
        filename = _safe_image_name(item.get("filename"))
        source_index = item.get("source_index", item.get("index"))
        if source_index is not None and (type(source_index) is not int or source_index < 1):
            raise ValueError("PPT source_index/index 必须是正整数或 null")
        start_ms = _record_start_ms(item)
        end_ms = _record_end_ms(item, start_ms)
        present = filename in image_by_name if filename else False
        if present:
            referenced.add(filename)
        source_filename = filename
        if source_filename is None and item.get("source_filename") is not None:
            source_filename = _safe_image_name(item.get("source_filename"))
        source_kind = item.get("timestamp_kind")
        timestamp_kind = source_kind if source_kind in {"metadata", "filename"} and start_ms is not None else ("metadata" if start_ms is not None else "unknown")
        normalized.append(
            {
                "occurrence_id": f"occ-{idx:04d}",
                "source_index": source_index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "timestamp_kind": timestamp_kind,
                "image_filename": filename if present else None,
                "source_filename": source_filename,
                "status": "ok" if present else "missing_image",
            }
        )

    for path in images:
        if path.name not in referenced:
            idx = len(normalized) + 1
            normalized.append(
                {
                    "occurrence_id": f"occ-{idx:04d}",
                    "source_index": None,
                    "start_ms": None,
                    "end_ms": None,
                    "timestamp_kind": "unknown",
                    "image_filename": path.name,
                    "source_filename": path.name,
                    "status": "ok",
                }
            )
    return normalized, images


def create_workspace(
    destination: str | Path,
    *,
    lecture_id: str,
    course_title: str,
    transcript: str | Path,
    segments: str | Path | None = None,
    raw_asr: str | Path | None = None,
    audio: str | Path | None = None,
    slides_dir: str | Path | None = None,
    slides_meta: str | Path | None = None,
    source_type: str = "local_existing_materials",
) -> WorkspaceSummary:
    """Create a NEW lecture workspace without modifying source materials."""

    lecture_id = validate_lecture_id(lecture_id)
    course_title = course_title.strip()
    if not course_title:
        raise ValueError("course_title 不能为空")
    if source_type not in {"local_existing_materials", "local_audio_asr", "media_asr", "zhiyun_asset_zip"}:
        raise ValueError("source_type 无效")

    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"工作区已存在，拒绝覆盖: {destination}")

    transcript_source = Path(transcript)
    if not transcript_source.is_file() or transcript_source.is_symlink():
        raise FileNotFoundError(f"转写文件不存在或不是普通文件: {transcript_source}")
    # Validate readability/encoding before creating destination.
    transcript_text = transcript_source.read_text(encoding="utf-8-sig")
    if not transcript_text.strip():
        raise ValueError("转写文件为空")

    segments_source = Path(segments) if segments is not None else None
    raw_asr_source = Path(raw_asr) if raw_asr is not None else None
    segment_records: list[dict[str, Any]] | None = None
    transcript_timestamp_kind = "unavailable"
    if segments_source is not None:
        if not segments_source.is_file() or segments_source.is_symlink():
            raise FileNotFoundError(f"ASR 分段文件不存在或不是普通文件: {segments_source}")
        loaded = json.loads(segments_source.read_text(encoding="utf-8-sig"))
        if not isinstance(loaded, list) or not all(isinstance(item, dict) for item in loaded):
            raise ValueError("segments.json 必须是对象列表")
        segment_records = loaded
        timed = 0
        for item in segment_records:
            start, end = item.get("start_ms"), item.get("end_ms")
            if start is not None and (type(start) is not int or start < 0):
                raise ValueError("ASR start_ms 必须是非负整数或 null")
            if end is not None and (type(end) is not int or end < 0):
                raise ValueError("ASR end_ms 必须是非负整数或 null")
            if start is not None and end is not None:
                if end < start:
                    raise ValueError("ASR end_ms 不能早于 start_ms")
                timed += 1
        if segment_records:
            transcript_timestamp_kind = "sentence_or_vad" if timed == len(segment_records) else ("partial" if timed else "unavailable")
    if raw_asr_source is not None:
        if not raw_asr_source.is_file() or raw_asr_source.is_symlink():
            raise FileNotFoundError(f"ASR 原始结果不存在或不是普通文件: {raw_asr_source}")
        json.loads(raw_asr_source.read_text(encoding="utf-8-sig"))
    audio_source = Path(audio) if audio is not None else None
    if audio_source is not None and (not audio_source.is_file() or audio_source.is_symlink()):
        raise FileNotFoundError(f"音频不存在或不是普通文件: {audio_source}")

    records: list[dict[str, Any]] = []
    source_images: list[Path] = []
    source_slide_dir = Path(slides_dir) if slides_dir is not None else None
    source_slides_meta = Path(slides_meta) if slides_meta is not None else None
    if source_slides_meta is not None and source_slide_dir is None:
        raise ValueError("指定 --slides-meta 时必须同时提供 PPT 图片目录")
    if source_slide_dir is not None:
        if source_slides_meta is not None and not source_slides_meta.is_file():
            raise FileNotFoundError(f"PPT 元数据不存在: {source_slides_meta}")
        records, source_images = _load_slide_records(source_slide_dir, source_slides_meta)

    destination.mkdir(parents=True, exist_ok=False)
    try:
        (destination / "transcript").mkdir()
        (destination / "audio").mkdir()
        (destination / "slides" / "images").mkdir(parents=True)
        (destination / "handoff").mkdir()
        (destination / "notes").mkdir()

        transcript_target = destination / "transcript" / "transcript.txt"
        transcript_target.write_text(transcript_text, encoding="utf-8")

        copied_images: dict[str, str] = {}
        file_entries = [
            {
                "role": "transcript",
                "path": "transcript/transcript.txt",
                "sha256": sha256_file(transcript_target),
                "bytes": transcript_target.stat().st_size,
            }
        ]
        segments_relative = None
        raw_asr_relative = None
        if segments_source is not None:
            segments_target = destination / "transcript" / "segments.json"
            shutil.copyfile(segments_source, segments_target)
            segments_relative = "transcript/segments.json"
            file_entries.append({
                "role": "transcript_segments",
                "path": segments_relative,
                "sha256": sha256_file(segments_target),
                "bytes": segments_target.stat().st_size,
            })
        if raw_asr_source is not None:
            raw_target = destination / "transcript" / "raw.json"
            shutil.copyfile(raw_asr_source, raw_target)
            raw_asr_relative = "transcript/raw.json"
            file_entries.append({
                "role": "asr_raw",
                "path": raw_asr_relative,
                "sha256": sha256_file(raw_target),
                "bytes": raw_target.stat().st_size,
            })
        audio_relative = None
        if audio_source is not None:
            audio_name = "source" + (audio_source.suffix.lower() or ".audio")
            audio_target = destination / "audio" / audio_name
            shutil.copyfile(audio_source, audio_target)
            audio_relative = audio_target.relative_to(destination).as_posix()
            file_entries.append({
                "role": "audio",
                "path": audio_relative,
                "sha256": sha256_file(audio_target),
                "bytes": audio_target.stat().st_size,
            })
        if source_slide_dir is not None:
            for source in source_images:
                target = destination / "slides" / "images" / source.name
                shutil.copyfile(source, target)
                copied_images[source.name] = target.relative_to(destination).as_posix()
                file_entries.append(
                    {
                        "role": "slide_image",
                        "path": target.relative_to(destination).as_posix(),
                        "sha256": sha256_file(target),
                        "bytes": target.stat().st_size,
                    }
                )

        slide_index = []
        for idx, item in enumerate(records, 1):
            slide_index.append(
                {
                    "occurrence_id": item["occurrence_id"],
                    "index": idx,
                    "source_index": item["source_index"],
                    "start_ms": item["start_ms"],
                    "end_ms": item["end_ms"],
                    "timestamp_kind": item["timestamp_kind"],
                    "image_path": copied_images.get(item["image_filename"]),
                    "source_filename": item["source_filename"],
                    "status": item["status"],
                }
            )
        slide_index_path = destination / "slides" / "index.json"
        _json_dump(slide_index_path, slide_index)
        file_entries.append({
            "role": "slide_index",
            "path": "slides/index.json",
            "sha256": sha256_file(slide_index_path),
            "bytes": slide_index_path.stat().st_size,
        })

        alignment_relative = None
        if segment_records is not None and slide_index:
            from .alignment import align_segments_to_slides

            alignment = align_segments_to_slides(segment_records, slide_index)
            alignment_path = destination / "slides" / "alignment.json"
            _json_dump(alignment_path, alignment)
            alignment_relative = "slides/alignment.json"
            file_entries.append({
                "role": "slide_alignment",
                "path": alignment_relative,
                "sha256": sha256_file(alignment_path),
                "bytes": alignment_path.stat().st_size,
            })

        missing_count = sum(item["status"] == "missing_image" for item in slide_index)
        unknown_time_count = sum(item["start_ms"] is None for item in slide_index)
        limitations = []
        if transcript_timestamp_kind == "unavailable":
            limitations.append("当前转写没有可靠结构化分段时间戳；不得伪造逐句时间或精确 PPT 对齐。")
        elif transcript_timestamp_kind == "partial":
            limitations.append("仅部分 ASR 分段具有时间戳；无时间段不得按字数猜测或伪造 PPT 对齐。")
        else:
            limitations.append("ASR 时间是句段/VAD 边界，不应宣称为逐字精确时间。")
        if not slide_index:
            limitations.append("本讲次没有 PPT 材料。")
        else:
            if missing_count:
                limitations.append(f"PPT 记录中有 {missing_count} 条缺少实际图片。")
            if unknown_time_count:
                limitations.append(f"PPT 记录中有 {unknown_time_count} 条没有可靠展示时间。")

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "lecture_id": lecture_id,
            "course_title": course_title,
            "source_type": source_type,
            "audio": {"path": audio_relative} if audio_relative else None,
            "transcript": {
                "path": "transcript/transcript.txt",
                "segments_path": segments_relative,
                "raw_asr_path": raw_asr_relative,
                "timestamp_kind": transcript_timestamp_kind,
                "segment_count": len(segment_records or []),
            },
            "slides": {
                "index_path": "slides/index.json",
                "alignment_path": alignment_relative,
                "event_count": len(slide_index),
                "image_count": len(copied_images),
                "missing_image_count": missing_count,
                "unknown_time_count": unknown_time_count,
            },
            "files": file_entries,
            "limitations": limitations,
        }
        _json_dump(destination / "manifest.json", manifest)
        _json_dump(
            destination / "state.json",
            {
                "schema_version": SCHEMA_VERSION,
                "materials": "ready",
                "handoff": "not_created",
                "agent_output": "not_started",
                "validation": "not_run",
            },
        )
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    return WorkspaceSummary(
        lecture_id=lecture_id,
        course_title=course_title,
        workspace=destination,
        transcript_path="transcript/transcript.txt",
        slide_event_count=len(records),
        slide_image_count=len(source_images),
        slide_missing_count=sum(item["status"] == "missing_image" for item in records),
        slide_unknown_time_count=sum(item["start_ms"] is None for item in records),
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
