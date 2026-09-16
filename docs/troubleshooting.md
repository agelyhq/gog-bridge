# Troubleshooting

Organised by what you observed, because that is what you have when something breaks. Each entry
says what the symptom means, what to check and in what order, and where to read further.

Failures from this server arrive as MCP tool errors carrying a readable message, and the message
tells you which of three things happened: the policy refused the call before anything ran, gog
ran and exited non-zero, or gog could not be started. The startup checks are the exception: they
fail before the server exists, so they show in the client's MCP log, on Windows under
`%APPDATA%\Claude\logs`, and not in a tool result.

## The gog connector does not appear

**What you see.** Claude Desktop lists no `gog` server, or lists it as failed or disconnected,
and no tool named `gog_run` is offered.

**What it means.** Either the client never read the entry, or it read it and the server exited
at startup. The MCP log tells the two apart: a startup failure leaves a message there, a missing
entry leaves nothing.

**What to check, in order.**

1. That the file is the one the client reads, `%APPDATA%\Claude\claude_desktop_config.json` on
   Windows, `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, and that
   it is valid JSON. A trailing comma after the last entry is the usual reason the client
   silently ignores the whole file.
2. That the client was fully restarted after the edit. On Windows, closing the window leaves it
   running in the tray; quit from the tray icon.
3. The MCP log. `mcp-gog-bridge cannot start: invalid environment.` means the `env` block is wrong,
   and the next lines name the variable and the reason: a missing `GOG_BRIDGE_EXE`, a relative
   path, `no file at <path>`, a `GOG_BRIDGE_ACCOUNTS` that does not parse or is absent because
   the block still sets the former `GOG_BRIDGE_ACCOUNT_PERSO` and `GOG_BRIDGE_ACCOUNT_WORK`. The
   process exits with status 2 on purpose so the client shows the message instead of retrying.
   [configuration.md](configuration.md) lists every way `GOG_BRIDGE_ACCOUNTS` can fail.

## uvx is not found

**What you see.** The MCP log says the command could not be found, `spawn uvx ENOENT` or the
Windows equivalent, and a terminal on the same machine runs `uvx --version` without complaint.

**What it means.** Claude Desktop does not inherit a PATH that changed after it started, and the
uv installer changed it. The terminal opened after the install sees the new PATH; the client,
opened before, does not. Replace `"command": "uvx"` with the absolute path: `where uvx` on
Windows prints it, typically `C:\Users\you\.local\bin\uvx.exe`, `which uvx` elsewhere, typically
`/home/you/.local/bin/uvx`. Double the backslashes in JSON. Logging out and back in also works,
since the PATH the client inherits is the session's and the session read it at login.

## The first start looks like a failure

**What you see.** The server shows as starting, or as failed, for about a minute after a fresh
install, then works on the next restart.

**What it means.** `uvx` downloads a Python and the `mcp-gog-bridge` package on its first run, and
the client's patience is shorter than the download. Nothing is wrong; the second start reads
from uv's cache and takes about a second ([configuration.md](configuration.md) says where that
cache is). Run `uvx mcp-gog-bridge --version` in a terminal before the first start of the client: it
prints `mcp-gog-bridge 0.1.0` after the download, and it also gives an antivirus or SmartScreen its
first look at the cached Python, which is the other thing that makes a first start slow.

## Commande refusée par la politique du pont

**What you see.**

```
Commande refusée par la politique du pont : « auth » relève de l'administration locale de gog
(auth et ses alias login, logout et status, config, mcp, batch, schema, backup, update) et n'est
pas accessible d'ici.
```

or `Argument refusé par la politique du pont : « --account=x » ...`, or the same prefix with
`-ja` and the words `drapeau court -a`, or with an argument that contains a newline, or
`Aucun argument fourni : ...`.

**What it means.** The policy stopped the call before any process was spawned. Nothing ran,
nothing needs undoing. The message names the argument; [policy.md](policy.md) explains the rule
it hit and why the rule exists.

**What to check, in order.**

1. Whether the call was choosing the account through `args`. It cannot: `account` is the only
   selector, and `--account`, `-a` and every cluster containing `a` are refused. If the person
   wants another mailbox, it is another pair in `GOG_BRIDGE_ACCOUNTS`.
2. Whether the command is one of the administrative ones, with or without global flags in
   front of it. They are meant to be run by the person in a terminal. `gog auth add`,
   `gog auth list` and `gog config set` in particular never run through the bridge.
3. Whether an argument carries a newline. Move the text to `stdin` and pass `--body-file -` or
   the command's equivalent.
4. Whether the alias exists, if the message is instead
   `Compte inconnu : « pro » n'est pas configuré sur ce pont. Comptes disponibles : perso, work.`
   The fix is to use one of the listed aliases, or to add the missing pair to
   `GOG_BRIDGE_ACCOUNTS` and restart the client.

