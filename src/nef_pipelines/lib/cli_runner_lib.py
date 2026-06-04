"""Shared CliRunner helpers for version-safe stdout/stderr separation.

click < 8.3 merges stdout and stderr when mix_stderr=True (the default).
These helpers let both the test harness and the MCP runner reliably split
the two streams regardless of which click generation is installed.

TODO: when click >= 8.3 is the minimum required version for all supported
Pythons (3.9-3.15 currently), delete this module and replace every import
site with a plain ``CliRunner()`` call that reads ``result.stdout`` and
``result.stderr`` directly.
"""

from __future__ import annotations

import contextlib
import sys

from typer.testing import CliRunner

# Sentinel bytes injected around every stderr write on click < 8.3.
# TODO: remove when click >= 8.3 is the minimum required version.
_STDERR_START = "\x00STDERR_START\x00"
_STDERR_END = "\x00STDERR_END\x00"


@contextlib.contextmanager
def _marking_stderr():
    """Wrap sys.stderr so every write is bracketed with START/END markers.

    Legacy helper for click < 8.3 where CliRunner(mix_stderr=True) collapses
    stdout/stderr into a single buffer. Bracketing each write (rather than each
    line) is robust against partial writes that don't end with a newline —
    without it, a stderr write ending mid-line followed by a stdout write would
    be mis-classified because they share the same physical line in the buffer.

    TODO: remove when click >= 8.3 is the minimum required version.
    """
    original = sys.stderr

    class _MarkedWriter:
        encoding = getattr(original, "encoding", "utf-8")
        errors = getattr(original, "errors", "replace")

        def write(self, s):
            """Write s to the underlying stderr, bracketed with markers."""
            if not s:
                return 0
            original.write(_STDERR_START + s + _STDERR_END)
            return len(s)

        def writelines(self, lines):
            """Write each line bracketed with markers."""
            for line in lines:
                self.write(line)

        def flush(self):
            """Flush the underlying stderr."""
            original.flush()

        def isatty(self):
            """Return False — this is never a terminal."""
            return False

    sys.stderr = _MarkedWriter()
    try:
        yield
    finally:
        sys.stderr = original


class _MarkerCliRunner(CliRunner):
    """CliRunner that marks stderr writes for post-processing on click < 8.3.

    TODO: remove when click >= 8.3 is the minimum required version.
    """

    @contextlib.contextmanager
    def isolation(self, input=None, env=None, color=False):
        """Run isolation with stderr marking active."""
        with super().isolation(input=input, env=env, color=color) as streams:
            with _marking_stderr():
                yield streams


def _split_marked_output(output: str):
    """Split combined output into (stdout, stderr) via per-write START/END markers.

    Text between _STDERR_START and _STDERR_END belongs to stderr; everything
    outside those brackets is stdout. Works for any interleaving of the two streams.

    TODO: remove when click >= 8.3 is the minimum required version.
    """
    stdout_parts = []
    stderr_parts = []
    i = 0
    while i < len(output):
        start = output.find(_STDERR_START, i)
        if start == -1:
            stdout_parts.append(output[i:])
            break
        stdout_parts.append(output[i:start])
        body_start = start + len(_STDERR_START)
        end = output.find(_STDERR_END, body_start)
        if end == -1:
            stderr_parts.append(output[body_start:])
            break
        stderr_parts.append(output[body_start:end])
        i = end + len(_STDERR_END)
    return "".join(stdout_parts), "".join(stderr_parts)
