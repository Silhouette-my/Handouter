"""Tests for the package-level slide importer used by CLI/TUI services."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from handouter.importers import import_slides_zip, read_private_media_source
from handouter.service import BuildResult, build_from_asset_zip, prepare_lecture

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jG9kAAAAASUVORK5CYII="
)


class PackageImporterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "assets.zip"

    def make_exporter_zip(self):
        metadata = [{
            "index": 1,
            "filename": "slide_001.jpg",
            "timestamp": None,
            "seconds": None,
            "timeStatus": "unknown_numeric_unit",
            "sourceField": "time",
            "rawTimeValue": 11400,
            "status": "ok",
        }]
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("slides_meta.json", json.dumps(metadata))
            archive.writestr("slides/slide_001.jpg", PNG)
            archive.writestr("course_info.json", json.dumps({"courseName": "A"}))
            archive.writestr("private/source.json", json.dumps({"videoUrl": "https://example.invalid/x?auth_key=SECRET"}))

    def test_private_source_is_never_extracted_and_unknown_time_diagnostics_survive(self):
        self.make_exporter_zip()
        out = self.root / "slides"
        mapping = import_slides_zip(self.archive, out)
        self.assertEqual(mapping[0]["start_ms"], None)
        self.assertEqual(mapping[0]["time_status"], "unknown_numeric_unit")
        self.assertEqual(mapping[0]["raw_time_value"], 11400)
        self.assertFalse((out / "private").exists())
        text = (out / "slides_meta.json").read_text()
        self.assertNotIn("SECRET", text)

    def test_private_media_source_is_read_only_in_memory(self):
        self.make_exporter_zip()
        url = read_private_media_source(self.archive)
        self.assertIn("auth_key=SECRET", url)

    def test_build_asset_passes_private_url_to_media_pipeline_without_expanding_it(self):
        self.make_exporter_zip()
        sentinel = object()
        with patch("handouter.service.build_from_media", return_value=sentinel) as build:
            result = build_from_asset_zip(
                self.root / "workspace",
                lecture_id="a-01",
                course_title="A",
                asset_zip=self.archive,
            )
        self.assertIs(result, sentinel)
        kwargs = build.call_args.kwargs
        self.assertIn("auth_key=SECRET", kwargs["media_source"])
        self.assertEqual(Path(kwargs["slides_zip"]), self.archive)
        self.assertEqual(kwargs["source_type"], "zhiyun_asset_zip")

    def test_prepare_can_consume_exporter_zip_directly(self):
        self.make_exporter_zip()
        transcript = self.root / "lecture.txt"
        transcript.write_text("课程内容", encoding="utf-8")
        skill = self.root / "SKILL.md"
        skill.write_text("skill", encoding="utf-8")
        result = prepare_lecture(
            self.root / "workspace",
            lecture_id="a-01",
            course_title="A",
            transcript=transcript,
            slides_zip=self.archive,
            skill_path=skill,
        )
        self.assertEqual(result.materials.slide_image_count, 1)
        self.assertEqual(result.materials.slide_unknown_time_count, 1)
        self.assertFalse(any(path.name.startswith(".a-01.slides-") for path in (self.root / "workspace").iterdir()))
        prompt = (result.workspace / "handoff" / "PROMPT.md").read_text()
        self.assertNotIn("SECRET", prompt)


if __name__ == "__main__":
    unittest.main()
