"""What a gog invocation looks like before and after it runs.

`CommandRequest` is built by the tools from validated input, executed by a
`CommandRunner`, and comes back as a `CommandOutcome`. The runner is a protocol
so the tools depend on nothing that spawns processes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

Account = Literal["perso", "work"]

NO_INPUT_FLAG = "--no-input"
ACCOUNT_FLAG = "--account"
HELP_FLAG = "--help"

# With GOG_HELP=full, `gog --help` expands from the top-level groups into the
# whole command tree (213 lines against 1963 on v0.40.0). A single command's
# help is the same either way and already lists the global flags.
HELP_ENV = {"GOG_HELP": "full"}

# Capture caps, in bytes. A gog JSON listing rarely exceeds a few tens of
# kilobytes; the stdout cap keeps a runaway export from flooding the context.
STDOUT_LIMIT = 200_000
STDERR_LIMIT = 20_000

# Reported when the process was killed on timeout, so it never collides with
# a real gog exit status, which is 0 or positive.
TIMEOUT_EXIT_CODE = -1


@dataclass(frozen=True, slots=True)
class Accounts:
    """The two Google accounts the bridge may act on, keyed by the tool's alias."""

    perso: str
    work: str

    def email_for(self, account: Account) -> str:
        """Return the address gog receives for a tool alias."""
        return self.perso if account == "perso" else self.work


@dataclass(frozen=True, slots=True)
class CommandRequest:
    """A fully assembled gog invocation, ready to spawn."""

    argv: tuple[str, ...]
    stdin: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    """What came back: exit code, both streams, and whether limits were hit."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    timed_out: bool = False


class CommandRunner(Protocol):
    """Runs one command to completion. The adapter layer provides the implementation."""

    async def run(self, request: CommandRequest) -> CommandOutcome:
        """Spawn the process, feed stdin, capture both streams, wait for exit."""
        ...


def build_run_request(
    exe: Path, accounts: Accounts, account: Account, args: Sequence[str], stdin: str | None
) -> CommandRequest:
    """Assemble `gog --account <email> --no-input <args...>` for the chosen account."""
    argv = (str(exe), ACCOUNT_FLAG, accounts.email_for(account), NO_INPUT_FLAG, *args)
    return CommandRequest(argv=argv, stdin=stdin)


def build_help_request(exe: Path, args: Sequence[str]) -> CommandRequest:
    """Assemble `gog <args...> --help` with the full help enabled."""
    argv = (str(exe), *args, HELP_FLAG)
    return CommandRequest(argv=argv, env=HELP_ENV)
