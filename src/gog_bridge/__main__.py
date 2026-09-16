"""Command line entrypoint. The server speaks MCP over stdio and nothing else."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import version

from gog_bridge.config import SettingsLoadError, load_settings
from gog_bridge.server import DISTRIBUTION, create_server

CONFIGURATION_EXIT_CODE = 2


def main() -> None:
    """Start the MCP server on stdio, or exit non-zero with the reason on stderr."""
    parser = argparse.ArgumentParser(
        prog=DISTRIBUTION,
        description="MCP server exposing the gog CLI to Claude Desktop through a policy.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {version(DISTRIBUTION)}")
    parser.parse_args()

    try:
        settings = load_settings()
    except SettingsLoadError as exc:
        print(exc, file=sys.stderr)
        sys.exit(CONFIGURATION_EXIT_CODE)

    create_server(settings).run(transport="stdio")


if __name__ == "__main__":
    main()
