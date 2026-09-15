"""Agent adapters, GUI handoff bundle, and progressive Skill-plan tests."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from handouter import cli
from handouter.agents.base import AgentAvailability
from handouter.agents.manual import _publish_exclusive_file, create_manual_bundle
from handouter.agents.runner import run_cli_agent
from handouter.agents import claude, codex
from handouter.service import prepare_lecture
from handouter.skill_plan import plan_modules


class AgentInteractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        transcript = self.root / "lecture.txt"
        transcript.write_text("第一段。第二段不是无条件结论。", encoding="utf-8")
        raw = self.root / "raw.json"
        raw.write_text(json.dumps({"debug": "auth_key=SHOULD_NOT_BUNDLE"}), encoding="utf-8")
        audio = self.root / "source.m4a"
        audio.write_bytes(b"not-real-audio-but-regular-file")
        skill = ROOT / ".agents" / "skills" / "zhiyun-lecture-notes" / "SKILL.md"
        self.result = prepare_lecture(
            self.root / "output",
            lecture_id="agent-course-001",
            course_title="Agent 测试课程",
            transcript=transcript,
            raw_asr=raw,
            audio=audio,
            modes=("deep", "summary"),
            use_slides_as_source=False,
            format_profile="clean",
            skill_path=skill,
        )
        self.workspace = self.result.workspace

    def test_progressive_skill_plan_materializes_only_selected_modules(self):
        sources = json.loads((self.workspace / "handoff" / "sources.json").read_text(encoding="utf-8"))
        skill = sources["skill"]
        modules = skill["modules"]
        self.assertEqual(skill["entry"], "handoff/skill/SKILL.md")
        self.assertIn("handoff/skill/references/common/evidence.md", modules)
        self.assertIn("handoff/skill/references/modes/deep.md", modules)
        self.assertIn("handoff/skill/references/modes/summary.md", modules)
        self.assertIn("handoff/skill/references/formats/clean.md", modules)
        self.assertIn("handoff/skill/references/slides/ignore.md", modules)
        self.assertIn("handoff/skill/references/execution/multi-output.md", modules)
        self.assertNotIn("handoff/skill/references/modes/full.md", modules)
        self.assertNotIn("handoff/skill/references/formats/traceable.md", modules)
        for relative in [skill["entry"], *modules]:
            self.assertTrue((self.workspace / relative).is_file(), relative)

    def test_long_course_and_embed_modules_are_conditional(self):
        skill = ROOT / ".agents" / "skills" / "zhiyun-lecture-notes" / "SKILL.md"
        modules = plan_modules(
            skill,
            modes=("deep",),
            format_profile="traceable",
            use_slides_as_source=True,
            embed_slides=True,
            segment_count=100,
        )
        self.assertIn("references/formats/traceable.md", modules)
        self.assertIn("references/slides/embed.md", modules)
        self.assertIn("references/execution/long-course.md", modules)
        self.assertNotIn("references/execution/multi-output.md", modules)
        plain_long = plan_modules(
            skill,
            modes=("deep",),
            format_profile="clean",
            use_slides_as_source=False,
            embed_slides=False,
            segment_count=0,
            transcript_bytes=20_000,
        )
        self.assertIn("references/execution/long-course.md", plain_long)

    def test_custom_single_file_skill_remains_supported_without_modules(self):
        custom = self.root / "CUSTOM_SKILL.md"
        custom.write_text("# Custom skill\n\nOnly follow this file.\n", encoding="utf-8")
        modules = plan_modules(
            custom,
            modes=("deep",),
            format_profile="clean",
            use_slides_as_source=False,
            embed_slides=False,
        )
        self.assertEqual(modules, ())
        transcript = self.root / "custom.txt"
        transcript.write_text("custom course content", encoding="utf-8")
        result = prepare_lecture(
            self.root / "custom-output",
            lecture_id="custom-skill-course",
            course_title="Custom Skill Course",
            transcript=transcript,
            mode="deep",
            use_slides_as_source=False,
            skill_path=custom,
        )
        sources = json.loads((result.workspace / "handoff" / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(sources["skill"]["modules"], [])
        self.assertTrue((result.workspace / "handoff" / "skill" / "SKILL.md").is_file())

    def test_refresh_replaces_materialized_skill_modules(self):
        before = json.loads((self.workspace / "handoff" / "sources.json").read_text(encoding="utf-8"))
        self.assertIn("handoff/skill/references/modes/deep.md", before["skill"]["modules"])
        self.assertNotIn("handoff/skill/references/modes/full.md", before["skill"]["modules"])

        from handouter.service import refresh_handoff

        refreshed = refresh_handoff(
            self.workspace,
            modes=("full",),
            use_slides_as_source=False,
            format_profile="traceable",
        )
        self.assertTrue(refreshed.archived_prompt.is_file())
        after = json.loads((self.workspace / "handoff" / "sources.json").read_text(encoding="utf-8"))
        self.assertIn("handoff/skill/references/modes/full.md", after["skill"]["modules"])
        self.assertNotIn("handoff/skill/references/modes/deep.md", after["skill"]["modules"])
        self.assertIn("handoff/skill/references/formats/traceable.md", after["skill"]["modules"])
        self.assertFalse((self.workspace / "handoff" / "skill" / "references" / "modes" / "deep.md").exists())
        self.assertTrue(any((self.workspace / "handoff" / "history").glob("task-*-skill/references/modes/deep.md")))

    def test_manual_bundle_falls_back_when_hard_links_are_unavailable(self):
        from handouter.agents import manual

        output = self.workspace / "handoff" / "portable-fallback.zip"
        with patch("handouter.agents.manual.os.link", side_effect=OSError("hard links unavailable")):
            result = manual.create_manual_bundle(self.workspace, output=output)
        self.assertEqual(result.bundle, output.resolve())
        self.assertTrue(result.bundle.is_file())
        with zipfile.ZipFile(result.bundle, "r") as archive:
            self.assertIsNone(archive.testzip())

    def test_bundle_fallback_preserves_target_created_during_publication(self):
        output = self.workspace / "handoff" / "contended.zip"
        existing = b"another task owns this file"

        def unavailable_link(_source, target):
            Path(target).write_bytes(existing)
            raise OSError("hard links unavailable")

        with patch("handouter.agents.manual.os.link", side_effect=unavailable_link):
            with self.assertRaises(FileExistsError):
                create_manual_bundle(self.workspace, output=output)
        self.assertEqual(output.read_bytes(), existing)
        self.assertEqual(list(output.parent.glob(".contended.zip.tmp-*")), [])

    def test_bundle_fallback_removes_only_its_own_partial_copy(self):
        output = self.workspace / "handoff" / "failed-copy.zip"
        source = self.root / "new-bundle.zip"
        source.write_bytes(b"synthetic bundle bytes")

        def broken_copy(_source, target, **_kwargs):
            target.write(b"partial")
            raise OSError("disk write failed")

        with patch("handouter.agents.manual.os.link", side_effect=OSError("no hard links")), \
             patch("handouter.agents.manual.shutil.copyfileobj", side_effect=broken_copy):
            with self.assertRaisesRegex(OSError, "disk write failed"):
                _publish_exclusive_file(source, output)
        self.assertFalse(output.exists())
        self.assertEqual(source.read_bytes(), b"synthetic bundle bytes")

    def test_bundle_fallback_preserves_replacement_after_copy_failure(self):
        output = self.root / "failed-copy.zip"
        source = self.root / "new-bundle.zip"
        replacement = self.root / "replacement.zip"
        source.write_bytes(b"new")
        replacement.write_bytes(b"another task's replacement")
        real_open = Path.open

        @contextlib.contextmanager
        def replace_after_close(path, mode="r", *args, **kwargs):
            try:
                with real_open(path, mode, *args, **kwargs) as handle:
                    yield handle
            finally:
                if path == output and mode == "xb":
                    replacement.replace(output)

        with patch("handouter.agents.manual.os.link", side_effect=OSError("no hard links")), \
             patch.object(Path, "open", replace_after_close), \
             patch("handouter.agents.manual.shutil.copyfileobj", side_effect=OSError("copy failed")):
            with self.assertRaisesRegex(OSError, "copy failed"):
                _publish_exclusive_file(source, output)
        self.assertEqual(output.read_bytes(), b"another task's replacement")

    def test_validate_note_cli_checks_all_outputs_and_aggregates_state(self):
        outputs = self.result.handoff.output_paths
        (self.workspace / outputs["deep"]).write_text("# Deep\n\n内容。\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(["validate-note", str(self.workspace), "--update-state"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["outputs"], outputs)
        self.assertTrue(payload["reports"]["deep"]["ok"])
        self.assertFalse(payload["reports"]["summary"]["ok"])
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["agent_output"]["status"], "invalid")
        self.assertEqual(set(state["agent_output"]["outputs"]), {"deep", "summary"})

        (self.workspace / outputs["summary"]).write_text("# Summary\n\n结论。\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(["validate-note", str(self.workspace), "--update-state"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["agent_output"]["status"], "validated")
        self.assertEqual(state["agent_output"]["semantic_review"], "required")

    def test_validate_note_explicit_output_keeps_single_file_contract(self):
        deep = self.result.handoff.output_paths["deep"]
        (self.workspace / deep).write_text("# Deep\n\n内容。\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(["validate-note", str(self.workspace), "--output", deep])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["output"], deep)
        self.assertNotIn("outputs", payload)

    def test_manual_bundle_is_portable_and_excludes_private_internal_material(self):
        bundle = create_manual_bundle(self.workspace)
        with zipfile.ZipFile(bundle.bundle) as archive:
            names = set(archive.namelist())
            self.assertIn("handoff/PROMPT.md", names)
            self.assertIn("handoff/sources.json", names)
            self.assertIn("handoff/skill/SKILL.md", names)
            self.assertIn("transcript/transcript.txt", names)
            self.assertNotIn("transcript/raw.json", names)
            self.assertFalse(any(name.startswith("audio/") for name in names))
            self.assertNotIn("manifest.json", names)
            self.assertNotIn("state.json", names)
            self.assertFalse(any(name.startswith("notes/") for name in names))
            sources = json.loads(archive.read("handoff/sources.json"))
            self.assertIsNone(sources["transcript"]["raw_asr_path"])
            all_text = b"\n".join(archive.read(name) for name in names if name.endswith((".md", ".json", ".txt")))
            self.assertNotIn(b"SHOULD_NOT_BUNDLE", all_text)

    def test_manual_bundle_includes_selected_slide_evidence(self):
        slides = self.root / "slides"
        slides.mkdir()
        (slides / "slide_001.png").write_bytes(b"synthetic-slide")
        (slides / "slides_meta.json").write_text(
            json.dumps([{"filename": "slide_001.png", "seconds": 3}]),
            encoding="utf-8",
        )
        transcript = self.root / "slides-lecture.txt"
        transcript.write_text("带 PPT 的课程内容。", encoding="utf-8")
        skill = ROOT / ".agents" / "skills" / "zhiyun-lecture-notes" / "SKILL.md"
        result = prepare_lecture(
            self.root / "slides-output",
            lecture_id="slides-course",
            course_title="Slides Course",
            transcript=transcript,
            slides_dir=slides,
            mode="deep",
            use_slides_as_source=True,
            embed_slides=False,
            skill_path=skill,
        )
        bundle = create_manual_bundle(result.workspace)
        with zipfile.ZipFile(bundle.bundle) as archive:
            names = set(archive.namelist())
        self.assertIn("slides/index.json", names)
        self.assertIn("slides/images/slide_001.png", names)
        self.assertIn("handoff/skill/references/slides/source-only.md", names)

    def test_codex_adapter_uses_workspace_write_noninteractive_exec(self):
        with patch("handouter.agents.codex.availability", return_value=AgentAvailability("codex", True, "/fake/codex", "cli")):
            command = codex.build_command(self.workspace, model="model-x")
        self.assertEqual(command[:2], ["/fake/codex", "exec"])
        self.assertIn("workspace-write", command)
        self.assertIn(str(self.workspace.resolve()), command)
        self.assertIn("model-x", command)
        self.assertEqual(command[-1], "-")

    def test_claude_adapter_is_noninteractive(self):
        with patch("handouter.agents.claude.availability", return_value=AgentAvailability("claude", True, "/fake/claude", "cli")):
            command = claude.build_command(self.workspace, model="model-y")
        self.assertEqual(command[0], "/fake/claude")
        self.assertIn("--print", command)
        self.assertIn("acceptEdits", command)
        self.assertIn("model-y", command)

    def test_claude_runner_sends_prompt_over_stdin(self):
        observed = {}

        def fake_run(command, **kwargs):
            observed["command"] = list(command)
            observed["input"] = kwargs.get("input")
            root = Path(kwargs["cwd"])
            sources = json.loads((root / "handoff" / "sources.json").read_text(encoding="utf-8"))
            for relative in sources["expected_outputs"].values():
                (root / relative).write_text("# Generated note\n\nCourse content.\n", encoding="utf-8")
            return SimpleNamespace(returncode=0)

        with patch("handouter.agents.claude.availability", return_value=AgentAvailability("claude", True, "/fake/claude", "cli")), \
             patch("handouter.agents.claude.build_command", return_value=["/fake/claude", "--print"]), \
             patch("handouter.agents.runner.subprocess.run", side_effect=fake_run):
            result = run_cli_agent(self.workspace, agent="claude")

        self.assertTrue(result.validation_ok)
        self.assertEqual(observed["command"], ["/fake/claude", "--print"])
        self.assertIsInstance(observed["input"], str)
        self.assertIn("Handouter Agent", observed["input"])

    def test_codex_runner_validates_all_outputs_and_updates_state(self):
        def fake_run(command, **kwargs):
            root = Path(kwargs["cwd"])
            sources = json.loads((root / "handoff" / "sources.json").read_text(encoding="utf-8"))
            for relative in sources["expected_outputs"].values():
                path = root / relative
                path.write_text("# Generated note\n\nCourse content.\n", encoding="utf-8")
            return SimpleNamespace(returncode=0)

        with patch("handouter.agents.codex.availability", return_value=AgentAvailability("codex", True, "/fake/codex", "cli")), \
             patch("handouter.agents.codex.build_command", return_value=["/fake/codex", "exec", "-"]), \
             patch("handouter.agents.runner.subprocess.run", side_effect=fake_run):
            result = run_cli_agent(self.workspace, agent="codex")

        self.assertTrue(result.validation_ok)
        self.assertEqual(set(result.outputs), {"deep", "summary"})
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["agent_output"]["agent"], "codex")
        self.assertEqual(state["agent_output"]["status"], "validated")
        self.assertEqual(state["agent_output"]["semantic_review"], "required")

    def test_agent_runner_detects_workspace_tampering(self):
        def fake_run(command, **kwargs):
            root = Path(kwargs["cwd"])
            sources = json.loads((root / "handoff" / "sources.json").read_text(encoding="utf-8"))
            for relative in sources["expected_outputs"].values():
                (root / relative).write_text("# note\n", encoding="utf-8")
            (root / "transcript" / "transcript.txt").write_text("tampered", encoding="utf-8")
            return SimpleNamespace(returncode=0)

        with patch("handouter.agents.codex.availability", return_value=AgentAvailability("codex", True, "/fake/codex", "cli")), \
             patch("handouter.agents.codex.build_command", return_value=["/fake/codex", "exec", "-"]), \
             patch("handouter.agents.runner.subprocess.run", side_effect=fake_run):
            result = run_cli_agent(self.workspace, agent="codex")
        self.assertFalse(result.validation_ok)
        self.assertTrue(any("workspace:" in error for error in result.validation_errors))

    def test_cli_bundle_command_returns_uploadable_path(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(["bundle", str(self.workspace)])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "gui_handoff_ready")
        self.assertTrue(Path(payload["bundle"]).is_file())
        self.assertFalse(payload["agent_was_run"])

    def test_agents_cli_reports_manual_and_cli_backends(self):
        fake = [AgentAvailability("codex", True, "/codex", "cli"), AgentAvailability("claude", False, None, "cli")]
        stdout = io.StringIO()
        with patch("handouter.cli.available_cli_agents", return_value=fake), contextlib.redirect_stdout(stdout):
            code = cli.main(["agents"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["manual"]["available"])
        self.assertTrue(payload["cli"][0]["available"])
        self.assertFalse(payload["cli"][1]["available"])

    def test_cli_agent_success_without_files_is_not_accepted(self):
        with patch("handouter.agents.codex.availability", return_value=AgentAvailability("codex", True, "/fake/codex", "cli")), \
             patch("handouter.agents.codex.build_command", return_value=["/fake/codex", "exec", "-"]), \
             patch("handouter.agents.runner.subprocess.run", return_value=SimpleNamespace(returncode=0)):
            result = run_cli_agent(self.workspace, agent="codex")
        self.assertFalse(result.validation_ok)
        self.assertTrue(any("不存在" in error for error in result.validation_errors))


if __name__ == "__main__":
    unittest.main()
