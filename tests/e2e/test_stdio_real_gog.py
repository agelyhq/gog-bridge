"""The installed bridge over stdio, against the real gog v0.40.0, with no credentials.

Each test is one client session: the console script starts, the handshake runs,
one or two tools are called, the process exits. The isolated configuration holds
no OAuth client and no token, so every command that would talk to Google fails
inside gog before any request leaves the machine; what the tests check is that
the failure comes back as a report the model can read, and that the policy and
the help path work on the real binary rather than on the fake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from reports import parse_report, report_text

if TYPE_CHECKING:
    from pathlib import Path

    from fastmcp import Client

    from e2e.conftest import ToolCall

GOG_VERSION = "v0.40.0"


async def test_e2e_tools_list_shows_both_tools_with_the_account_enum(client: Client) -> None:
    listed = {tool.name: tool for tool in await client.list_tools()}

    assert set(listed) == {"gog_run", "gog_help"}
    schema = listed["gog_run"].inputSchema
    assert schema["properties"]["account"]["enum"] == ["perso", "work"]
    assert set(schema["required"]) == {"account", "args"}
    assert "perso (perso@example.invalid)" in schema["properties"]["account"]["description"]


async def test_e2e_version_runs_through_the_account_and_no_input_prefix(call: ToolCall) -> None:
    result = await call("gog_run", {"account": "work", "args": ["--version"]})

    assert not result.is_error, report_text(result)
    report = parse_report(report_text(result))
    assert report["exit_code"] == 0
    assert GOG_VERSION in report["stdout"]


async def test_e2e_help_prints_the_full_flag_list_of_gmail_send(call: ToolCall) -> None:
    result = await call("gog_help", {"args": ["gmail", "send"]})

    assert not result.is_error, report_text(result)
    report = parse_report(report_text(result))
    assert report["exit_code"] == 0
    assert "--to" in report["stdout"]


async def test_e2e_auth_list_is_refused_by_the_policy(call: ToolCall) -> None:
    result = await call("gog_run", {"account": "work", "args": ["auth", "list"]})

    assert result.is_error
    message = report_text(result)
    assert "refusée par la politique" in message
    assert "auth" in message
    assert "exit_code" not in message


async def test_e2e_short_account_flag_is_refused_by_the_policy(call: ToolCall) -> None:
    result = await call(
        "gog_run", {"account": "work", "args": ["gmail", "search", "-a", "perso", "x"]}
    )

    assert result.is_error
    message = report_text(result)
    assert "refusé" in message
    assert "-a" in message
    assert "exit_code" not in message


async def test_e2e_unknown_alias_is_refused_in_french(call: ToolCall) -> None:
    result = await call("gog_run", {"account": "pro", "args": ["drive", "ls"]})

    assert result.is_error
    message = report_text(result)
    assert "Compte inconnu" in message
    assert "perso, work" in message


async def test_e2e_drive_ls_without_credentials_is_a_readable_failure(
    call: ToolCall, tmp_path: Path
) -> None:
    """Nothing reaches Google: gog stops on the missing OAuth client and says so on stderr.

    The path gog names for the missing file must sit under the isolated home,
    which is the proof that the user's own gog configuration was never read.
    """
    result = await call("gog_run", {"account": "perso", "args": ["drive", "ls"]})

    assert result.is_error
    report = parse_report(report_text(result))
    assert report["exit_code"] != 0
    assert report["stderr"].strip(), report_text(result)
    assert str(tmp_path / "home") in report["stderr"], report["stderr"]


async def test_e2e_gmail_send_without_credentials_fails_closed(call: ToolCall) -> None:
    """The send path must fail the same way: a non-zero exit, no prompt, no hang."""
    result = await call(
        "gog_run",
        {
            "account": "perso",
            "args": [
                "gmail",
                "send",
                "--to",
                "nobody@example.invalid",
                "--subject",
                "s",
                "--body",
                "b",
            ],
        },
    )

    assert result.is_error
    report = parse_report(report_text(result))
    assert report["exit_code"] != 0
    assert report["stderr"].strip(), report_text(result)
