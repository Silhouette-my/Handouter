"""Tiny stdlib-only PEP 517 backend for Handouter.

The package keeps build-time dependencies at zero. macOS/Linux core installs
remain offline-capable; Windows declares a conditional ``windows-curses``
runtime dependency for the ASCII TUI. The in-repo backend still avoids
downloading setuptools merely to build the wheel.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import tarfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "handouter"


def _project() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def _dist_name() -> str:
    return str(_project()["name"]).replace("-", "_")


def _version() -> str:
    return str(_project()["version"])


def _dist_info() -> str:
    return f"{_dist_name()}-{_version()}.dist-info"


def _metadata_text() -> str:
    project = _project()
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {project['name']}",
        f"Version: {project['version']}",
        f"Summary: {project.get('description', '')}",
        f"Requires-Python: {project.get('requires-python', '>=3.11')}",
    ]
    lines.extend(f"Requires-Dist: {dependency}" for dependency in project.get("dependencies", []))
    return "\n".join(lines) + "\n"


def _wheel_text() -> str:
    return "Wheel-Version: 1.0\nGenerator: handouter-build\nRoot-Is-Purelib: true\nTag: py3-none-any\n"


def _entry_points_text() -> str:
    return "[console_scripts]\nhandouter = handouter.cli:main\n"


def _record_row(name: str, data: bytes) -> list[str]:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
    return [name, f"sha256={digest}", str(len(data))]


def _build_wheel_file(wheel_directory: str, *, editable: bool) -> str:
    wheel_dir = Path(wheel_directory)
    wheel_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_dist_name()}-{_version()}-py3-none-any.whl"
    target = wheel_dir / filename
    dist_info = _dist_info()
    files: dict[str, bytes] = {
        f"{dist_info}/METADATA": _metadata_text().encode(),
        f"{dist_info}/WHEEL": _wheel_text().encode(),
        f"{dist_info}/entry_points.txt": _entry_points_text().encode(),
    }
    if editable:
        files["handouter-editable.pth"] = (str((ROOT / "src").resolve()) + os.linesep).encode()
    else:
        for path in sorted(SRC.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in {".py", ".json", ".md"}:
                files[(Path("handouter") / path.relative_to(SRC)).as_posix()] = path.read_bytes()
        exporter = ROOT / "zhiyun_exporter.user.js"
        if exporter.is_file():
            files["handouter/assets/zhiyun_exporter.user.js"] = exporter.read_bytes()
        skill_root = ROOT / ".agents" / "skills" / "zhiyun-lecture-notes"
        for source in sorted(skill_root.rglob("*.md")):
            if not source.is_file():
                continue
            relative = source.relative_to(skill_root)
            files[(Path("handouter/assets/zhiyun-lecture-notes") / relative).as_posix()] = source.read_bytes()

    rows = [_record_row(name, data) for name, data in sorted(files.items())]
    record_name = f"{dist_info}/RECORD"
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(rows)
    writer.writerow([record_name, "", ""])
    files[record_name] = output.getvalue().encode()

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    return filename


def build_wheel(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    return _build_wheel_file(wheel_directory, editable=False)


def build_editable(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    return _build_wheel_file(wheel_directory, editable=True)


def prepare_metadata_for_build_wheel(metadata_directory: str, config_settings=None) -> str:
    target = Path(metadata_directory) / _dist_info()
    target.mkdir(parents=True, exist_ok=True)
    (target / "METADATA").write_text(_metadata_text(), encoding="utf-8")
    (target / "WHEEL").write_text(_wheel_text(), encoding="utf-8")
    (target / "entry_points.txt").write_text(_entry_points_text(), encoding="utf-8")
    return target.name


def prepare_metadata_for_build_editable(metadata_directory: str, config_settings=None) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_sdist(sdist_directory: str, config_settings=None) -> str:
    directory = Path(sdist_directory)
    directory.mkdir(parents=True, exist_ok=True)
    base = f"{_dist_name()}-{_version()}"
    filename = f"{base}.tar.gz"
    target = directory / filename
    include = [
        "pyproject.toml",
        "handouter_build.py",
        "README.md",
        "zhiyun_exporter.user.js",
        ".agents/skills/zhiyun-lecture-notes/SKILL.md",
    ]
    include += [
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / ".agents" / "skills" / "zhiyun-lecture-notes" / "references").rglob("*.md"))
    ]
    include += [path.relative_to(ROOT).as_posix() for path in sorted(SRC.rglob("*.py"))]
    with tarfile.open(target, "w:gz") as archive:
        for relative in include:
            path = ROOT / relative
            archive.add(path, arcname=f"{base}/{relative}")
    return filename
