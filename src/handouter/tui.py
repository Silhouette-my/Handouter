"""Full-screen ASCII TUI for Handouter's normal product workflow.

The interface is intentionally dependency-free (stdlib curses) and delegates all
business work to the canonical CLI. Internal manifest/raw/alignment files remain
hidden from the normal user surface.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unicodedata
from typing import Any

from .agents import available_cli_agents
from .platform_support import start_task_process, terminate_process_tree
from .product import exporter_script_path, inspect_asset_zip, normalize_terminal_path, product_artifacts, resolve_asset_zip

# Kept for compatibility with older tests/importers. The default product TUI is
# deliberately curses/ASCII even when Textual happens to be installed.
App = None


def available_agent_choices() -> tuple[list[str], dict[str, str]]:
    """Return only Agent backends that are usable on this machine."""
    values = ["manual"]
    labels = {"manual": "GUI handoff"}
    for item in available_cli_agents():
        if not item.available:
            continue
        values.append(item.name)
        labels[item.name] = {"codex": "Codex CLI", "claude": "Claude CLI"}.get(item.name, f"{item.name} CLI")
    return values, labels


def selected_modes(cfg: dict[str, Any]) -> list[str]:
    """Return selected deliverables in stable order.

    ``full`` is the polished complete lecture text; ``verbatim`` is the faithful
    transcript-style deliverable. Older callers that only provide ``mode``
    continue to work.
    """
    explicit = cfg.get("modes")
    if explicit:
        wanted = set(explicit)
    elif any(key in cfg for key in ("notes_full", "notes_deep", "notes_summary", "verbatim_transcript", "clean_transcript")):
        wanted = set()
        if cfg.get("notes_deep"):
            wanted.add("deep")
        if cfg.get("notes_summary"):
            wanted.add("summary")
        if cfg.get("notes_full"):
            wanted.add("full")
        # clean_transcript is the legacy TUI key; it now means the faithful
        # verbatim deliverable rather than the newly redefined full mode.
        if cfg.get("verbatim_transcript") or cfg.get("clean_transcript"):
            wanted.add("verbatim")
    else:
        wanted = {str(cfg.get("mode") or "deep")}
    return [mode for mode in ("deep", "summary", "full", "verbatim") if mode in wanted]


def build_cli_args(cfg: dict[str, Any]) -> list[str]:
    """Build the canonical CLI invocation used by the ASCII TUI."""
    kind = cfg.get("kind", "product")
    modes = selected_modes(cfg)
    if not modes:
        raise ValueError("至少选择一种交付物")

    if kind == "prompt":
        workspace = Path(cfg.get("output_dir") or "output").expanduser() / cfg["lecture"]
        args = [
            "prompt", str(workspace),
            "--modes", *modes,
            "--format-profile", cfg.get("format_profile") or "clean",
        ]
        args.append("--use-slides-as-source" if cfg.get("use_slides", True) else "--ignore-slides")
        args.append("--embed-slides" if cfg.get("embed_slides") else "--no-embed-slides")
        args.append("--allow-web" if cfg.get("allow_web") else "--no-allow-web")
        args += ["--agent", str(cfg.get("agent") or "manual")]
        return args

    if kind == "product":
        args = [
            "run",
            "--output-dir", str(cfg.get("output_dir") or "output"),
            "--modes", *modes,
            "--format-profile", cfg.get("format_profile") or "clean",
        ]
        if cfg.get("asset"):
            args += ["--asset", normalize_terminal_path(cfg["asset"])]
        elif cfg.get("input_dir"):
            # Backward-compatible CLI construction for old callers/tests.
            args += ["--input-dir", str(cfg["input_dir"])]
        if cfg.get("lecture"):
            args += ["--lecture-id", str(cfg["lecture"])]
        if cfg.get("title"):
            args += ["--course-title", str(cfg["title"])]
        args.append("--use-slides-as-source" if cfg.get("use_slides", True) else "--ignore-slides")
        if cfg.get("embed_slides"):
            args.append("--embed-slides")
        if cfg.get("allow_web"):
            args.append("--allow-web")
        args += ["--device", str(cfg.get("device") or "auto")]
        args += ["--agent", str(cfg.get("agent") or "manual")]
        return args

    # Advanced compatibility path retained for tests/tools, but not exposed in
    # the normal ASCII form.
    source = cfg["source"]
    if kind == "asset":
        args = ["build-asset", source]
    elif kind == "transcript":
        args = ["prepare", "--transcript", source]
    elif kind == "audio":
        args = ["build-audio", source]
    elif kind == "media":
        args = ["build-media", source]
    else:
        raise ValueError(f"未知输入类型: {kind}")
    args += [
        "--lecture-id", cfg["lecture"],
        "--course-title", cfg["title"],
        "--output-dir", cfg.get("root") or "workspace",
        "--modes", *modes,
        "--format-profile", cfg.get("format_profile") or "clean",
    ]
    if kind != "asset":
        if cfg.get("slides_zip"):
            args += ["--slides-zip", cfg["slides_zip"]]
        else:
            if cfg.get("slides"):
                args += ["--slides-dir", cfg["slides"]]
            if cfg.get("meta"):
                args += ["--slides-meta", cfg["meta"]]
    args.append("--use-slides-as-source" if cfg.get("use_slides", True) else "--ignore-slides")
    if cfg.get("embed_slides"):
        args.append("--embed-slides")
    if cfg.get("allow_web"):
        args.append("--allow-web")
    if kind in {"asset", "audio", "media"}:
        args += ["--device", cfg.get("device") or "auto"]
    return args


def friendly_artifact_paths(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return only artifacts a normal user should care about."""
    root = Path(cfg.get("output_dir") or "output").expanduser().resolve() / cfg["lecture"]
    if (root / "state.json").is_file():
        try:
            artifacts = product_artifacts(root)
            return {
                "exporter_script": artifacts.exporter_script,
                "prompt": artifacts.prompt,
                "transcript": artifacts.transcript,
                "slides": artifacts.slides,
                "notes": artifacts.notes,
                "expected_note": artifacts.expected_note,
                "expected_notes": artifacts.expected_notes,
            }
        except (OSError, ValueError, KeyError):
            pass
    modes = selected_modes(cfg) or ["deep"]
    expected = {mode: root / "notes" / f"{mode}-001.md" for mode in modes}
    return {
        "exporter_script": exporter_script_path(),
        "prompt": root / "handoff" / "PROMPT.md",
        "transcript": root / "transcript" / "transcript.txt",
        "slides": root / "slides" / "images",
        "notes": root / "notes",
        "expected_note": next(iter(expected.values())),
        "expected_notes": expected,
    }


