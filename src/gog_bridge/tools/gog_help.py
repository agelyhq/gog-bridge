"""gog_help: the full help of any gog command, no account involved."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from gog_bridge.domain.commands import build_help_request
from gog_bridge.domain.policy import validate_help_args
from gog_bridge.tools._errors import as_tool_errors
from gog_bridge.tools._execute import execute

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from gog_bridge.deps import ToolDeps

ARGS_DESCRIPTION = (
    "The command path whose help you want, as separate argv entries, for example "
    '["gmail", "send"]. Empty for the top-level list of commands.'
)


def register(mcp: FastMCP, deps: ToolDeps) -> None:
    """Register gog_help on the server."""

    @mcp.tool
    @as_tool_errors
    async def gog_help(
        args: Annotated[list[str], Field(description=ARGS_DESCRIPTION)] = [],  # noqa: B006
    ) -> str:
        """Show the full help of a gog command, with every flag it accepts.

        Runs `gog <args...> --help` with GOG_HELP=full, so that an empty args
        prints every command of the tree rather than the top-level groups
        alone. A command's help lists the global flags (--json, --dry-run,
        -y, --select) next to its own. Call it before a gog_run whose flags
        you are unsure of. The same policy as gog_run applies to args, except
        that an empty list is allowed and means the top-level help.

        Args:
            args: The command path, one argv entry per item, or empty.
        """
        # A list default is safe here: pydantic copies it on every call.
        validate_help_args(args)
        request = build_help_request(deps.exe, args)
        return await execute(deps, request)
