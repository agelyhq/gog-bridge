"""Scenarios for the entrypoint, run as a real process: --version and a bad environment."""

from __future__ import annotations

import os
import subprocess
import sys
from importlib.metadata import version
from typing import TYPE_CHECKING

import pytest
from conftest import ACCOUNTS_SPEC

if TYPE_CHECKING:
    from pathlib import Path

BRIDGE_VARS = ("GOG_BRIDGE_EXE", "GOG_BRIDGE_ACCOUNTS", "GOG_BRIDGE_TIMEOUT_SECONDS")

# Values of GOG_BRIDGE_ACCOUNTS that must stop the server, with the words the
# operator reads on stderr.
MALFORMED_ACCOUNTS = [
    pytest.param("perso=a@example.com,perso=b@example.com", "appears twice", id="duplicate-alias"),
    pytest.param("perso=a@example.com,", "entry 2 is empty", id="trailing-comma"),
    pytest.param("perso", "not of the form alias=email", id="no-equals"),
    pytest.param("Perso=a@example.com", "must match", id="uppercase-alias"),
    pytest.param("perso=example.com", "has no @", id="address-without-at"),
]


def _run(args: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "gog_bridge", *args],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )


def _clean_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in BRIDGE_VARS}


def test_main_version_prints_name_and_version(tmp_path: Path) -> None:
    completed = _run(["--version"], _clean_env(), tmp_path)

    assert completed.returncode == 0
    assert completed.stdout.strip() == f"mcp-gog-bridge {version('mcp-gog-bridge')}"


def test_main_refuses_to_start_without_the_required_variables(tmp_path: Path) -> None:
    completed = _run([], _clean_env(), tmp_path)

    assert completed.returncode != 0
    assert "mcp-gog-bridge cannot start" in completed.stderr
    for name in ("GOG_BRIDGE_EXE", "GOG_BRIDGE_ACCOUNTS"):
        assert name in completed.stderr, name


def test_main_refuses_an_exe_path_that_is_not_a_file(tmp_path: Path) -> None:
    env = _clean_env()
    env.update(
        GOG_BRIDGE_EXE=str(tmp_path / "missing" / "gog.exe"), GOG_BRIDGE_ACCOUNTS=ACCOUNTS_SPEC
    )

    completed = _run([], env, tmp_path)

    assert completed.returncode != 0
    assert "GOG_BRIDGE_EXE" in completed.stderr
    assert "no file at" in completed.stderr


def test_main_refuses_an_empty_account_list(tmp_path: Path) -> None:
    """An empty variable counts as absent: the message asks for the pairs."""
    env = _clean_env()
    env.update(GOG_BRIDGE_EXE=sys.executable, GOG_BRIDGE_ACCOUNTS="")

    completed = _run([], env, tmp_path)

    assert completed.returncode == 2
    assert "GOG_BRIDGE_ACCOUNTS: Field required" in completed.stderr
    assert "alias=email" in completed.stderr


@pytest.mark.parametrize(("spec", "expected_in_stderr"), MALFORMED_ACCOUNTS)
def test_main_refuses_a_malformed_account_list_naming_the_problem(
    tmp_path: Path, spec: str, expected_in_stderr: str
) -> None:
    env = _clean_env()
    env.update(GOG_BRIDGE_EXE=sys.executable, GOG_BRIDGE_ACCOUNTS=spec)

    completed = _run([], env, tmp_path)

    assert completed.returncode == 2
    assert "GOG_BRIDGE_ACCOUNTS" in completed.stderr
    assert expected_in_stderr in completed.stderr