def _terminate_process_group(process: subprocess.Popen[str]) -> threading.Thread | None:
    return terminate_process_tree(process)


def _char_width(char: str) -> int:
    if unicodedata.combining(char):
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def _display_width(text: str) -> int:
    return sum(_char_width(char) for char in text)


def _clip_columns(text: str, columns: int) -> str:
    if columns <= 0:
        return ""
    used = 0
    result: list[str] = []
    for char in text:
        width = _char_width(char)
        if used + width > columns:
            break
        result.append(char)
        used += width
    return "".join(result)


def _safe_add(stdscr, row: int, col: int, text: str, attr: int = 0) -> None:
    height, width = stdscr.getmaxyx()
    if row < 0 or row >= height or col >= width:
        return
    available = max(0, width - col - 1)
    if available:
        try:
            stdscr.addstr(row, col, _clip_columns(text, available), attr)
        except Exception:
            pass


def _box(stdscr, top: int, left: int, bottom: int, right: int, title: str = "") -> None:
    if right <= left + 1 or bottom <= top + 1:
        return
    _safe_add(stdscr, top, left, "+" + "-" * max(0, right - left - 1) + "+")
    for row in range(top + 1, bottom):
        _safe_add(stdscr, row, left, "|")
        _safe_add(stdscr, row, right, "|")
    _safe_add(stdscr, bottom, left, "+" + "-" * max(0, right - left - 1) + "+")
    if title:
        _safe_add(stdscr, top, left + 2, f" {title} ")


def _checkbox(value: bool) -> str:
    return "[x]" if value else "[ ]"


