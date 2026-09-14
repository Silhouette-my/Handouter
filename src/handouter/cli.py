"""Command-line entry point for Handouter's local material pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .asr import transcribe_sensevoice
from .doctor import run_doctor
from .media import extract_audio
from .service import BuildResult, PrepareResult, build_from_asset_zip, build_from_audio, build_from_media, prepare_lecture
from .validation import validate_note_output, validate_workspace


def _lecture_args(parser: argparse.ArgumentParser, *, transcript: bool) -> None:
    parser.add_argument("--lecture-id", required=True, help="稳定讲次 ID；不能包含路径分隔符")
    parser.add_argument("--course-title", required=True, help="课程显示名称")
    if transcript:
        parser.add_argument("--transcript", required=True, help="已有 UTF-8 转写 TXT")
        parser.add_argument("--segments", help="可选结构化 ASR segments.json")
        parser.add_argument("--raw-asr", help="可选原始 ASR raw.json")
        parser.add_argument("--audio", help="可选本地音频证据；复制进工作区但不会交给 Agent")
    parser.add_argument("--slides-dir", help="可选 PPT 图片目录；可内含 slides_meta.json")
    parser.add_argument("--slides-meta", help="可选独立 slides_meta.json；用于旧版元数据与图片分目录布局")
    parser.add_argument("--slides-zip", help="可选浏览器资产 ZIP；与 slides-dir/slides-meta 互斥，private/ 不会进入交接")
    parser.add_argument("--workspace-root", default="workspace", help="工作区父目录，默认 ./workspace")
    parser.add_argument("--mode", choices=("full", "deep", "summary"), default="deep")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--use-slides-as-source", dest="use_slides", action="store_true", help="允许 Agent 参考 PPT")
    source.add_argument("--ignore-slides", dest="use_slides", action="store_false", help="即使提供 PPT，也不允许 Agent 使用")
    parser.set_defaults(use_slides=None)
    parser.add_argument("--embed-slides", action="store_true", help="允许最终 Markdown 嵌入 PPT；同时启用 PPT 来源")
    parser.add_argument("--allow-web", action="store_true", help="允许 Agent 使用外部资料补充；默认关闭")
    parser.add_argument("--skill-path", help="覆盖默认讲义 Skill 路径")


def _asr_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    parser.add_argument("--language", default="auto", help="SenseVoice 语言提示，默认 auto")
    parser.add_argument("--model-path", help="可选本地 SenseVoice 模型路径；不填则使用默认模型 ID")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handouter",
        description="Local-first lecture material preparation and Agent handoff.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="已有转写/PPT -> 标准工作区 -> Agent 交接包")
    _lecture_args(prepare, transcript=True)

    audio = sub.add_parser("build-audio", help="本地音频 -> SenseVoice -> 标准工作区 -> Agent 交接包")
    audio.add_argument("audio_input", help="本地音频文件")
    _lecture_args(audio, transcript=False)
    _asr_args(audio)

    media = sub.add_parser("build-media", help="本地/授权媒体 -> 抽音频 -> SenseVoice -> Agent 交接包")
    media.add_argument("media_source", help="本地视频/媒体路径，或用户有权访问的 HTTP(S) 媒体地址")
    _lecture_args(media, transcript=False)
    _asr_args(media)

    asset = sub.add_parser("build-asset", help="新版浏览器资产 ZIP -> 音频/PPT/ASR -> Agent 交接包")
    asset.add_argument("asset_zip", help="zhiyun_exporter.user.js v1.4+ 导出的私有资产 ZIP")
    _lecture_args(asset, transcript=False)
    _asr_args(asset)

    extract = sub.add_parser("extract-audio", help="只抽取音频；新文件写入并验证，不上传云端")
    extract.add_argument("source", help="本地媒体或授权 HTTP(S) 地址")
    extract.add_argument("output", help="新的音频输出路径，例如 lecture.m4a")

    transcribe = sub.add_parser("transcribe", help="只运行本地 SenseVoice 并保存 raw/segments/txt")
    transcribe.add_argument("audio", help="本地音频文件")
    transcribe.add_argument("output_dir", help="新的 ASR 输出目录")
    _asr_args(transcribe)

    validate = sub.add_parser("validate", help="检查已有工作区材料、hash、PPT/ASR/交接结构")
    validate.add_argument("workspace", help="讲次工作区路径")

    note = sub.add_parser("validate-note", help="Agent 生成后检查 Markdown 路径、图片链接、凭证泄漏等结构问题")
    note.add_argument("workspace", help="讲次工作区路径")
    note.add_argument("--output", help="可选指定 notes/ 下输出；默认读取 handoff expected_output")
    note.add_argument("--update-state", action="store_true", help="将结构校验结果写入 state.json；不代表语义验收通过")

    sub.add_parser("doctor", help="检查 Python、ffmpeg、ASR 与 TUI 可用性，不安装任何东西")
    sub.add_parser("tui", help="启动 TUI；优先 Textual，未安装时使用标准库 curses")
    return parser


def _prepare_payload(result: PrepareResult) -> dict:
    return {
        "status": "handoff_ready",
        "workspace": str(result.workspace),
        "lecture_id": result.materials.lecture_id,
        "mode": result.handoff.mode,
        "prompt": str(result.workspace / result.handoff.prompt_path),
        "sources": str(result.workspace / result.handoff.sources_path),
        "expected_agent_output": str(result.workspace / result.handoff.output_path),
        "slides": {
            "events": result.materials.slide_event_count,
            "images": result.materials.slide_image_count,
            "missing": result.materials.slide_missing_count,
            "unknown_time": result.materials.slide_unknown_time_count,
            "use_as_source": result.handoff.use_slides_as_source,
            "embed": result.handoff.embed_slides,
        },
        "validation": "passed",
        "agent_was_run": False,
    }


def _prepare(args: argparse.Namespace) -> int:
    result = prepare_lecture(
        args.workspace_root,
        lecture_id=args.lecture_id,
        course_title=args.course_title,
        transcript=args.transcript,
        segments=args.segments,
        raw_asr=args.raw_asr,
        audio=args.audio,
        slides_dir=args.slides_dir,
        slides_meta=args.slides_meta,
        slides_zip=args.slides_zip,
        mode=args.mode,
        use_slides_as_source=args.use_slides,
        embed_slides=args.embed_slides,
        allow_web=args.allow_web,
        skill_path=args.skill_path,
    )
    print(json.dumps(_prepare_payload(result), ensure_ascii=False, indent=2))
    return 0


def _build_payload(result: BuildResult) -> dict:
    payload = _prepare_payload(result.prepare)
    payload["asr"] = {
        "segments": result.asr.segment_count,
        "timestamp_kind": result.asr.timestamp_kind,
        "device": result.asr.device,
        "elapsed_seconds": round(result.asr.elapsed_seconds, 3),
        "raw": str(result.asr.raw_path),
        "segments_path": str(result.asr.segments_path),
    }
    if result.media is not None:
        payload["media"] = {
            "audio": str(result.media.output),
            "duration_ms": result.media.duration_ms,
            "bytes": result.media.bytes,
            "extract_mode": result.media.mode,
        }
    return payload


def _build_audio(args: argparse.Namespace) -> int:
    result = build_from_audio(
        args.workspace_root,
        lecture_id=args.lecture_id,
        course_title=args.course_title,
        audio=args.audio_input,
        slides_dir=args.slides_dir,
        slides_meta=args.slides_meta,
        slides_zip=args.slides_zip,
        mode=args.mode,
        use_slides_as_source=args.use_slides,
        embed_slides=args.embed_slides,
        allow_web=args.allow_web,
        skill_path=args.skill_path,
        device=args.device,
        language=args.language,
        model_path=args.model_path,
    )
    print(json.dumps(_build_payload(result), ensure_ascii=False, indent=2))
    return 0


def _build_asset(args: argparse.Namespace) -> int:
    if args.slides_dir or args.slides_meta or args.slides_zip:
        raise ValueError("build-asset 已从 asset_zip 获取 PPT，不要再传 slides-dir/slides-meta/slides-zip")
    result = build_from_asset_zip(
        args.workspace_root,
        lecture_id=args.lecture_id,
        course_title=args.course_title,
        asset_zip=args.asset_zip,
        mode=args.mode,
        use_slides_as_source=args.use_slides,
        embed_slides=args.embed_slides,
        allow_web=args.allow_web,
        skill_path=args.skill_path,
        device=args.device,
        language=args.language,
        model_path=args.model_path,
    )
    print(json.dumps(_build_payload(result), ensure_ascii=False, indent=2))
    return 0


def _build_media(args: argparse.Namespace) -> int:
    result = build_from_media(
        args.workspace_root,
        lecture_id=args.lecture_id,
        course_title=args.course_title,
        media_source=args.media_source,
        slides_dir=args.slides_dir,
        slides_meta=args.slides_meta,
        slides_zip=args.slides_zip,
        mode=args.mode,
        use_slides_as_source=args.use_slides,
        embed_slides=args.embed_slides,
        allow_web=args.allow_web,
        skill_path=args.skill_path,
        device=args.device,
        language=args.language,
        model_path=args.model_path,
    )
    print(json.dumps(_build_payload(result), ensure_ascii=False, indent=2))
    return 0


def _extract(args: argparse.Namespace) -> int:
    result = extract_audio(args.source, args.output)
    print(json.dumps({
        "status": "audio_ready",
        "output": str(result.output),
        "duration_ms": result.duration_ms,
        "bytes": result.bytes,
        "mode": result.mode,
    }, ensure_ascii=False, indent=2))
    return 0


def _transcribe(args: argparse.Namespace) -> int:
    result = transcribe_sensevoice(
        args.audio,
        args.output_dir,
        device=args.device,
        language=args.language,
        model_path=args.model_path,
    )
    print(json.dumps({
        "status": "transcript_ready",
        "output_dir": str(result.output_dir),
        "segments": result.segment_count,
        "timestamp_kind": result.timestamp_kind,
        "device": result.device,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
    }, ensure_ascii=False, indent=2))
    return 0


def _validate(args: argparse.Namespace) -> int:
    report = validate_workspace(Path(args.workspace), update_state=False)
    payload = {
        "ok": report.ok,
        "checked_files": report.checked_files,
        "slide_events": report.slide_events,
        "errors": list(report.errors),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


def _validate_note(args: argparse.Namespace) -> int:
    report = validate_note_output(args.workspace, output=args.output, update_state=args.update_state)
    print(json.dumps({
        "ok": report.ok,
        "output": report.output_path,
        "sha256": report.sha256,
        "image_links": report.image_links,
        "errors": list(report.errors),
        "semantic_review": "required",
    }, ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            return _prepare(args)
        if args.command == "build-audio":
            return _build_audio(args)
        if args.command == "build-media":
            return _build_media(args)
        if args.command == "build-asset":
            return _build_asset(args)
        if args.command == "extract-audio":
            return _extract(args)
        if args.command == "transcribe":
            return _transcribe(args)
        if args.command == "validate":
            return _validate(args)
        if args.command == "validate-note":
            return _validate_note(args)
        if args.command == "doctor":
            report = run_doctor()
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["ok_core"] else 1
        if args.command == "tui":
            from .tui import run_tui
            run_tui()
            return 0
        parser.error("unknown command")
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"handouter: error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
