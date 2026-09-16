"""Every sentence the calling model reads, in French.

The model driving this server works in French for a French user, and a refusal
it can quote verbatim saves a translation round. Nothing else in the code base is
in French: these constants are the whole list, so a wording change happens here.
"""

from __future__ import annotations

REFUSED_COMMAND = (
    "Commande refusée par la politique du pont : « {command} » relève de l'administration "
    "locale de gog (auth et ses alias login, logout et status, config, mcp, batch, schema, "
    "backup, update) et n'est pas accessible d'ici."
)

REFUSED_FLAG = (
    "Argument refusé par la politique du pont : « {arg} » change le compte, l'environnement "
    "ou la liste des commandes de gog. Le compte se choisit uniquement par le paramètre "
    "account (perso ou work)."
)

REFUSED_SHORT_ACCOUNT = (
    "Argument refusé par la politique du pont : « {arg} » contient le drapeau court -a "
    "(compte). Le compte se choisit uniquement par le paramètre account (perso ou work)."
)

REFUSED_EMPTY = (
    "Aucun argument fourni : indiquez la commande gog à exécuter, par exemple "
    '["gmail", "search", "is:unread", "--json"].'
)

REFUSED_NEWLINE = (
    "Argument refusé par la politique du pont : « {arg} » contient un saut de ligne. "
    "Passez les textes multilignes par le paramètre stdin."
)

TIMEOUT_NOTE = (
    "Délai dépassé : gog a été interrompu après {seconds} s sans terminer. "
    "La sortie ci-dessous est celle reçue avant l'interruption."
)

TRUNCATED_MARKER = "[... sortie tronquée à {limit} octets par le pont ...]"

SPAWN_FAILED = "Impossible de lancer gog ({exe}) : {reason}"
