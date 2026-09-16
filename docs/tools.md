# Tool reference

Two tools. `gog_run` executes one gog command on one of the configured accounts, `gog_help`
prints the full help of a command. Both return one text block and never anything else; both go
through the same policy before a process exists.

## gog_run

Runs `gog --account <email> --no-input <args...>`.

| Parameter | Type | Allowed values | Default | Behaviour |
|---|---|---|---|---|
| `account` | string | one of the aliases from `GOG_BRIDGE_ACCOUNTS` | required, or the single alias when only one is configured | Which address gog acts on. The schema lists the aliases as an enum and the description names each one with its address. The bridge writes `--account <email>` itself; no argument can change it. |
| `args` | list of strings | one argv entry per item, without the leading `gog` | required, non-empty | The command line after `gog`. `["gmail", "search", "is:unread", "--json"]`, not one string with spaces. |
| `stdin` | string or null | any text | `null` | Fed to gog on standard input, for commands that read a body or a file from `-`. When null, stdin is closed, not inherited from the MCP pipe. |

With one alias configured, `account` may be omitted and defaults to it. With two or more it is
required, and an alias that is not configured is refused in French with the valid ones listed,
before anything runs.

`--no-input` is always present, so gog never waits on a prompt the model cannot see. A command
that would have asked for confirmation fails instead, with gog's own sentence in stderr, and the
model adds `-y` on the next call if that is what the person wants. See
[policy.md](policy.md) for where that line sits.

## gog_help

Runs `gog <args...> --help` with `GOG_HELP=full` in the environment.

| Parameter | Type | Allowed values | Default | Behaviour |
|---|---|---|---|---|
| `args` | list of strings | a command path, possibly empty | `[]` | `[]` prints the top-level command list; `["gmail", "send"]` prints the flags of `gmail send`. |

`GOG_HELP=full` changes one thing: `gog_help([])` prints every command of the tree, 1963 lines
on v0.40.0, where the default stops at the top-level groups after 213. A single command's help
is the same either way and already lists the global flags, `--json`, `--dry-run`, `-y`,
`--select` and `--results-only`, next to its own. No `--account` is passed, since help needs
none, and the same policy applies to `args` as on `gog_run`, except that an empty list is
allowed.

## The report

Every call returns one text block, on success and on failure:

```
exit_code: 0
--- stdout ---
{"threads": [...]}
--- stderr ---
```

Line by line: `exit_code: N` first; a `note: ...` line only when the process timed out; the
`--- stdout ---` header and the captured stdout; the `--- stderr ---` header and the captured
stderr. Both streams are decoded as UTF-8 with replacement, on every platform, so a byte that is
not UTF-8 shows as U+FFFD rather than failing the call. A trailing newline is stripped from each
stream, which is why a command that printed nothing shows the two headers back to back.

**A non-zero exit is an error result.** The same report comes back, but on the MCP error channel
(`isError: true`), so the model sees it as a failure and reads gog's message in stderr:

```
exit_code: 2
--- stdout ---
--- stderr ---
unknown flag --bogus-flag
Run with --help to see available flags
```

That is deliberate. gog's exit codes carry meaning, 1 error, 2 usage, 3 empty, 4 auth,
5 not found, 6 denied, 7 rate limited, 8 retryable, 10 config, per `gog --help` on v0.40.0,
and a model that reads `exit_code: 5` corrects its call rather than reporting success.

## Caps and timeout

| Limit | Value | What happens past it |
|---|---|---|
| stdout | 200 000 bytes | The stream is cut there and ends with `[... sortie tronquée à 200000 octets par le pont ...]`. |
| stderr | 20 000 bytes | Same, with its own figure in the marker. |
| duration | `GOG_BRIDGE_TIMEOUT_SECONDS`, 120 by default | The process is killed, the report carries `exit_code: -1` and a `note:` line in French saying gog was interrupted after N seconds, and the streams hold what arrived before the kill. |

Past a cap the bridge keeps reading and discards, so a child blocked on a full pipe still exits.
The caps count bytes before decoding, which is why the markers give byte counts. `-1` never
collides with a real gog exit status, which is 0 or positive.

## Errors that are not gog's

Four failures come from the bridge itself, each as a tool error with a French message:

`Commande refusée par la politique du pont : « auth » ...` and
`Argument refusé par la politique du pont : « --account=x » ...` when the policy stopped the call.
Nothing ran. [policy.md](policy.md) lists every rule.

`Compte inconnu : « pro » n'est pas configuré sur ce pont. Comptes disponibles : perso, work.`
when `account` names an alias that is not in `GOG_BRIDGE_ACCOUNTS`. The parameter is typed as a
string with an enum in the schema rather than as a closed type, precisely so that a wrong alias
reaches this sentence instead of a validation error in English.

`Aucun argument fourni : ...` when `args` was empty on `gog_run`.

`Impossible de lancer gog (<path>) : <reason>` when the executable existed at startup but could
not be started now: permissions, an antivirus quarantine, a file replaced since. The reason after
the colon is the operating system's.

