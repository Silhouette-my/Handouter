"""Offline smoke tests for the retained prototype, not an end-to-end product test.

Run from the project root:
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v

These tests never download a model, contact a server, upload audio, or execute
lecture-specific builders. All subprocess calls in audio tests are mocked.
"""

import ast
import contextlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import download_slides
import pipeline
import zhiyun_to_feishu


class SyntaxSmokeTests(unittest.TestCase):
    def test_all_legacy_python_files_parse(self):
        files = sorted(ROOT.glob("*.py"))
        files += sorted(
            (ROOT / ".agents/skills/zhiyun-lecture-notes/scripts").glob("*.py")
        )
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=path.relative_to(ROOT)):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_structured_example_imports_path(self):
        tree = ast.parse((ROOT / "generate_structured_notes.py").read_text(encoding="utf-8"))
        self.assertTrue(any(
            isinstance(node, ast.ImportFrom)
            and node.module == "pathlib"
            and any(alias.name == "Path" for alias in node.names)
            for node in tree.body
        ))


class TimeConversionTests(unittest.TestCase):
    def test_hours_minutes_seconds(self):
        self.assertEqual(download_slides.time_str_to_seconds("01:02:03"), 3723)

    def test_minutes_seconds(self):
        self.assertEqual(download_slides.time_str_to_seconds(" 02:05 "), 125)

    def test_midnight(self):
        self.assertEqual(download_slides.time_str_to_seconds("00:00:00"), 0)


class SlideStrippingTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = pipeline.ZhiyunPipeline(str(ROOT))

    def test_removes_legacy_slide_image(self):
        text = "正文\n\n![Slide 001](slides/slide_001.jpg)\n\n结尾"
        result = self.pipeline.strip_slides(text)
        self.assertNotIn("![Slide", result)
        self.assertIn("正文", result)
        self.assertIn("结尾", result)

    def test_removes_legacy_slide_caption(self):
        text = (
            "> ⏱️ **讲授时段**: `00:00:01` ~ `00:00:10`\n"
            "> 🏷️ **幻灯片**: `Slide 001` — 标题\n\n正文"
        )
        self.assertEqual(self.pipeline.strip_slides(text), "正文")

    def test_retains_non_slide_images_and_math(self):
        text = "![实验示意图](diagram.png)\n\n公式 $x^2$，不是所有情况都成立。"
        self.assertEqual(self.pipeline.strip_slides(text), text)

    def test_stripping_is_idempotent(self):
        text = "A\n\n![Slide 002](slides/slide_002.jpg)\n\n\nB"
        once = self.pipeline.strip_slides(text)
        self.assertEqual(self.pipeline.strip_slides(once), once)


class AudioImportAndCommandTests(unittest.TestCase):
    def test_playwright_is_not_a_module_level_dependency(self):
        self.assertNotIn("sync_playwright", vars(zhiyun_to_feishu))

    def _extract_with_results(self, returncodes):
        # No real output path is opened: ffmpeg and the output size probe are mocked.
        with patch.object(
            zhiyun_to_feishu.subprocess, "run",
            side_effect=[SimpleNamespace(returncode=code) for code in returncodes],
        ) as run, patch.object(
            zhiyun_to_feishu.os.path, "getsize", return_value=1024,
        ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            zhiyun_to_feishu.extract_audio(
                "https://example.invalid/lecture.mp4", "never-created.m4a"
            )
            return run.call_args_list

    def test_stream_copy_uses_no_cloud_upload(self):
        with patch.object(zhiyun_to_feishu, "upload_to_feishu") as upload:
            calls = self._extract_with_results([0])
        self.assertEqual(len(calls), 1)
        self.assertIn("copy", calls[0].args[0])
        upload.assert_not_called()

    def test_failed_copy_falls_back_to_aac(self):
        calls = self._extract_with_results([1, 0])
        self.assertEqual(len(calls), 2)
        self.assertIn("aac", calls[1].args[0])

    def test_both_ffmpeg_attempts_failing_exit_nonzero(self):
        with self.assertRaises(SystemExit) as caught:
            self._extract_with_results([1, 1])
        self.assertEqual(caught.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
