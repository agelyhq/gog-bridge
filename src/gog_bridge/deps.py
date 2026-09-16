"""The dependency bundle handed to every tool at registration time.

It lives outside the tools package on purpose. Modules inside `tools/` are
discovered as tools unless their name starts with an underscore, and the
composition root should not have to import a private module to build this.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from gog_bridge.domain.accounts import Accounts
    from gog_bridge.domain.commands import CommandRunner


@dataclass(frozen=True, slots=True)
class ToolDeps:
    """Everything the tools need, built once by the composition root."""

    exe: Path
    accounts: Accounts
    runner: CommandRunner
    timeout_seconds: float