## exit_code: 2 and "refusing to ... without --force"

**What you see.** An error result ending with

```
--- stderr ---
refusing to permanently delete drive file 1AbC... without --force (non-interactive)
```

**What it means.** gog asks for confirmation before the commands it considers destructive, and
`--no-input`, present on every call, turns the question into a refusal with exit code 2. This is
the bridge's only confirmation mechanism, and it is working. If the person agreed to the action,
the model adds `-y` and calls again; if not, the refusal was the right outcome. Check first that
the destructive form was intended at all: `drive delete` without `--permanent` moves to the trash
and asks nothing. [policy.md](policy.md) says why `-y` is allowed through.

The other `exit_code: 2` is `unknown flag --xyz` followed by `Run with --help to see available
flags`: the flag does not exist on the installed version, and `gog_help` on that command path is
how the model finds the one that does.

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
before the kill, which for a JSON listing is a document with no closing bracket.

**What to check, in order.**

1. The command. A Drive listing with `--all` over a whole account, a `gmail search --all` with no
   date term, or a `docs export` of a very long document can legitimately take minutes. Narrow
   it with `--max`, a `newer_than:` term, a `--parent` folder or a `--tab`, rather than retrying
   the same call.
2. The network. gog waiting on Google looks the same as gog working; a second timeout on a small
   command points at the line rather than at the command.
3. The timeout itself, if the command really needs longer: raise `GOG_BRIDGE_TIMEOUT_SECONDS` in
   the `env` block and restart the client.
4. On Windows only, whether `GOG_BRIDGE_EXE` points at a `.cmd` or `.bat` wrapper rather than at
   `gog.exe`. Killing a wrapper kills `cmd.exe` and not its child, which keeps the pipes open; the
   bridge runs `taskkill /T /F` on the tree for that reason and waits at most five more seconds
   before answering with what it has. Pointing at `gog.exe` avoids the whole path.

## A stream ends with a truncation marker

**What you see.** The stdout block ends with
`[... sortie tronquée à 200000 octets par le pont ...]`, or the stderr block with the same
sentence and `20000`.

**What it means.** The output exceeded the cap and was cut; the rest was read and discarded so gog
could exit. The figure is in bytes, counted before decoding. A truncated JSON document does not
parse, and the model should narrow the query rather than repair the text: `--max` on listings,
`--results-only` with `--select` or `--fields` on anything JSON so that gog sends only the
fields needed, `--page` with the previous `nextPageToken` instead of `--all`, and on a long
document `docs cat --max-bytes` below its default of 2 000 000 bytes, ten times the cap, or a
single `--tab`.

## invalid_grant, or exit_code: 4

**What you see.** `exit_code: 4` and a stderr mentioning `invalid_grant`, `token has been
expired or revoked`, or `auth required`.

**What it means.** The refresh token for that address is no longer valid. Google revokes tokens
when the password changes, when the user removes the app from their account, when a test OAuth
client's seven-day window runs out, and after long inactivity. gog's own retry cannot help; only
a new sign-in can.

**What to check, in order.**

1. `gog auth list` in a terminal, then `gog auth doctor --check`, which exchanges each stored
   token and says which one fails.
