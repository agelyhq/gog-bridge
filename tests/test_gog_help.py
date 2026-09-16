"""Scenarios for gog_help: the --help suffix, the GOG_HELP=full environment, no account."""

from __future__ import annotations

from typing import TYPE_CHECKING

from conftest import echoed, parse_report, report_text

if TYPE_CHECKING:
    from fastmcp import Client


async def test_help_appends_help_and_sets_full_help_without_an_account(client: Client) -> None:
    async with client:
        result = await client.call_tool("gog_help", {"args": ["gmail", "send"]})

    assert not result.is_error
    assert parse_report(report_text(result))["exit_code"] == 0

    seen = echoed(report_text(result))
    assert seen["argv"] == ["gmail", "send", "--help"]
    assert seen["gog_help"] == "full"
    assert "--account" not in seen["argv"]
    assert "--no-input" not in seen["argv"]


async def test_help_with_no_args_asks_for_the_top_level_help(client: Client) -> None:
    async with client:
        result = await client.call_tool("gog_help", {})

    assert not result.is_error
    assert echoed(report_text(result))["argv"] == ["--help"]
