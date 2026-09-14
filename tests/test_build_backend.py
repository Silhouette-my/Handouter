"""Regression tests for the stdlib-only PEP 517 backend."""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import handouter_build


class BuildBackendTests(unittest.TestCase):
    def test_normal_wheel_contains_package_and_console_script(self):
        with tempfile.TemporaryDirectory() as td:
            filename = handouter_build.build_wheel(td)
            wheel = Path(td) / filename
            self.assertTrue(wheel.is_file())
            with zipfile.ZipFile(wheel) as archive:
                names = set(archive.namelist())
                self.assertIn("handouter/cli.py", names)
                entry = archive.read("handouter-0.2.0.dist-info/entry_points.txt").decode()
                self.assertIn("handouter = handouter.cli:main", entry)
                self.assertIn("handouter-0.2.0.dist-info/RECORD", names)

    def test_editable_wheel_uses_project_src_path(self):
        with tempfile.TemporaryDirectory() as td:
            filename = handouter_build.build_editable(td)
            with zipfile.ZipFile(Path(td) / filename) as archive:
                pth = archive.read("handouter-editable.pth").decode().strip()
            self.assertEqual(Path(pth), (ROOT / "src").resolve())


if __name__ == "__main__":
    unittest.main()
