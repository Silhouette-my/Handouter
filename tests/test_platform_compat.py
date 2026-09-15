"""Cross-platform compatibility regressions that can run on any host OS."""

from __future__ import annotations

from pathlib import Path
import os
import signal
import selectors
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from handouter.doctor import run_doctor
from handouter.platform_support import (
    WINDOWS_CREATE_NEW_PROCESS_GROUP,
    _force_termination,
    _request_termination,
    _join_inherited_windows_job,
    process_group_popen_kwargs,
    start_task_process,
    terminate_process_tree,
)
from handouter.product import normalize_terminal_path


class TerminalPathTests(unittest.TestCase):
    def test_windows_drive_path_is_not_posix_shlex_parsed(self):
        value = r"C:\Users\Alice\Downloads\My Course.zip"
        self.assertEqual(normalize_terminal_path(value, platform_name="nt"), value)

    def test_windows_quoted_drag_path(self):
        value = '"C:\\Users\\Alice\\Downloads\\My Course.zip"'
        self.assertEqual(
            normalize_terminal_path(value, platform_name="nt"),
            r"C:\Users\Alice\Downloads\My Course.zip",
        )

    def test_windows_file_uri(self):
        self.assertEqual(
            normalize_terminal_path("file:///C:/Users/Alice/My%20Course.zip", platform_name="nt"),
            r"C:\Users\Alice\My Course.zip",
        )

    def test_windows_unc_file_uri(self):
        self.assertEqual(
            normalize_terminal_path("file://server/share/My%20Course.zip", platform_name="nt"),
            r"\\server\share\My Course.zip",
        )

    def test_posix_drag_path_keeps_existing_behavior(self):
        self.assertEqual(
            normalize_terminal_path(r"/Users/alice/My\ Course.zip", platform_name="posix"),
            "/Users/alice/My Course.zip",
        )


class DoctorTests(unittest.TestCase):
    def test_windows_doctor_reports_windows_curses_backend(self):
        real_find_spec = __import__("importlib.util").util.find_spec

        def fake_find_spec(name):
            if name in {"curses", "funasr", "torch"}:
                return object()
            return real_find_spec(name)

        with patch("handouter.doctor.platform.system", return_value="Windows"), patch(
            "handouter.doctor.importlib.util.find_spec", side_effect=fake_find_spec
        ), patch("handouter.doctor._version", side_effect=lambda name: "2.4.1" if name == "windows-curses" else "1.0"), patch(
            "handouter.doctor.shutil.which", side_effect=lambda name: f"C:/tools/{name}.exe"
        ):
            report = run_doctor()
        self.assertEqual(report["platform"], "Windows")
        self.assertTrue(report["ok_tui"])
        curses = next(item for item in report["checks"] if item["name"] == "curses")
        self.assertEqual(curses["detail"], "2.4.1")