def _edit_value(stdscr, label: str, current: str, *, initial: str = "") -> tuple[str, bool]:
    """Edit one text value with real cursor movement and paste/drop support.

    Left/right/home/end are consumed by the editor, so they no longer conflict
    with option switching in the main form. Esc cancels; Enter commits.
    """
    import curses

    value = current
    cursor = len(value)
    if initial:
        value = initial
        cursor = len(value)
    curses.curs_set(1)
    try:
        while True:
            height, width = stdscr.getmaxyx()
            row = max(1, height - 1)
            prompt = f"EDIT {label}: "
            prompt_width = _display_width(prompt)
            available = max(8, width - prompt_width - 4)
            start = cursor
            used = 0
            while start > 0:
                char_width = _char_width(value[start - 1])
                if used + char_width > max(1, available - 1):
                    break
                start -= 1
                used += char_width
            end = start
            used = 0
            while end < len(value):
                char_width = _char_width(value[end])
                if used + char_width > available:
                    break
                used += char_width
                end += 1
            visible = value[start:end]
            stdscr.move(row, 0)
            stdscr.clrtoeol()
            _safe_add(stdscr, row, 1, prompt + visible)
            cursor_col = 1 + prompt_width + _display_width(value[start:cursor])
            try:
                stdscr.move(row, min(width - 2, cursor_col))
            except Exception:
                pass
            stdscr.refresh()
            key = stdscr.get_wch()
            if key in ("\n", "\r"):
                return value.strip(), True
            if key == "\x1b":
                return current, False
            if isinstance(key, int):
                if key == curses.KEY_LEFT:
                    cursor = max(0, cursor - 1)
                elif key == curses.KEY_RIGHT:
                    cursor = min(len(value), cursor + 1)
                elif key == curses.KEY_HOME:
                    cursor = 0
                elif key == curses.KEY_END:
                    cursor = len(value)
                elif key == curses.KEY_DC and cursor < len(value):
                    value = value[:cursor] + value[cursor + 1 :]
                elif key == curses.KEY_BACKSPACE and cursor > 0:
                    value = value[: cursor - 1] + value[cursor:]
                    cursor -= 1
                continue
            if key in ("\x7f", "\b"):
                if cursor > 0:
                    value = value[: cursor - 1] + value[cursor:]
                    cursor -= 1
                continue
            if key == "\x01":  # Ctrl-A
                cursor = 0
                continue
            if key == "\x05":  # Ctrl-E
                cursor = len(value)
                continue
            if key == "\x15":  # Ctrl-U
                value = ""
                cursor = 0
                continue
            if key == "\x0b":  # Ctrl-K
                value = value[:cursor]
                continue
            if isinstance(key, str) and key.isprintable():
                value = value[:cursor] + key + value[cursor:]
                cursor += len(key)
    finally:
        curses.curs_set(0)


def _load_asset_into_state(state: dict[str, Any]) -> str:
    raw = str(state.get("asset") or "").strip()
    if not raw:
        return "请选择资产 ZIP：聚焦 Asset ZIP 后按 Enter，再拖入文件。"
    normalized = normalize_terminal_path(raw)
    asset = resolve_asset_zip(".", normalized)
    state["asset"] = str(asset)
    identity = inspect_asset_zip(asset)
    if identity.course_title:
        state["title"] = identity.course_title
    state["lecture"] = identity.lecture_id
    return f"Loaded: {asset.name}  |  course/id identified."


def _commit_text_value(state: dict[str, Any], field_key: str, value: str) -> str | None:
    if field_key in {"asset", "output_dir"}:
        value = normalize_terminal_path(value)
    state[field_key] = value
    if field_key == "asset" and value:
        return _load_asset_into_state(state)
    return None


def _view_text(stdscr, title: str, path: Path) -> None:
    if not path.is_file():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    offset = 0
    while True:
        height, width = stdscr.getmaxyx()
        stdscr.erase()
        _box(stdscr, 0, 0, max(3, height - 2), max(10, width - 2), title)
        page = max(1, height - 5)
        for row, line in enumerate(lines[offset : offset + page], start=2):
            _safe_add(stdscr, row, 2, line)
        _safe_add(stdscr, height - 1, 1, "Up/Down scroll | PgUp/PgDn | Q/Esc return")
        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return
        if key in (258, ord("j")):
            offset = min(max(0, len(lines) - page), offset + 1)
        elif key in (259, ord("k")):
            offset = max(0, offset - 1)
        elif key == 338:
            offset = min(max(0, len(lines) - page), offset + page)
        elif key == 339:
            offset = max(0, offset - page)


