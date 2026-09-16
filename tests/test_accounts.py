"""Scenarios for the account aliases: how GOG_BRIDGE_ACCOUNTS shapes gog_run.

Each test builds a server from a different alias list and drives it through the
MCP client: the schema the model sees, the address gog receives, and the refusal
for an alias that was never configured. Startup refusals of a malformed variable
are in test_main.py, where the entrypoint runs as a process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from conftest import PERSO, WORK, echoed, make_client, write_wrapper
from reports import report_text

if TYPE_CHECKING:
    from pathlib import Path

    from fastmcp import Client


async def _gog_run_schema(client: Client) -> dict[str, Any]:
    async with client:
        listed = await client.list_tools()
    return next(tool for tool in listed if tool.name == "gog_run").inputSchema


async def test_accounts_two_aliases_make_account_a_required_enum(fake_exe: Path) -> None:
    schema = await _gog_run_schema(make_client(fake_exe))
    account = schema["properties"]["account"]

    assert account["enum"] == ["perso", "work"]
    assert "default" not in account
    assert "account" in schema["required"]
    assert f"perso ({PERSO})" in account["description"]
    assert f"work ({WORK})" in account["description"]


async def test_accounts_single_alias_is_optional_and_defaults_to_it(fake_exe: Path) -> None:
    client = make_client(fake_exe, gog_bridge_accounts=f"seul={WORK}")

    schema = await _gog_run_schema(client)
    account = schema["properties"]["account"]
    assert account["enum"] == ["seul"]
    assert account["default"] == "seul"
    assert "account" not in schema["required"]
    assert "left out" in account["description"]

    async with client:
        result = await client.call_tool("gog_run", {"args": ["drive", "ls"]})

    assert not result.is_error
    assert echoed(report_text(result))["argv"][:3] == ["--account", WORK, "--no-input"]


async def test_accounts_aliases_are_free_names_mapped_to_their_address(fake_exe: Path) -> None:
    spec = "damien-perso=d@example.com,agely_work=w@example.com,x9=x@example.com"
    client = make_client(fake_exe, gog_bridge_accounts=spec)

    schema = await _gog_run_schema(client)
    assert schema["properties"]["account"]["enum"] == ["damien-perso", "agely_work", "x9"]

    async with client:
        result = await client.call_tool(
            "gog_run", {"account": "agely_work", "args": ["calendar", "list"]}
        )

    assert echoed(report_text(result))["argv"][1] == "w@example.com"


async def test_accounts_unknown_alias_is_refused_in_french_naming_the_valid_ones(
    tmp_path: Path,
) -> None:
    """The enum is advice to the model; the bridge itself refuses, before any spawn."""
    marker = tmp_path / "spawned.txt"
    exe = write_wrapper(tmp_path, marker=marker)

    async with make_client(exe) as client:
        result = await client.call_tool(
            "gog_run", {"account": "pro", "args": ["drive", "ls"]}, raise_on_error=False
        )

    assert result.is_error
    message = report_text(result)
    assert "Compte inconnu" in message
    assert "« pro »" in message
    assert "perso, work" in message
    assert "exit_code" not in message
    assert not marker.exists()


async def test_accounts_instructions_list_the_configured_accounts(fake_exe: Path) -> None:
    """The server instructions are the first thing a client reads about the accounts."""
    client = make_client(fake_exe, gog_bridge_accounts=f"perso={PERSO}")

    async with client:
        instructions = client.initialize_result.instructions or ""

    assert f"perso ({PERSO})" in instructions
    assert WORK not in instructions