class ProcessTreeTests(unittest.TestCase):
    def test_tui_cleans_task_when_reader_thread_cannot_start(self):
        from handouter.tui import _run_task

        process = Mock()
        process.poll.return_value = None
        job = Mock()
        cleanup = Mock()
        reader = Mock()
        reader.start.side_effect = RuntimeError("cannot start reader")

        def cancel(_process):
            process.poll.return_value = -15
            return cleanup

        with patch("handouter.tui._task_cli_args", return_value=(["doctor"], "build")), \
             patch("handouter.tui.start_task_process", return_value=(process, job)), \
             patch("handouter.tui.threading.Thread", return_value=reader), \
             patch("handouter.tui._terminate_process_group", side_effect=cancel):
            with self.assertRaisesRegex(RuntimeError, "cannot start reader"):
                _run_task(Mock(), {}, prompt_only=False)
        job.close.assert_called_once()
        cleanup.join.assert_called_once()
        process.wait.assert_called_once()
        reader.join.assert_not_called()

    def test_managed_task_bootstrap_runs_cli(self):
        process, job = start_task_process(
            ["--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        try:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn("usage: handouter", stdout)
        finally:
            if job is not None:
                job.close()
            if process.poll() is None:
                cleanup = terminate_process_tree(process, grace_seconds=0)
                if cleanup is not None:
                    cleanup.join(timeout=10)
                process.wait(timeout=10)
            process.stdout.close()
            process.stderr.close()

    def test_process_group_kwargs_are_platform_specific(self):
        self.assertEqual(process_group_popen_kwargs("posix"), {"start_new_session": True})
        self.assertEqual(
            process_group_popen_kwargs("nt"),
            {"creationflags": WINDOWS_CREATE_NEW_PROCESS_GROUP},
        )

    def test_windows_termination_falls_back_to_terminate_without_ctrl_break(self):
        class FakeProcess:
            pid = 321

            def __init__(self):
                self.terminated = False

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True

        process = FakeProcess()
        with patch("handouter.platform_support.signal.CTRL_BREAK_EVENT", None, create=True):
            _request_termination(process, "nt")
        self.assertTrue(process.terminated)

    def test_windows_force_kill_uses_taskkill_tree(self):
        class FakeProcess:
            pid = 654

            def poll(self):
                return None

            def kill(self):
                raise AssertionError("taskkill should be attempted first")

        with patch("handouter.platform_support.time.sleep"), patch(
            "handouter.platform_support.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0),
        ) as run:
            _force_termination(FakeProcess(), grace_seconds=0, platform_name="nt")
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["taskkill", "/PID", "654", "/T", "/F"])

    def test_posix_termination_targets_process_group(self):
        class FakeProcess:
            pid = 987

            def poll(self):
                return None

        with patch("handouter.platform_support.os.killpg") as killpg:
            _request_termination(FakeProcess(), "posix")
        killpg.assert_called_once_with(987, __import__("signal").SIGTERM)

    def test_posix_force_kills_group_after_root_has_exited(self):
        process = SimpleNamespace(pid=987, poll=lambda: 0)
        with patch("handouter.platform_support.os.killpg") as killpg:
            _force_termination(process, grace_seconds=0, platform_name="posix")
        killpg.assert_called_once_with(987, signal.SIGKILL)

    @unittest.skipIf(os.name == "nt", "POSIX process-group integration")
    def test_cancel_reaps_group_when_root_exits_and_child_ignores_sigterm(self):
        child = "import os,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print(os.getpid(), flush=True); time.sleep(30)"
        parent = "import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', sys.argv[1]]); time.sleep(30)"
        process = subprocess.Popen(
            [sys.executable, "-c", parent, child], start_new_session=True,
            stdout=subprocess.PIPE, text=True,
        )
        cleanup = None
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5), "child did not become ready")
                self.assertGreater(int(process.stdout.readline()), 0)
                cleanup = terminate_process_tree(process, grace_seconds=0.15)
                process.wait(timeout=5)
                self.assertEqual(process.returncode, -signal.SIGTERM)
                cleanup.join(timeout=5)
                self.assertFalse(cleanup.is_alive())
                self.assertTrue(selector.select(timeout=5), "surviving child kept stdout open")
                self.assertEqual(process.stdout.read(), "")
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
            if cleanup is not None:
                cleanup.join(timeout=5)
            process.stdout.close()

    def test_windows_launch_passes_only_job_handle_and_closes_on_spawn_failure(self):
        job = SimpleNamespace(handle=123, close=Mock())
        with patch("handouter.platform_support.is_windows", return_value=True), \
             patch("handouter.platform_support._WindowsJob", return_value=job), \
             patch("handouter.platform_support.subprocess.STARTUPINFO", SimpleNamespace, create=True), \
             patch("handouter.platform_support.os.set_handle_inheritable", create=True) as inheritable, \
             patch("handouter.platform_support.subprocess.Popen", side_effect=OSError("spawn failed")) as popen:
            with self.assertRaisesRegex(OSError, "spawn failed"):
                start_task_process(["doctor"], env={"PYTHONUTF8": "1"})
        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["startupinfo"].lpAttributeList, {"handle_list": [123]})
        self.assertTrue(kwargs["close_fds"])
        self.assertEqual(kwargs["env"]["HANDOUTER_TASK_JOB_HANDLE"], "123")
        self.assertEqual([call.args for call in inheritable.call_args_list], [(123, True), (123, False)])
        job.close.assert_called_once()

    def test_windows_bootstrap_closes_inherited_handle_on_assignment_failure(self):
        api = SimpleNamespace(
            AssignProcessToJobObject=Mock(return_value=False),
            GetCurrentProcess=Mock(return_value=-1),
            CloseHandle=Mock(),
        )
        with patch.dict(os.environ, {"HANDOUTER_TASK_JOB_HANDLE": "123"}), \
             patch("handouter.platform_support.is_windows", return_value=True), \
             patch("handouter.platform_support._windows_job_api", return_value=api), \
             patch("ctypes.get_last_error", return_value=5, create=True), \
             patch("ctypes.WinError", return_value=OSError("assignment denied"), create=True):
            with self.assertRaisesRegex(OSError, "assignment denied"):
                _join_inherited_windows_job()
            self.assertNotIn("HANDOUTER_TASK_JOB_HANDLE", os.environ)
        api.AssignProcessToJobObject.assert_called_once_with(123, -1)
        api.CloseHandle.assert_called_once_with(123)

    @unittest.skipUnless(os.name == "nt", "requires real Windows Job Objects")
    def test_windows_job_closes_orphan_child_after_root_exits(self):
        # Exercise the real launch/handle inheritance with a disposable task body.
        child = "import os,time; print(os.getpid(), flush=True); time.sleep(30)"
        parent = (
            "from handouter.platform_support import _join_inherited_windows_job; "
            "_join_inherited_windows_job(); "
            "import subprocess,sys; subprocess.Popen([sys.executable, '-c', sys.argv[1]])"
        )
        real_popen = subprocess.Popen

        def synthetic_task(_command, **kwargs):
            return real_popen([sys.executable, "-c", parent, child], **kwargs)

        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        with patch("handouter.platform_support.subprocess.Popen", side_effect=synthetic_task):
            process, job = start_task_process(["doctor"], env=env, stdout=subprocess.PIPE, text=True)
        drained = threading.Event()
        try:
            process.wait(timeout=10)
            self.assertEqual(process.returncode, 0)
            self.assertGreater(int(process.stdout.readline()), 0)

            def drain():
                process.stdout.read()
                drained.set()

            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            self.assertFalse(drained.wait(0.1), "child should still be alive before job close")
            job.close()
            self.assertTrue(drained.wait(5), "job close did not stop orphan child")
            reader.join(timeout=5)
        finally:
            job.close()
            process.wait(timeout=5)
            process.stdout.close()


if __name__ == "__main__":
    unittest.main()
