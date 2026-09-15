"""Install and launch the checkout without activating a virtual environment."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def run(command: list[str], **kwargs) -> None:
    subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def refresh_windows_path() -> None:
    """Pick up package-manager PATH additions without restarting the terminal."""
    if sys.platform != "win32":
        return
    import winreg

    paths = [os.environ.get("PATH", "")]
    for hive, key in (
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, r"Environment"),
    ):
        try:
            with winreg.OpenKey(hive, key) as handle:
                value, _ = winreg.QueryValueEx(handle, "Path")
                paths.append(os.path.expandvars(value))
        except OSError:
            pass
    os.environ["PATH"] = os.pathsep.join(paths)


def ensure_media() -> None:
    refresh_windows_path()
    if not all(shutil.which(name) for name in ("ffmpeg", "ffprobe")):
        print("Installing FFmpeg (ffmpeg + ffprobe)...", flush=True)
        if sys.platform == "win32" and shutil.which("winget"):
            run(["winget", "install", "--id", "Gyan.FFmpeg", "--exact",
                 "--accept-package-agreements", "--accept-source-agreements",
                 "--disable-interactivity"])
            refresh_windows_path()
        elif sys.platform == "darwin" and shutil.which("brew"):
            run(["brew", "install", "ffmpeg"])
        else:
            raise RuntimeError("FFmpeg is missing. Windows: install App Installer (winget); "
                               "macOS: install Homebrew; Linux: install ffmpeg with your package manager. "
                               "Then run this installer again.")
    for name in ("ffmpeg", "ffprobe"):
        executable = shutil.which(name)
        if not executable:
            raise RuntimeError(f"{name} is still unavailable. Reopen the terminal and retry.")
        run([executable, "-version"], stdout=subprocess.DEVNULL)


def check_runtime(python: Path) -> None:
    # Import the native extensions, rather than accepting package presence alone.
    run([str(python), "-c",
         "import torch, torchaudio, funasr, curses; "
         "from torchaudio.compliance.kaldi import fbank; "
         "assert callable(curses.initscr); "
         "fbank(torch.zeros(1, 16000), sample_frequency=16000); "
         "print('ASR imports OK:', torch.__version__, torchaudio.__version__)"])
    run([str(python), "-m", "pip", "check"])
    run([str(python), "-m", "handouter", "doctor"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", action="store_true", help="launch an existing installation")
    args = parser.parse_args(argv)
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    try:
        if args.start:
            if not python.is_file():
                raise RuntimeError("Run setup_handouter.py first to install Handouter.")
            refresh_windows_path()
            run([str(python), "-m", "handouter", "tui"])
            return 0
        if sys.version_info < (3, 11):
            raise RuntimeError("Python 3.11 or newer is required; Python 3.11 is recommended.")
        print("[1/4] Preparing project .venv...", flush=True)
        if not python.is_file():
            if (ROOT / ".venv").exists():
                raise RuntimeError("Existing .venv is incomplete; inspect it before retrying. Nothing was deleted.")
            run([sys.executable, "-m", "venv", str(ROOT / ".venv")])
        run([str(python), "-c", "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ required'"])
        print("[2/4] Installing Handouter, ASR and terminal dependencies...", flush=True)
        run([str(python), "-m", "pip", "install", ".[asr]"])
        print("[3/4] Checking FFmpeg...", flush=True)
        ensure_media()
        print("[4/4] Verifying installed runtime...", flush=True)
        check_runtime(python)
        print("Ready. Run start-handouter.cmd (Windows) or bash start-handouter.command (macOS).\n"
              "The first transcription downloads the speech models and needs internet access.")
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Setup stopped: {exc}\nFix the reported error, then run setup again; existing files are preserved.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
