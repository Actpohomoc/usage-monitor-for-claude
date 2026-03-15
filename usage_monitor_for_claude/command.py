"""
Command
========

Execute user-configured shell commands on usage events.

Commands run as fire-and-forget subprocesses.  Event details are passed
via environment variables so the user's script can inspect them without
any string interpolation in the command itself.
"""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

__all__ = ['run_event_command']


def run_event_command(command: str, env_vars: dict[str, str]) -> None:
    """Launch a shell command with event-specific environment variables.

    The command runs asynchronously (fire-and-forget).  Exceptions from
    ``subprocess.Popen`` are caught so the tray app is never disrupted
    by a misconfigured user command.

    Parameters
    ----------
    command : str
        Shell command string to execute.
    env_vars : dict[str, str]
        Mapping of ``USAGE_MONITOR_*`` environment variable names to
        their values.  Merged into the current process environment.
    """
    if not command:
        return

    env = {**os.environ, **env_vars}

    # Pin working directory to the executable's folder so that relative paths
    # in commands resolve predictably - even when Windows autostart sets the
    # CWD to C:\Windows\System32.
    if getattr(sys, 'frozen', False):
        working_dir = Path(sys.executable).parent
    else:
        working_dir = Path(__file__).resolve().parent.parent

    try:
        log_path = working_dir / 'commands_output.log'
        # Open for appending. Handle is inherited by subprocess.
        # We don't use 'with' here because the subprocess is asynchronous.
        # The OS will close it when the subprocess (and its parent) exits,
        # or we accept the single leak per app-lifetime of this specific handle
        # in exchange for correctness since we are 'fire-and-forget'.
        # Actually, Python's GC will close it eventually if the process is long-running,
        # but the subprocess will keep its own copy of the descriptor on most OSs.
        log_file = open(log_path, 'a', encoding='utf-8')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_file.write(f"\n[{timestamp}] Executing: {command}\n")
        log_file.flush()
        subprocess.Popen(
            command, shell=True, env=env, cwd=working_dir,
            stdout=log_file, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        traceback.print_exc()
