"""Composition root: builds the dependency graph and the FastMCP server."""

from __future__ import annotations

from importlib.metadata import version
from typing import TYPE_CHECKING

from fastmcp import FastMCP

from gog_bridge.adapters.process_runner import AsyncioProcessRunner
from gog_bridge.config import load_settings
from gog_bridge.deps import ToolDeps
from gog_bridge.tools import register_all_tools

if TYPE_CHECKING:
    from gog_bridge.config import Settings
    from gog_bridge.domain.commands import CommandRunner

DISTRIBUTION = "gog-bridge"

INSTRUCTIONS = """\
Bridge to the gog command line tool for Google Workspace: Gmail, Calendar,
Drive, Docs, Sheets, Slides, Contacts and more, on the configured accounts:
{accounts}.

Two tools. gog_run executes one gog command on the account you name by its
alias and returns exit code, stdout and stderr. gog_help prints the full help
of any command, flags included; call it first when unsure of a flag.

Pass the command line as a list of argv entries, without the leading 'gog'.
Ask for --json when you need to read the answer back. The bridge chooses the
account and refuses the flags that would change it, as well as the commands
that administer the local gog installation.
"""


def create_server(
    settings: Settings | None = None, *, runner: CommandRunner | None = None
) -> FastMCP:
    """Build the MCP server with every tool registered.

    Args:
        settings: Configuration to use. Loaded from the environment when omitted.
        runner: Command runner to use instead of the asyncio one. This is the
            seam tests may drive; production leaves it unset, and the test suite
            leaves it unset too so the real runner is exercised.
    """
    settings = settings or load_settings()
    deps = ToolDeps(
        exe=settings.exe,
        accounts=settings.accounts,
        runner=runner or AsyncioProcessRunner(timeout_seconds=settings.timeout_seconds),
        timeout_seconds=settings.timeout_seconds,
    )

    mcp = FastMCP(
        name=DISTRIBUTION,
        instructions=INSTRUCTIONS.format(accounts=settings.accounts.describe()),
        # Without an explicit version, a client is told the FastMCP version instead.
        version=version(DISTRIBUTION),
    )
    register_all_tools(mcp, deps)

    return mcp
