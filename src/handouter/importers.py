"""Bounded, metadata-aware importers for local Handouter asset packages."""

from __future__ import annotations

import json
import re
import stat
import unicodedata
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath

from .platform_support import is_portable_path_component

MAX_ZIP_MEMBERS = 10_000
MAX_ZIP_BYTES = 512 * 1024 * 1024
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_PRIVATE_SOURCE_BYTES = 1024 * 1024
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _seconds_to_ms(value) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("seconds 必须是有限的非负数，单位为秒")
    try:
        seconds = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("seconds 字段不是有效数字") from exc
    if not seconds.is_finite() or not 0 <= seconds <= Decimal(2**53 - 1) / 1000:
        raise ValueError("seconds 超出有效范围")
    milliseconds = seconds * 1000
    if milliseconds != milliseconds.to_integral_value():
        raise ValueError("时间精度小于毫秒，不能无提示地舍入")
    return int(milliseconds)


def _clock_to_ms(value: str) -> int:
    if not isinstance(value, str):
        raise ValueError("时间字符串必须是 HH:MM:SS 或 MM:SS")
    parts = value.strip().split(":")
    if len(parts) not in (2, 3) or not all(re.fullmatch(r"\d+", part) for part in parts[:-1]):
        raise ValueError("无效的时间字符串")
    if not re.fullmatch(r"\d{1,2}(?:\.\d{1,3})?", parts[-1]):
        raise ValueError("秒字段必须在 0 到 60 之间，最多三位小数")
    seconds = _seconds_to_ms(parts[-1])
    if seconds >= 60_000 or (len(parts) == 3 and int(parts[1]) >= 60):
        raise ValueError("时间字符串的分/秒字段越界")
    minutes = int(parts[0]) if len(parts) == 2 else int(parts[0]) * 60 + int(parts[1])
    total = minutes * 60_000 + seconds
    if total > 2**53 - 1:
        raise ValueError("时间超出有效范围")
    return total


def _metadata_time_ms(item: dict) -> int | None:
    values: list[int] = []
    if item.get("seconds") is not None and item["seconds"] != "":
        values.append(_seconds_to_ms(item["seconds"]))
    for key in ("timestamp", "time", "switchTime"):
        if item.get(key) is not None and item[key] != "":
            values.append(_clock_to_ms(item[key]))
    if values and len(set(values)) != 1:
        raise ValueError("同一条 PPT 元数据的时间字段互相矛盾")
    return values[0] if values else None


def _format_timestamp(milliseconds: int | None) -> str | None:
    if milliseconds is None:
        return None
    seconds, fraction = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    suffix = f".{fraction:03d}".rstrip("0") if fraction else ""
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{suffix}"


def _safe_zip_name(name: str) -> PurePosixPath:
    if not isinstance(name, str) or not name or re.search(r'[\x00-\x1f\\:*?"<>|]', name):
        raise ValueError("ZIP 中包含不安全或跨平台歧义路径")
    body = name[:-1] if name.endswith("/") else name
    parts = body.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("ZIP 路径不得是绝对路径或包含空段、点、上级目录")
    if any(not is_portable_path_component(part) for part in parts):
        raise ValueError("ZIP 路径包含 Windows/macOS/Linux 间不可移植的文件名")
    return PurePosixPath(body)


def _natural_key(name: str):
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold()) for part in re.split(r"(\d+)", name))


def _image_extension(header: bytes) -> str:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("图片头不是支持的 PNG/JPEG/WebP；可能下载到了登录页或错误页")


def _safe_timing_diagnostics(item: dict) -> dict:
    status = item.get("timeStatus")
    field = item.get("sourceField")
    raw = item.get("rawTimeValue")
    if status is not None and not isinstance(status, str):
        status = None
    if field is not None and not isinstance(field, str):
        field = None
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float, type(None))):
        raw = None
    return {"time_status": status, "source_time_field": field, "raw_time_value": raw}


def read_private_media_source(zip_path: str | Path) -> str:
    """Read the browser export's private media URL without extracting or persisting it."""
    source_zip = Path(zip_path)
    if not source_zip.is_file() or source_zip.is_symlink():
        raise FileNotFoundError(f"ZIP 不存在或不是普通文件: {source_zip}")
    with zipfile.ZipFile(source_zip, "r") as archive:
        candidates = [info for info in archive.infolist() if info.filename == "private/source.json"]
        if len(candidates) != 1:
            raise ValueError("资产 ZIP 缺少唯一的 private/source.json；请重新从新版浏览器导出器打包")
        info = candidates[0]
        if info.file_size > MAX_PRIVATE_SOURCE_BYTES or info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError("private/source.json 不安全或超过大小限制")
        with archive.open(info) as handle:
            raw = handle.read(MAX_PRIVATE_SOURCE_BYTES + 1)
        if len(raw) > MAX_PRIVATE_SOURCE_BYTES:
            raise ValueError("private/source.json 超过大小限制")
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError("private/source.json 不是有效 UTF-8 JSON") from exc
        url = payload.get("videoUrl") if isinstance(payload, dict) else None
        if not isinstance(url, str) or not re.match(r"^https?://", url.strip(), re.I):
            raise ValueError("private/source.json 中没有有效 HTTP(S) 视频地址")
        return url.strip()