## Worked examples

Each `args` array below was checked against gog v0.40.0 with `<command> --help` and against the
policy. They are the arrays the model sends; the bridge prepends `--account <email> --no-input`.
Ids in angle brackets come from a previous call's JSON.

**Gmail.** Read, then write.

```
["gmail", "search", "from:marc@company.com newer_than:7d", "--json", "--max", "5"]
["gmail", "thread", "get", "<threadId>", "--json"]
["gmail", "reply", "<messageId>", "--body-file", "-"]            with stdin = the reply text
["gmail", "send", "--to", "marie@company.com", "--subject", "Compte rendu", "--body-file", "-"]
["gmail", "drafts", "create", "--to", "marie@company.com", "--subject", "Brouillon", "--body", "À relire"]
```

`--body-file -` with the text in `stdin` is the shape to prefer for any body longer than a line:
an argument containing a newline is refused by the policy, and stdin carries accents and
paragraphs untouched. `gmail send --reply-all` needs `--reply-to-message-id` or `--thread-id`
with it; `gmail reply` fills the recipients from the original by itself.

**Calendar.** Find the event, then move it.

```
["calendar", "events", "primary", "--from", "2026-09-17", "--to", "2026-09-18", "--json"]
["calendar", "create", "primary", "--summary", "Point Marc", "--from", "2026-09-17T10:00:00+02:00", "--to", "2026-09-17T10:30:00+02:00", "--attendees", "marc@company.com", "--send-updates", "all"]
["calendar", "update", "primary", "<eventId>", "--from", "2026-09-18T10:00:00+02:00", "--to", "2026-09-18T10:30:00+02:00", "--send-updates", "all"]
["calendar", "freebusy", "--from", "tomorrow", "--to", "monday", "--json"]
["calendar", "delete", "primary", "<eventId>", "--send-updates", "all"]
```

`calendar update` passes the policy although `update` is on the refused list, because the
refused word is the command in first position and here it is a subcommand of `calendar`.
`--send-updates` defaults to `none`, so an event created or moved without it tells nobody.

**Drive.** Locate by text, then share.

```
["drive", "search", "Q3 deck", "--json", "--max", "5"]
["drive", "ls", "--parent", "<folderId>", "--json"]
["drive", "share", "<fileId>", "--to", "user", "--email", "marie@company.com", "--role", "commenter", "--notify"]
["drive", "upload", "/home/you/report.pdf", "--parent", "<folderId>"]
["drive", "delete", "<fileId>"]
```

`drive delete` moves to the trash; with `--permanent` gog asks for a confirmation that
`--no-input` turns into a refusal, `exit_code: 2` and
`refusing to permanently delete drive file <fileId> without --force (non-interactive)`, until
`-y` is added. The upload path is a path on the machine where gog runs, which under Cowork is the
host and not the VM.

**Sheets and Docs.** Ranges in A1 notation, documents as plain text.

```
["sheets", "get", "<spreadsheetId>", "2026!A1:F40", "--json"]
["sheets", "append", "<spreadsheetId>", "Dépenses!A:D", "2026-09-16", "Bayard", "encart", "1200"]
["docs", "cat", "<docId>"]
```

`sheets append` takes the values as positional arguments after the range, or as a JSON 2D array
through `--values-json`. `docs cat` prints the document as text, `--max-bytes` defaulting to
2 000 000, which is ten times the bridge's stdout cap: pass a smaller `--max-bytes` or read a
single `--tab` on a long document.

**Contacts and Tasks.**

```
["contacts", "search", "Bayard", "--json"]
["tasks", "lists", "list", "--json"]
["tasks", "add", "<tasklistId>", "--title", "Relancer Marie", "--due", "2026-09-20"]
```

**Narrowing output.** `--json`, `--results-only` and `--select` are global flags, so they go
on any command. `--max` and `--fields` exist on most listing commands, each with its own
default (`contacts search` caps at 50), and are absent on a few such as `docs cat`, so check
with `gog_help` first:

```
["gmail", "search", "is:unread", "--json", "--results-only", "--select", "id,subject,from"]
["drive", "ls", "--all", "--json", "--max", "50"]
["calendar", "events", "--week", "--json", "--fields", "summary,start,end"]
```

`--select` and `--fields` are applied by gog before anything reaches the bridge, so the
200 000 byte cap sees only what is left. `--dry-run` (`-n`) on a writing
command prints what gog would do and exits 0, which is a cheap way to show the person the exact
action before asking for the word.

**Reading without risk.** `--readonly` is a global flag on v0.40.0 that makes gog refuse any
mutating request at runtime, and `--gmail-no-send` blocks sends alone. Both pass the policy,
since they narrow rather than widen, and a skill that wants a guaranteed read can put one of them
on every call it makes in that mode.

## Next

[policy.md](policy.md) for the rules these examples were checked against,
[troubleshooting.md](troubleshooting.md) for each error above worked through by symptom.
