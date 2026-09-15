"""Exercise real Markdown/math rendering and portable output boundaries."""

import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from handouter.html_export import export_html

READY = all(importlib.util.find_spec(name) for name in ('markdown_it', 'mdit_py_plugins', 'latex2mathml'))


@unittest.skipUnless(READY, 'HTML extra not installed')
class HTMLExportTests(unittest.TestCase):
    def test_handoff_includes_offline_dual_delivery_rules(self):
        from handouter.service import prepare_lecture
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            transcript = root / 'transcript.txt'
            transcript.write_text('这是一段测试课程内容。', encoding='utf-8')
            result = prepare_lecture(root / 'output', lecture_id='test-html', course_title='测试',
                                     transcript=transcript, modes=['deep', 'summary'])
            prompt = (result.workspace / 'handoff' / 'PROMPT.md').read_text(encoding='utf-8')
            self.assertIn('Markdown + 离线 HTML', prompt)
            self.assertIn('HTML 待导出/核验', prompt)
            self.assertIn('无 CDN/远程脚本依赖', prompt)
            presentation = result.workspace / 'handoff' / 'skill' / 'references' / 'common' / 'presentation.md'
            self.assertIn('Offline HTML reading delivery', presentation.read_text(encoding='utf-8'))

    def test_agent_command_reports_html_failure_without_losing_markdown(self):
        from handouter.cli import main
        from handouter.agents.base import AgentRunResult
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            note = self.fixture(root)
            original = note.read_bytes()
            result = AgentRunResult('codex', 0, {'deep': 'notes/deep.md'}, True, ())
            with patch('handouter.cli.run_cli_agent', return_value=result), \
                 patch('handouter.html_export.render_note', side_effect=ValueError('unsupported formula')), \
                 contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
                code = main(['agent-run', str(root), '--agent', 'codex'])
            self.assertNotEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue())['html_delivery']['status'], 'failed')
            self.assertIn('HTML 导出失败', err.getvalue())
            self.assertEqual(note.read_bytes(), original)

    def test_cli_exports_json_and_real_html(self):
        from handouter.cli import main
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['export-html', str(root)]), 0)
            paths = json.loads(out.getvalue())['html']
            self.assertEqual(len(paths), 1)
            self.assertIn('<math', Path(paths[0]).read_text(encoding='utf-8'))

    def test_agent_exports_only_this_runs_outputs(self):
        from handouter.agents.base import AgentRunResult
        from handouter.html_export import export_agent_html
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            (root / 'notes' / 'old.md').write_text('old', encoding='utf-8')
            result = AgentRunResult('codex', 0, {'deep': 'notes/deep.md'}, True, ())
            delivery = export_agent_html(root, result)
            self.assertEqual(delivery['status'], 'ready')
            self.assertEqual(set(delivery['outputs']), {'deep'})
            self.assertFalse((root / 'notes' / 'old.html').exists())
            failed = AgentRunResult('codex', 1, result.outputs, False, ('failed',))
            self.assertEqual(export_agent_html(root, failed)['status'], 'skipped')

    def fixture(self, root):
        (root / 'notes').mkdir()
        images = root / 'slides' / 'images'
        images.mkdir(parents=True)
        (images / 'PPT 01.png').write_bytes(base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='))
        note = root / 'notes' / 'deep.md'
        note.write_text('# 测试讲义\n\n> [!IMPORTANT]\n> 下周小测\n\n'
                        '<details><summary>课程信息</summary>教师</details>\n\n'
                        '## 第一章\n\n<details><summary>本章时间与来源</summary>00:00–10:00</details>\n\n'
                        '行内 $E=mc^2$\n\n$$\n\\frac{1}{2}+\\sqrt{x}\n$$\n\n'
                        '![PPT](<../slides/images/PPT 01.png>)\n\n'
                        '<details><summary>待核对</summary>术语</details>', encoding='utf-8')
        return note

    def test_offline_images_math_and_folds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            output = export_html(root)[0].read_text(encoding='utf-8')
            self.assertIn('data:image/png;base64,', output)
            self.assertIn('<math', output)
            self.assertIn('<mfrac>', output)
            self.assertIn('<msqrt>', output)
            self.assertIn('<summary>本章时间与来源</summary>', output)
            self.assertIn('<summary>待核对</summary>', output)
            self.assertNotIn('<script', output)
            self.assertNotIn('../slides/', output)

    def test_repeat_export_preserves_previous_html_and_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            note = self.fixture(root)
            original = note.read_bytes()
            first = export_html(note)[0]
            first.write_text('user edited HTML', encoding='utf-8')
            second = export_html(note)[0]
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(), 'user edited HTML')
            self.assertEqual(note.read_bytes(), original)

    def test_active_html_removed(self):
        with tempfile.TemporaryDirectory() as td:
            note = Path(td) / 'note.md'
            note.write_text('<script>alert(1)</script><iframe src="https://example.com"></iframe>'
                            '<details open onclick="alert(1)"><summary>X</summary>Y</details>'
                            '<a href="javascript:alert(1)">bad</a>', encoding='utf-8')
            html = export_html(note)[0].read_text()
            for forbidden in ('<script', '<iframe', 'onclick', 'href="javascript:', '<details open'):
                self.assertNotIn(forbidden, html)

    def test_bad_image_stops_export_without_partial_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            bad = root / 'notes' / 'summary.md'
            bad.write_text('![bad](https://example.com/private.png)', encoding='utf-8')
            with self.assertRaises(ValueError):
                export_html(root)
            self.assertEqual(list((root / 'notes').glob('*.html')), [])

    def test_symlink_cannot_embed_outside_materials(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            root = Path(td)
            note = self.fixture(root)
            outside = Path(other) / 'outside.png'
            outside.write_bytes(b'\x89PNG\r\n\x1a\n')
            link = root / 'slides' / 'images' / 'outside.png'
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest('symlinks unavailable')
            note.write_text('![bad](../slides/images/outside.png)', encoding='utf-8')
            with self.assertRaises(ValueError):
                export_html(root)
