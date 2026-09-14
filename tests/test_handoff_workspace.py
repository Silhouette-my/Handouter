"""M1 tests: existing transcript/PPT -> isolated workspace -> Agent handoff."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from handouter import cli
from handouter.service import prepare_lecture
from handouter.validation import validate_note_output, validate_workspace


class HandoffWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspaces = self.root / "workspace"
        self.transcript = self.root / "lecture.txt"
        self.transcript.write_text("第一段课程内容。\n第二段不是结论，只是一个限定条件。\n", encoding="utf-8")
        self.skill = ROOT / ".agents" / "skills" / "zhiyun-lecture-notes" / "SKILL.md"

    def make_slides(self, records=None, images=("slide_001.png",)) -> Path:
        directory = self.root / f"slides-{len(list(self.root.glob('slides-*')))}"
        directory.mkdir()
        for name in images:
            (directory / name).write_bytes(b"synthetic-image")
        if records is not None:
            (directory / "slides_meta.json").write_text(
                json.dumps(records, ensure_ascii=False), encoding="utf-8"
            )
        return directory

    def prepare(self, lecture_id="course-a-001", title="课程 A", **kwargs):
        return prepare_lecture(
            self.workspaces,
            lecture_id=lecture_id,
            course_title=title,
            transcript=self.transcript,
            skill_path=self.skill,
            **kwargs,
        )

    def test_transcript_only_creates_valid_handoff_without_fake_timestamps(self):
        result = self.prepare(mode="full")
        workspace = result.workspace
        self.assertTrue((workspace / "handoff" / "PROMPT.md").is_file())
        self.assertFalse((workspace / "notes" / "full-001.md").exists())
        manifest = json.loads((workspace / "manifest.json").read_text())
        self.assertEqual(manifest["transcript"]["timestamp_kind"], "unavailable")
        self.assertEqual(manifest["slides"]["event_count"], 0)
        prompt = (workspace / "handoff" / "PROMPT.md").read_text()
        self.assertIn("不按字数均摊时间", prompt)
        self.assertNotIn("{{", prompt)
        self.assertTrue(validate_workspace(workspace).ok)

    def test_slides_are_copied_and_can_be_reference_without_embedding(self):
        slides = self.make_slides(None)
        legacy_meta = self.root / "legacy_slides_meta.json"
        legacy_meta.write_text(
            json.dumps([{"filename": "slide_001.png", "seconds": 5, "index": 9}]),
            encoding="utf-8",
        )
        result = self.prepare(slides_dir=slides, slides_meta=legacy_meta, mode="deep")
        sources = json.loads((result.workspace / "handoff" / "sources.json").read_text())
        index = json.loads((result.workspace / "slides" / "index.json").read_text())
        self.assertTrue(sources["options"]["use_slides_as_source"])
        self.assertFalse(sources["options"]["embed_slides"])
        self.assertEqual(index[0]["start_ms"], 5000)
        self.assertTrue((result.workspace / index[0]["image_path"]).is_file())

    def test_embedding_implies_slide_source(self):
        slides = self.make_slides(None)
        result = self.prepare(slides_dir=slides, embed_slides=True)
        sources = json.loads((result.workspace / "handoff" / "sources.json").read_text())
        self.assertTrue(sources["options"]["use_slides_as_source"])
        self.assertTrue(sources["options"]["embed_slides"])

    def test_slides_can_be_present_but_ignored_by_agent(self):
        slides = self.make_slides(None)
        result = self.prepare(slides_dir=slides, use_slides_as_source=False)
        sources = json.loads((result.workspace / "handoff" / "sources.json").read_text())
        self.assertFalse(sources["options"]["use_slides_as_source"])
        self.assertEqual(sources["slides"]["image_count"], 1)
        self.assertIn("不要读取或依赖 PPT", (result.workspace / "handoff" / "PROMPT.md").read_text())

    def test_source_transcript_is_never_modified(self):
        before = hashlib.sha256(self.transcript.read_bytes()).hexdigest()
        self.prepare()
        after = hashlib.sha256(self.transcript.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_existing_lecture_workspace_is_not_overwritten(self):
        first = self.prepare()
        sentinel = first.workspace / "notes" / "user.md"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(sentinel.read_text(), "keep")

    def test_two_courses_are_isolated(self):
        a = self.prepare(lecture_id="a-001", title="课程 Alpha", mode="summary")
        self.transcript.write_text("完全不同的 B 课程内容。", encoding="utf-8")
        b = self.prepare(lecture_id="b-001", title="课程 Beta", mode="deep")
        a_prompt = (a.workspace / "handoff" / "PROMPT.md").read_text()
        b_prompt = (b.workspace / "handoff" / "PROMPT.md").read_text()
        self.assertIn("课程 Alpha", a_prompt)
        self.assertNotIn("课程 Beta", a_prompt)
        self.assertIn("课程 Beta", b_prompt)
        self.assertNotIn("课程 Alpha", b_prompt)
        self.assertIn("第一段课程内容", (a.workspace / "transcript" / "transcript.txt").read_text())
        self.assertIn("完全不同的 B", (b.workspace / "transcript" / "transcript.txt").read_text())

    def test_conflicting_slide_time_aborts_without_partial_workspace(self):
        slides = self.make_slides([
            {"filename": "slide_001.png", "seconds": 5, "timestamp": "00:00:06"}
        ])
        with self.assertRaises(ValueError):
            self.prepare(lecture_id="bad-time", slides_dir=slides)
        self.assertFalse((self.workspaces / "bad-time").exists())
        self.assertFalse(any(self.workspaces.glob(".bad-time.tmp-*")))

    def test_requesting_slides_without_images_fails_cleanly(self):
        with self.assertRaises(ValueError):
            self.prepare(lecture_id="need-slides", use_slides_as_source=True)
        self.assertFalse((self.workspaces / "need-slides").exists())

    def test_signed_urls_and_cookie_fields_are_not_propagated(self):
        secret = "SECRET_AUTH_KEY_123"
        slides = self.make_slides([{
            "filename": "slide_001.png",
            "seconds": 2,
            "url": f"https://example.invalid/x?auth_key={secret}",
            "cookie": secret,
        }])
        result = self.prepare(slides_dir=slides)
        for relative in ("manifest.json", "slides/index.json", "handoff/sources.json", "handoff/PROMPT.md"):
            self.assertNotIn(secret, (result.workspace / relative).read_text())

    def test_revisited_slide_counts_one_image_and_multiple_events(self):
        slides = self.make_slides([
            {"filename": "slide_001.png", "seconds": 1},
            {"filename": "slide_001.png", "seconds": 20},
        ])
        result = self.prepare(slides_dir=slides)
        manifest = json.loads((result.workspace / "manifest.json").read_text())
        self.assertEqual(manifest["slides"]["event_count"], 2)
        self.assertEqual(manifest["slides"]["image_count"], 1)
        self.assertTrue(validate_workspace(result.workspace).ok)

    def test_validation_detects_material_tampering(self):
        result = self.prepare()
        copied = result.workspace / "transcript" / "transcript.txt"
        copied.write_text("tampered", encoding="utf-8")
        report = validate_workspace(result.workspace)
        self.assertFalse(report.ok)
        self.assertTrue(any("哈希" in error for error in report.errors))

    def test_note_validation_accepts_expected_markdown_and_updates_state_without_semantic_claim(self):
        result = self.prepare(mode="summary")
        note = result.workspace / "notes" / "summary-001.md"
        note.write_text("# 摘要\n\n这里是 Agent 输出。\n", encoding="utf-8")
        report = validate_note_output(result.workspace, update_state=True)
        self.assertTrue(report.ok)
        state = json.loads((result.workspace / "state.json").read_text())
        self.assertEqual(state["agent_output"]["status"], "validated")
        self.assertEqual(state["agent_output"]["semantic_review"], "required")

    def test_note_validation_rejects_slide_embed_when_disabled_and_credential_leak(self):
        slides = self.make_slides(None)
        result = self.prepare(slides_dir=slides, embed_slides=False)
        note = result.workspace / "notes" / "deep-001.md"
        note.write_text(
            "# bad\n\n![slide](../slides/images/slide_001.png)\n\nauth_key=SECRET\n",
            encoding="utf-8",
        )
        report = validate_note_output(result.workspace)
        self.assertFalse(report.ok)
        self.assertTrue(any("禁止嵌入" in error for error in report.errors))
        self.assertTrue(any("凭证" in error for error in report.errors))

    def test_cli_prepare_reports_handoff_not_agent_completion(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main([
                "prepare",
                "--lecture-id", "cli-001",
                "--course-title", "CLI 课程",
                "--transcript", str(self.transcript),
                "--workspace-root", str(self.workspaces),
                "--mode", "summary",
                "--skill-path", str(self.skill),
            ])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "handoff_ready")
        self.assertFalse(payload["agent_was_run"])
        self.assertFalse(Path(payload["expected_agent_output"]).exists())


if __name__ == "__main__":
    unittest.main()
