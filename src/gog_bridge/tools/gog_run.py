"""gog_run: one gog command on one of the two configured accounts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from gog_bridge.domain.commands import Account, build_run_request
from gog_bridge.domain.policy import validate_run_args
from gog_bridge.tools._errors import as_tool_errors
from gog_bridge.tools._execute import execute

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from gog_bridge.deps import ToolDeps

ACCOUNT_DESCRIPTION = (
    "Which Google account gog acts on: perso (the personal Gmail address) or work "
    "(the company address). The bridge maps the alias to the address itself."
)
ARGS_DESCRIPTION = (
    "The gog command and its flags as separate argv entries, without the leading 'gog' "
    'and without --account, for example ["gmail", "search", "is:unread", "--json"]. '
    "Prefer --json for anything you need to read back. Use gog_help to discover flags."
)
STDIN_DESCRIPTION = (
    "Text fed to gog on standard input, for commands that read a body or a file from "
    "stdin. Leave unset when the command needs no input."
)


def register(mcp: FastMCP, deps: ToolDeps) -> None:
    """Register gog_run on the server."""

    @mcp.tool
    @as_tool_errors
    async def gog_run(
        account: Annotated[Account, Field(description=ACCOUNT_DESCRIPTION)],
        args: Annotated[list[str], Field(description=ARGS_DESCRIPTION)],
        stdin: Annotated[str | None, Field(description=STDIN_DESCRIPTION)] = None,
    ) -> str:
        """Run one gog command on the chosen account and return its output.

        The command runs as `gog --account <address> --no-input <args...>`, so it
        never prompts. The result is a text report: `exit_code: N`, then the
        captured stdout under `--- stdout ---` and stderr under `--- stderr ---`.
        A non-zero exit comes back as a tool error carrying the same report, so
        read stderr there for gog's own message. Long outputs are truncated at
        200000 bytes of stdout and 20000 bytes of stderr, with a marker.

        The bridge refuses, before running anything: the administrative commands
        auth (and its aliases login, logout, status), config, mcp, batch, schema
        and backup; any --account or -a flag,
        --home, --client, --access-token, --quota-project, --enable-commands and
        --disable-commands; empty args; and arguments containing a newline.

        Args:
            account: perso or work. Nothing else selects the account.
            args: The gog command line after 'gog', one argv entry per item.
            stdin: Optional text for gog's standard input.
        """
        validate_run_args(args)
        request = build_run_request(deps.exe, deps.accounts, account, args, stdin)
        return await execute(deps, request)
