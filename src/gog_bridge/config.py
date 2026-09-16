"""Environment-based configuration.

Read from the process environment only. An MCP server started by Claude Desktop
has no working directory worth trusting, so no .env file is consulted: the env
block of the client's config is the complete source. Every variable is prefixed
GOG_BRIDGE_.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from gog_bridge.domain.commands import Accounts

DEFAULT_TIMEOUT_SECONDS = 120.0

ENV_EXE = "GOG_BRIDGE_EXE"
ENV_ACCOUNT_PERSO = "GOG_BRIDGE_ACCOUNT_PERSO"
ENV_ACCOUNT_WORK = "GOG_BRIDGE_ACCOUNT_WORK"
ENV_TIMEOUT_SECONDS = "GOG_BRIDGE_TIMEOUT_SECONDS"


class Settings(BaseSettings):
    """Runtime settings for the bridge."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        # Without this, building Settings in code with a field name rather than
        # its environment alias is silently ignored and the default wins.
        populate_by_name=True,
    )

    exe: Path = Field(alias="gog_bridge_exe")
    account_perso: str = Field(alias="gog_bridge_account_perso", min_length=1)
    account_work: str = Field(alias="gog_bridge_account_work", min_length=1)
    timeout_seconds: float = Field(
        default=DEFAULT_TIMEOUT_SECONDS, alias="gog_bridge_timeout_seconds", gt=0
    )

    @field_validator("exe")
    @classmethod
    def _exe_must_be_an_absolute_file(cls, value: Path) -> Path:
        # Checked at startup so a mistyped path fails once, in the client's log,
        # rather than on every tool call.
        if not value.is_absolute():
            raise ValueError(f"must be an absolute path, got {value}")
        if not value.is_file():
            raise ValueError(f"no file at {value}")
        return value

    @property
    def accounts(self) -> Accounts:
        """The two addresses gog receives, keyed by the tool alias."""
        return Accounts(perso=self.account_perso, work=self.account_work)


class SettingsLoadError(Exception):
    """The environment does not describe a runnable bridge. Message is operator-facing."""


def load_settings() -> Settings:
    """Load settings from the environment, or raise one readable error."""
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        raise SettingsLoadError(_describe(exc)) from exc


def _describe(exc: ValidationError) -> str:
    lines = ["gog-bridge cannot start: invalid environment."]
    for error in exc.errors():
        variable = str(error["loc"][0]).upper() if error["loc"] else "environment"
        lines.append(f"  {variable}: {error['msg']}")
    lines.append(
        f"Required: {ENV_EXE} (absolute path of gog.exe), {ENV_ACCOUNT_PERSO}, "
        f"{ENV_ACCOUNT_WORK}. Optional: {ENV_TIMEOUT_SECONDS} (default "
        f"{DEFAULT_TIMEOUT_SECONDS:g})."
    )
    return "\n".join(lines)