def import_slides_zip(zip_path: str | Path, output_dir: str | Path) -> list[dict]:
    """Import only slide images and safe timing metadata into a NEW directory.

    ``private/`` and ``course_info.json`` are intentionally not extracted. The
    source ZIP remains private input and may contain signed media URLs.
    """
    source_zip = Path(zip_path)
    destination = Path(output_dir)
    if not source_zip.is_file() or source_zip.is_symlink():
        raise FileNotFoundError(f"ZIP 不存在或不是普通文件: {source_zip}")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("PPT 导入目录已存在；拒绝覆盖")

    with zipfile.ZipFile(source_zip, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_MEMBERS or sum(info.file_size for info in infos) > MAX_ZIP_BYTES:
            raise ValueError("ZIP 文件数量或总解压大小超过限制")
        files: dict[str, zipfile.ZipInfo] = {}
        seen: set[str] = set()
        for info in infos:
            name = _safe_zip_name(info.orig_filename)
            key = unicodedata.normalize("NFC", name.as_posix()).casefold()
            if key in seen:
                raise ValueError("ZIP 存在重名或大小写/Unicode 歧义成员")
            seen.add(key)
            if stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
                raise ValueError("不接受 ZIP 符号链接或加密成员")
            if not info.is_dir() and "__MACOSX" not in name.parts:
                files[name.as_posix()] = info

        images = {name: info for name, info in files.items() if PurePosixPath(name).suffix.lower() in IMAGE_SUFFIXES}
        if not images:
            raise ValueError("ZIP 中没有可导入的 PPT 图片")
        metadata_names = [name for name in files if PurePosixPath(name).name == "slides_meta.json"]
        if len(metadata_names) > 1:
            raise ValueError("ZIP 内有多份 slides_meta.json，不能猜测采用哪份")

        events: list[tuple[str | None, int | None, str, int | None, str, dict]] = []
        referenced: set[str] = set()
        if metadata_names:
            metadata_name = metadata_names[0]
            info = files[metadata_name]
            if info.file_size > MAX_METADATA_BYTES:
                raise ValueError("PPT 元数据超过大小限制")
            with archive.open(info) as handle:
                raw = handle.read(MAX_METADATA_BYTES + 1)
            if len(raw) > MAX_METADATA_BYTES:
                raise ValueError("PPT 元数据超过大小限制")
            try:
                records = json.loads(raw.decode("utf-8-sig"))
            except (UnicodeError, ValueError) as exc:
                raise ValueError("slides_meta.json 不是有效 UTF-8 JSON") from exc
            if not isinstance(records, list) or len(records) > MAX_ZIP_MEMBERS:
                raise ValueError("PPT 元数据必须是数量受限的列表")
            base = PurePosixPath(metadata_name).parent
            for item in records:
                if not isinstance(item, dict):
                    raise ValueError("每条 PPT 元数据必须是对象")
                filename = _safe_zip_name(item.get("filename"))
                if filename.suffix.lower() not in IMAGE_SUFFIXES:
                    raise ValueError("元数据 filename 不是支持的图片类型")
                candidates = {str(base / filename), str(base / "slides" / filename)}
                matches = candidates.intersection(images)
                if len(matches) > 1:
                    raise ValueError("同一元数据图片对应多个文件，不能猜测")
                image = next(iter(matches), None)
                if image is not None:
                    referenced.add(image)
                source_index = item.get("index")
                if source_index is not None and (type(source_index) is not int or source_index < 1):
                    raise ValueError("PPT 原始 index 必须是正整数或 null")
                events.append((
                    image, _metadata_time_ms(item), "metadata", source_index,
                    filename.as_posix(), _safe_timing_diagnostics(item),
                ))

        for name in sorted(set(images) - referenced, key=_natural_key):
            milliseconds = None
            kind = "unreferenced_image" if metadata_names else "filename"
            if not metadata_names:
                match = re.search(r"__(\d+-\d{2}-\d{2}(?:\.\d{1,3})?)$", PurePosixPath(name).stem)
                if match:
                    milliseconds = _clock_to_ms(match.group(1).replace("-", ":"))
            events.append((name, milliseconds, kind, None, name, {}))

        targets: dict[str, str] = {}
        for image, *_ in events:
            if image is None or image in targets:
                continue
            if images[image].file_size > MAX_IMAGE_BYTES:
                raise ValueError("单张 PPT 图片超过大小限制")
            with archive.open(images[image]) as handle:
                extension = _image_extension(handle.read(12))
            targets[image] = f"slide_{len(targets) + 1:03d}{extension}"

        mapping: list[dict] = []
        for index, (image, milliseconds, origin, source_index, source_filename, diagnostics) in enumerate(events, 1):
            filename = targets.get(image)
            row = {
                "index": index,
                "source_index": source_index,
                "source_filename": source_filename,
                "occurrence_id": f"occ-{index:04d}",
                "filename": filename,
                "path": str(destination / filename) if filename else None,
                "timestamp": _format_timestamp(milliseconds),
                "seconds": milliseconds / 1000 if milliseconds is not None else None,
                "start_ms": milliseconds,
                "end_ms": None,
                "timestamp_kind": origin if milliseconds is not None else "unknown",
                "origin": origin,
                "status": "ok" if filename else "missing_image",
            }
            row.update(diagnostics)
            mapping.append(row)

        destination.mkdir(parents=True, exist_ok=False)
        created: list[Path] = []
        try:
            for image, filename in targets.items():
                with archive.open(images[image]) as handle:
                    data = handle.read(MAX_IMAGE_BYTES + 1)
                if len(data) > MAX_IMAGE_BYTES or len(data) != images[image].file_size:
                    raise ValueError("图片实际解压大小异常")
                target = destination / filename
                with target.open("xb") as output:
                    created.append(target)
                    output.write(data)
            metadata_path = destination / "slides_meta.json"
            with metadata_path.open("x", encoding="utf-8") as output:
                created.append(metadata_path)
                json.dump(mapping, output, ensure_ascii=False, indent=2, allow_nan=False)
        except BaseException:
            for path in reversed(created):
                try:
                    path.unlink()
                except OSError:
                    pass
            try:
                destination.rmdir()
            except OSError:
                pass
            raise
    return mapping
