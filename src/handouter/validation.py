"""Structural validation for prepared Handouter workspaces and handoff bundles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .workspace import read_json, sha256_file


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    errors: tuple[str, ...]
    checked_files: int
    slide_events: int


@dataclass(frozen=True)
class NoteValidationReport:
    ok: bool
    output_path: str | None
    errors: tuple[str, ...]
    image_links: int
    sha256: str | None


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("路径必须是非空相对路径")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"不安全的相对路径: {value!r}")
    return path.as_posix()


def _dump(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def validate_workspace(workspace: str | Path, *, update_state: bool = False) -> ValidationReport:
    workspace = Path(workspace)
    errors: list[str] = []
    checked_files = 0
    slide_events = 0

    try:
        manifest = read_json(workspace / "manifest.json")
        state = read_json(workspace / "state.json")
        sources = read_json(workspace / "handoff" / "sources.json")
        prompt = (workspace / "handoff" / "PROMPT.md").read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return ValidationReport(False, (f"核心交接文件不可读: {exc}",), 0, 0)

    if "{{" in prompt or "}}" in prompt:
        errors.append("PROMPT.md 仍含未填写模板占位符")
    if manifest.get("lecture_id") != sources.get("lecture_id"):
        errors.append("manifest 与 sources 的 lecture_id 不一致")
    if manifest.get("course_title") != sources.get("course_title"):
        errors.append("manifest 与 sources 的 course_title 不一致")

    handoff_state = state.get("handoff")
    if not isinstance(handoff_state, dict) or handoff_state.get("status") != "ready":
        errors.append("state.json 未标记 handoff ready")
    else:
        if handoff_state.get("mode") != sources.get("mode"):
            errors.append("state 与 sources 的 mode 不一致")
        if handoff_state.get("expected_output") != sources.get("expected_output"):
            errors.append("state 与 sources 的 expected_output 不一致")

    for entry in manifest.get("files", []):
        try:
            relative = _safe_relative(entry.get("path"))
            path = workspace / relative
            if not path.is_file() or path.is_symlink():
                errors.append(f"manifest 文件缺失或不是普通文件: {relative}")
                continue
            checked_files += 1
            expected = entry.get("sha256")
            if not isinstance(expected, str) or sha256_file(path) != expected:
                errors.append(f"文件哈希与 manifest 不一致: {relative}")
        except (ValueError, OSError) as exc:
            errors.append(str(exc))

    transcript_manifest = manifest.get("transcript", {})
    try:
        transcript_rel = _safe_relative(transcript_manifest["path"])
        if not (workspace / transcript_rel).is_file():
            errors.append("转写文件不存在")
    except (KeyError, TypeError, ValueError):
        errors.append("manifest.transcript.path 无效")

    segments_data: list[dict[str, Any]] = []
    segments_rel = transcript_manifest.get("segments_path")
    if segments_rel:
        try:
            segments_path = workspace / _safe_relative(segments_rel)
            raw_segments = read_json(segments_path)
            if not isinstance(raw_segments, list) or not all(isinstance(item, dict) for item in raw_segments):
                raise ValueError("transcript/segments.json 必须是对象列表")
            segments_data = raw_segments
            for idx, segment in enumerate(segments_data, 1):
                start, end = segment.get("start_ms"), segment.get("end_ms")
                if start is not None and (type(start) is not int or start < 0):
                    errors.append(f"ASR 第 {idx} 段 start_ms 无效")
                if end is not None and (type(end) is not int or end < 0):
                    errors.append(f"ASR 第 {idx} 段 end_ms 无效")
                if type(start) is int and type(end) is int and end < start:
                    errors.append(f"ASR 第 {idx} 段结束时间早于开始时间")
            if int(transcript_manifest.get("segment_count", -1)) != len(segments_data):
                errors.append("manifest.transcript.segment_count 与实际不一致")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"ASR 分段不可读: {exc}")
    elif int(transcript_manifest.get("segment_count", 0)):
        errors.append("manifest 声称有 ASR 分段但 segments_path 为空")

    slides_manifest = manifest.get("slides", {})
    index_rel = slides_manifest.get("index_path")
    slide_index: list[dict[str, Any]] = []
    if index_rel:
        try:
            index_path = workspace / _safe_relative(index_rel)
            raw = read_json(index_path)
            if not isinstance(raw, list):
                raise ValueError("slides/index.json 必须是列表")
            slide_index = raw
            slide_events = len(raw)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"PPT 索引不可读: {exc}")
    elif int(slides_manifest.get("event_count", 0)):
        errors.append("manifest 声称存在 PPT 事件但没有 index_path")

    ok_image_paths: set[str] = set()
    missing_images = 0
    unknown_times = 0
    for idx, event in enumerate(slide_index, 1):
        if not isinstance(event, dict):
            errors.append(f"PPT 第 {idx} 条事件不是对象")
            continue
        start_ms = event.get("start_ms")
        if start_ms is None:
            unknown_times += 1
        elif isinstance(start_ms, bool) or not isinstance(start_ms, int) or start_ms < 0:
            errors.append(f"PPT 第 {idx} 条 start_ms 无效")
        status = event.get("status")
        image_path = event.get("image_path")
        if status == "ok":
            try:
                rel = _safe_relative(image_path)
                path = workspace / rel
                if not path.is_file() or path.is_symlink():
                    errors.append(f"PPT 图片缺失: {rel}")
                else:
                    ok_image_paths.add(rel)
            except (TypeError, ValueError):
                errors.append(f"PPT 第 {idx} 条有效事件缺少安全 image_path")
        elif status == "missing_image":
            missing_images += 1
            if image_path is not None:
                errors.append(f"PPT 第 {idx} 条标为缺图但仍有 image_path")
        else:
            errors.append(f"PPT 第 {idx} 条 status 无效")

    alignment_rel = slides_manifest.get("alignment_path")
    if alignment_rel:
        try:
            alignment = read_json(workspace / _safe_relative(alignment_rel))
            if not isinstance(alignment, list):
                raise ValueError("slides/alignment.json 必须是列表")
            if segments_data and len(alignment) != len(segments_data):
                errors.append("alignment 条数与 ASR 分段数不一致")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"PPT 对齐索引不可读: {exc}")

    expected_counts = {
        "event_count": len(slide_index),
        "image_count": len(ok_image_paths),
        "missing_image_count": missing_images,
        "unknown_time_count": unknown_times,
    }
    for key, actual in expected_counts.items():
        if int(slides_manifest.get(key, 0)) != actual:
            errors.append(f"manifest.slides.{key} 与实际索引不一致")

    try:
        expected_output = _safe_relative(sources.get("expected_output"))
        if not expected_output.startswith("notes/"):
            errors.append("expected_output 必须位于 notes/ 下")
    except ValueError as exc:
        errors.append(str(exc))

    if sources.get("transcript", {}).get("segments_path") != transcript_manifest.get("segments_path"):
        errors.append("sources 与 manifest 的 segments_path 不一致")
    if sources.get("slides", {}).get("alignment_path") != slides_manifest.get("alignment_path"):
        errors.append("sources 与 manifest 的 alignment_path 不一致")

    source_options = sources.get("options", {})
    if source_options.get("embed_slides") and not source_options.get("use_slides_as_source"):
        errors.append("sources 配置矛盾：嵌图但未允许 PPT 来源")
    if source_options.get("use_slides_as_source") and not ok_image_paths:
        errors.append("sources 要求使用 PPT，但工作区没有可用图片")

    report = ValidationReport(not errors, tuple(errors), checked_files, slide_events)
    if update_state:
        state["validation"] = {
            "status": "passed" if report.ok else "failed",
            "checked_files": checked_files,
            "slide_events": slide_events,
            "errors": list(report.errors),
        }
        _dump(workspace / "state.json", state)
    return report


def validate_note_output(
    workspace: str | Path,
    *,
    output: str | Path | None = None,
    update_state: bool = False,
) -> NoteValidationReport:
    """Validate one Agent-produced Markdown structurally, without claiming semantic correctness."""
    workspace = Path(workspace)
    errors: list[str] = []
    image_links = 0
    output_hash: str | None = None
    output_rel: str | None = None

    try:
        state = read_json(workspace / "state.json")
        sources = read_json(workspace / "handoff" / "sources.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return NoteValidationReport(False, None, (f"无法读取 handoff/state: {exc}",), 0, None)

    candidate = output if output is not None else sources.get("expected_output")
    try:
        if candidate is None:
            raise ValueError("没有 expected_output")
        candidate_path = Path(candidate)
        if candidate_path.is_absolute():
            try:
                target = candidate_path.resolve(strict=True)
                root = workspace.resolve(strict=True)
                target.relative_to(root)
            except (OSError, ValueError) as exc:
                raise ValueError("输出必须位于讲次工作区内") from exc
            output_rel = target.relative_to(root).as_posix()
        else:
            output_rel = _safe_relative(str(candidate))
            target = workspace / output_rel
        if not output_rel.startswith("notes/"):
            errors.append("Agent 输出必须位于 notes/ 下")
        if not target.is_file() or target.is_symlink():
            errors.append(f"讲义输出不存在或不是普通文件: {output_rel}")
            text = ""
        else:
            text = target.read_text(encoding="utf-8")
            if not text.strip():
                errors.append("讲义输出为空")
            if "{{" in text or "}}" in text:
                errors.append("讲义仍含模板占位符")
            if re.search(r"(?i)(auth_key|cookie|api[_ -]?key|signature|token)\s*[:=]\s*\S+", text):
                errors.append("讲义疑似包含凭证或签名参数")
            output_hash = sha256_file(target)
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
        text = ""

    embed_slides = bool(sources.get("options", {}).get("embed_slides"))
    # Markdown image links only; remote image links are allowed only when external
    # web augmentation was explicitly enabled, but local slide links are always verified.
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
        raw_link = match.group(1).strip().split()[0].strip("<>")
        image_links += 1
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw_link):
            if not sources.get("options", {}).get("allow_web"):
                errors.append(f"未允许联网补充却出现远程图片链接: {raw_link}")
            continue
        try:
            note_dir = (workspace / output_rel).parent if output_rel else workspace / "notes"
            resolved = (note_dir / raw_link).resolve(strict=True)
            root = workspace.resolve(strict=True)
            relative = resolved.relative_to(root).as_posix()
            if not resolved.is_file() or resolved.is_symlink():
                errors.append(f"图片链接不是普通文件: {raw_link}")
            if relative.startswith("slides/images/") and not embed_slides:
                errors.append(f"配置禁止嵌入 PPT，但讲义引用了幻灯片: {raw_link}")
        except (OSError, ValueError):
            errors.append(f"图片链接无效或越出工作区: {raw_link}")

    report = NoteValidationReport(not errors, output_rel, tuple(errors), image_links, output_hash)
    if update_state:
        try:
            state["agent_output"] = {
                "status": "validated" if report.ok else "invalid",
                "path": output_rel,
                "sha256": output_hash,
                "image_links": image_links,
                "errors": list(report.errors),
                "semantic_review": "required",
            }
            _dump(workspace / "state.json", state)
        except OSError:
            pass
    return report
