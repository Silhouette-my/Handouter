"""Command-line entry point for Handouter's local material pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agents import available_cli_agents, create_manual_bundle, run_cli_agent
from .agents.base import expected_outputs, read_handoff
from .asr import transcribe_sensevoice
from .doctor import run_doctor
from .media import extract_audio
from .product import inspect_asset_zip, product_artifacts, resolve_asset_zip
from .service import BuildResult, PrepareResult, build_from_asset_zip, build_from_audio, build_from_media, prepare_lecture, refresh_handoff
from .validation import validate_note_output, validate_workspace


def _selected_modes(args: argparse.Namespace) -> list[str]:
    modes = getattr(args, "modes", None)
    if modes:
        return list(dict.fromkeys(modes))
    return [getattr(args, "mode", None) or "deep"]


def _progress_event(stage: str, percent: int, detail: str = "") -> None:
    width = 24
    filled = round(width * max(0, min(100, percent)) / 100)
    bar = "#" * filled + "-" * (width - filled)
    suffix = f"  {detail}" if detail else ""
    print(f"[progress] {stage:<10} [{bar}] {percent:3d}%{suffix}", file=sys.stderr, flush=True)


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
    parser.add_argument("--workspace-root", "--output-dir", dest="workspace_root", default="workspace", help="成果根目录（兼容名 --workspace-root），默认 ./workspace")
    parser.add_argument("--mode", choices=("verbatim", "full", "deep", "summary"), default="deep", help="兼容单交付物入口")
    parser.add_argument("--modes", nargs="+", choices=("verbatim", "full", "deep", "summary"), help="一次选择多个交付物，例如 --modes full deep summary verbatim")
    parser.add_argument("--format-profile", choices=("clean", "traceable"), default="clean", help="最终讲义格式：clean 干净阅读版（默认）或 traceable 可见来源版")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--use-slides-as-source", dest="use_slides", action="store_true", help="允许 Agent 参考 PPT")
    source.add_argument("--ignore-slides", dest="use_slides", action="store_false", help="即使提供 PPT，也不允许 Agent 使用")
    parser.set_defaults(use_slides=None)
    parser.add_argument("--embed-slides", action="store_true", help="允许最终 Markdown 嵌入 PPT；同时启用 PPT 来源")
    parser.add_argument("--allow-web", action="store_true", help="允许 Agent 使用外部资料补充；默认关闭")
    parser.add_argument("--skill-path", help="覆盖默认讲义 Skill 路径")


def _agent_args(parser: argparse.ArgumentParser, *, default: str = "none") -> None:
    parser.add_argument(
        "--agent",
        choices=("none", "manual", "codex", "claude"),
        default=default,
        help="none=只准备 handoff；manual=生成 GUI 上传包；codex/claude=自动调用本机 CLI Agent",
    )
    parser.add_argument("--agent-model", help="可选覆盖 CLI Agent 使用的模型")
    parser.add_argument("--bundle-output", help="manual 模式可选 GUI handoff ZIP 输出路径")


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

    run = sub.add_parser("run", help="面向普通用户：输入目录中的智云资产 ZIP -> 指定输出目录 -> Prompt/转写/PPT/讲义目标")
    run.add_argument("--input-dir", default="input", help="兼容旧用法：扫描 ZIP 的目录；普通用户更推荐直接传 --asset")
    run.add_argument("--output-dir", default="output", help="成果输出根目录，默认 ./output")
    run.add_argument("--asset", help="课程资产 ZIP 文件路径；支持绝对路径，推荐普通用户直接使用")
    run.add_argument("--lecture-id", help="可选；默认从智云 pageUrl 的 tenant/course/sub 自动生成")
    run.add_argument("--course-title", help="可选；默认读取资产 ZIP 的 course_info.json")
    run.add_argument("--mode", choices=("verbatim", "full", "deep", "summary"), default="deep", help="兼容单交付物入口")
    run.add_argument("--modes", nargs="+", choices=("verbatim", "full", "deep", "summary"), help="多选输出；verbatim=逐字版，full=完整整理版，deep=深度讲义，summary=精简版")
    run.add_argument("--format-profile", choices=("clean", "traceable"), default="clean")
    run_source = run.add_mutually_exclusive_group()
    run_source.add_argument("--use-slides-as-source", dest="use_slides", action="store_true", help="允许 Agent 参考 PPT")
    run_source.add_argument("--ignore-slides", dest="use_slides", action="store_false", help="完全不让 Agent 使用 PPT")
    run.set_defaults(use_slides=True)
    run.add_argument("--embed-slides", action="store_true", help="最终讲义可嵌 PPT 图片")
    run.add_argument("--allow-web", action="store_true", help="允许 Agent 联网补充，默认关闭")
    run.add_argument("--skill-path", help="覆盖默认讲义 Skill 路径")
    _agent_args(run, default="none")
    _asr_args(run)

    prepare = sub.add_parser("prepare", help="高级入口：已有转写/PPT -> 标准工作区 -> Agent 交接包")
    _lecture_args(prepare, transcript=True)

    audio = sub.add_parser("build-audio", help="高级入口：本地音频 -> SenseVoice -> 标准工作区 -> Agent 交接包")
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

    prompt = sub.add_parser("prompt", help="已有课程工作区只刷新 Prompt/格式，不重新跑音频或 ASR")
    prompt.add_argument("workspace", help="已有讲次工作区，例如 output/course-001")
    prompt.add_argument("--mode", choices=("verbatim", "full", "deep", "summary"), help="兼容单交付物入口")
    prompt.add_argument("--modes", nargs="+", choices=("verbatim", "full", "deep", "summary"), help="刷新为多个交付物；不填则沿用当前选择")
    prompt.add_argument("--format-profile", choices=("clean", "traceable"), help="不填则沿用当前格式")
    prompt_source = prompt.add_mutually_exclusive_group()
    prompt_source.add_argument("--use-slides-as-source", dest="use_slides", action="store_true")
    prompt_source.add_argument("--ignore-slides", dest="use_slides", action="store_false")
    prompt.set_defaults(use_slides=None)
    prompt.add_argument("--embed-slides", action=argparse.BooleanOptionalAction, default=None)
    prompt.add_argument("--allow-web", action=argparse.BooleanOptionalAction, default=None)
    prompt.add_argument("--skill-path", help="覆盖默认讲义 Skill 路径")
    _agent_args(prompt, default="none")

    agents = sub.add_parser("agents", help="检查 Handouter 可用的 Agent 交互后端")

    agent_run = sub.add_parser("agent-run", help="对已有 handoff 自动运行本机 CLI Agent 并校验输出")
    agent_run.add_argument("workspace", help="已有讲次工作区")
    agent_run.add_argument("--agent", choices=("codex", "claude"), required=True)
    agent_run.add_argument("--agent-model", help="可选覆盖 CLI Agent 使用的模型")

    bundle = sub.add_parser("bundle", help="为 GUI/Web Agent 生成可上传的安全 handoff ZIP")
    bundle.add_argument("workspace", help="已有讲次工作区")
    bundle.add_argument("--output", help="可选 bundle 输出路径；默认写入 workspace/handoff/")

    note = sub.add_parser("validate-note", help="Agent 生成后检查 Markdown 路径、图片链接、凭证泄漏等结构问题")
    note.add_argument("workspace", help="讲次工作区路径")
    note.add_argument("--output", help="只检查指定的 notes/ 下输出；默认检查全部 expected_outputs")
    note.add_argument("--update-state", action="store_true", help="将结构校验结果写入 state.json；不代表语义验收通过")

    sub.add_parser("doctor", help="检查 Python、ffmpeg、ASR 与 TUI 可用性，不安装任何东西")
    sub.add_parser("tui", help="启动标准库 curses 全屏 ASCII TUI；可选择 GUI handoff / Codex CLI / Claude CLI")
    return parser


def _prepare_payload(result: PrepareResult) -> dict:
    return {
        "status": "handoff_ready",
        "workspace": str(result.workspace),
        "lecture_id": result.materials.lecture_id,
        "mode": result.handoff.mode,
        "modes": list(result.handoff.modes),
        "format_profile": result.handoff.format_profile,
        "prompt": str(result.workspace / result.handoff.prompt_path),
        "sources": str(result.workspace / result.handoff.sources_path),
        "expected_agent_output": str(result.workspace / result.handoff.output_path),
        "expected_agent_outputs": {mode: str(result.workspace / path) for mode, path in result.handoff.output_paths.items()},
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
        "artifacts": product_artifacts(result.workspace).as_dict(),
    }


def _apply_agent_interaction(
    workspace: str | Path,
    *,
    agent: str,
    agent_model: str | None = None,
    bundle_output: str | Path | None = None,
) -> tuple[dict, int]:
    mode = (agent or "none").strip().lower()
    if mode == "none":
        return {"mode": "none", "agent_was_run": False}, 0
    if mode == "manual":
        bundle = create_manual_bundle(workspace, output=bundle_output)
        return {
            "mode": "manual",
            "agent_was_run": False,
            "prompt": str(bundle.prompt),
            "bundle": str(bundle.bundle),
            "expected_outputs": bundle.expected_outputs,
            "included_files": list(bundle.included_files),
        }, 0
    result = run_cli_agent(workspace, agent=mode, model=agent_model)
    return {
        "mode": "cli",
        "agent": result.agent,
        "agent_was_run": True,
        "returncode": result.returncode,
        "expected_outputs": result.outputs,
        "validation_ok": result.validation_ok,
        "validation_errors": list(result.validation_errors),
        "semantic_review": "required",
    }, (0 if result.validation_ok and result.returncode == 0 else 3)


def _run_product(args: argparse.Namespace) -> int:
    asset = resolve_asset_zip(args.input_dir, args.asset)
    _progress_event("检查资产", 0, "正在读取课程信息")
    identity = inspect_asset_zip(asset)
    _progress_event("检查资产", 100, "完成")
    lecture_id = args.lecture_id or identity.lecture_id
    course_title = args.course_title or identity.course_title
    if not course_title:
        raise ValueError("资产 ZIP 没有可用课程标题，请用 --course-title 指定")
    result = build_from_asset_zip(
        args.output_dir,
        lecture_id=lecture_id,
        course_title=course_title,
        asset_zip=asset,
        mode=args.mode,
        modes=_selected_modes(args),
        use_slides_as_source=args.use_slides,
        embed_slides=args.embed_slides,
        allow_web=args.allow_web,
        format_profile=args.format_profile,
        skill_path=args.skill_path,
        device=args.device,
        language=args.language,
        model_path=args.model_path,
        progress=_progress_event,
    )
    payload = _build_payload(result)
    payload["input"] = {
        "directory": str(Path(args.input_dir).expanduser().resolve()),
        "asset": str(asset),
    }
    payload["output_directory"] = str(Path(args.output_dir).expanduser().resolve())
    _progress_event("Agent/交付", 0, "正在准备最终交付")
    interaction, code = _apply_agent_interaction(
        result.prepare.workspace,
        agent=args.agent,
        agent_model=args.agent_model,
        bundle_output=args.bundle_output,
    )
    _progress_event("Agent/交付", 100, "完成")
    payload["agent_interaction"] = interaction
    payload["agent_was_run"] = bool(interaction.get("agent_was_run"))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


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
        modes=_selected_modes(args),
        use_slides_as_source=args.use_slides,
        embed_slides=args.embed_slides,
        allow_web=args.allow_web,
        format_profile=args.format_profile,
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
        modes=_selected_modes(args),
        use_slides_as_source=args.use_slides,
        embed_slides=args.embed_slides,
        allow_web=args.allow_web,
        format_profile=args.format_profile,
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
        modes=_selected_modes(args),
        use_slides_as_source=args.use_slides,
        embed_slides=args.embed_slides,
        allow_web=args.allow_web,
        format_profile=args.format_profile,
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
        modes=_selected_modes(args),
        use_slides_as_source=args.use_slides,
        embed_slides=args.embed_slides,
        allow_web=args.allow_web,
        format_profile=args.format_profile,
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


def _refresh_prompt(args: argparse.Namespace) -> int:
    result = refresh_handoff(
        args.workspace,
        mode=args.mode,
        modes=args.modes,
        use_slides_as_source=args.use_slides,
        embed_slides=args.embed_slides,
        allow_web=args.allow_web,
        format_profile=args.format_profile,
        skill_path=args.skill_path,
    )
    artifacts = product_artifacts(result.workspace)
    interaction, code = _apply_agent_interaction(
        result.workspace,
        agent=args.agent,
        agent_model=args.agent_model,
        bundle_output=args.bundle_output,
    )
    print(json.dumps({
        "status": "prompt_ready",
        "workspace": str(result.workspace),
        "mode": result.handoff.mode,
        "modes": list(result.handoff.modes),
        "format_profile": result.handoff.format_profile,
        "prompt": str(artifacts.prompt),
        "expected_agent_output": str(artifacts.expected_note),
        "expected_agent_outputs": {mode: str(path) for mode, path in artifacts.expected_notes.items()},
        "archived_prompt": str(result.archived_prompt),
        "artifacts": artifacts.as_dict(),
        "validation": "passed",
        "agent_was_run": bool(interaction.get("agent_was_run")),
        "agent_interaction": interaction,
    }, ensure_ascii=False, indent=2))
    return code


def _agents_status(_args: argparse.Namespace) -> int:
    payload = {
        "manual": {"available": True, "mode": "gui_bundle"},
        "cli": [
            {
                "name": item.name,
                "available": item.available,
                "executable": item.executable,
                "mode": item.mode,
            }
            for item in available_cli_agents()
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _agent_run(args: argparse.Namespace) -> int:
    result = run_cli_agent(args.workspace, agent=args.agent, model=args.agent_model)
    print(json.dumps({
        "agent": result.agent,
        "returncode": result.returncode,
        "outputs": result.outputs,
        "validation_ok": result.validation_ok,
        "validation_errors": list(result.validation_errors),
        "semantic_review": "required",
    }, ensure_ascii=False, indent=2))
    return 0 if result.returncode == 0 and result.validation_ok else 3


def _bundle(args: argparse.Namespace) -> int:
    result = create_manual_bundle(args.workspace, output=args.output)
    print(json.dumps({
        "status": "gui_handoff_ready",
        "bundle": str(result.bundle),
        "prompt": str(result.prompt),
        "expected_outputs": result.expected_outputs,
        "included_files": list(result.included_files),
        "agent_was_run": False,
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
    if args.output is None:
        root, sources, _prompt = read_handoff(args.workspace)
        outputs = expected_outputs(sources)
        if len(outputs) > 1:
            reports = {
                mode: validate_note_output(root, output=relative, update_state=False)
                for mode, relative in outputs.items()
            }
            payload = {
                "ok": all(report.ok for report in reports.values()),
                "outputs": outputs,
                "reports": {
                    mode: {
                        "ok": report.ok,
                        "output": report.output_path,
                        "sha256": report.sha256,
                        "image_links": report.image_links,
                        "errors": list(report.errors),
                        "warnings": list(report.warnings),
                    }
                    for mode, report in reports.items()
                },
                "errors": [f"{mode}: {error}" for mode, report in reports.items() for error in report.errors],
                "warnings": [f"{mode}: {warning}" for mode, report in reports.items() for warning in report.warnings],
                "semantic_review": "required",
            }
            if args.update_state:
                state_path = root / "state.json"
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["agent_output"] = {
                    **payload,
                    "status": "validated" if payload["ok"] else "invalid",
                }
                state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0 if payload["ok"] else 1
    report = validate_note_output(args.workspace, output=args.output, update_state=args.update_state)
    print(json.dumps({
        "ok": report.ok,
        "output": report.output_path,
        "sha256": report.sha256,
        "image_links": report.image_links,
        "errors": list(report.errors),
        "warnings": list(report.warnings),
        "semantic_review": "required",
    }, ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return _run_product(args)
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
        if args.command == "prompt":
            return _refresh_prompt(args)
        if args.command == "validate-note":
            return _validate_note(args)
        if args.command == "agents":
            return _agents_status(args)
        if args.command == "agent-run":
            return _agent_run(args)
        if args.command == "bundle":
            return _bundle(args)
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
