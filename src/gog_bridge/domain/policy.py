"""The policy: what a caller may not pass to gog through this bridge.

This is the security boundary of the server. The account is fixed by the tool
parameter and the caller must not be able to override it, point gog at another
configuration root, inject a token, or reach the commands that administer the
local gog installation. Every rule runs before a process is spawned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gog_bridge.domain import messages
from gog_bridge.domain.errors import PolicyError

if TYPE_CHECKING:
    from collections.abc import Sequence

# Commands that manage the local gog installation: credentials, configuration,
# the bundled MCP server, batch files, schemas and backups. None of them is a
# Google Workspace operation, and each is a way around the bridge. login, logout
# and status are top-level aliases of auth add, auth remove and auth status
# (gog v0.40.0), so they are refused with it.
FORBIDDEN_COMMANDS = frozenset(
    {"auth", "login", "logout", "status", "config", "mcp", "batch", "schema", "backup"}
)

# Matched as prefixes on the whole argument, so --account=x, --client="" and
# --enable-commands-exact are all covered by their shorter form.
FORBIDDEN_FLAG_PREFIXES = (
    "--home",
    "--client",
    "--access-token",
    "--quota-project",
    "--account",
    "--enable-commands",
    "--disable-commands",
)

SHORT_ACCOUNT_LETTER = "a"
NEWLINE_CHARS = ("\n", "\r")


def validate_run_args(args: Sequence[str]) -> None:
    """Check the arguments of gog_run. Empty args are refused: there is nothing to run."""
    if not args:
        raise PolicyError(messages.REFUSED_EMPTY)
    _validate_common(args)


def validate_help_args(args: Sequence[str]) -> None:
    """Check the arguments of gog_help. Empty args are fine: that is the top-level help."""
    _validate_common(args)


def _validate_common(args: Sequence[str]) -> None:
    for arg in args:
        if any(char in arg for char in NEWLINE_CHARS):
            raise PolicyError(messages.REFUSED_NEWLINE.format(arg=arg))

    if args and args[0] in FORBIDDEN_COMMANDS:
        raise PolicyError(messages.REFUSED_COMMAND.format(command=args[0]))

    for arg in args:
        if arg.startswith(FORBIDDEN_FLAG_PREFIXES):
            raise PolicyError(messages.REFUSED_FLAG.format(arg=arg))
        if carries_short_account_flag(arg):
            raise PolicyError(messages.REFUSED_SHORT_ACCOUNT.format(arg=arg))


def carries_short_account_flag(arg: str) -> bool:
    """Whether a single-dash argument names the -a flag in any form kong accepts.

    kong parses `-a`, `-a=x`, `-ax` and clusters such as `-ja` or `-jaX`, where
    every letter is a flag until one of them takes a value. The letters after the
    dash are scanned until the first non-letter; an `a` among them is the account
    flag, or close enough to it that refusing is the safe answer.
    """
    if len(arg) < 2 or arg[0] != "-" or arg[1] == "-":
        return False
    for char in arg[1:]:
        if not char.isalpha():
            return False
        if char == SHORT_ACCOUNT_LETTER:
            return True
    return False
