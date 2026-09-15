"""Product-surface regressions: simple dirs, clean prompts, and readable output rules."""

from __future__ import annotations

import json
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from handouter.agents.base import AgentAvailability
from handouter import cli
from handouter.product import discover_asset_zips, inspect_asset_zip, normalize_dropped_path, product_artifacts, resolve_asset_zip
from handouter.service import prepare_lecture, refresh_handoff
from handouter.tui import _clip_columns, _display_width, _task_cli_args, available_agent_choices, build_cli_args, friendly_artifact_paths
from handouter.validation import validate_note_output


class ProductDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / "input"
        self.input.mkdir()

    def make_zip(self, name: str, *, identified: bool = False) -> Path:
        path = self.input / name
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("placeholder.txt", "x")
            if identified:
                archive.writestr("course_info.json", json.dumps({"courseName": "自动识别课程"}))
                archive.writestr(
                    "private/source.json",
                    json.dumps({"pageUrl": "https://interactivemeta.cmc.zju.edu.cn/#/replay?course_id=85721&sub_id=1965580&tenant_code=112", "videoUrl": "https://secret.invalid/x?auth_key=SECRET"}),
                )
        return path

    def test_single_zip_auto_resolves(self):
        expected = self.make_zip("course.zip")
        self.assertEqual(resolve_asset_zip(self.input), expected.resolve())

    def test_multiple_zips_require_explicit_selection(self):
        self.make_zip("a.zip")
        selected = self.make_zip("b.zip")
        with self.assertRaises(ValueError):
            resolve_asset_zip(self.input)
        self.assertEqual(resolve_asset_zip(self.input, "b.zip"), selected.resolve())
        self.assertEqual({p.name for p in discover_asset_zips(self.input)}, {"a.zip", "b.zip"})

    def test_asset_identity_uses_safe_course_info_and_page_ids(self):
        asset = self.make_zip("identified.zip", identified=True)
        identity = inspect_asset_zip(asset)
        self.assertEqual(identity.course_title, "自动识别课程")
        self.assertEqual(identity.lecture_id, "zhiyun-112-85721-1965580")
        self.assertNotIn("SECRET", identity.lecture_id)

    def test_absolute_asset_does_not_require_input_directory(self):
        asset = self.make_zip("absolute.zip", identified=True)
        missing_dir = self.root / "does-not-exist"
        self.assertEqual(resolve_asset_zip(missing_dir, asset.resolve()), asset.resolve())

    def _make_transcript(self) -> Path:
        path = self.root / "lecture.txt"
        path.write_text("课程内容。", encoding="utf-8")
        return path

    def test_existing_ready_workspace_reuses_gui_bundle_instead_of_rebuilding(self):
        result = prepare_lecture(
            self.root / "output",
            lecture_id="reuse-course",
            course_title="Reuse Course",
            transcript=self._make_transcript(),
            modes=("deep", "summary", "verbatim"),
            use_slides_as_source=False,
            embed_slides=False,
            format_profile="clean",
            skill_path=ROOT / ".agents" / "skills" / "zhiyun-lecture-notes" / "SKILL.md",
        )
        cfg = {
            "output_dir": str(self.root / "output"),
            "lecture": "reuse-course",
            "notes_deep": True,
            "notes_summary": True,
            "clean_transcript": True,
            "format_profile": "clean",
            "use_slides": False,
            "embed_slides": False,
            "allow_web": False,
            "agent": "manual",
        }
        args, action = _task_cli_args(cfg, prompt_only=False)
        self.assertEqual(action, "bundle")
        self.assertEqual(args[:2], ["bundle", str(result.workspace.resolve())])

    def test_existing_ready_workspace_refreshes_when_selection_changes(self):
        result = prepare_lecture(
            self.root / "output",
            lecture_id="refresh-course",
            course_title="Refresh Course",
            transcript=self._make_transcript(),
            mode="deep",
            use_slides_as_source=False,
            embed_slides=False,
            format_profile="clean",
            skill_path=ROOT / ".agents" / "skills" / "zhiyun-lecture-notes" / "SKILL.md",
        )
        cfg = {
            "output_dir": str(self.root / "output"),
            "lecture": "refresh-course",
            "notes_deep": True,
            "notes_summary": True,
            "clean_transcript": False,
            "format_profile": "traceable",
            "use_slides": False,
            "embed_slides": False,
            "allow_web": False,
            "agent": "manual",
        }
        args, action = _task_cli_args(cfg, prompt_only=False)
        self.assertEqual(action, "refresh")
        self.assertEqual(args[0], "prompt")
        self.assertEqual(Path(args[1]).resolve(), result.workspace.resolve())
        self.assertIn("--modes", args)
        self.assertIn("traceable", args)

    def test_tui_only_lists_available_cli_agents(self):
        fake = [
            AgentAvailability("codex", True, "/codex", "cli"),
            AgentAvailability("claude", False, None, "cli"),
        ]
        with patch("handouter.tui.available_cli_agents", return_value=fake):
            values, labels = available_agent_choices()
        self.assertEqual(values, ["manual", "codex"])
        self.assertEqual(labels["manual"], "GUI handoff")
        self.assertEqual(labels["codex"], "Codex CLI")
        self.assertNotIn("claude", labels)

    def test_product_tui_command_uses_direct_asset_and_output_dir(self):
        args = build_cli_args({
            "kind": "product",
            "output_dir": "/out",
            "asset": "/Users/test/Downloads/course.zip",
            "lecture": "lecture-01",
            "title": "Course",
            "mode": "full",
            "format_profile": "clean",
            "device": "auto",
            "use_slides": True,
            "embed_slides": False,
            "allow_web": False,
        })
        self.assertEqual(args[0], "run")
        self.assertNotIn("--input-dir", args)
        self.assertIn("--asset", args)
        self.assertIn("/Users/test/Downloads/course.zip", args)
        self.assertIn("--output-dir", args)
        self.assertIn("/out", args)
        self.assertIn("--format-profile", args)
        self.assertIn("clean", args)

    def test_dragged_paths_are_normalized(self):
        self.assertEqual(
            normalize_dropped_path(r"/Users/test/Downloads/My\ Course.zip"),
            "/Users/test/Downloads/My Course.zip",
        )
        self.assertEqual(
            normalize_dropped_path("'/Users/test/Downloads/课程 01.zip'"),
            "/Users/test/Downloads/课程 01.zip",
        )
        self.assertEqual(
            normalize_dropped_path("file:///Users/test/Downloads/%E8%AF%BE%E7%A8%8B%2001.zip"),
            "/Users/test/Downloads/课程 01.zip",
        )

    def test_ascii_clipping_respects_wide_chinese_characters(self):
        clipped = _clip_columns("ABC课程路径", 7)
        self.assertLessEqual(_display_width(clipped), 7)
        self.assertEqual(clipped, "ABC课程")

    def test_friendly_paths_only_surface_user_artifacts(self):
        paths = friendly_artifact_paths({
            "output_dir": self.root / "out",
            "lecture": "lecture-01",
            "mode": "summary",
        })
        self.assertEqual(Path(paths["prompt"]).name, "PROMPT.md")
        self.assertEqual(Path(paths["transcript"]).name, "transcript.txt")
        self.assertEqual(Path(paths["slides"]).name, "images")
        self.assertEqual(Path(paths["notes"]).name, "notes")
        self.assertEqual(Path(paths["expected_note"]).name, "summary-001.md")

    def test_ascii_tui_multi_deliverables_map_to_cli_modes(self):
        args = build_cli_args({
            "kind": "product",
            "input_dir": "/in",
            "output_dir": "/out",
            "asset": "course.zip",
            "lecture": "lecture-01",
            "title": "Course",
            "notes_deep": True,
            "notes_summary": True,
            "clean_transcript": True,
            "format_profile": "clean",
            "device": "auto",
            "use_slides": True,
            "embed_slides": False,
            "allow_web": False,
            "agent": "codex",
        })
        start = args.index("--modes") + 1
        end = args.index("--format-profile")
        self.assertEqual(args[start:end], ["deep", "summary", "verbatim"])
        self.assertEqual(args[args.index("--agent") + 1], "codex")

    def test_ascii_tui_can_request_notes_without_clean_transcript(self):
        args = build_cli_args({
            "kind": "product",
            "input_dir": "/in",
            "output_dir": "/out",
            "notes_deep": True,
            "notes_summary": True,
            "clean_transcript": False,
            "format_profile": "clean",
            "device": "auto",
            "use_slides": True,
            "embed_slides": False,
            "allow_web": False,
            "agent": "manual",
        })
        start = args.index("--modes") + 1
        end = args.index("--format-profile")
        self.assertEqual(args[start:end], ["deep", "summary"])
        self.assertEqual(args[args.index("--agent") + 1], "manual")

    def test_tui_can_select_full_and_verbatim_as_distinct_deliverables(self):
        args = build_cli_args({
            "kind": "product",
            "output_dir": "/out",
            "notes_full": True,
            "notes_deep": False,
            "notes_summary": False,
            "verbatim_transcript": True,
            "format_profile": "clean",
            "device": "auto",
            "use_slides": False,
            "embed_slides": False,
            "allow_web": False,
            "agent": "manual",
        })
        start = args.index("--modes") + 1
        end = args.index("--format-profile")
        self.assertEqual(args[start:end], ["full", "verbatim"])


class PromptFormatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.transcript = self.root / "lecture.txt"
        self.transcript.write_text("老师说：这个结论不是无条件成立。", encoding="utf-8")
        self.skill = ROOT / ".agents" / "skills" / "zhiyun-lecture-notes" / "SKILL.md"

    def prepare(self, mode: str = "deep", format_profile: str = "clean"):
        return prepare_lecture(
            self.root / "output",
            lecture_id=f"{mode}-{format_profile}",
            course_title="测试课程",
            transcript=self.transcript,
            mode=mode,
            format_profile=format_profile,
            skill_path=self.skill,
        )

    def test_clean_full_uses_progressive_skill_modules(self):
        result = self.prepare("full", "clean")
        prompt = (result.workspace / "handoff" / "PROMPT.md").read_text(encoding="utf-8")
        sources = json.loads((result.workspace / "handoff" / "sources.json").read_text())
        self.assertEqual(sources["options"]["format_profile"], "clean")
        self.assertIn("handoff/skill/references/modes/full.md", sources["skill"]["modules"])
        self.assertIn("handoff/skill/references/formats/clean.md", sources["skill"]["modules"])
        self.assertIn("本次 Skill 模块", prompt)
        full_rule = (result.workspace / "handoff" / "skill" / "references" / "modes" / "full.md").read_text(encoding="utf-8")
        self.assertIn("comparison tables", full_rule)
        artifacts = product_artifacts(result.workspace)
        self.assertEqual(artifacts.prompt.resolve(), (result.workspace / "handoff" / "PROMPT.md").resolve())

    def test_full_and_verbatim_have_distinct_skill_rules_and_prompt_positioning(self):
        result = prepare_lecture(
            self.root / "full-verbatim",
            lecture_id="full-verbatim-01",
            course_title="测试课程",
            transcript=self.transcript,
            modes=("full", "verbatim"),
            format_profile="clean",
            skill_path=self.skill,
        )
        sources = json.loads((result.workspace / "handoff" / "sources.json").read_text(encoding="utf-8"))
        modules = sources["skill"]["modules"]
        self.assertIn("handoff/skill/references/modes/full.md", modules)
        self.assertIn("handoff/skill/references/modes/verbatim.md", modules)
        full_rule = (result.workspace / "handoff" / "skill" / "references" / "modes" / "full.md").read_text(encoding="utf-8")
        verbatim_rule = (result.workspace / "handoff" / "skill" / "references" / "modes" / "verbatim.md").read_text(encoding="utf-8")
        self.assertIn("aggressively removing oral redundancy", full_rule)
        self.assertIn("Never map ASR/VAD segments directly to paragraphs", full_rule)
        self.assertIn("stays close to what was actually said", verbatim_rule)
        self.assertIn("Never treat one ASR/VAD segment as one paragraph", verbatim_rule)
        prompt = (result.workspace / "handoff" / "PROMPT.md").read_text(encoding="utf-8")
        self.assertIn("逐字版 / `verbatim`", prompt)
        self.assertIn("完整整理版 / `full`", prompt)
        self.assertIn("不是同一种写法", prompt)

    def test_traceable_profile_selects_traceable_module(self):
        result = self.prepare("deep", "traceable")
        sources = json.loads((result.workspace / "handoff" / "sources.json").read_text(encoding="utf-8"))
        self.assertIn("handoff/skill/references/formats/traceable.md", sources["skill"]["modules"])
        rule = (result.workspace / "handoff" / "skill" / "references" / "formats" / "traceable.md").read_text(encoding="utf-8")
        self.assertIn("major section", rule)
        self.assertEqual(result.handoff.format_profile, "traceable")

    def test_handoff_materializes_classroom_order_and_folded_presentation_rules(self):
        for profile in ("clean", "traceable"):
            with self.subTest(profile=profile):
                result = self.prepare("deep", profile)
                sources = json.loads((result.workspace / "handoff/sources.json").read_text(encoding="utf-8"))
                relative = "handoff/skill/references/common/presentation.md"
                self.assertIn(relative, sources["skill"]["modules"])
                rule = (result.workspace / relative).read_text(encoding="utf-8")
                self.assertIn("Except for summary, preserve the actual order of the lecture", rule)
                self.assertIn("> [!IMPORTANT]", rule)
                self.assertIn("<summary>课程信息</summary>", rule)
                self.assertIn("<summary>本章时间与来源</summary>", rule)
                self.assertIn("Do not add source folds after individual natural paragraphs", rule)
                self.assertIn("<summary>待核对</summary>", rule)
                self.assertIn("时间：未知", rule)
                self.assertIn("disjoint sources", rule)
                deep = (result.workspace / "handoff/skill/references/modes/deep.md").read_text(encoding="utf-8")
                self.assertIn("Preserve the actual lecture order", deep)
                self.assertIn("Do not reorganize", deep)
                prompt = (result.workspace / "handoff/PROMPT.md").read_text(encoding="utf-8")
                self.assertIn("除 `summary` 外", prompt)
                self.assertIn("正文前", prompt)
                self.assertIn("每个主要章节", prompt)
                self.assertIn("不是每个自然段都标注", prompt)
                self.assertIn("<summary>待核对</summary>", prompt)
                self.assertNotIn("每个自然段后使用", prompt)

    def test_clean_folded_metadata_does_not_warn_but_visible_source_still_does(self):
        result = self.prepare("deep", "clean")
        note = result.workspace / result.handoff.output_path
        text = (
            "# 课程\n\n> [!IMPORTANT]\n> 小测以课堂通知为准。\n\n"
            "<details>\n<summary>课程信息</summary>\n\n## 讲义元信息\n"
            "transcript/segments.json\n</details>\n\n正文。\n\n"
            "<details>\n<summary>本章时间与来源</summary>\n"
            "时间：未知；seg-0001\n</details>\n"
        )
        note.write_text(text, encoding="utf-8")
        report = validate_note_output(result.workspace)
        self.assertTrue(report.ok)
        self.assertEqual(report.warnings, ())
        note.write_text(text + "\n正文显示 seg-0002。\n", encoding="utf-8")
        self.assertTrue(any("来源 ID" in warning for warning in validate_note_output(result.workspace).warnings))

    def test_open_details_and_visible_summary_labels_still_warn(self):
        result = self.prepare("deep", "clean")
        note = result.workspace / result.handoff.output_path
        for fold in (
            "<details open><summary>来源</summary>seg-0001</details>",
            "<details><summary>seg-0001</summary>内容</details>",
            "<details><summary>来源</summary>seg-0001",  # unclosed
            "<![unexpected]>seg-0001",  # malformed HTML declaration
        ):
            with self.subTest(fold=fold):
                note.write_text("# 课程\n\n" + fold, encoding="utf-8")
                self.assertTrue(any("来源 ID" in warning for warning in validate_note_output(result.workspace).warnings))

    def test_closed_nested_details_do_not_expose_inner_metadata(self):
        result = self.prepare("deep", "clean")
        note = result.workspace / result.handoff.output_path
        note.write_text(
            "# 课程\n\n<details><summary>课程信息</summary>"
            "<details open><summary>seg-0001</summary>transcript/segments.json</details>"
            "</details>\n\n正文。\n", encoding="utf-8",
        )
        self.assertEqual(validate_note_output(result.workspace).warnings, ())

    def test_folded_raw_asr_comparison_remains_invalid(self):
        result = self.prepare("verbatim", "clean")
        note = result.workspace / result.handoff.output_path
        note.write_text(
            "# 课程\n\n<details><summary>对照</summary>\n\n"
            "| 原始 ASR | 精修逐字稿 |\n| --- | --- |\n| 啊你好 | 你好 |\n\n</details>\n",
            encoding="utf-8",
        )
        self.assertTrue(any("双轨对照" in error for error in validate_note_output(result.workspace).errors))

    def test_multi_mode_handoff_has_separate_outputs(self):
        result = prepare_lecture(
            self.root / "multi-output",
            lecture_id="multi-01",
            course_title="多输出课程",
            transcript=self.transcript,
            modes=("deep", "summary", "full"),
            format_profile="clean",
            skill_path=self.skill,
        )
        self.assertEqual(result.handoff.modes, ("deep", "summary", "full"))
        self.assertEqual(result.handoff.expected_outputs, {
            "deep": "notes/deep-001.md",
            "summary": "notes/summary-001.md",
            "full": "notes/full-001.md",
        })
        sources = json.loads((result.workspace / "handoff" / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(sources["modes"], ["deep", "summary", "full"])
        self.assertEqual(sources["expected_outputs"], result.handoff.expected_outputs)
        prompt = (result.workspace / "handoff" / "PROMPT.md").read_text(encoding="utf-8")
        self.assertIn("必须生成 3 个独立 Markdown 文件", prompt)
        self.assertIn("notes/deep-001.md", prompt)
        self.assertIn("notes/summary-001.md", prompt)
        self.assertIn("notes/full-001.md", prompt)
        artifacts = product_artifacts(result.workspace)
        self.assertEqual(set(artifacts.expected_notes), {"deep", "summary", "full"})

    def test_refresh_multi_mode_versions_advance_independently(self):
        result = prepare_lecture(
            self.root / "multi-refresh",
            lecture_id="multi-refresh-01",
            course_title="多输出课程",
            transcript=self.transcript,
            modes=("deep", "summary"),
            skill_path=self.skill,
        )
        deep_first = result.workspace / result.handoff.expected_outputs["deep"]
        deep_first.write_text("# Deep v1\n", encoding="utf-8")
        refreshed = refresh_handoff(
            result.workspace,
            modes=("deep", "summary", "full"),
            format_profile="clean",
            use_slides_as_source=False,
        )
        self.assertEqual(refreshed.handoff.expected_outputs, {
            "deep": "notes/deep-002.md",
            "summary": "notes/summary-001.md",
            "full": "notes/full-001.md",
        })
        self.assertTrue(refreshed.archived_prompt.is_file())
        self.assertEqual((result.workspace / "transcript" / "transcript.txt").read_text(encoding="utf-8"), self.transcript.read_text(encoding="utf-8"))

    def test_prompt_cli_explicit_single_mode_replaces_existing_modes(self):
        result = self.prepare("deep", "clean")
        refresh_handoff(result.workspace, modes=("deep", "summary"))
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(["prompt", str(result.workspace), "--mode", "verbatim"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["modes"], ["verbatim"])
        sources = json.loads((result.workspace / "handoff" / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(set(sources["expected_outputs"]), {"verbatim"})
        self.assertIn("handoff/skill/references/modes/verbatim.md", sources["skill"]["modules"])
        self.assertNotIn("handoff/skill/references/modes/deep.md", sources["skill"]["modules"])

    def test_refresh_preserves_modes_when_omitted_and_prefers_explicit_modes(self):
        result = self.prepare("full", "clean")
        refresh_handoff(result.workspace, modes=("deep", "summary"))
        unchanged = refresh_handoff(result.workspace, format_profile="traceable")
        self.assertEqual(unchanged.handoff.modes, ("deep", "summary"))
        explicit = refresh_handoff(result.workspace, mode="verbatim", modes=("full",))
        self.assertEqual(explicit.handoff.modes, ("full",))

    def test_validate_full_rejects_old_dual_track_format(self):
        result = self.prepare("full", "clean")
        note = result.workspace / result.handoff.output_path
        note.write_text(
            "# 测试课程\n\n| 原始 ASR | 精修逐字稿 |\n| --- | --- |\n| 啊你好 | 你好 |\n",
            encoding="utf-8",
        )
        report = validate_note_output(result.workspace)
        self.assertFalse(report.ok)
        self.assertTrue(any("双轨对照" in error for error in report.errors))

    def test_refresh_prompt_archives_old_task_without_rerunning_materials(self):
        result = self.prepare("deep", "clean")
        transcript_before = (result.workspace / "transcript" / "transcript.txt").read_bytes()
        first_note = result.workspace / result.handoff.output_path
        first_note.write_text("# 第一版\n", encoding="utf-8")
        refreshed = refresh_handoff(
            result.workspace,
            mode="deep",
            format_profile="traceable",
            use_slides_as_source=False,
        )
        self.assertTrue(refreshed.archived_prompt.is_file())
        self.assertEqual(refreshed.handoff.output_path, "notes/deep-002.md")
        self.assertEqual(refreshed.handoff.format_profile, "traceable")
        self.assertEqual((result.workspace / "transcript" / "transcript.txt").read_bytes(), transcript_before)
        self.assertIn("traceable", (result.workspace / "handoff" / "PROMPT.md").read_text(encoding="utf-8"))

    def test_prompt_only_tui_command_never_mentions_input_asset(self):
        args = build_cli_args({
            "kind": "prompt",
            "output_dir": "/out",
            "lecture": "lecture-01",
            "mode": "summary",
            "format_profile": "clean",
            "use_slides": True,
            "embed_slides": False,
            "allow_web": False,
        })
        self.assertEqual(args[:2], ["prompt", "/out/lecture-01"])
        self.assertNotIn("--input-dir", args)
        self.assertNotIn("--asset", args)

    def test_validate_clean_warns_about_engineering_metadata(self):
        result = self.prepare("deep", "clean")
        note = result.workspace / result.handoff.output_path
        note.write_text(
            "# 测试课程\n\n## 讲义元信息\n来源 transcript/segments.json，seg-0001。\n\n## 正文\n内容。\n",
            encoding="utf-8",
        )
        report = validate_note_output(result.workspace)
        self.assertTrue(report.ok)
        self.assertGreaterEqual(len(report.warnings), 2)

    def test_single_output_validation_cli_preserves_existing_json(self):
        result = self.prepare("deep", "clean")
        (result.workspace / result.handoff.output_path).write_text("# 测试课程\n\n内容。\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(["validate-note", str(result.workspace)])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["output"], result.handoff.output_path)
        self.assertNotIn("outputs", payload)


if __name__ == "__main__":
    unittest.main()
