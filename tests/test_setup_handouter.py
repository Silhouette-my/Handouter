"""Installer orchestration without network or changes to the user's environment."""

import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import setup_handouter as setup


class SetupTests(unittest.TestCase):
    def test_existing_environment_is_reused_without_forcing_dependencies(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            python = root / '.venv' / ('Scripts/python.exe' if setup.os.name == 'nt' else 'bin/python')
            python.parent.mkdir(parents=True)
            python.touch()
            with patch.object(setup, 'ROOT', root), patch.object(setup, 'run') as run, \
                 patch.object(setup, 'ensure_media'), patch.object(setup, 'check_runtime'), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(setup.main([]), 0)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn([str(python), '-m', 'pip', 'install', '.[asr,html]'], commands)
            self.assertFalse(any('venv' in command or '--force-reinstall' in command for command in commands))

    def test_incomplete_environment_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / '.venv').mkdir()
            with patch.object(setup, 'ROOT', root), patch.object(setup, 'run') as run, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(setup.main([]), 1)
            run.assert_not_called()

    def test_existing_ffmpeg_is_verified_without_package_manager(self):
        with patch.object(setup, 'refresh_windows_path'), \
             patch.object(setup.shutil, 'which', side_effect=lambda name: '/tools/' + name), \
             patch.object(setup, 'run') as run:
            setup.ensure_media()
        self.assertEqual([c.args[0] for c in run.call_args_list],
                         [['/tools/ffmpeg', '-version'], ['/tools/ffprobe', '-version']])

    def test_windows_install_rechecks_both_executables(self):
        found = {'winget': 'winget.exe'}
        def install(command, **kwargs):
            if command[0] == 'winget':
                found.update(ffmpeg='ffmpeg.exe', ffprobe='ffprobe.exe')
        with patch.object(setup.sys, 'platform', 'win32'), \
             patch.object(setup, 'refresh_windows_path') as refresh, \
             patch.object(setup.shutil, 'which', side_effect=found.get), \
             patch.object(setup, 'run', side_effect=install), contextlib.redirect_stdout(io.StringIO()):
            setup.ensure_media()
        self.assertEqual(refresh.call_count, 2)

    def test_runtime_failure_cannot_report_ready(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(setup, 'ROOT', Path(td)), patch.object(setup, 'run'), \
                 patch.object(setup, 'ensure_media'), \
                 patch.object(setup, 'check_runtime', side_effect=RuntimeError('native import failed')), \
                 contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(setup.main([]), 1)
                self.assertNotIn('Ready.', output.getvalue())
