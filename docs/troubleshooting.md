# Troubleshooting

Organised by what you observed, because that is what you have when something breaks. Each entry
says what the symptom means, what to check and in what order, and where to read further.

Failures from this server arrive as MCP tool errors carrying a readable message, and the message
tells you which of three things happened: the policy refused the call before anything ran, gog
ran and exited non-zero, or gog could not be started. The startup checks are the one exception:
they fail before the server exists, so they show up in the client's MCP log, not in a tool
result.

## The server does not start

**What you see.** Claude Desktop lists `gog` as failed or disconnected, and its MCP log holds:

```
gog-bridge cannot start: invalid environment.
  GOG_BRIDGE_EXE: Value error, no file at C:\Users\you\gog\gog.exe
Required: GOG_BRIDGE_EXE (absolute path of gog.exe), GOG_BRIDGE_ACCOUNT_PERSO, GOG_BRIDGE_ACCOUNT_WORK. Optional: GOG_BRIDGE_TIMEOUT_SECONDS (default 120).
```

**What it means.** The `env` block of the client config does not describe a runnable bridge.
The second line names the variable and the reason: missing, empty, a relative path, or a path
with no file behind it. The process exits with status 2 on purpose, so the client shows the
message instead of retrying a server that would fail on its first call.

**What to check, in order.**

1. The three required variables are spelled exactly, in the `env` block of the `gog` entry.
2. `GOG_BRIDGE_EXE` is absolute and points at a file. On Windows, double every backslash in
   JSON: `C:\\Users\\you\\gog\\gog.exe`.
3. If the log says `uvx` itself was not found, the problem is upstream of the bridge: put the
   absolute path of `uvx.exe` in `command`. See [getting-started.md](getting-started.md).

## A refusal in French

**What you see.**

```
Commande refusée par la politique du pont : « auth » relève de l'administration locale de gog
(auth et ses alias login, logout et status, config, mcp, batch, schema, backup) et n'est pas
accessible d'ici.
```

or `Argument refusé par la politique du pont : « --account=x » ...`, or `Aucun argument
fourni : ...`.

**What it means.** The policy stopped the call before any process was spawned. Nothing ran, and
nothing needs undoing. The message names the argument; [tools.md](tools.md) lists the rules.

**What to check, in order.**

1. Whether the call was trying to pick the account through `args`. It cannot: `account` is the
   only selector, and `--account`, `-a` and every cluster containing `a` are refused.
2. Whether the command is one of the administrative ones. They are meant to be run by the
   person, in a terminal, and the bridge will not run them with any flag in front.
3. Whether an argument carries a newline. Move the text to `stdin`.

## gog exited non-zero

**What you see.** An error result whose text starts with `exit_code: 1` (or 2, 3, 4, 5, 6, 7,
10) and carries stdout and stderr.

**What it means.** The bridge did its job: gog ran and failed, and its own message is in the
`--- stderr ---` block. The exit codes follow gog's own table, printed at the end of
`gog --help`: 1 error, 2 usage, 3 empty, 4 auth, 5 not found, 6 denied, 7 rate limited,
8 retryable, 10 config.

**What to check, in order.**

1. `exit_code: 2` with a usage message: a flag does not exist in the installed version. Call
   `gog_help` on that command before guessing again.
2. `exit_code: 4` or `invalid_grant` in stderr: the account's authorisation is revoked or
   expired. Only `gog auth add` in a terminal fixes it, and the bridge refuses `auth` by design.
3. `exit_code: 6` with `insufficientPermissions`: the account was signed in without the scope
   the command needs. Same remedy, with the missing service granted.
4. `refusing to ... without --force (non-interactive)` in stderr: gog wanted a confirmation
   that `--no-input` prevents. Add `-y` once the user has agreed.

## exit_code: -1 with a note

**What you see.**

```
exit_code: -1
note: Délai dépassé : gog a été interrompu après 120 s sans terminer. La sortie ci-dessous est celle reçue avant l'interruption.
--- stdout ---
...
```

**What it means.** The command ran past `GOG_BRIDGE_TIMEOUT_SECONDS` and was killed. `-1` never
collides with a real gog exit status, which is 0 or positive. The streams hold what arrived
before the kill.

**What to check, in order.**

1. The command itself. A `drive` listing over a whole account or a `gmail search` without a
   date window can legitimately take minutes; narrow it with `--max`, a `newer_than:` term or a
   folder, rather than retrying the same call.
2. The timeout, if the command really needs longer: raise `GOG_BRIDGE_TIMEOUT_SECONDS` in the
   `env` block and restart the client.
3. On Windows only: whether `GOG_BRIDGE_EXE` points at a `.cmd` or `.bat` wrapper rather than
   `gog.exe`. Killing a wrapper kills `cmd.exe` and not its child, which keeps the pipes open;
   the bridge runs `taskkill /T /F` on the tree for that reason, and waits at most five more
   seconds before answering with what it has. Pointing at `gog.exe` directly avoids the whole
   path.

## A stream ends with a truncation marker

**What you see.** The stdout block ends with
`[... sortie tronquée à 200000 octets par le pont ...]`, or the stderr block with the same
sentence and `20000`.

**What it means.** The output exceeded the cap and was cut; the rest was read and discarded so
gog could exit. The figure is in bytes, counted before decoding.

**What to check, in order.**

1. Whether JSON was requested. A truncated JSON document does not parse; the model should
   narrow the query rather than repair the text.
2. `--max`, `--select` or `--results-only`, all global flags gog prints under `GOG_HELP=full`,
   which is what `gog_help` uses.

## Impossible de lancer gog

**What you see.**

```
Impossible de lancer gog (C:\Users\you\gog\gog.exe) : Permission denied
```

**What it means.** The file existed at startup but could not be executed now: permissions, an
antivirus quarantine, or a file replaced since the server started. The reason after the colon
is the operating system's.

**What to check, in order.**

1. Run the same path in a terminal with `--version`.
2. Restart the client after replacing or updating the executable, so the startup check runs
   again on the new file.

## The answer comes from the wrong account

**What you see.** Mail or events from the personal address when the work one was meant, or the
reverse.

**What it means.** Not a bridge failure: the model passed the other `account` value. The bridge
cannot infer intent, and nothing in `args` can override the alias.

**What to check, in order.**

1. The `account` value in the call. Ask for it explicitly in the request when the context is
   ambiguous.
2. The two addresses in the `env` block, if both aliases return the same mailbox: they may be
   the same string.
