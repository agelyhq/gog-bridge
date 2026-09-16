"""Domain errors, translated to MCP tool errors by the tools layer.

The split that matters is who can act on the failure. A policy refusal or a
failed command is something the calling model can react to by changing its next
call; a spawn failure is a configuration problem it can only report.
"""

from __future__ import annotations


class GogBridgeError(Exception):
    """Base class for every failure this server reports to its caller."""


class PolicyError(GogBridgeError):
    """The arguments break a rule this server enforces before spawning gog."""


class CommandSpawnError(GogBridgeError):
    """The gog executable could not be started at all."""


class CommandFailedError(GogBridgeError):
    """gog exited non-zero or was killed on timeout. The message is the full report."""
