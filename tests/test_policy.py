"""Scenarios for the policy: every refusal, and the proof that nothing was spawned.

The server for these tests points at a wrapper that writes a marker file before
running the fake gog. A refusal is only a refusal if that file never appears.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import make_client, write_wrapper
from reports import report_text

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from fastmcp import Client

REFUSED_RUN_ARGS = [
    pytest.param(["auth", "list"], "auth", id="auth-first-arg"),
    pytest.param(["login", "x@example.com"], "login", id="login-alias-of-auth-add"),
    pytest.param(["logout", "x@example.com"], "logout", id="logout-alias-of-auth-remove"),
    pytest.param(["status"], "status", id="status-alias-of-auth-status"),
    pytest.param(["config", "show"], "config", id="config-first-arg"),
    pytest.param(["mcp"], "mcp", id="mcp-first-arg"),
    pytest.param(["batch", "run"], "batch", id="batch-first-arg"),
    pytest.param(["schema"], "schema", id="schema-first-arg"),
    pytest.param(["backup", "create"], "backup", id="backup-first-arg"),
    pytest.param(["update"], "update", id="update-self-update-of-the-binary"),
    pytest.param(["--json", "auth", "list"], "auth", id="auth-behind-long-flag"),
    pytest.param(["-j", "config", "get"], "config", id="config-behind-short-flag"),
    pytest.param(["--color", "auto", "auth", "list"], "auth", id="auth-behind-flag-value"),
    pytest.param(["-j", "--select", "x", "backup", "create"], "backup", id="behind-select"),
    pytest.param(["gmail", "search", "--home=/tmp/x"], "--home=/tmp/x", id="home-flag"),
    pytest.param(["gmail", "search", "--client", "x"], "--client", id="client-flag"),
    pytest.param(["gmail", "search", "--access-token=t"], "--access-token=t", id="token-flag"),
    pytest.param(["gmail", "search", "--quota-project", "p"], "--quota-project", id="quota"),
    pytest.param(["gmail", "search", "--account", "x"], "--account", id="account-flag"),
    pytest.param(["gmail", "search", "--account=x"], "--account=x", id="account-flag-eq"),
    pytest.param(["gmail", "--enable-commands=gmail"], "--enable-commands", id="enable"),
    pytest.param(["gmail", "--disable-commands=x"], "--disable-commands", id="disable"),
    pytest.param(["gmail", "search", "-a", "x"], "-a", id="short-a"),
    pytest.param(["gmail", "search", "-a=x"], "-a=x", id="short-a-eq"),
    pytest.param(["gmail", "search", "-ax"], "-ax", id="short-a-glued"),
    pytest.param(["gmail", "search", "-ja"], "-ja", id="short-cluster-ja"),
    pytest.param(["gmail", "search", "-jaX"], "-jaX", id="short-cluster-jaX"),
    pytest.param(["gmail", "search", "is:unread\nauth"], "saut de ligne", id="newline"),
]

ALLOWED_RUN_ARGS = [
    pytest.param(["gmail", "search", "-j"], id="short-j"),
    pytest.param(["gmail", "search", "-jp"], id="short-cluster-jp"),
    pytest.param(["gmail", "search", "-n5a"], id="short-value-with-a"),
    pytest.param(["gmail", "search", "--max", "-1"], id="negative-number"),
    pytest.param(["gmail", "search", "-"], id="lone-dash"),
    pytest.param(["gmail", "search", "authentication"], id="word-containing-auth"),
    pytest.param(["drive", "ls", "--parent", "auth"], id="auth-not-first"),
    pytest.param(["calendar", "update", "primary", "e1", "--summary", "x"], id="update-not-first"),
    pytest.param(["--json", "gmail", "search", "auth"], id="flag-then-ordinary-command"),
    pytest.param(["--color", "never", "drive", "ls"], id="flag-value-then-ordinary-command"),
]


@pytest.fixture
def marker(tmp_path: Path) -> Path:
    return tmp_path / "spawned.txt"


@pytest.fixture
async def tripwire(tmp_path: Path, marker: Path) -> AsyncIterator[Client]:
    exe = write_wrapper(tmp_path, marker=marker)
    async with make_client(exe) as client:
        yield client


@pytest.mark.parametrize(("args", "expected_in_message"), REFUSED_RUN_ARGS)
async def test_policy_refuses_before_spawning(
    tripwire: Client, marker: Path, args: list[str], expected_in_message: str
) -> None:
    result = await tripwire.call_tool(
        "gog_run", {"account": "work", "args": args}, raise_on_error=False
    )

    assert result.is_error
    message = report_text(result)
    assert "refusé" in message
    assert expected_in_message in message
    assert "exit_code" not in message
    assert not marker.exists()


async def test_policy_refuses_empty_args_for_gog_run(tripwire: Client, marker: Path) -> None:
    result = await tripwire.call_tool(
        "gog_run", {"account": "work", "args": []}, raise_on_error=False
    )

    assert result.is_error
    assert "Aucun argument fourni" in report_text(result)
    assert not marker.exists()


@pytest.mark.parametrize("args", ALLOWED_RUN_ARGS)
async def test_policy_lets_ordinary_flags_through(
    tripwire: Client, marker: Path, args: list[str]
) -> None:
    """The refusal rules must not eat legitimate short flags or words."""
    result = await tripwire.call_tool("gog_run", {"account": "work", "args": args})

    assert not result.is_error
    assert marker.exists()


async def test_policy_applies_to_gog_help_too(tripwire: Client, marker: Path) -> None:
    result = await tripwire.call_tool("gog_help", {"args": ["auth", "add"]}, raise_on_error=False)

    assert result.is_error
    assert "auth" in report_text(result)
    assert not marker.exists()
