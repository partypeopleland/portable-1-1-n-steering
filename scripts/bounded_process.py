#!/usr/bin/env python3
"""Run one foreground command with a finite process-group lifecycle.

Callers must provide a positive timeout.  The command starts in its own
session/process group.  If the deadline expires, the helper sends SIGTERM to
the whole group, waits for a bounded grace period, sends SIGKILL when needed,
and reaps the root process.  Successful calls return captured stdout/stderr;
timeouts raise ``BoundedProcessTimeout`` with cleanup evidence and output.
"""

from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


DEFAULT_GRACE_TIMEOUT = 0.25


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


class BoundedProcessTimeout(subprocess.TimeoutExpired):
    """A timeout after the process group cleanup attempt has completed."""

    def __init__(
        self,
        command: Sequence[str],
        timeout: float,
        *,
        stdout: str,
        stderr: str,
        cleanup_actions: Sequence[str],
    ) -> None:
        super().__init__(command, timeout, output=stdout, stderr=stderr)
        self.stdout = stdout
        self.stderr = stderr
        self.cleanup_actions = tuple(cleanup_actions)


def _signal_process_group(process: subprocess.Popen[str], signum: int) -> None:
    if os.name == "posix":
        # start_new_session=True makes the child PID the process-group ID.
        os.killpg(process.pid, signum)
        return

    if signum == signal.SIGTERM and hasattr(signal, "CTRL_BREAK_EVENT"):
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        process.kill()


def _record_timeout_output(
    exception: subprocess.TimeoutExpired,
    stdout: str,
    stderr: str,
) -> tuple[str, str]:
    if exception.output is not None:
        stdout = _as_text(exception.output)
    if exception.stderr is not None:
        stderr = _as_text(exception.stderr)
    return stdout, stderr


def _cleanup_process_group(
    process: subprocess.Popen[str],
    *,
    grace_timeout: float,
) -> tuple[str, str, tuple[str, ...]]:
    actions: list[str] = ["SIGTERM process group"]
    try:
        _signal_process_group(process, signal.SIGTERM)
    except ProcessLookupError:
        actions.append("SIGTERM process group already exited")

    stdout = ""
    stderr = ""
    try:
        stdout, stderr = process.communicate(timeout=grace_timeout)
        actions.append("reaped root process")
        return _as_text(stdout), _as_text(stderr), tuple(actions)
    except subprocess.TimeoutExpired as exception:
        stdout, stderr = _record_timeout_output(exception, stdout, stderr)

    actions.append("SIGKILL process group")
    try:
        _signal_process_group(process, signal.SIGKILL)
    except ProcessLookupError:
        actions.append("SIGKILL process group already exited")

    try:
        final_stdout, final_stderr = process.communicate(timeout=grace_timeout)
        actions.append("reaped root process")
        return _as_text(final_stdout), _as_text(final_stderr), tuple(actions)
    except subprocess.TimeoutExpired as exception:
        stdout, stderr = _record_timeout_output(exception, stdout, stderr)

    # A double-forked descendant can retain the pipe after the group is gone.
    # Close our read ends and still give the root a finite, direct kill/reap
    # path rather than allowing cleanup itself to become unbounded.
    actions.append("SIGKILL root process")
    try:
        process.kill()
    except ProcessLookupError:
        pass
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            stream.close()
    try:
        process.wait(timeout=grace_timeout)
    except subprocess.TimeoutExpired as exception:
        raise RuntimeError("could not reap timed-out process within bounded cleanup") from exception
    actions.append("reaped root process")
    return stdout, stderr, tuple(actions)


def run_bounded(
    command: Sequence[str],
    *,
    timeout: float,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    grace_timeout: float = DEFAULT_GRACE_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    """Run ``command`` with a finite timeout and process-group cleanup.

    ``timeout`` is deliberately required at every call site.  The returned
    object preserves return code, stdout, and stderr so callers can make
    non-raising return-code assertions.
    """

    if not command:
        raise ValueError("command must not be empty")
    if timeout <= 0 or grace_timeout <= 0:
        raise ValueError("timeout and grace_timeout must be positive")

    normalized_command = tuple(str(part) for part in command)
    popen_options: dict[str, Any] = {
        "cwd": cwd,
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "shell": False,
    }
    if os.name == "posix":
        popen_options["start_new_session"] = True
    elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(normalized_command, **popen_options)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exception:
        stdout, stderr, cleanup_actions = _cleanup_process_group(
            process,
            grace_timeout=grace_timeout,
        )
        if not stdout and exception.output is not None:
            stdout = _as_text(exception.output)
        if not stderr and exception.stderr is not None:
            stderr = _as_text(exception.stderr)
        raise BoundedProcessTimeout(
            normalized_command,
            timeout,
            stdout=stdout,
            stderr=stderr,
            cleanup_actions=cleanup_actions,
        ) from exception

    return subprocess.CompletedProcess(
        normalized_command,
        process.returncode,
        _as_text(stdout),
        _as_text(stderr),
    )
