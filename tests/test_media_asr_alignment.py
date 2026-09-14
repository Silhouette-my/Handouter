"""Regression tests for the production media/ASR/time-alignment path."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from handouter.alignment import align_segments_to_slides
from handouter.asr import ASRResult, normalize_funasr_result
from handouter.doctor import run_doctor
from handouter.media import MediaError, extract_audio, probe_duration_ms
from handouter.service import build_from_audio, prepare_lecture
import handouter.tui as tui_module
from handouter.tui import build_cli_args
from handouter.validation import validate_workspace


class ASRNormalizationTests(unittest.TestCase):
    def test_sentence_info_becomes_timed_segments(self):
        raw = [{
            "text": "完整文本",
            "sentence_info": [
                {"text": "第一句", "start": 100, "end": 900},
                {"sentence": "第二句", "start": 900, "end": 1800, "spk": 0},
            ],
        }]
        segments, text, kind = normalize_funasr_result(raw)
        self.assertEqual(kind, "sentence_or_vad")
        self.assertEqual([s["start_ms"] for s in segments], [100, 900])
        self.assertEqual(text, "第一句\n第二句")
        self.assertEqual(segments[1]["speaker"], 0)

    def test_missing_timestamps_remain_unknown(self):
        segments, text, kind = normalize_funasr_result([{"text": "不能编造时间"}])
        self.assertEqual(kind, "unavailable")
        self.assertEqual(segments[0]["start_ms"], None)
        self.assertEqual(text, "不能编造时间")

    def test_punctuation_only_vad_noise_is_filtered_but_raw_result_can_still_be_saved(self):
        raw = [{"text": "。有效内容", "sentence_info": [
            {"text": "。", "start": 0, "end": 100},
            {"text": "有效内容", "start": 100, "end": 500},
        ]}]
        segments, text, kind = normalize_funasr_result(raw)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["text"], "有效内容")
        self.assertEqual(text, "有效内容")
        self.assertEqual(kind, "sentence_or_vad")

    def test_invalid_empty_result_is_rejected(self):
        with self.assertRaises(RuntimeError):
            normalize_funasr_result([])


class AlignmentTests(unittest.TestCase):
    def test_cross_page_segment_can_reference_two_events(self):
        segments = [{"id": "seg-1", "start_ms": 900, "end_ms": 1100}]
        events = [
            {"occurrence_id": "occ-1", "start_ms": 0, "end_ms": None, "image_path": "a.png"},
            {"occurrence_id": "occ-2", "start_ms": 1000, "end_ms": None, "image_path": "b.png"},
        ]
        result = align_segments_to_slides(segments, events)
        self.assertEqual([x["occurrence_id"] for x in result[0]["slide_occurrences"]], ["occ-1", "occ-2"])

    def test_unknown_segment_time_is_not_aligned(self):
        result = align_segments_to_slides(
            [{"id": "seg-1", "start_ms": None, "end_ms": None}],
            [{"occurrence_id": "occ-1", "start_ms": 0, "end_ms": None}],
        )
        self.assertEqual(result[0]["alignment_kind"], "unavailable")
        self.assertEqual(result[0]["slide_occurrences"], [])


class StructuredWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skill = self.root / "SKILL.md"
        self.skill.write_text("---\nname: test\n---\n", encoding="utf-8")

    def test_segments_raw_and_alignment_are_preserved_and_validated(self):
        transcript = self.root / "lecture.txt"
        transcript.write_text("第一句。\n第二句。", encoding="utf-8")
        segments = self.root / "segments.json"
        segments.write_text(json.dumps([
            {"id": "seg-0001", "start_ms": 0, "end_ms": 900, "text": "第一句。", "timestamp_kind": "sentence_or_vad", "speaker": None},
            {"id": "seg-0002", "start_ms": 900, "end_ms": 1800, "text": "第二句。", "timestamp_kind": "sentence_or_vad", "speaker": None},
        ]), encoding="utf-8")
        raw = self.root / "raw.json"
        raw.write_text(json.dumps({"backend": "test", "result": []}), encoding="utf-8")
        slides = self.root / "slides"
        slides.mkdir()
        # Header validity is irrelevant here: workspace copies already-normalized local material.
        (slides / "slide_001.png").write_bytes(b"png-data")
        (slides / "slides_meta.json").write_text(json.dumps([
            {"filename": "slide_001.png", "start_ms": 500},
        ]), encoding="utf-8")

        result = prepare_lecture(
            self.root / "workspace",
            lecture_id="course-a-01",
            course_title="课程 A",
            transcript=transcript,
            segments=segments,
            raw_asr=raw,
            slides_dir=slides,
            mode="deep",
            skill_path=self.skill,
        )
        manifest = json.loads((result.workspace / "manifest.json").read_text())
        sources = json.loads((result.workspace / "handoff" / "sources.json").read_text())
        self.assertEqual(manifest["transcript"]["timestamp_kind"], "sentence_or_vad")
        self.assertEqual(manifest["transcript"]["segment_count"], 2)
        self.assertEqual(manifest["slides"]["alignment_path"], "slides/alignment.json")
        self.assertEqual(sources["transcript"]["segments_path"], "transcript/segments.json")
        self.assertTrue(validate_workspace(result.workspace).ok)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
class MediaIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_local_video_extracts_verified_audio_without_overwrite(self):
        video = self.root / "sample.mp4"
        subprocess.run([
            shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-shortest", "-c:v", "libx264", "-c:a", "aac", str(video),
        ], check=True)
        output = self.root / "audio.m4a"
        result = extract_audio(video, output)
        self.assertTrue(output.is_file())
        self.assertGreater(result.duration_ms, 500)
        self.assertGreater(probe_duration_ms(output), 500)
        before = output.read_bytes()
        with self.assertRaises(FileExistsError):
            extract_audio(video, output)
        self.assertEqual(output.read_bytes(), before)

    def test_decode_verification_failure_falls_back_to_aac(self):
        video = self.root / "fallback.mp4"
        subprocess.run([
            shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
            "-f", "lavfi", "-i", "sine=frequency=660:duration=1",
            "-shortest", "-c:v", "libx264", "-c:a", "aac", str(video),
        ], check=True)
        output = self.root / "fallback.m4a"
        with patch("handouter.media.verify_audio_decodable", side_effect=[MediaError("bad copy"), None]) as verify:
            result = extract_audio(video, output)
        self.assertEqual(result.mode, "aac")
        self.assertEqual(verify.call_count, 2)
        self.assertTrue(output.is_file())


class ServiceBuildTests(unittest.TestCase):
    def test_build_from_audio_persists_asr_evidence_before_scratch_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audio = root / "input.m4a"
            audio.write_bytes(b"fake audio")
            skill = root / "SKILL.md"
            skill.write_text("skill", encoding="utf-8")

            def fake_asr(_audio, output_dir, **kwargs):
                out = Path(output_dir)
                out.mkdir()
                (out / "raw.json").write_text("{}", encoding="utf-8")
                (out / "segments.json").write_text(json.dumps([
                    {"id": "seg-0001", "start_ms": 0, "end_ms": 1000, "text": "测试", "timestamp_kind": "sentence_or_vad", "speaker": None}
                ]), encoding="utf-8")
                (out / "transcript.txt").write_text("测试", encoding="utf-8")
                return ASRResult(out, out / "raw.json", out / "segments.json", out / "transcript.txt", 1, "sentence_or_vad", "cpu", 0.1)

            with patch("handouter.service.transcribe_sensevoice", side_effect=fake_asr):
                result = build_from_audio(
                    root / "workspace", lecture_id="a-01", course_title="A", audio=audio,
                    skill_path=skill, device="cpu",
                )
            self.assertTrue(result.asr.raw_path.is_file())
            self.assertTrue(result.asr.segments_path.is_file())
            self.assertTrue((result.prepare.workspace / "audio" / "source.m4a").is_file())
            manifest = json.loads((result.prepare.workspace / "manifest.json").read_text())
            self.assertEqual(manifest["source_type"], "local_audio_asr")
            self.assertTrue(validate_workspace(result.prepare.workspace).ok)


class TUICommandTests(unittest.TestCase):
    def test_asset_mode_uses_single_asset_zip_source(self):
        args = build_cli_args({
            "kind": "asset", "source": "/tmp/course.zip", "lecture": "a-01", "title": "A",
            "root": "workspace", "mode": "deep", "device": "mps", "use_slides": True,
            "embed_slides": False, "allow_web": False, "slides": "/ignored", "meta": "/ignored.json",
            "slides_zip": "/ignored.zip",
        })
        self.assertEqual(args[:2], ["build-asset", "/tmp/course.zip"])
        self.assertNotIn("--slides-dir", args)
        self.assertNotIn("--slides-zip", args)
        self.assertIn("--device", args)

    def test_transcript_mode_does_not_add_asr_device(self):
        args = build_cli_args({
            "kind": "transcript", "source": "lecture.txt", "lecture": "a-01", "title": "A",
            "root": "workspace", "mode": "full", "device": "mps", "use_slides": False,
            "embed_slides": False, "allow_web": False, "slides": None, "meta": None, "slides_zip": None,
        })
        self.assertEqual(args[:3], ["prepare", "--transcript", "lecture.txt"])
        self.assertNotIn("--device", args)
        self.assertIn("--ignore-slides", args)

    def test_run_tui_falls_back_to_curses_without_textual(self):
        with patch.object(tui_module, "App", None), patch.object(tui_module, "_run_curses") as fallback:
            tui_module.run_tui()
        fallback.assert_called_once_with()


class DoctorTests(unittest.TestCase):
    def test_doctor_has_separate_feature_readiness(self):
        report = run_doctor()
        for key in ("ok_core", "ok_media", "ok_asr", "ok_tui", "checks"):
            self.assertIn(key, report)
        self.assertTrue(report["ok_core"])


if __name__ == "__main__":
    unittest.main()
