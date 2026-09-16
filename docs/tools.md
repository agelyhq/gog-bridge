# Tool reference

Two tools. `gog_run` executes one gog command on one of the two configured accounts,
`gog_help` prints the full help of a command. Both return one text block and never anything
else; both go through the same policy before a process exists.

## gog_run

Runs `gog --account <address> --no-input <args...>`.

| Parameter | Type | Allowed values | Default | Behaviour |
|---|---|---|---|---|
| `account` | string | `perso`, `work` | required | Which address gog acts on. The bridge maps the alias to the address from its environment; no argument can change it. |
| `args` | list of strings | one argv entry per item, without the leading `gog` | required, non-empty | The command line after `gog`. `["gmail", "search", "is:unread", "--json"]`, not one string with spaces. |
| `stdin` | string or null | any text | `null` | Fed to gog on standard input, for commands that read a body or a file from `-`. When null, stdin is closed, not inherited. |

`--no-input` is always present, so gog never waits on a prompt the model cannot see: a command
that would have asked for confirmation fails instead, with gog's own message in stderr, and the
model can add `--force` or `-y` on the next call if that is what the user wants.

## gog_help

Runs `gog <args...> --help` with `GOG_HELP=full` in the environment.

| Parameter | Type | Allowed values | Default | Behaviour |
|---|---|---|---|---|
| `args` | list of strings | a command path, possibly empty | `[]` | `[]` prints the top-level command list; `["gmail", "send"]` prints the flags of `gmail send`. |

`GOG_HELP=full` matters: without it gog hides its global flags (`--json`, `--dry-run`,
`--force`, `--select` and the rest) from every command's help, and the model would not know
they exist. No `--account` is passed, since help needs none.

## The report

Every call returns one text block, on success and on failure:

```
exit_code: 0
--- stdout ---
{"messages": [...]}
--- stderr ---
```

Line by line: `exit_code: N` first; a `note: ...` line only when the process timed out; the
`--- stdout ---` header and the captured stdout; the `--- stderr ---` header and the captured
stderr. Both streams are decoded as UTF-8 with replacement, on every platform, so a byte that is
not UTF-8 shows as U+FFFD rather than crashing the call. A trailing newline is stripped from
each stream.

**A non-zero exit is an error result.** The same report comes back, but on the MCP error
channel (`isError: true`), so the model sees it as a failure and reads gog's message in stderr.
This is deliberate: gog's exit codes carry meaning (1 error, 2 usage, 3 empty, 4 auth, 5 not
found, 6 denied, 7 rate limited, 10 config, per `gog --help`), and a model that reads
`exit_code: 5` with `not found` in stderr corrects its call rather than reporting success.

## Caps and timeout

| Limit | Value | What happens past it |
|---|---|---|
| stdout | 200000 bytes | The stream is cut there and ends with `[... sortie tronquée à 200000 octets par le pont ...]`. |
| stderr | 20000 bytes | Same, with its own figure in the marker. |
| duration | `GOG_BRIDGE_TIMEOUT_SECONDS`, 120 by default | The process is killed, the report carries `exit_code: -1` and a `note:` line in French saying gog was interrupted after N seconds, and the streams hold what arrived before the kill. |

Past a cap the bridge keeps reading and discards, so a child blocked on a full pipe still
exits. The caps are counted in bytes before decoding, which is why the figures in the markers
are byte counts.

## The policy

Checked on `args` before anything is spawned, for both tools. Each refusal is a tool error
whose message is in French and names the offending argument.

**The command.** The first argument that is not a global flag may not be `auth`, `config`,
`mcp`, `batch`, `schema`, `backup`, nor `login`, `logout` or `status`, which gog v0.40.0 exposes
as top-level aliases of `auth add`, `auth remove` and `auth status`. "Not a global flag" means:
arguments starting with a dash are skipped, and so is the value after `--color` or `--select`
in their two-argument form, the only value-taking global flags the policy lets through. So
`auth list`, `--json auth list`, `-j config get` and `--color auto auth list` are all refused,
while `drive ls --parent auth` passes because `auth` is a value there.

**Long flags.** Any argument starting with `--home`, `--client`, `--access-token`,
`--quota-project`, `--account`, `--enable-commands` or `--disable-commands` is refused. The
match is a prefix on the whole argument, so `--account=x`, `--client=""` and
`--enable-commands-exact` fall under it, wherever they appear in `args`.

**The short account flag.** A single dash followed by letters is a flag or a cluster of flags
in kong; if an `a` appears among those letters the argument is refused. That covers `-a`,
`-a=x`, `-ax`, `-ja` and `-jaX`. The scan stops at the first non-letter, so `-n5a` is a value
and passes, and `-` alone passes.

**Empty `args`.** Refused on `gog_run` only. `gog_help` accepts it and prints the top-level
help.

**Newlines.** An argument containing `\n` or `\r` is refused; multi-line text belongs in
`stdin`.

Everything else passes, `gmail send`, `calendar create`, `drive upload`, `--force` included.
The policy is about identity and configuration, not about what the signed-in user may do with
their own account. Not on the list, by decision rather than oversight: `update` (self-update of
the gog binary) and `api call` (raw Google API), both present in v0.40.0.

## Messages the model reads

The refusal messages, the timeout note and the truncation marker are the only French strings in
the server, all in `domain/messages.py`. They begin with a fixed prefix a client can match on:

- `Commande refusée par la politique du pont : « auth » ...` for a refused command.
- `Argument refusé par la politique du pont : « --account=x » ...` for a refused flag, the
  short account flag, or a newline.
- `Aucun argument fourni : ...` for empty `args` on `gog_run`.
- `Délai dépassé : gog a été interrompu après 120 s sans terminer. ...` on the `note:` line.
- `Impossible de lancer gog (<path>) : <reason>` when the executable could not be started.
