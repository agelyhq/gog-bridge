"""gog_run: one gog command on one of the configured accounts.

This module does not defer its annotations. The `account` parameter is typed
with a value built at registration from the configured aliases, and FastMCP can
only see it if the annotation is evaluated where that value is in scope. A
deferred annotation would be the string "account_param", which nothing can
resolve; on Python 3.14 an assignment to `__annotations__` after the `def` is
lost as well, because `functools.wraps` copies `__annotate__` instead.
"""

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from gog_bridge.domain.commands import build_run_request
from gog_bridge.domain.policy import validate_run_args
from gog_bridge.tools._errors import as_tool_errors
from gog_bridge.tools._execute import execute

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from gog_bridge.deps import ToolDeps
    from gog_bridge.domain.accounts import Accounts

ACCOUNT_DESCRIPTION = (
    "Which Google account gog acts on, by alias. Configured on this bridge: {accounts}. "
    "The bridge maps the alias to the address itself.{default}"
)
ACCOUNT_DEFAULT_NOTE = " Only one account is configured, so this may be left out."
ARGS_DESCRIPTION = (
    "The gog command and its flags as separate argv entries, without the leading 'gog' "
    'and without --account, for example ["gmail", "search", "is:unread", "--json"]. '
    "Prefer --json for anything you need to read back. Use gog_help to discover flags."
)
STDIN_DESCRIPTION = (
    "Text fed to gog on standard input, for commands that read a body or a file from "
    "stdin. Leave unset when the command needs no input."
)


def account_annotation(accounts: "Accounts") -> Any:
    """The `account` parameter: an enum of the aliases, described with their addresses.

    The type stays `str` so that an alias outside the enum reaches the tool and
    is refused there in French, naming the valid ones, instead of dying in
    pydantic's English validation error.
    """
    default_note = ACCOUNT_DEFAULT_NOTE if accounts.default_alias else ""
    description = ACCOUNT_DESCRIPTION.format(accounts=accounts.describe(), default=default_note)
    return Annotated[
        str, Field(description=description, json_schema_extra={"enum": list(accounts.aliases)})
    ]


def register(mcp: "FastMCP", deps: "ToolDeps") -> None:
    """Register gog_run on the server, with `account` shaped by the configured aliases."""
    account_param = account_annotation(deps.accounts)

    # Keyword-only, so `account` can carry a default while `args` does not.
    async def gog_run(
        *,
        account: account_param,  # type: ignore[valid-type]
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
        auth (and its aliases login, logout, status), config, mcp, batch, schema,
        backup and update; any --account or -a flag,
        --home, --client, --access-token, --quota-project, --enable-commands and
        --disable-commands; empty args; and arguments containing a newline.

        Args:
            account: The alias of a configured account. Nothing else selects it.
            args: The gog command line after 'gog', one argv entry per item.
            stdin: Optional text for gog's standard input.
        """
        validate_run_args(args)
        request = build_run_request(deps.exe, deps.accounts, account, args, stdin)
        return await execute(deps, request)

    # A default cannot be conditional in the `def`, so it is set here. FastMCP
    # reads it through inspect.signature, which follows the wrapper's __wrapped__.
    if deps.accounts.default_alias is not None:
        defaults = gog_run.__kwdefaults__ or {}
        gog_run.__kwdefaults__ = {**defaults, "account": deps.accounts.default_alias}

    mcp.tool(as_tool_errors(gog_run))