def _workspace_for_state(cfg: dict[str, Any]) -> Path | None:
    lecture = str(cfg.get("lecture") or "").strip()
    if not lecture:
        return None
    return (Path(cfg.get("output_dir") or "output").expanduser() / lecture).resolve()


def _handoff_matches_selection(cfg: dict[str, Any], workspace: Path) -> bool:
    state_path = workspace / "state.json"
    if not state_path.is_file():
        raise ValueError(f"已有输出目录缺少 state.json，拒绝覆盖: {workspace}")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    handoff = payload.get("handoff")
    if not isinstance(handoff, dict) or handoff.get("status") != "ready":
        raise ValueError(f"已有 workspace 尚未 handoff ready，拒绝自动覆盖: {workspace}")
    current_modes = handoff.get("modes")
    if not isinstance(current_modes, list):
        current_modes = [str(handoff.get("mode") or "deep")]
    return (
        list(current_modes) == selected_modes(cfg)
        and str(handoff.get("format_profile") or "clean") == str(cfg.get("format_profile") or "clean")
        and bool(handoff.get("use_slides_as_source")) == bool(cfg.get("use_slides", True))
        and bool(handoff.get("embed_slides")) == bool(cfg.get("embed_slides"))
        and bool(handoff.get("allow_web")) == bool(cfg.get("allow_web"))
    )


def _task_cli_args(cfg: dict[str, Any], *, prompt_only: bool) -> tuple[list[str], str]:
    """Choose build, refresh, or Agent continuation without redoing finished ASR."""
    if prompt_only:
        prompt_cfg = dict(cfg)
        prompt_cfg["kind"] = "prompt"
        return build_cli_args(prompt_cfg), "refresh"

    workspace = _workspace_for_state(cfg)
    if workspace is not None and workspace.exists():
        if not workspace.is_dir():
            raise ValueError(f"输出目标已存在但不是目录: {workspace}")
        if _handoff_matches_selection(cfg, workspace):
            agent = str(cfg.get("agent") or "manual")
            if agent == "manual":
                return ["bundle", str(workspace)], "bundle"
            if agent in {"codex", "claude"}:
                return ["agent-run", str(workspace), "--agent", agent], "agent"
            return ["validate", str(workspace)], "reuse"
        refresh_cfg = dict(cfg)
        refresh_cfg["kind"] = "prompt"
        return build_cli_args(refresh_cfg), "refresh"

    product_cfg = dict(cfg)
    product_cfg["kind"] = "product"
    return build_cli_args(product_cfg), "build"


def _task_error_summary(lines: list[str], code: int) -> str:
    for line in reversed(lines):
        text = line.strip()
        if text.startswith("handouter: error:"):
            return text
    tail = [line.strip() for line in lines[-4:] if line.strip()]
    return " | ".join(tail) if tail else f"Task ended with code {code}."


