"""Environment-based configuration.

Read from the process environment only. An MCP server started by Claude Desktop
has no working directory worth trusting, so no .env file is consulted: the env
block of the client's config is the complete source. Every variable is prefixed
GOG_BRIDGE_.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from gog_bridge.domain.accounts import EXAMPLE, Accounts, AccountsParseError

DEFAULT_TIMEOUT_SECONDS = 120.0

ENV_EXE = "GOG_BRIDGE_EXE"
ENV_ACCOUNTS = "GOG_BRIDGE_ACCOUNTS"
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
    # NoDecode keeps pydantic-settings from running json.loads on the value
    # before the validator sees it, which it does for any non-scalar field.
    accounts: Annotated[Accounts, NoDecode] = Field(alias="gog_bridge_accounts")
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

    @field_validator("accounts", mode="before")
    @classmethod
    def _accounts_from_alias_email_pairs(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return Accounts.parse(value)
        except AccountsParseError as exc:
            raise ValueError(str(exc)) from exc


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
        f"Required: {ENV_EXE} (absolute path of gog.exe), {ENV_ACCOUNTS} (alias=email pairs "
        f"separated by commas, for example {EXAMPLE}). Optional: {ENV_TIMEOUT_SECONDS} "
        f"(default {DEFAULT_TIMEOUT_SECONDS:g})."
    )
    return "\n".join(lines)
