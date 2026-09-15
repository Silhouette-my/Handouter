"""Local/authorized media handling with overwrite protection and verification."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class MediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioExtractResult:
    output: Path
    duration_ms: int
    bytes: int
    mode: str


def _is_remote(source: str) -> bool:
    return urlsplit(source).scheme.lower() in {"http", "https"}


def _redact(text: str) -> str:
    text = re.sub(r"https?://[^\s'\"]+", "<redacted-url>", text)
    text = re.sub(r"(?i)(cookie|auth_key|token|signature|sign)=([^&\s]+)", r"\1=<redacted>", text)
    return text[-2000:]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONUTF8": "1"},
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def probe_duration_ms(path: str | Path) -> int:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"媒体文件不存在: {target}")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise MediaError("找不到 ffprobe，请先安装 ffmpeg")
    result = _run([
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(target),
    ])
    if result.returncode != 0:
        raise MediaError(f"ffprobe 读取失败: {_redact(result.stderr)}")
    try:
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MediaError("ffprobe 没有返回有效媒体时长") from exc
    if not duration > 0:
        raise MediaError("媒体时长必须大于 0")
    return int(round(duration * 1000))


def verify_audio_decodable(path: str | Path, *, duration_ms: int | None = None) -> None:
    """Decode short samples from the beginning/end so container-only success is insufficient."""
    target = Path(path)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise MediaError("找不到 ffmpeg")
    if duration_ms is None:
        duration_ms = probe_duration_ms(target)
    offsets = [0.0]
    if duration_ms > 20_000:
        offsets.append(max(0.0, duration_ms / 1000 - 5.0))
    for offset in offsets:
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-nostdin"]
        if offset > 0:
            command += ["-ss", f"{offset:.3f}"]
        command += ["-i", str(target), "-map", "0:a:0", "-t", "3", "-f", "null", "-"]
        result = _run(command)
        if result.returncode != 0:
            raise MediaError(f"音频解码校验失败: {_redact(result.stderr) or 'ffmpeg decode failed'}")


def _input_args(source: str, referer: str | None) -> list[str]:
    args = ["-rw_timeout", "15000000"]
    if _is_remote(source):
        headers = "User-Agent: Mozilla/5.0\r\n"
        if referer:
            headers += f"Referer: {referer}\r\n"
        args += [
            "-headers", headers,
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
        ]
    return args + ["-i", source]


def extract_audio(
    source: str | Path,
    output: str | Path,
    *,
    referer: str | None = "https://interactivemeta.cmc.zju.edu.cn/",
) -> AudioExtractResult:
    """Extract audio to a NEW path.

    Source may be a local media file or an authorized HTTP(S) media URL. The
    function never clears proxy variables and never overwrites the requested
    output. It writes a sibling temporary file, verifies it with ffprobe, then
    atomically renames it into place.
    """

    source_text = str(source)
    if not _is_remote(source_text):
        source_path = Path(source_text)
        if not source_path.is_file() or source_path.is_symlink():
            raise FileNotFoundError(f"本地媒体不存在或不是普通文件: {source_path}")
        source_text = str(source_path)

    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"音频输出已存在，拒绝覆盖: {output}")
    if not output.parent.exists():
        output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise MediaError("找不到 ffmpeg")

    suffix = output.suffix or ".m4a"
    temp = output.parent / f".{output.stem}.part-{uuid.uuid4().hex}{suffix}"
    common = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n"]
    input_args = _input_args(source_text, referer)
    commands = [
        ("copy", common + input_args + ["-vn", "-map", "0:a:0?", "-c:a", "copy", str(temp)]),
        ("aac", common + input_args + ["-vn", "-map", "0:a:0?", "-c:a", "aac", "-b:a", "128k", str(temp)]),
    ]

    errors: list[str] = []
    try:
        for mode, command in commands:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass
            result = _run(command)
            if result.returncode == 0 and temp.is_file() and temp.stat().st_size > 0:
                try:
                    duration_ms = probe_duration_ms(temp)
                    verify_audio_decodable(temp, duration_ms=duration_ms)
                except (MediaError, OSError) as exc:
                    errors.append(f"{mode}: {_redact(str(exc))}")
                    continue
                size = temp.stat().st_size
                temp.replace(output)
                return AudioExtractResult(output=output, duration_ms=duration_ms, bytes=size, mode=mode)
            errors.append(f"{mode}: {_redact(result.stderr) or 'ffmpeg failed'}")
        raise MediaError("音频抽取失败；" + " | ".join(errors))
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