def _run_task(stdscr, state: dict[str, Any], *, prompt_only: bool) -> tuple[bool, str]:
    cfg = dict(state)
    cli_args, action = _task_cli_args(cfg, prompt_only=prompt_only)
    kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
        "env": os.environ.copy(),
        "encoding": "utf-8",
        "errors": "replace",
    }
    kwargs["env"]["PYTHONUTF8"] = "1"
    process, job = start_task_process(cli_args, **kwargs)
    cancellation = None
    lines: list[str] = []
    progress_line = {"text": "Working..."}

    def reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            clean = line.rstrip()
            if clean.startswith("[progress]"):
                progress_line["text"] = clean
            else:
                lines.append(clean)

    thread = threading.Thread(target=reader, daemon=True)
    reader_started = False
    try:
        thread.start()
        reader_started = True
        stdscr.nodelay(True)
        while process.poll() is None:
            height, width = stdscr.getmaxyx()
            stdscr.erase()
            _box(stdscr, 0, 0, max(5, height - 2), max(20, width - 2), " HANDOUTER / RUNNING ")
            _safe_add(stdscr, 2, 2, progress_line["text"] + "  Q/Esc = cancel process group")
            for row, line in enumerate(lines[-max(1, height - 7) :], start=4):
                _safe_add(stdscr, row, 2, line)
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("q"), ord("Q"), 27):
                cancellation = _terminate_process_group(process)
                break
            time.sleep(0.08)
        code = process.wait()
    finally:
        try:
            if process.poll() is None and cancellation is None:
                cancellation = _terminate_process_group(process)
            if job is not None:
                job.close()
            if cancellation is not None:
                cancellation.join()
            process.wait()
            if reader_started:
                thread.join(timeout=1)
        finally:
            stdscr.nodelay(False)
    if code != 0:
        return False, _task_error_summary(lines, code)
    agent = str(cfg.get("agent") or "manual")
    if action == "bundle":
        root = Path(cfg.get("output_dir") or "output").expanduser() / str(cfg.get("lecture") or "") / "handoff"
        bundles = sorted(root.glob("gui-handoff-*.zip"), key=lambda path: path.stat().st_mtime_ns if path.exists() else 0)
        suffix = f" {bundles[-1]}" if bundles else ""
        return True, "Existing workspace reused; GUI handoff bundle ready:" + suffix
    if action == "agent":
        return True, f"Existing workspace reused; {agent} finished; outputs structurally validated."
    if action == "refresh":
        return True, ("Prompt refreshed and GUI handoff bundle ready." if agent == "manual" else f"Prompt refreshed; {agent} finished; outputs structurally validated.")
    if action == "reuse":
        return True, "Existing workspace is valid."
    return True, ("GUI handoff bundle ready." if agent == "manual" else f"{agent} finished; outputs structurally validated.")


