"""Timestamp-only association between ASR segments and slide display events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_list(path: Path, label: str) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{label} 必须是对象列表")
    return value


def _event_intervals(events: list[dict[str, Any]]) -> list[tuple[dict[str, Any], int | None, int | None]]:
    intervals: list[tuple[dict[str, Any], int | None, int | None]] = []
    for index, event in enumerate(events):
        start = event.get("start_ms")
        end = event.get("end_ms")
        if start is not None and (type(start) is not int or start < 0):
            raise ValueError("PPT start_ms 必须是非负整数或 null")
        if end is not None and (type(end) is not int or end < 0):
            raise ValueError("PPT end_ms 必须是非负整数或 null")
        if start is not None and end is not None and end < start:
            raise ValueError("PPT end_ms 不能早于 start_ms")
        if start is not None and end is None:
            for later in events[index + 1 :]:
                later_start = later.get("start_ms")
                if type(later_start) is int and later_start >= start:
                    end = later_start
                    break
        intervals.append((event, start, end))
    return intervals


def align_segments_to_slides(
    segments: list[dict[str, Any]], events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Associate by interval overlap only; no semantic matching is claimed."""
    intervals = _event_intervals(events)
    output: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, 1):
        start = segment.get("start_ms")
        end = segment.get("end_ms")
        if start is not None and (type(start) is not int or start < 0):
            raise ValueError("ASR start_ms 必须是非负整数或 null")
        if end is not None and (type(end) is not int or end < 0):
            raise ValueError("ASR end_ms 必须是非负整数或 null")
        if start is not None and end is not None and end < start:
            raise ValueError("ASR end_ms 不能早于 start_ms")

        matches: list[dict[str, Any]] = []
        if start is not None and end is not None:
            for event, event_start, event_end in intervals:
                if event_start is None:
                    continue
                # Unknown last-page end: any segment extending past the slide start overlaps it.
                overlaps = end > event_start if event_end is None else max(start, event_start) < min(end, event_end)
                # Preserve zero-length boundary segments without fabricating duration.
                if start == end:
                    overlaps = start >= event_start and (event_end is None or start < event_end)
                if overlaps:
                    matches.append({
                        "occurrence_id": event.get("occurrence_id"),
                        "image_path": event.get("image_path"),
                        "slide_start_ms": event_start,
                        "slide_end_ms": event_end,
                    })
        output.append({
            "segment_id": segment.get("id") or f"seg-{index:04d}",
            "start_ms": start,
            "end_ms": end,
            "slide_occurrences": matches,
            "alignment_kind": "time_overlap" if matches else ("unavailable" if start is None or end is None else "no_overlap"),
        })
    return output


def create_alignment(workspace: str | Path) -> Path | None:
    workspace = Path(workspace)
    segments_path = workspace / "transcript" / "segments.json"
    slides_path = workspace / "slides" / "index.json"
    if not segments_path.is_file() or not slides_path.is_file():
        return None
    segments = _load_list(segments_path, "segments.json")
    events = _load_list(slides_path, "slides/index.json")
    aligned = align_segments_to_slides(segments, events)
    path = workspace / "slides" / "alignment.json"
    if path.exists():
        raise FileExistsError(f"对齐文件已存在，拒绝覆盖: {path}")
    path.write_text(json.dumps(aligned, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path
