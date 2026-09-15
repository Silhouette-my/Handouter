"""Small cross-platform helpers shared by the TUI and subprocess workflows."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any

WINDOWS_CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
WINDOWS_RESERVED_DEVICE_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
WINDOWS_INVALID_COMPONENT_CHARS = set('<>:"/\\|?*')
_TASK_JOB_ENV = "HANDOUTER_TASK_JOB_HANDLE"


def _windows_job_api():
    """Load Windows APIs lazily so the same module imports on POSIX."""
    import ctypes
    from ctypes import wintypes

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
        "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
        "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
        "GetCurrentProcess": ([], wintypes.HANDLE),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes = args
        function.restype = result
    return api


class _WindowsJob:
    """Parent-owned job; closing its last handle kills all task descendants."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimits),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self.api = _windows_job_api()
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def close(self) -> None:
        if self.handle is not None:
            if not self.api.CloseHandle(self.handle):
                import ctypes

                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = None


def _join_inherited_windows_job() -> None:
    """Join before importing/running CLI code that can spawn worker processes."""
    value = os.environ.pop(_TASK_JOB_ENV, None)
    if value is None:
        return
    if not is_windows():
        raise RuntimeError("Windows task job handle supplied on a non-Windows host")
    import ctypes

    handle = int(value)
    api = _windows_job_api()
    try:
        if not api.AssignProcessToJobObject(handle, api.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        # Only the TUI keeps a handle; workers must not keep the job alive.
        api.CloseHandle(handle)


def start_task_process(cli_args: list[str], **kwargs: Any) -> tuple[subprocess.Popen[str], _WindowsJob | None]:
    """Start a managed CLI task, with a Windows job established before workers."""
    command = [sys.executable, "-m", "handouter.platform_support", *cli_args]
    kwargs.update(process_group_popen_kwargs())
    env = dict(kwargs.get("env", os.environ))
    env.pop(_TASK_JOB_ENV, None)
    kwargs["env"] = env
    job = _WindowsJob() if is_windows() else None
    try:
        if job is not None:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.lpAttributeList = {"handle_list": [job.handle]}
            kwargs.update(startupinfo=startupinfo, close_fds=True)
            env[_TASK_JOB_ENV] = str(job.handle)
            os.set_handle_inheritable(job.handle, True)
        try:
            process = subprocess.Popen(command, **kwargs)
        finally:
            if job is not None:
                os.set_handle_inheritable(job.handle, False)
    except BaseException:
        if job is not None:
            job.close()
        raise
    return process, job


def is_portable_path_component(value: str) -> bool:
    """Return whether one filename component is safe on macOS/Linux/Windows."""
    if not value or value in {".", ".."} or value.endswith((" ", ".")):
        return False
    if any(char in WINDOWS_INVALID_COMPONENT_CHARS or ord(char) < 32 for char in value):
        return False
    stem = value.split(".", 1)[0].casefold()
    return stem not in WINDOWS_RESERVED_DEVICE_NAMES


def is_windows(platform_name: str | None = None) -> bool:
    return (platform_name or os.name).lower() in {"nt", "windows", "win32"}


def process_group_popen_kwargs(platform_name: str | None = None) -> dict[str, Any]:
    """Return Popen kwargs that isolate a task into its own cancellable group."""
    if is_windows(platform_name):
        return {"creationflags": WINDOWS_CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _request_termination(process: subprocess.Popen[Any], platform_name: str | None = None) -> None:
    if process.poll() is not None:
        return
    if is_windows(platform_name):
        ctrl_break = getattr(signal, "CTRL_BREAK_EVENT", None)
        if ctrl_break is not None:
            try:
                process.send_signal(ctrl_break)
                return
            except (OSError, ValueError):
                pass
        try:
            process.terminate()
        except OSError:
            pass
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def _force_termination(
    process: subprocess.Popen[Any],
    *,
    grace_seconds: float,
    platform_name: str | None = None,
) -> None:
    time.sleep(grace_seconds)
    if is_windows(platform_name):
        # The TUI closes its Job Object even when this root process has exited.
        if process.poll() is not None:
            return
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
            if result.returncode == 0:
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            process.kill()
        except OSError:
            pass
        return

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def terminate_process_tree(
    process: subprocess.Popen[Any],
    *,
    grace_seconds: float = 3.0,
    platform_name: str | None = None,
) -> threading.Thread | None:
    """Request cancellation; callers join the returned cleanup thread.

    Windows callers must also close the job returned by start_task_process.
    A process-group ID alone cannot contain Windows descendants after root exit.
    """
    if is_windows(platform_name) and process.poll() is not None:
        return
    _request_termination(process, platform_name)
    cleanup = threading.Thread(
        target=_force_termination,
        kwargs={"process": process, "grace_seconds": grace_seconds, "platform_name": platform_name},
        daemon=False,
    )
    cleanup.start()
    return cleanup


if __name__ == "__main__":
    try:
        _join_inherited_windows_job()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"handouter: error: cannot establish task process containment: {exc}", file=sys.stderr)
        raise SystemExit(2)
    from .cli import main

    raise SystemExit(main())