def _run_curses() -> None:  # pragma: no cover - interactive UI
    import curses

    def main(stdscr) -> None:
        curses.curs_set(0)
        stdscr.keypad(True)
        state: dict[str, Any] = {
            "asset": "",
            "output_dir": "output",
            "title": "",
            "lecture": "",
            "notes_full": False,
            "notes_deep": True,
            "notes_summary": False,
            "verbatim_transcript": False,
            "format_profile": "clean",
            "use_slides": True,
            "embed_slides": False,
            "allow_web": False,
            "device": "auto",
            "agent": "manual",
        }
        # key, label, kind. Actions behave like buttons.
        fields = [
            ("asset", "Asset ZIP", "text"),
            ("output_dir", "Output Dir", "text"),
            ("title", "Course", "text"),
            ("lecture", "Lecture ID", "text"),
            ("notes_full", "Full polished notes", "toggle"),
            ("notes_deep", "Deep notes", "toggle"),
            ("notes_summary", "Summary notes", "toggle"),
            ("verbatim_transcript", "Verbatim transcript", "toggle"),
            ("format_profile", "Reading format", "format"),
            ("use_slides", "Use PPT as source", "toggle"),
            ("embed_slides", "Embed PPT", "toggle"),
            ("allow_web", "Allow web supplements", "toggle"),
            ("device", "ASR device", "device"),
            ("agent", "Agent interaction", "agent"),
            ("run", "RUN", "action"),
            ("prompt", "REFRESH PROMPT", "action"),
            ("view", "VIEW PROMPT", "action"),
            ("quit", "QUIT", "action"),
        ]
        selected = 0
        status = "Ready. Focus Asset ZIP, press Enter, then drag the ZIP file into this terminal."
        device_values = ["auto", "mps", "cuda", "cpu"]
        agent_values, agent_labels = available_agent_choices()

        while True:
            height, width = stdscr.getmaxyx()
            if height < 30 or width < 94:
                stdscr.erase()
                _safe_add(stdscr, 1, 2, "Handouter ASCII TUI needs at least 94x30. Resize terminal; Q quits.")
                stdscr.refresh()
                if stdscr.getch() in (ord("q"), ord("Q")):
                    return
                continue

            stdscr.erase()
            right = width - 2
            _box(stdscr, 0, 0, height - 2, right, " HANDOUTER :: ZHIYUN -> LOCAL NOTES ")
            exporter = exporter_script_path()
            exporter_name = exporter.name if exporter else "not found"
            _safe_add(stdscr, 1, 2, f"Exporter: {exporter_name}  |  Asset ZIP supports terminal drag & drop")
            _safe_add(stdscr, 2, 2, "Tab/Up/Down move | Enter edit/action | Space toggle | Left/Right options | F5 run | P refresh | Q quit")

            _box(stdscr, 4, 2, 10, right - 2, " SOURCE / DESTINATION ")
            labels = [
                ("Asset ZIP", state["asset"] or "<Enter, then drag ZIP here>"),
                ("Output Dir", state["output_dir"]),
                ("Course", state["title"] or "<auto from ZIP>"),
                ("Lecture ID", state["lecture"] or "<auto from page ids>"),
            ]
            for idx, (label, value) in enumerate(labels):
                attr = curses.A_REVERSE if selected == idx else 0
                _safe_add(stdscr, 5 + idx, 4, f"{label:<11} [ {value[: max(20, width - 28)]} ]", attr)
            _safe_add(stdscr, 9, 4, "Asset ZIP expects a file path. Press Enter, then drag a .zip file into the terminal.")

            mid = width // 2
            _box(stdscr, 11, 2, 19, mid - 1, " DELIVERABLES ")
            deliver_rows = [
                (4, 13, "Full polished notes", "notes_full"),
                (5, 14, "Deep notes", "notes_deep"),
                (6, 15, "Summary notes", "notes_summary"),
                (7, 16, "Verbatim transcript", "verbatim_transcript"),
            ]
            for idx, row, label, key in deliver_rows:
                attr = curses.A_REVERSE if selected == idx else 0
                _safe_add(stdscr, row, 5, f"{_checkbox(bool(state[key]))} {label}", attr)

            _box(stdscr, 11, mid, 19, right - 2, " OPTIONS ")
            option_lines = [
                (8, 13, f"Reading format  < {state['format_profile']} >"),
                (9, 14, f"{_checkbox(bool(state['use_slides']))} Use PPT as source"),
                (10, 15, f"{_checkbox(bool(state['embed_slides']))} Embed PPT"),
                (11, 16, f"{_checkbox(bool(state['allow_web']))} Allow web supplements"),
                (12, 17, f"ASR device      < {state['device']} >"),
                (13, 18, f"Agent           < {agent_labels[state['agent']]} >"),
            ]
            for idx, row, text in option_lines:
                attr = curses.A_REVERSE if selected == idx else 0
                _safe_add(stdscr, row, mid + 3, text, attr)

            _box(stdscr, 20, 2, 23, right - 2, " ACTIONS ")
            actions = [(14, "[ RUN ]"), (15, "[ REFRESH PROMPT ]"), (16, "[ VIEW PROMPT ]"), (17, "[ QUIT ]")]
            col = 5
            for idx, text in actions:
                attr = curses.A_REVERSE if selected == idx else 0
                _safe_add(stdscr, 21, col, text, attr)
                col += len(text) + 3
            _safe_add(stdscr, 22, 5, "H = EXPORT HTML (offline reading)")

            _box(stdscr, 24, 2, height - 3, right - 2, " STATUS ")
            modes = selected_modes(state)
            _safe_add(stdscr, 25, 4, f"Deliverables: {', '.join(modes) if modes else '<none selected>'}  |  Agent: {agent_labels[state['agent']]}")
            _safe_add(stdscr, 26, 4, status)
            stdscr.refresh()

            key = stdscr.getch()
            if key in (ord('h'), ord('H')):
                default = str(_workspace_for_state(state) or state.get('source_note') or '')
                value, committed = _edit_value(stdscr, 'Markdown file or lecture folder', default)
                if committed and value.strip():
                    try:
                        from .html_export import export_html
                        import webbrowser
                        outputs = export_html(normalize_terminal_path(value))
                        webbrowser.open(outputs[0].as_uri())
                        status = f'Exported {len(outputs)} offline HTML file(s) beside Markdown: {outputs[0].name}'
                    except (OSError, ValueError, RuntimeError) as exc:
                        status = f'HTML export failed: {exc}'
                continue
            if key in (ord("q"), ord("Q")):
                return
            if key in (9, 258):  # Tab / Down
                selected = (selected + 1) % len(fields)
                continue
            if key in (353, 259):  # Shift-Tab / Up
                selected = (selected - 1) % len(fields)
                continue
            if key == curses.KEY_F5:
                selected = 14
                key = 10
            elif key in (ord("p"), ord("P")):
                selected = 15
                key = 10

            field_key, label, kind = fields[selected]
            if kind == "text" and 32 <= key <= 126 and key not in (ord("q"), ord("Q")):
                value, committed = _edit_value(stdscr, label, str(state[field_key]), initial=chr(key))
                if committed:
                    try:
                        message = _commit_text_value(state, field_key, value)
                        if message:
                            status = message
                    except Exception as exc:
                        status = f"Invalid {label}: {exc}"
                continue
            if key in (260, 261):  # left/right
                if kind == "format":
                    state[field_key] = "traceable" if state[field_key] == "clean" else "clean"
                elif kind == "device":
                    pos = device_values.index(state[field_key])
                    state[field_key] = device_values[(pos + (1 if key == 261 else -1)) % len(device_values)]
                elif kind == "agent":
                    pos = agent_values.index(state[field_key])
                    state[field_key] = agent_values[(pos + (1 if key == 261 else -1)) % len(agent_values)]
                continue
            if key == ord(" "):
                if kind == "toggle":
                    state[field_key] = not bool(state[field_key])
                    if field_key == "embed_slides" and state[field_key]:
                        state["use_slides"] = True
                elif kind == "format":
                    state[field_key] = "traceable" if state[field_key] == "clean" else "clean"
                elif kind == "device":
                    pos = device_values.index(state[field_key])
                    state[field_key] = device_values[(pos + 1) % len(device_values)]
                elif kind == "agent":
                    pos = agent_values.index(state[field_key])
                    state[field_key] = agent_values[(pos + 1) % len(agent_values)]
                continue
            if key not in (10, 13):
                continue

            if kind == "text":
                value, committed = _edit_value(stdscr, label, str(state[field_key]))
                if committed:
                    try:
                        message = _commit_text_value(state, field_key, value)
                        if message:
                            status = message
                    except Exception as exc:
                        status = f"Invalid {label}: {exc}"
                continue
            if kind == "toggle":
                state[field_key] = not bool(state[field_key])
                if field_key == "embed_slides" and state[field_key]:
                    state["use_slides"] = True
                continue
            if kind in {"format", "device", "agent"}:
                if kind == "format":
                    state[field_key] = "traceable" if state[field_key] == "clean" else "clean"
                elif kind == "device":
                    pos = device_values.index(state[field_key])
                    state[field_key] = device_values[(pos + 1) % len(device_values)]
                else:
                    pos = agent_values.index(state[field_key])
                    state[field_key] = agent_values[(pos + 1) % len(agent_values)]
                continue

            if field_key == "quit":
                return
            if field_key == "view":
                if not state.get("lecture"):
                    status = "No lecture selected yet."
                    continue
                path = friendly_artifact_paths(state)["prompt"]
                if isinstance(path, Path) and path.is_file():
                    _view_text(stdscr, " PROMPT.md ", path)
                else:
                    status = f"Prompt not found: {path}"
                continue
            if field_key in {"run", "prompt"}:
                modes = selected_modes(state)
                if not modes:
                    status = "Select at least one deliverable."
                    continue
                if field_key == "run":
                    try:
                        status = _load_asset_into_state(state)
                    except Exception as exc:
                        status = f"Cannot load asset ZIP: {exc}"
                        continue
                    if not state.get("title"):
                        status = "Course title is missing; edit Course manually."
                        continue
                if not state.get("lecture"):
                    status = "Lecture ID is required."
                    continue
                try:
                    ok, message = _run_task(stdscr, state, prompt_only=(field_key == "prompt"))
                    status = message
                    if ok:
                        paths = friendly_artifact_paths(state)
                        expected = paths.get("expected_notes", {})
                        if isinstance(expected, dict):
                            status += " Targets: " + ", ".join(Path(path).name for path in expected.values())
                except Exception as exc:
                    status = f"Task failed: {exc}"

    curses.wrapper(main)


def run_tui() -> None:
    try:
        import curses  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("ASCII TUI requires Python curses support.") from exc
    _run_curses()
