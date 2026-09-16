"""The Google accounts the bridge may act on, keyed by a short alias.

The operator writes them once, as `alias=email` pairs separated by commas. The
alias is what the calling model sees and types; the address is what gog
receives. Parsing happens at startup, so a typo stops the server with a message
instead of surfacing on the first tool call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gog_bridge.domain import messages
from gog_bridge.domain.errors import UnknownAccountError

ALIAS_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
PAIR_SEPARATOR = ","
ALIAS_EMAIL_SEPARATOR = "="

EXAMPLE = "perso=me@gmail.com,work=me@company.com"


class AccountsParseError(ValueError):
    """The alias=email list cannot be used. Operator-facing, in English."""


@dataclass(frozen=True, slots=True)
class Accounts:
    """Alias to address, in the order the operator wrote them.

    A builtin dict rather than a Mapping so pydantic can hold the value as a
    settings field without a runtime import in this module.
    """

    by_alias: dict[str, str]

    @classmethod
    def parse(cls, spec: str) -> Accounts:
        """Read `alias=email,alias=email` and refuse anything ambiguous.

        Refused: an empty list, an entry without `=`, an alias outside
        `ALIAS_PATTERN`, an address that is empty or has no `@`, and an alias
        given twice. The message names the offending entry.
        """
        by_alias: dict[str, str] = {}
        for position, raw_entry in enumerate(spec.split(PAIR_SEPARATOR), start=1):
            entry = raw_entry.strip()
            if not entry:
                raise AccountsParseError(f"entry {position} is empty; expected {EXAMPLE}")
            alias, separator, email = entry.partition(ALIAS_EMAIL_SEPARATOR)
            alias, email = alias.strip(), email.strip()
            if not separator:
                raise AccountsParseError(f"entry '{entry}' is not of the form alias=email")
            if not ALIAS_PATTERN.match(alias):
                raise AccountsParseError(
                    f"alias '{alias}' must match {ALIAS_PATTERN.pattern}: lowercase letters, "
                    "digits, _ and -, starting with a letter, 32 characters at most"
                )
            if "@" not in email:
                raise AccountsParseError(f"address '{email}' for alias '{alias}' has no @")
            if alias in by_alias:
                raise AccountsParseError(f"alias '{alias}' appears twice")
            by_alias[alias] = email
        return cls(by_alias=by_alias)

    @property
    def aliases(self) -> tuple[str, ...]:
        return tuple(self.by_alias)

    @property
    def default_alias(self) -> str | None:
        """The alias a call may leave out: only when there is exactly one."""
        return self.aliases[0] if len(self.by_alias) == 1 else None

    def email_for(self, alias: str) -> str:
        """The address gog receives for an alias, or a French refusal naming the valid ones."""
        try:
            return self.by_alias[alias]
        except KeyError:
            raise UnknownAccountError(
                messages.UNKNOWN_ACCOUNT.format(alias=alias, aliases=", ".join(self.aliases))
            ) from None

    def describe(self) -> str:
        """`perso (me@gmail.com), work (me@company.com)`, for descriptions the model reads."""
        return ", ".join(f"{alias} ({email})" for alias, email in self.by_alias.items())
