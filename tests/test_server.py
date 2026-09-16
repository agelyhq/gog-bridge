"""Scenarios for the server surface itself: which tools exist and what they accept.

The schema is the first line of validation: an account outside the enum is
refused by the client's own MCP library before this server sees it. These tests
pin what the two schemas advertise so a drift shows up here first.
"""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP

from gog_bridge import tools
from gog_bridge.deps import ToolDeps
from gog_bridge.domain.accounts import Accounts
from gog_bridge.tools import register_all_tools

if TYPE_CHECKING:
    from pathlib import Path

    from fastmcp import Client

EXPECTED_TOOLS = {"gog_run", "gog_help"}


async def _tools(client: Client) -> dict[str, Any]:
    async with client:
        listed = await client.list_tools()
    return {tool.name: tool for tool in listed}


async def test_server_exposes_exactly_two_tools(client: Client) -> None:
    listed = await _tools(client)

    assert set(listed) == EXPECTED_TOOLS


async def test_server_gog_run_schema_takes_account_args_and_optional_stdin(client: Client) -> None:
    schema = (await _tools(client))["gog_run"].inputSchema

    assert set(schema["required"]) == {"account", "args"}
    assert schema["properties"]["account"]["enum"] == ["perso", "work"]
    assert schema["properties"]["args"]["type"] == "array"
    assert schema["properties"]["args"]["items"] == {"type": "string"}
    assert "stdin" in schema["properties"]
    assert "stdin" not in schema["required"]


async def test_server_gog_help_schema_takes_optional_args_only(client: Client) -> None:
    schema = (await _tools(client))["gog_help"].inputSchema

    assert list(schema["properties"]) == ["args"]
    assert not schema.get("required")
    assert schema["properties"]["args"]["type"] == "array"
    assert schema["properties"]["args"]["default"] == []


async def test_server_descriptions_name_the_policy_and_the_report_shape(client: Client) -> None:
    """The docstrings are what the calling model reads; they must say what is refused."""
    listed = await _tools(client)

    run_description = listed["gog_run"].description or ""
    assert "exit_code" in run_description
    assert "--no-input" in run_description
    for refused in ("auth", "--account", "--home", "--access-token", "newline"):
        assert refused in run_description, refused
    assert "GOG_HELP=full" in (listed["gog_help"].description or "")


async def test_server_registry_rejects_a_module_without_register(
    tmp_path: Path, fake_exe: Path
) -> None:
    """A file dropped in the tools package must register itself or fail at startup."""
    (tmp_path / "probe_not_a_tool.py").write_text('"""A module that forgot to register."""\n')
    importlib.invalidate_caches()
    tools.__path__.append(str(tmp_path))
    deps = ToolDeps(
        exe=fake_exe,
        accounts=Accounts.parse("perso=perso@example.com"),
        runner=MagicMock(),
        timeout_seconds=1,
    )

    try:
        with pytest.raises(RuntimeError, match="has no register"):
            register_all_tools(FastMCP(name="probe"), deps)
    finally:
        tools.__path__.remove(str(tmp_path))
        sys.modules.pop("gog_bridge.tools.probe_not_a_tool", None)
        importlib.invalidate_caches()