2. `gog auth add <address>` in that terminal, for the failing address. The bridge refuses `auth`
   by design, so this step is never done from a conversation.
3. If the token dies every week, the OAuth client is in testing status in the Google Cloud
   console; publishing it is the fix, and gog's documentation covers it.

## exit_code: 6, insufficientPermissions or a 403

**What you see.** `exit_code: 6` with `insufficientPermissions`, `403`, or `Request had
insufficient authentication scopes` in stderr.

**What it means.** The account was signed in without the scope the command needs, or with a
read-only variant of it. A token authorised for `gmail` with `--gmail-scope readonly` reads mail
and cannot send; one authorised without `drive` cannot list Drive at all.

**What to check, in order.**

1. Which service the command belongs to, and its name on gog's side: `gog auth services` in a
   terminal lists the services gog can request and the scopes each one carries.
2. `gog auth add <address> --services gmail,calendar,drive,...` again, in a terminal, with the
   missing service named and the full scope mode where the command writes. The browser consent
   screen shows the added permissions.
3. On a Workspace account, whether the administrator restricted the OAuth client or the API.
   The 403 then names the policy, and only the administrator can lift it.

## no TTY available for keyring file backend password prompt

**What you see.** Every call fails with `exit_code: 1` and

```
read OAuth client secret from keyring: read secret: get secret: read encoded file keyring item:
no TTY available for keyring file backend password prompt; set GOG_KEYRING_PASSWORD
```

while the same command works in a terminal.

**What it means.** gog is on its file keyring, the encrypted file backend, and needs a password
to open it. In a terminal it asks; under Claude Desktop there is no terminal to ask on, so it
fails and names the variable that would have answered. The bridge passes its environment to gog
unchanged, so the variable has to be in the `env` block of the client config. The related case
is a platform keyring, Windows Credential Manager or the macOS keychain, whose read fails only
when Claude Desktop is the parent process; the error then names that backend, and the way out is
to move gog to the file keyring, whose only failure `GOG_KEYRING_PASSWORD` fixes.

**What to check, in order.**

1. `gog auth status` in a terminal: the `keyring_backend` line says `file`, `keychain` or `auto`.
2. For `file`: the value the terminal session uses, `echo $env:GOG_KEYRING_PASSWORD` in
   PowerShell or `echo $GOG_KEYRING_PASSWORD` elsewhere, copied into the `env` block as
   `"GOG_KEYRING_PASSWORD": "..."`. Restart the client.
3. For a platform backend that fails only under the client: set `GOG_KEYRING_PASSWORD` in the
   session, `gog auth keyring file`, `gog auth add` for each address again, then step 2.

## A console window flashes behind Claude Desktop

**What you see.** On Windows, a black window appears for a fraction of a second on some or every
call.

**What it means.** The bridge starts gog with `CREATE_NO_WINDOW`, so `gog.exe` itself should
never show one. A flash means something in between did: a `.cmd` or `.bat` wrapper in
`GOG_BRIDGE_EXE`, which starts `cmd.exe` and its window before gog, or a `command` that is a
batch shim from another package manager rather than `uvx.exe`. Point `GOG_BRIDGE_EXE` at the
`gog.exe` from the release archive and `command` at the `.exe` that `where uvx` lists.

## The answer comes from the wrong account

**What you see.** Mail or events from the personal address when the work one was meant, or the
reverse.

**What it means.** Not a bridge failure: the model passed the other alias, or a single alias is
configured and every call goes there whatever the request said. Nothing in `args` can override
the alias, so the choice was made in the `account` parameter or in `GOG_BRIDGE_ACCOUNTS`. Name
the account in the request when the context is ambiguous.

## Still stuck

The report carries gog's own message wherever there is one, so the `--- stderr ---` block is
worth reading in full before assuming the problem is in the bridge. If a failure looks like a
genuine bug here rather than a refusal from gog or from Google, open an issue at
[github.com/agelyhq/mcp-gog-bridge/issues](https://github.com/agelyhq/mcp-gog-bridge/issues) with the
tool name, the `args` array and the exact report.
