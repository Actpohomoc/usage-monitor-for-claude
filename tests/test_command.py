"""
Command Tests
===============

Unit tests for the command module: subprocess execution with environment variables.
"""
from __future__ import annotations

import subprocess
import os
import unittest
import re
from pathlib import Path
from unittest.mock import patch, MagicMock

# Prevent real notifications during automated tests
os.environ['USAGE_MONITOR_DRY_RUN'] = '1'

from usage_monitor_for_claude.command import run_event_command


class TestRunEventCommand(unittest.TestCase):
    """Tests for run_event_command() subprocess launching."""

    @patch('usage_monitor_for_claude.command.open')
    @patch('usage_monitor_for_claude.command.subprocess.Popen')
    def test_command_executed_with_shell(self, mock_popen: MagicMock, mock_open: MagicMock):
        """Command is passed to Popen with shell=True."""
        run_event_command('echo hello', {'USAGE_MONITOR_EVENT': 'reset'})

        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        self.assertEqual(args[0], 'echo hello')
        self.assertTrue(kwargs['shell'])

    @patch('usage_monitor_for_claude.command.open')
    @patch('usage_monitor_for_claude.command.subprocess.Popen')
    def test_env_vars_merged_into_environment(self, mock_popen: MagicMock, mock_open: MagicMock):
        """Event-specific variables are merged into the process environment."""
        env_vars = {
            'USAGE_MONITOR_EVENT': 'threshold',
            'USAGE_MONITOR_VARIANT': 'five_hour',
            'USAGE_MONITOR_UTILIZATION': '84.5',
        }
        run_event_command('notify.bat', env_vars)

        passed_env = mock_popen.call_args[1]['env']
        for key, value in env_vars.items():
            self.assertEqual(passed_env[key], value)

    @patch('usage_monitor_for_claude.command.open')
    @patch('usage_monitor_for_claude.command.subprocess.Popen')
    def test_existing_env_preserved(self, mock_popen: MagicMock, mock_open: MagicMock):
        """Existing environment variables are preserved alongside new ones."""
        with patch.dict('os.environ', {'PATH': '/usr/bin', 'HOME': '/home/user'}):
            run_event_command('test', {'USAGE_MONITOR_EVENT': 'reset'})

        passed_env = mock_popen.call_args[1]['env']
        self.assertEqual(passed_env['PATH'], '/usr/bin')
        self.assertEqual(passed_env['HOME'], '/home/user')
        self.assertEqual(passed_env['USAGE_MONITOR_EVENT'], 'reset')

    @patch('usage_monitor_for_claude.command.open')
    @patch('usage_monitor_for_claude.command.subprocess.Popen')
    def test_stdout_stderr_logging(self, mock_popen: MagicMock, mock_open: MagicMock):
        """stdout is redirected to a file and stderr to STDOUT with a timestamp."""
        mock_file = mock_open.return_value
        run_event_command('test_cmd', {'USAGE_MONITOR_EVENT': 'reset'})

        kwargs = mock_popen.call_args[1]
        self.assertEqual(kwargs['stdout'], mock_file)
        self.assertEqual(kwargs['stderr'], subprocess.STDOUT)
        
        # Verify timestamp was written
        # It's in the format [YYYY-MM-DD HH:MM:SS]
        all_writes = "".join(call.args[0] for call in mock_file.write.call_args_list)
        self.assertTrue(re.search(r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]', all_writes), 
                        f"Timestamp not found in: {all_writes}")
        self.assertIn("Executing: test_cmd", all_writes)

        mock_open.assert_called_once()
        self.assertIn('command_errors.log', str(mock_open.call_args[0][0]))

    @patch('usage_monitor_for_claude.command.open')
    @patch('usage_monitor_for_claude.command.subprocess.Popen')
    def test_create_no_window_flag(self, mock_popen: MagicMock, mock_open: MagicMock):
        """CREATE_NO_WINDOW flag is set."""
        run_event_command('test', {'USAGE_MONITOR_EVENT': 'reset'})

        kwargs = mock_popen.call_args[1]
        self.assertEqual(kwargs['creationflags'], subprocess.CREATE_NO_WINDOW)

    @patch('usage_monitor_for_claude.command.subprocess.Popen')
    def test_empty_command_skipped(self, mock_popen: MagicMock):
        """Empty command string does not invoke Popen."""
        run_event_command('', {'USAGE_MONITOR_EVENT': 'reset'})

        mock_popen.assert_not_called()

    @patch('usage_monitor_for_claude.command.open')
    @patch('usage_monitor_for_claude.command.traceback.print_exc')
    @patch('usage_monitor_for_claude.command.subprocess.Popen', side_effect=OSError('not found'))
    def test_popen_exception_caught(self, mock_popen: MagicMock, mock_print_exc: MagicMock, mock_open: MagicMock):
        """OSError from Popen is caught and printed to stderr."""
        run_event_command('nonexistent_command', {'USAGE_MONITOR_EVENT': 'reset'})

        mock_print_exc.assert_called_once()

    @patch('usage_monitor_for_claude.command.open')
    @patch('usage_monitor_for_claude.command.traceback.print_exc')
    @patch('usage_monitor_for_claude.command.subprocess.Popen', side_effect=ValueError('bad'))
    def test_unexpected_exception_caught(self, mock_popen: MagicMock, mock_print_exc: MagicMock, mock_open: MagicMock):
        """Unexpected exceptions from Popen are caught and printed to stderr."""
        run_event_command('bad_command', {'USAGE_MONITOR_EVENT': 'reset'})

        mock_print_exc.assert_called_once()

    @patch('usage_monitor_for_claude.command.open')
    @patch('usage_monitor_for_claude.command.subprocess.Popen')
    def test_popen_not_waited(self, mock_popen: MagicMock, mock_open: MagicMock):
        """Popen result is not waited on (fire-and-forget)."""
        run_event_command('long_running', {'USAGE_MONITOR_EVENT': 'reset'})

        mock_process = mock_popen.return_value
        mock_process.wait.assert_not_called()
        mock_process.communicate.assert_not_called()

    @patch('usage_monitor_for_claude.command.open')
    @patch('usage_monitor_for_claude.command.subprocess.Popen')
    def test_cwd_set_to_project_root(self, mock_popen: MagicMock, mock_open: MagicMock):
        """Working directory is set to the project root (non-frozen)."""
        run_event_command('test', {'USAGE_MONITOR_EVENT': 'reset'})

        kwargs = mock_popen.call_args[1]
        expected = Path(__file__).resolve().parent.parent
        self.assertEqual(kwargs['cwd'], expected)

    @patch('usage_monitor_for_claude.command.open')
    @patch('usage_monitor_for_claude.command.subprocess.Popen')
    @patch('usage_monitor_for_claude.command.sys')
    def test_cwd_set_to_executable_dir_when_frozen(self, mock_sys: MagicMock, mock_popen: MagicMock, mock_open: MagicMock):
        """Working directory is set to the executable's folder when frozen."""
        mock_sys.frozen = True
        mock_sys.executable = 'C:\\Program Files\\MyApp\\app.exe'

        run_event_command('test', {'USAGE_MONITOR_EVENT': 'reset'})

        kwargs = mock_popen.call_args[1]
        self.assertEqual(kwargs['cwd'], Path('C:\\Program Files\\MyApp'))


if __name__ == '__main__':
    unittest.main()
