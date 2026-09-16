"""Running a validated request through the runner and into a report."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gog_bridge.domain import messages
from gog_bridge.domain.errors import CommandFailedError, CommandSpawnError
from gog_bridge.domain.rendering import render_outcome

if TYPE_CHECKING:
    from gog_bridge.deps import ToolDeps
    from gog_bridge.domain.commands import CommandRequest


async def execute(deps: ToolDeps, request: CommandRequest) -> str:
    """Run the request and return the report, or raise on failure.

    A non-zero exit, a timeout included, is raised as CommandFailedError
    carrying the full report, so the client sees an error result that still
    contains stdout and stderr.
    """
    try:
        outcome = await deps.runner.run(request)
    except CommandSpawnError as exc:
        raise CommandSpawnError(messages.SPAWN_FAILED.format(exe=deps.exe, reason=exc)) from exc

    report = render_outcome(outcome, timeout_seconds=deps.timeout_seconds)
    if outcome.exit_code != 0:
        raise CommandFailedError(report)
    return report
