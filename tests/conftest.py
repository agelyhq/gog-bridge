"""Shared fixtures for the MCP test suite.

Nothing here touches the network, and nothing replaces the runner: every test
spawns a real process through `AsyncioProcessRunner`, so the subprocess code is
exercised on every OS the CI matrix runs. The external dependency, the gog
executable, is `fake_gog.py` behind a platform wrapper that plays the role of
`GOG_BRIDGE_EXE`.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastmcp import Client, FastMCP

from gog_bridge.config import Settings
from gog_bridge.server import create_server

if TYPE_CHECKING:
    from collections.abc import Iterator

PERSO = "perso@example.com"
WORK = "work@example.com"

FAKE_GOG = Path(__file__).with_name("fake_gog.py")
FAKE_ENV_VARS = (
    "FAKE_GOG_EXIT",
    "FAKE_GOG_SLEEP_MS",
    "FAKE_GOG_STDOUT_BYTES",
    "FAKE_GOG_STDERR_BYTES",
    "FAKE_GOG_RAW_BYTES",
)


def write_wrapper(directory: Path, marker: Path | None = None) -> Path:
    """Build the file GOG_BRIDGE_EXE points at: a .cmd on Windows, a shell script elsewhere.

    The .cmd goes through cmd.exe, the shell script execs Python directly. Both
    forward every argument and the standard streams untouched. With `marker`,
    the wrapper first appends a line to that file, which is how a test proves
    that a refused call never reached the executable.
    """
    if sys.platform == "win32":
        wrapper = directory / "gog.cmd"
        lines = ["@echo off"]
        if marker is not None:
            lines.append(f'echo spawned>> "{marker}"')
        lines.append(f'"{sys.executable}" "{FAKE_GOG}" %*')
        wrapper.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
        return wrapper

    wrapper = directory / "gog"
    lines = ["#!/bin/sh"]
    if marker is not None:
        lines.append(f'echo spawned >> "{marker}"')
    lines.append(f'exec "{sys.executable}" "{FAKE_GOG}" "$@"')
    wrapper.write_text("\n".join(lines) + "\n", encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return wrapper


@pytest.fixture(scope="session")
def fake_exe(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One wrapper for the whole session; the script it runs is stateless."""
    return write_wrapper(tmp_path_factory.mktemp("gog"))


@pytest.fixture(autouse=True)
def clean_fake_env() -> Iterator[None]:
    """No FAKE_GOG_* variable leaks from one test into the next."""
    for name in FAKE_ENV_VARS:
        os.environ.pop(name, None)
    yield
    for name in FAKE_ENV_VARS:
        os.environ.pop(name, None)


def make_settings(fake_exe: Path, **overrides: Any) -> Settings:
    """Build Settings in code, bypassing the environment.

    `overrides` are the environment aliases (gog_bridge_timeout_seconds, ...), so
    a test reads like the configuration an operator would write.
    """
    return Settings(
        gog_bridge_exe=str(fake_exe),
        gog_bridge_account_perso=PERSO,
        gog_bridge_account_work=WORK,
        **overrides,
    )  # type: ignore[call-arg]


def make_client(fake_exe: Path, **overrides: Any) -> Client:
    """A client on a fresh server built from non-default settings, real runner included."""
    return Client(create_server(make_settings(fake_exe, **overrides)))


@pytest.fixture
def settings(fake_exe: Path) -> Settings:
    return make_settings(fake_exe)


@pytest.fixture
def server(settings: Settings) -> FastMCP:
    return create_server(settings)


@pytest.fixture
def client(server: FastMCP) -> Client:
    return Client(server)


def report_text(result: Any) -> str:
    """The text block a tool call returned, on success or on error."""
    return result.content[0].text


def parse_report(text: str) -> dict[str, Any]:
    """Split a report into its exit code, stdout and stderr sections."""
    head, _, rest = text.partition("--- stdout ---\n")
    stdout, _, stderr = rest.partition("--- stderr ---\n")
    exit_line = head.splitlines()[0]
    return {
        "exit_code": int(exit_line.removeprefix("exit_code: ")),
        "note": next((line for line in head.splitlines() if line.startswith("note: ")), None),
        "stdout": stdout.removesuffix("\n"),
        "stderr": stderr,
    }


def echoed(text: str) -> dict[str, Any]:
    """What fake_gog saw: the JSON object on the first stdout line of a report."""
    return json.loads(parse_report(text)["stdout"].splitlines()[0])
