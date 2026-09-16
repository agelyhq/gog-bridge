"""Scenarios for the entrypoint, run as a real process: --version and a bad environment."""

from __future__ import annotations

import os
import subprocess
import sys
from importlib.metadata import version
from typing import TYPE_CHECKING

from conftest import PERSO, WORK

if TYPE_CHECKING:
    from pathlib import Path

BRIDGE_VARS = (
    "GOG_BRIDGE_EXE",
    "GOG_BRIDGE_ACCOUNT_PERSO",
    "GOG_BRIDGE_ACCOUNT_WORK",
    "GOG_BRIDGE_TIMEOUT_SECONDS",
)


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
    assert completed.stdout.strip() == f"gog-bridge {version('gog-bridge')}"


def test_main_refuses_to_start_without_the_required_variables(tmp_path: Path) -> None:
    completed = _run([], _clean_env(), tmp_path)

    assert completed.returncode != 0
    assert "gog-bridge cannot start" in completed.stderr
    for name in ("GOG_BRIDGE_EXE", "GOG_BRIDGE_ACCOUNT_PERSO", "GOG_BRIDGE_ACCOUNT_WORK"):
        assert name in completed.stderr, name


def test_main_refuses_an_exe_path_that_is_not_a_file(tmp_path: Path) -> None:
    env = _clean_env()
    env.update(
        GOG_BRIDGE_EXE=str(tmp_path / "missing" / "gog.exe"),
        GOG_BRIDGE_ACCOUNT_PERSO=PERSO,
        GOG_BRIDGE_ACCOUNT_WORK=WORK,
    )

    completed = _run([], env, tmp_path)

    assert completed.returncode != 0
    assert "GOG_BRIDGE_EXE" in completed.stderr
    assert "no file at" in completed.stderr
