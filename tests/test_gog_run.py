"""Scenarios for gog_run, driven through the MCP client into a real subprocess.

Each test runs the whole path: client, server, policy, asyncio runner, the fake
gog behind its platform wrapper, and the report back. Refusals have their own
file, test_policy.py.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from conftest import PERSO, WORK, echoed, make_client, parse_report, report_text

from gog_bridge.domain.commands import STDERR_LIMIT, STDOUT_LIMIT

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from fastmcp import Client


async def test_run_perso_builds_the_account_no_input_argv(client: Client) -> None:
    async with client:
        result = await client.call_tool(
            "gog_run", {"account": "perso", "args": ["gmail", "search", "is:unread", "--json"]}
        )

    assert not result.is_error
    report = parse_report(report_text(result))
    assert report["exit_code"] == 0
    assert report["note"] is None
    assert report["stderr"] == "fake gog: done"

    seen = echoed(report_text(result))
    assert seen["argv"] == [
        "--account",
        PERSO,
        "--no-input",
        "gmail",
        "search",
        "is:unread",
        "--json",
    ]
    assert seen["stdin"] == ""
    assert seen["gog_help"] is None


async def test_run_work_maps_to_the_work_address(client: Client) -> None:
    async with client:
        result = await client.call_tool(
            "gog_run", {"account": "work", "args": ["calendar", "list"]}
        )

    assert echoed(report_text(result))["argv"][:3] == ["--account", WORK, "--no-input"]


async def test_run_delivers_stdin_to_the_process(client: Client) -> None:
    body = "Bonjour,\n\nCeci est le corps du message.\nÀ bientôt\n"

    async with client:
        result = await client.call_tool(
            "gog_run",
            {"account": "work", "args": ["gmail", "send", "--body-file", "-"], "stdin": body},
        )

    assert echoed(report_text(result))["stdin"] == body


async def test_run_non_zero_exit_is_an_error_result_carrying_the_report(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model must read exit code, stdout and stderr even when gog fails."""
    monkeypatch.setenv("FAKE_GOG_EXIT", "3")

    async with client:
        result = await client.call_tool(
            "gog_run", {"account": "perso", "args": ["drive", "ls"]}, raise_on_error=False
        )

    assert result.is_error
    text = report_text(result)
    assert "exit_code: 3" in text
    report = parse_report(text)
    assert report["exit_code"] == 3
    assert report["stderr"] == "fake gog: done"
    assert echoed(text)["argv"][-2:] == ["drive", "ls"]


async def test_run_truncates_stdout_at_the_cap_with_a_french_marker(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GOG_STDOUT_BYTES", "300000")

    async with client:
        result = await client.call_tool("gog_run", {"account": "perso", "args": ["drive", "ls"]})

    assert not result.is_error
    report = parse_report(report_text(result))
    stdout = report["stdout"]
    marker = f"[... sortie tronquée à {STDOUT_LIMIT} octets par le pont ...]"
    assert stdout.endswith(marker)
    kept = stdout.removesuffix("\n" + marker)
    assert len(kept.encode("utf-8")) == STDOUT_LIMIT
    assert report["stderr"] == "fake gog: done"


async def test_run_truncates_stderr_at_its_own_cap_with_a_french_marker(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GOG_STDERR_BYTES", "30000")

    async with client:
        result = await client.call_tool("gog_run", {"account": "perso", "args": ["drive", "ls"]})

    assert not result.is_error
    report = parse_report(report_text(result))
    stderr = report["stderr"]
    marker = f"[... sortie tronquée à {STDERR_LIMIT} octets par le pont ...]"
    assert stderr.endswith(marker)
    kept = stderr.removesuffix("\n" + marker)
    assert kept.startswith("fake gog: done\n")
    assert len(kept.encode("utf-8")) == STDERR_LIMIT
    assert "tronquée" not in report["stdout"]


async def test_run_replaces_invalid_utf8_instead_of_crashing(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gog on Windows can emit bytes that are not UTF-8; the report carries U+FFFD for them."""
    monkeypatch.setenv("FAKE_GOG_RAW_BYTES", "fffe")

    async with client:
        result = await client.call_tool("gog_run", {"account": "perso", "args": ["drive", "ls"]})

    assert not result.is_error
    report = parse_report(report_text(result))
    assert report["stdout"].endswith("��")
    assert report["stderr"] == "fake gog: done\n��"
    assert echoed(report_text(result))["argv"][-2:] == ["drive", "ls"]


async def test_run_timeout_kills_the_process_and_reports_minus_one(
    fake_exe: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GOG_SLEEP_MS", "10000")

    started = time.monotonic()
    async with make_client(fake_exe, gog_bridge_timeout_seconds=0.5) as client:
        result = await client.call_tool(
            "gog_run", {"account": "perso", "args": ["drive", "ls"]}, raise_on_error=False
        )
    elapsed = time.monotonic() - started

    assert elapsed < 2, elapsed
    assert result.is_error
    report = parse_report(report_text(result))
    assert report["exit_code"] == -1
    assert report["note"] == (
        "note: Délai dépassé : gog a été interrompu après 0.5 s sans terminer. "
        "La sortie ci-dessous est celle reçue avant l'interruption."
    )
