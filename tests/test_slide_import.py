"""Synthetic ZIP regressions; never read or overwrite real lecture assets."""

import base64
import contextlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import download_slides
import handouter.importers as slide_importers

# Tiny PNG fixture, including a valid PNG header; no model or image library needed.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jG9kAAAAASUVORK5CYII="
)


class SlideZipImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "lecture.zip"
        self.output = self.root / "imported"

    def make_zip(self, metadata, images=None, prefix="", extra=None):
        if images is None:
            images = {"slides/slide_001.jpg": PNG}
        with zipfile.ZipFile(self.archive, "w") as archive:
            if metadata is not None:
                archive.writestr(prefix + "slides_meta.json", json.dumps(metadata))
            for name, data in images.items():
                archive.writestr(prefix + name, data)
            for name, data in (extra or {}).items():
                archive.writestr(name, data)

    def run_import(self):
        with contextlib.redirect_stdout(io.StringIO()), patch.object(download_slides, "SLIDES_DIR", self.output):
            result = download_slides.extract_from_zip(self.archive)
        if result is None:  # Also exercise the old implementation to reproduce regressions.
            return json.loads((self.output / "slides_meta.json").read_text())
        return result

    def test_exporter_metadata_preserves_nonzero_time(self):
        self.make_zip([{"filename": "slide_001.jpg", "timestamp": "00:02:05", "seconds": 125}])
        mapping = self.run_import()
        self.assertEqual(mapping[0]["seconds"], 125)
        self.assertEqual(mapping[0]["start_ms"], 125000)
        self.assertEqual(mapping[0]["timestamp_kind"], "metadata")
        self.assertIsNone(mapping[0]["end_ms"])

    def test_unknown_time_is_not_zero(self):
        self.make_zip([{"filename": "slide_001.jpg"}])
        item = self.run_import()[0]
        self.assertIsNone(item["start_ms"])
        self.assertIsNone(item["seconds"])
        self.assertIsNone(item["timestamp"])

    def test_real_zero_is_preserved(self):
        self.make_zip([{"filename": "slide_001.jpg", "seconds": 0}])
        self.assertEqual(self.run_import()[0]["start_ms"], 0)

    def test_fractional_seconds_preserve_milliseconds(self):
        self.make_zip([{"filename": "slide_001.jpg", "timestamp": "01:02:03.125", "seconds": 3723.125}])
        self.assertEqual(self.run_import()[0]["start_ms"], 3723125)

    def test_long_seconds_are_not_guessed_as_milliseconds(self):
        self.make_zip([{"filename": "slide_001.jpg", "seconds": 11400}])
        self.assertEqual(self.run_import()[0]["start_ms"], 11400000)

    def test_time_aliases(self):
        for key in ("time", "switchTime"):
            with self.subTest(key=key):
                self.output = self.root / key
                self.make_zip([{"filename": "slide_001.jpg", key: "02:05"}])
                self.assertEqual(self.run_import()[0]["start_ms"], 125000)

    def test_conflicting_time_fields_are_rejected(self):
        self.make_zip([{"filename": "slide_001.jpg", "timestamp": "00:02:05", "seconds": 1}])
        with self.assertRaises(ValueError):
            self.run_import()
        self.assertFalse(self.output.exists())

    def test_invalid_time_is_not_silently_zeroed(self):
        for bad in ("nonsense", "00:61:00", "-01:00", "00:00:60"):
            with self.subTest(bad=bad):
                self.make_zip([{"filename": "slide_001.jpg", "timestamp": bad}])
                with self.assertRaises(ValueError):
                    self.run_import()
        self.assertFalse(self.output.exists())

    def test_nonfinite_negative_or_boolean_seconds_are_rejected(self):
        for bad in (-1, float("nan"), float("inf"), True):
            with self.subTest(bad=bad):
                self.make_zip([{"filename": "slide_001.jpg", "seconds": bad}])
                with self.assertRaises(ValueError):
                    self.run_import()
        self.assertFalse(self.output.exists())

    def test_missing_image_remains_an_explicit_event(self):
        self.make_zip([
            {"filename": "slide_001.jpg", "seconds": 10},
            {"filename": "slide_002.jpg", "seconds": 30},
        ])
        mapping = self.run_import()
        self.assertEqual(len(mapping), 2)
        self.assertEqual(mapping[1]["status"], "missing_image")
        self.assertEqual(mapping[1]["source_filename"], "slide_002.jpg")
        self.assertEqual(mapping[1]["start_ms"], 30000)
        self.assertIsNone(mapping[1]["path"])

    def test_revisited_slide_retains_both_events(self):
        self.make_zip([
            {"filename": "slide_001.jpg", "seconds": 10},
            {"filename": "slide_001.jpg", "seconds": 100},
        ])
        mapping = self.run_import()
        self.assertEqual([item["start_ms"] for item in mapping], [10000, 100000])
        self.assertEqual(mapping[0]["filename"], mapping[1]["filename"])
        self.assertNotEqual(mapping[0]["occurrence_id"], mapping[1]["occurrence_id"])

    def test_parent_folder_export_is_supported(self):
        self.make_zip([{"filename": "slide_001.jpg", "seconds": 10}], prefix="lecture/")
        self.assertEqual(self.run_import()[0]["start_ms"], 10000)

    def test_legacy_filename_timestamp(self):
        self.make_zip(None, {"slide__00-02-05.jpeg": PNG})
        item = self.run_import()[0]
        self.assertEqual(item["start_ms"], 125000)
        self.assertEqual(item["timestamp_kind"], "filename")

    def test_metadata_time_wins_over_legacy_filename(self):
        self.make_zip(
            [{"filename": "slide__00-00-01.jpg", "seconds": 125}],
            {"slides/slide__00-00-01.jpg": PNG},
        )
        self.assertEqual(self.run_import()[0]["start_ms"], 125000)

    def test_actual_signature_determines_output_extension(self):
        self.make_zip([{"filename": "slide_001.jpg", "seconds": 1}])
        item = self.run_import()[0]
        self.assertTrue(item["filename"].endswith(".png"))
        self.assertEqual((self.output / item["filename"]).read_bytes(), PNG)

    def test_html_disguised_as_an_image_is_rejected(self):
        self.make_zip(None, {"slide.jpg": b"<html>please log in</html>"})
        with self.assertRaises(ValueError):
            self.run_import()
        self.assertFalse(self.output.exists())

    def test_private_urls_are_not_copied_to_mapping(self):
        self.make_zip([{
            "filename": "slide_001.jpg", "seconds": 10,
            "url": "https://example.invalid/image?auth_key=SECRET", "cookie": "SECRET",
        }], extra={"course_info.json": '{"videoUrl":"SECRET"}'})
        self.run_import()
        text = (self.output / "slides_meta.json").read_text()
        self.assertNotIn("SECRET", text)
        self.assertFalse((self.output / "course_info.json").exists())

    def test_existing_output_is_never_overwritten(self):
        self.make_zip(None)
        self.output.mkdir()
        sentinel = self.output / "user.txt"
        sentinel.write_text("keep")
        with self.assertRaises(FileExistsError):
            self.run_import()
        self.assertEqual(sentinel.read_text(), "keep")

    def test_existing_empty_output_is_also_rejected(self):
        self.make_zip(None)
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.run_import()

    def test_path_traversal_and_windows_paths_are_rejected(self):
        for path in ("../outside.png", "/absolute.png", "C:/drive.png", "slides\\bad.png"):
            with self.subTest(path=path):
                self.make_zip(None, {path: PNG})
                with self.assertRaises(ValueError):
                    self.run_import()
        self.assertFalse(self.output.exists())
        self.assertFalse((self.root / "outside.png").exists())

    def test_unsafe_metadata_filename_is_rejected(self):
        self.make_zip([{"filename": "../slide_001.jpg", "seconds": 1}])
        with self.assertRaises(ValueError):
            self.run_import()

    def test_symlink_archive_member_is_rejected(self):
        with zipfile.ZipFile(self.archive, "w") as archive:
            link = zipfile.ZipInfo("slide.png")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "../outside")
        with self.assertRaises(ValueError):
            self.run_import()

    def test_duplicate_casefolded_member_is_rejected(self):
        self.make_zip(None, {"slide.jpg": PNG, "SLIDE.JPG": PNG})
        with self.assertRaises(ValueError):
            self.run_import()

    def test_total_size_limit_is_checked_before_output(self):
        self.make_zip(None)
        with patch.object(slide_importers, "MAX_ZIP_BYTES", 10):
            with self.assertRaises(ValueError):
                self.run_import()
        self.assertFalse(self.output.exists())

    def test_image_size_limit_is_checked(self):
        self.make_zip(None)
        with patch.object(slide_importers, "MAX_IMAGE_BYTES", 10):
            with self.assertRaises(ValueError):
                self.run_import()
        self.assertFalse(self.output.exists())

    def test_bad_metadata_does_not_fall_back_to_filename_guess(self):
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("slides_meta.json", "not valid JSON")
            archive.writestr("slides/slide_001.jpg", PNG)
        with self.assertRaises(ValueError):
            self.run_import()
        self.assertFalse(self.output.exists())

    def test_unknown_images_without_metadata_are_retained(self):
        self.make_zip(None, {"plain.jpg": PNG})
        item = self.run_import()[0]
        self.assertIsNone(item["start_ms"])
        self.assertEqual(item["status"], "ok")

    def test_unreferenced_image_is_not_silently_dropped(self):
        self.make_zip(
            [{"filename": "slide_001.jpg", "seconds": 10}],
            {"slides/slide_001.jpg": PNG, "slides/extra.jpg": PNG},
        )
        mapping = self.run_import()
        self.assertEqual(len(mapping), 2)
        self.assertEqual(mapping[1]["origin"], "unreferenced_image")
        self.assertIsNone(mapping[1]["start_ms"])

    def test_import_does_not_change_source_archive(self):
        self.make_zip(None)
        before = self.archive.read_bytes()
        self.run_import()
        self.assertEqual(self.archive.read_bytes(), before)

    def test_manifest_write_failure_removes_only_new_output(self):
        self.make_zip(None)
        unrelated = self.root / "keep.txt"
        unrelated.write_text("keep")
        with patch.object(slide_importers.json, "dump", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                self.run_import()
        self.assertFalse(self.output.exists())
        self.assertEqual(unrelated.read_text(), "keep")

    def test_archive_member_count_is_bounded(self):
        self.make_zip(None, {"first.png": PNG, "second.png": PNG})
        with patch.object(slide_importers, "MAX_ZIP_MEMBERS", 1):
            with self.assertRaises(ValueError):
                self.run_import()
        self.assertFalse(self.output.exists())

    def test_multiple_metadata_files_are_rejected(self):
        self.make_zip([], extra={"another/slides_meta.json": "[]"})
        with self.assertRaises(ValueError):
            self.run_import()
        self.assertFalse(self.output.exists())

    def test_ambiguous_image_reference_is_rejected(self):
        self.make_zip(
            [{"filename": "slide_001.jpg", "seconds": 1}],
            {"slide_001.jpg": PNG, "slides/slide_001.jpg": PNG},
        )
        with self.assertRaises(ValueError):
            self.run_import()
        self.assertFalse(self.output.exists())

    def test_zip_cli_accepts_separate_output_directory(self):
        self.make_zip([{"filename": "slide_001.jpg", "seconds": 125}])
        result = subprocess.run(
            [sys.executable, str(ROOT / "download_slides.py"), "-z", str(self.archive),
             "--output-dir", str(self.output)],
            capture_output=True, text=True, cwd=self.root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        mapping = json.loads((self.output / "slides_meta.json").read_text())
        self.assertEqual(mapping[0]["start_ms"], 125000)

    def test_missing_explicit_zip_cli_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "download_slides.py"), "-z", str(self.root / "missing.zip")],
            capture_output=True, text=True, cwd=self.root,
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
