"""Turning a CommandOutcome into the one text block the tools return.

The shape is fixed and the same on success and failure, so the calling model
reads one format: the exit code, an optional note, then the two streams under
their own headers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gog_bridge.domain import messages
from gog_bridge.domain.commands import STDERR_LIMIT, STDOUT_LIMIT

if TYPE_CHECKING:
    from gog_bridge.domain.commands import CommandOutcome

STDOUT_HEADER = "--- stdout ---"
STDERR_HEADER = "--- stderr ---"
ENCODING = "utf-8"


def render_outcome(outcome: CommandOutcome, *, timeout_seconds: float) -> str:
    """Render the report the model reads, on every platform decoded as UTF-8."""
    lines = [f"exit_code: {outcome.exit_code}"]
    if outcome.timed_out:
        lines.append(f"note: {messages.TIMEOUT_NOTE.format(seconds=_seconds(timeout_seconds))}")
    lines.append(STDOUT_HEADER)
    lines.append(_stream_text(outcome.stdout, outcome.stdout_truncated, STDOUT_LIMIT))
    lines.append(STDERR_HEADER)
    lines.append(_stream_text(outcome.stderr, outcome.stderr_truncated, STDERR_LIMIT))
    return "\n".join(lines)


def _stream_text(data: bytes, truncated: bool, limit: int) -> str:
    text = data.decode(ENCODING, errors="replace")
    if not truncated:
        return text.rstrip("\n")
    marker = messages.TRUNCATED_MARKER.format(limit=limit)
    return f"{text}\n{marker}"


def _seconds(value: float) -> str:
    return f"{value:g}"
