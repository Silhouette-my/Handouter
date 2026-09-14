"""Optional Textual UI that delegates all work to the canonical CLI in a subprocess."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any


def build_cli_args(cfg: dict[str, Any]) -> list[str]:
    """Build the same CLI invocation the TUI will run; pure and testable."""
    kind = cfg["kind"]
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
        "--workspace-root", cfg.get("root") or "workspace",
        "--mode", cfg.get("mode") or "deep",
    ]
    if kind != "asset":
        if cfg.get("slides_zip"):
            args += ["--slides-zip", cfg["slides_zip"]]
        else:
            if cfg.get("slides"):
                args += ["--slides-dir", cfg["slides"]]
            if cfg.get("meta"):
                args += ["--slides-meta", cfg["meta"]]
    if cfg.get("use_slides", True):
        args.append("--use-slides-as-source")
    else:
        args.append("--ignore-slides")
    if cfg.get("embed_slides"):
        args.append("--embed-slides")
    if cfg.get("allow_web"):
        args.append("--allow-web")
    if kind in {"asset", "audio", "media"}:
        args += ["--device", cfg.get("device") or "auto"]
    return args


try:
    from textual import work
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, VerticalScroll
    from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, Switch
except ImportError:  # pragma: no cover - current environment intentionally lacks optional TUI
    App = None


if App is not None:
    class HandouterApp(App):
        TITLE = "Handouter"
        SUB_TITLE = "智云资产 → 本地 ASR → Agent 交接"
        CSS = """
        Screen { layout: vertical; }
        #body { padding: 1 2; height: 1fr; }
        .row { height: auto; margin-bottom: 1; }
        .field { width: 1fr; margin-right: 1; }
        .label { width: 16; content-align: left middle; }
        #log { height: 14; border: round $accent; }
        #run, #cancel { width: 22; margin-right: 2; }
        """

        def __init__(self) -> None:
            super().__init__()
            self._process: subprocess.Popen[str] | None = None

        def compose(self) -> ComposeResult:
            yield Header()
            with VerticalScroll(id="body"):
                yield Label("默认只在本地准备材料与 Prompt；不会自动运行你的 Agent，也不会把 private/ URL 写进交接包。")
                with Horizontal(classes="row"):
                    yield Label("输入类型", classes="label")
                    yield Select(
                        [("智云资产 ZIP（推荐）", "asset"), ("已有转写 TXT", "transcript"), ("本地音频", "audio"), ("本地/授权媒体", "media")],
                        value="asset", allow_blank=False, id="kind", classes="field"
                    )
                    yield Label("讲义模式", classes="label")
                    yield Select([("深度版", "deep"), ("清理逐字版", "full"), ("精简版", "summary")], value="deep", allow_blank=False, id="mode", classes="field")
                with Horizontal(classes="row"):
                    yield Label("课程标题", classes="label")
                    yield Input(placeholder="如：计算机系统", id="title", classes="field")
                    yield Label("讲次 ID", classes="label")
                    yield Input(placeholder="如：ics-20260914-01", id="lecture", classes="field")
                with Horizontal(classes="row"):
                    yield Label("主输入", classes="label")
                    yield Input(placeholder="资产 ZIP / TXT / 音频 / 视频路径，或授权媒体 URL", id="source", classes="field")
                with Horizontal(classes="row"):
                    yield Label("PPT 图片目录", classes="label")
                    yield Input(placeholder="非资产 ZIP 模式可填", id="slides", classes="field")
                    yield Label("PPT 元数据", classes="label")
                    yield Input(placeholder="可留空；独立 slides_meta.json", id="meta", classes="field")
                with Horizontal(classes="row"):
                    yield Label("PPT 资产 ZIP", classes="label")
                    yield Input(placeholder="非 build-asset 模式下可单独作为 PPT 来源", id="slides-zip", classes="field")
                with Horizontal(classes="row"):
                    yield Label("工作区根目录", classes="label")
                    yield Input(value="workspace", id="root", classes="field")
                    yield Label("ASR 设备", classes="label")
                    yield Select([("自动", "auto"), ("CPU", "cpu"), ("Apple MPS", "mps"), ("CUDA", "cuda")], value="auto", allow_blank=False, id="device", classes="field")
                with Horizontal(classes="row"):
                    yield Label("参考 PPT", classes="label")
                    yield Switch(value=True, id="use-slides")
                    yield Label("正文嵌图", classes="label")
                    yield Switch(value=False, id="embed-slides")
                    yield Label("允许联网补充", classes="label")
                    yield Switch(value=False, id="allow-web")
                with Horizontal(classes="row"):
                    yield Button("准备 Agent 交接包", variant="primary", id="run")
                    yield Button("取消当前任务", variant="error", id="cancel", disabled=True)
                yield RichLog(id="log", wrap=True, highlight=True, markup=True)
            yield Footer()

        def _config(self) -> dict[str, Any]:
            return {
                "kind": self.query_one("#kind", Select).value,
                "mode": self.query_one("#mode", Select).value,
                "title": self.query_one("#title", Input).value.strip(),
                "lecture": self.query_one("#lecture", Input).value.strip(),
                "source": self.query_one("#source", Input).value.strip(),
                "slides": self.query_one("#slides", Input).value.strip() or None,
                "meta": self.query_one("#meta", Input).value.strip() or None,
                "slides_zip": self.query_one("#slides-zip", Input).value.strip() or None,
                "root": self.query_one("#root", Input).value.strip() or "workspace",
                "device": self.query_one("#device", Select).value,
                "use_slides": self.query_one("#use-slides", Switch).value,
                "embed_slides": self.query_one("#embed-slides", Switch).value,
                "allow_web": self.query_one("#allow-web", Switch).value,
            }

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "cancel":
                self._request_cancel()
                return
            if event.button.id != "run":
                return
            cfg = self._config()
            if not cfg["title"] or not cfg["lecture"] or not cfg["source"]:
                self.query_one("#log", RichLog).write("[red]课程标题、讲次 ID 和主输入不能为空。[/red]")
                return
            if cfg["embed_slides"]:
                cfg["use_slides"] = True
            self.query_one("#run", Button).disabled = True
            self.query_one("#cancel", Button).disabled = False
            self.query_one("#log", RichLog).write("[cyan]任务已启动。TUI 正在运行同一套 handouter CLI。[/cyan]")
            self._run_cli(cfg)

        @work(thread=True, exclusive=True)
        def _run_cli(self, cfg: dict[str, Any]) -> None:
            command = [sys.executable, "-m", "handouter", *build_cli_args(cfg)]
            kwargs: dict[str, Any] = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "bufsize": 1,
                "env": os.environ.copy(),
            }
            if os.name != "nt":
                kwargs["start_new_session"] = True
            elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            try:
                process = subprocess.Popen(command, **kwargs)
                self._process = process
                assert process.stdout is not None
                for line in process.stdout:
                    self.call_from_thread(self.query_one("#log", RichLog).write, line.rstrip())
                code = process.wait()
                self._process = None
                if code == 0:
                    self.call_from_thread(self._finish, True, "任务完成：handoff 已就绪；程序没有自动运行 Agent。")
                elif code < 0:
                    self.call_from_thread(self._finish, False, "任务已取消，子进程已结束。")
                else:
                    self.call_from_thread(self._finish, False, f"任务失败，退出码 {code}。请查看上方日志。")
            except Exception as exc:
                self._process = None
                self.call_from_thread(self._finish, False, str(exc))

        def _request_cancel(self) -> None:
            process = self._process
            if process is None or process.poll() is not None:
                return
            self.query_one("#cancel", Button).disabled = True
            self.query_one("#log", RichLog).write("[yellow]正在终止任务进程组…[/yellow]")
            try:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
            except ProcessLookupError:
                return

            def force_kill() -> None:
                time.sleep(3)
                if process.poll() is None:
                    try:
                        if os.name != "nt":
                            os.killpg(process.pid, signal.SIGKILL)
                        else:
                            process.kill()
                    except ProcessLookupError:
                        pass
            threading.Thread(target=force_kill, daemon=True).start()

        def _finish(self, ok: bool, message: str) -> None:
            log = self.query_one("#log", RichLog)
            tag = "green" if ok else "red"
            log.write(f"[{tag}]{message}[/{tag}]")
            self.query_one("#run", Button).disabled = False
            self.query_one("#cancel", Button).disabled = True

        def on_unmount(self) -> None:
            self._request_cancel()


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass


def _curses_prompt(stdscr: Any, row: int, label: str, default: str = "") -> str:
    import curses

    stdscr.addstr(row, 1, label)
    if default:
        stdscr.addstr(row, min(len(label) + 2, 40), f"[{default}] ")
    stdscr.refresh()
    curses.echo()
    try:
        raw = stdscr.getstr(row, min(len(label) + len(default) + 5, 55), 180)
    finally:
        curses.noecho()
    value = raw.decode("utf-8", errors="replace").strip()
    return value or default


def _run_curses() -> None:
    import curses
    import queue

    def main(stdscr: Any) -> None:
        curses.curs_set(1)
        stdscr.clear()
        stdscr.addstr(0, 1, "Handouter — fallback TUI (standard-library curses)")
        stdscr.addstr(1, 1, "Textual 未安装；此界面仍调用同一套 CLI。任务运行时按 q 可取消。")
        stdscr.addstr(3, 1, "输入类型: 1=智云资产ZIP  2=转写TXT  3=本地音频  4=本地/授权媒体")
        kind_choice = _curses_prompt(stdscr, 4, "选择", "1")
        kind = {"1": "asset", "2": "transcript", "3": "audio", "4": "media"}.get(kind_choice)
        if kind is None:
            raise ValueError("输入类型必须是 1-4")
        title = _curses_prompt(stdscr, 6, "课程标题")
        lecture = _curses_prompt(stdscr, 7, "讲次 ID")
        source = _curses_prompt(stdscr, 8, "主输入路径/授权 URL")
        root = _curses_prompt(stdscr, 9, "工作区根目录", "workspace")
        stdscr.addstr(11, 1, "讲义模式: 1=deep  2=full  3=summary")
        mode_choice = _curses_prompt(stdscr, 12, "选择", "1")
        mode = {"1": "deep", "2": "full", "3": "summary"}.get(mode_choice)
        if mode is None:
            raise ValueError("讲义模式必须是 1-3")
        use_slides = _curses_prompt(stdscr, 14, "允许 Agent 参考 PPT? y/n", "y").lower() != "n"
        embed_slides = _curses_prompt(stdscr, 15, "正文嵌入 PPT? y/n", "n").lower() == "y"
        if embed_slides:
            use_slides = True
        slides = meta = slides_zip = None
        if kind != "asset":
            slides_zip = _curses_prompt(stdscr, 17, "可选 PPT 资产 ZIP", "") or None
            if not slides_zip:
                slides = _curses_prompt(stdscr, 18, "可选 PPT 图片目录", "") or None
                meta = _curses_prompt(stdscr, 19, "可选 slides_meta.json", "") or None
        device = "auto"
        if kind in {"asset", "audio", "media"}:
            device = _curses_prompt(stdscr, 20, "ASR 设备 auto/cpu/mps/cuda", "auto")
        cfg = {
            "kind": kind,
            "title": title,
            "lecture": lecture,
            "source": source,
            "root": root,
            "mode": mode,
            "slides": slides,
            "meta": meta,
            "slides_zip": slides_zip,
            "use_slides": use_slides,
            "embed_slides": embed_slides,
            "allow_web": False,
            "device": device,
        }
        if not title or not lecture or not source:
            raise ValueError("课程标题、讲次 ID 和主输入不能为空")

        command = [sys.executable, "-m", "handouter", *build_cli_args(cfg)]
        kwargs: dict[str, Any] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
            "env": os.environ.copy(),
        }
        if os.name != "nt":
            kwargs["start_new_session"] = True
        elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        process = subprocess.Popen(command, **kwargs)
        lines: queue.Queue[str] = queue.Queue()

        def reader() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                lines.put(line.rstrip())

        threading.Thread(target=reader, daemon=True).start()
        stdscr.clear()
        stdscr.nodelay(True)
        curses.curs_set(0)
        history: list[str] = ["任务已启动；按 q 取消。", ""]
        cancelled = False
        while True:
            try:
                while True:
                    history.append(lines.get_nowait())
            except queue.Empty:
                pass
            height, width = stdscr.getmaxyx()
            stdscr.erase()
            stdscr.addstr(0, 1, "Handouter task log — q: cancel", curses.A_BOLD)
            for idx, line in enumerate(history[-max(1, height - 3):], 1):
                try:
                    stdscr.addnstr(idx, 1, line, max(1, width - 2))
                except curses.error:
                    pass
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("q"), ord("Q")) and process.poll() is None:
                cancelled = True
                history.append("正在终止任务进程组…")
                _terminate_process(process)
            code = process.poll()
            if code is not None:
                while True:
                    try:
                        history.append(lines.get_nowait())
                    except queue.Empty:
                        break
                message = "任务已取消。" if cancelled else ("handoff 已就绪；未自动运行 Agent。" if code == 0 else f"任务失败，退出码 {code}。")
                history.extend(["", message, "按任意键退出。"])
                stdscr.nodelay(False)
                stdscr.erase()
                stdscr.addstr(0, 1, "Handouter task result", curses.A_BOLD)
                height, width = stdscr.getmaxyx()
                for idx, line in enumerate(history[-max(1, height - 2):], 1):
                    try:
                        stdscr.addnstr(idx, 1, line, max(1, width - 2))
                    except curses.error:
                        pass
                stdscr.refresh()
                stdscr.getch()
                return
            time.sleep(0.1)

    curses.wrapper(main)


def run_tui() -> None:
    if App is not None:
        HandouterApp().run()
        return
    try:
        _run_curses()
    except ImportError as exc:
        raise RuntimeError("没有可用 TUI 后端；安装 textual，或使用包含 curses 的标准 Python。") from exc
