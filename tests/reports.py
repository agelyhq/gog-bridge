"""Reading the text report gog_run and gog_help return.

Shared by the unit tier and the end-to-end tier, which have separate conftest
modules and cannot import each other's.
"""

from __future__ import annotations

from typing import Any

STDOUT_HEADER = "--- stdout ---\n"
STDERR_HEADER = "--- stderr ---\n"


def report_text(result: Any) -> str:
    """The text block a tool call returned, on success or on error."""
    return result.content[0].text


def parse_report(text: str) -> dict[str, Any]:
    """Split a report into its exit code, note, stdout and stderr."""
    head, _, rest = text.partition(STDOUT_HEADER)
    stdout, _, stderr = rest.partition(STDERR_HEADER)
    exit_line = head.splitlines()[0]
    return {
        "exit_code": int(exit_line.removeprefix("exit_code: ")),
        "note": next((line for line in head.splitlines() if line.startswith("note: ")), None),
        "stdout": stdout.removesuffix("\n"),
        "stderr": stderr,
    }
