"""Fixtures for the end-to-end tier: the installed console script against the real gog.

The bridge starts as Claude Desktop starts it, the `gog-bridge` executable of
this environment on stdio, and the client is fastmcp's StdioTransport. The gog
it points at is the real v0.40.0 binary named by GOG_BRIDGE_E2E_GOG, usually put
there by scripts/fetch_gog.py. Every directory gog could read a configuration or
a credential from is redirected under the test's tmp_path, on POSIX and on
Windows alike, so no user account is touched and nothing reaches Google.

Without GOG_BRIDGE_E2E_GOG the whole directory is skipped, with the reason.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    ToolCall = Callable[[str, dict[str, Any]], Awaitable[Any]]

E2E_GOG_ENV = "GOG_BRIDGE_E2E_GOG"
SKIP_REASON = (
    f"{E2E_GOG_ENV} does not name an existing gog binary; "
    "run `make e2e`, or scripts/fetch_gog.py and export the path it prints"
)
CONSOLE_SCRIPT = "gog-bridge"

PERSO = "perso@example.invalid"
WORK = "work@example.invalid"
ACCOUNTS_SPEC = f"perso={PERSO},work={WORK}"

# The bridge's own timeout stays at its default of 120 s; a call that gets
# anywhere near it means gog hung on a prompt, which --no-input must prevent.
CALL_BUDGET_SECONDS = 30

HERE = Path(__file__).parent


def _real_gog() -> Path | None:
    value = os.environ.get(E2E_GOG_ENV)
    if not value or not Path(value).is_file():
        return None
    return Path(value).resolve()


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Every test under this directory is e2e, and all of them skip without a real gog."""
    skip = None if _real_gog() else pytest.mark.skip(reason=SKIP_REASON)
    for item in items:
        if HERE not in item.path.parents:
            continue
        item.add_marker(pytest.mark.e2e)
        if skip is not None:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def gog_exe() -> Path:
    gog = _real_gog()
    assert gog is not None, SKIP_REASON
    return gog


@pytest.fixture(scope="session")
def bridge_command() -> str:
    """The console script installed next to this interpreter, as Claude Desktop would run it."""
    found = shutil.which(CONSOLE_SCRIPT, path=str(Path(sys.executable).parent))
    if found is None:
        pytest.fail(f"no {CONSOLE_SCRIPT} next to {sys.executable}; run `uv sync --all-extras`")
    return found


def isolated_environment(root: Path, gog_exe: Path) -> dict[str, str]:
    """The env block of the bridge process, with every user directory moved under `root`.

    The mcp stdio client starts from a short allowlist of inherited variables
    (HOME and PATH on POSIX, APPDATA, LOCALAPPDATA, USERPROFILE and the system
    ones on Windows) and layers this dict on top, so the developer's own
    GOG_* variables never reach the bridge, and the directories gog resolves
    through os.UserHomeDir, os.UserConfigDir and os.UserCacheDir all point at
    `root`. Both families are set on every platform; the unused ones are inert.
    """
    home = root / "home"
    home.mkdir()
    return {
        "GOG_BRIDGE_EXE": str(gog_exe),
        "GOG_BRIDGE_ACCOUNTS": ACCOUNTS_SPEC,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_STATE_HOME": str(home / ".local" / "state"),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
    }


@pytest.fixture
async def client(tmp_path: Path, gog_exe: Path, bridge_command: str) -> AsyncIterator[Client]:
    """One bridge process per test, gone when the session closes."""
    transport = StdioTransport(
        command=bridge_command,
        args=[],
        env=isolated_environment(tmp_path, gog_exe),
        cwd=str(tmp_path),
        keep_alive=False,
    )
    async with Client(transport) as connected:
        yield connected


@pytest.fixture
def call(client: Client) -> ToolCall:
    """Call a tool on the connected bridge, keep error results, and time the call."""

    async def _call(name: str, arguments: dict[str, Any]) -> Any:
        started = time.monotonic()
        result = await client.call_tool(name, arguments, raise_on_error=False)
        elapsed = time.monotonic() - started
        assert elapsed < CALL_BUDGET_SECONDS, f"{name} took {elapsed:.1f} s"
        return result

    return _call
