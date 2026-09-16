# Getting started

From a machine where gog already works to a Google command answered inside Claude Desktop.
Fifteen minutes, most of it the OAuth consent screens.

## What you need

Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and
[gog](https://github.com/openclaw/gogcli) v0.40 or newer. The bridge starts gog and reads its
output; it installs neither and it signs into nothing.

## Install uv

The official installer puts `uv` and `uvx` in `~/.local/bin` on Linux and macOS and in
`%USERPROFILE%\.local\bin` on Windows, and adds that directory to your PATH:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close the terminal and open a new one, then:

```bash
uvx gog-bridge --version
```

That downloads a Python and the package into uv's cache, prints `gog-bridge 0.1.0` and exits.
It takes about a minute the first time and about a second afterwards, which is why this page
asks you to run it once by hand: your MCP client will run the same command, and a client that
waits a minute on a silent server tends to declare it dead.

## Install gog and authorise the accounts

Download the release for your platform from the
[gogcli releases page](https://github.com/openclaw/gogcli/releases), check the archive against
`checksums.txt`, and put the binary somewhere stable: `/usr/local/bin/gog`, or
`C:\Users\you\gog\gog.exe`. The bridge needs that absolute path later, and the file must still
be there every time the client starts.

Then sign in each account, in a terminal, with the services you intend to use:

```bash
gog auth add you@gmail.com --services gmail,calendar,drive,docs,sheets,contacts,tasks
gog auth add you@company.com --services gmail,calendar,drive,docs,sheets,slides,contacts
gog auth list
```

A browser opens on Google's consent screen for each address. `gog auth list` should print every
address you signed in. This is the only time `auth` is involved: the bridge refuses the command,
so an account that needs signing in again, or a scope that was not granted, always comes back to
this terminal.

If your organisation's OAuth client is not the one gog ships with, `gog auth credentials set`
takes the `client_secret.json` before the first `auth add`. gog's own documentation covers that
part.

## Declare the server

Open `claude_desktop_config.json`. On Windows it is `%APPDATA%\Claude\claude_desktop_config.json`
(`notepad $env:APPDATA\Claude\claude_desktop_config.json` in PowerShell); on macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`. Add the server:

```json
{
  "mcpServers": {
    "gog": {
      "command": "uvx",
      "args": ["gog-bridge"],
      "env": {
        "GOG_BRIDGE_EXE": "C:\\Users\\you\\gog\\gog.exe",
        "GOG_BRIDGE_ACCOUNTS": "perso=you@gmail.com,work=you@company.com"
      }
    }
  }
}
```

Two variables and, on Windows, one path to get right. The variables are checked at startup, so
a mistake shows once, in the client's MCP log, rather than on every call.

`GOG_BRIDGE_EXE` is the absolute path of the gog executable, and the file must exist. In JSON on
Windows every backslash is doubled, as above.

`GOG_BRIDGE_ACCOUNTS` lists the accounts as `alias=email` pairs separated by commas.
The addresses are the ones `gog auth list` printed; the aliases are the names the model will use
in the `account` parameter, and they are yours to choose within `^[a-z][a-z0-9_-]{0,31}$`.
`perso` and `work` are a habit, not a rule. One pair is fine, and with one pair the model may
omit `account` altogether.

On Windows, `command` may need to be the absolute path of `uvx.exe`. Claude Desktop does not
inherit a PATH that changed after it started, and the uv installer changed it, so the first start
after installing uv often fails with `uvx` not found. `where uvx` in a new terminal prints the
path, typically `C:\Users\you\.local\bin\uvx.exe`; write it in `command` with doubled
backslashes. The same applies to any launcher that was not on the PATH when Claude Desktop
opened.

Quit Claude Desktop completely, on Windows from the tray icon near the clock, and reopen it. The
server named `gog` appears with two tools, `gog_run` and `gog_help`.

## For Claude Code

One command, and the same two variables:

```bash
claude mcp add gog \
  -e GOG_BRIDGE_EXE=/usr/local/bin/gog \
  -e GOG_BRIDGE_ACCOUNTS=perso=you@gmail.com,work=you@company.com \
  -- uvx gog-bridge
```

## A first command

Ask something the model can answer with one read:

```
What is in my work inbox this morning?
```

The model calls `gog_run(account="work", args=["gmail", "search", "newer_than:1d", "--json"])`
and gets back one text block:

```
exit_code: 0
--- stdout ---
{"threads": [...]}
--- stderr ---
```

That shape never changes, on success or on failure, which is why [tools.md](tools.md) is short
on the subject. Underneath, the bridge ran
`gog --account you@company.com --no-input gmail search newer_than:1d --json`: the address came
from the alias, `--no-input` is on every call, and nothing the model wrote could have changed
either.

## A first discovery

Then ask for something whose flags the model may not know by heart:

```
Put a 30-minute call with Marc on the work calendar tomorrow at 10.
```

A careful model calls `gog_help(args=["calendar", "create"])` first, reads the flags of the
installed version, and only then calls `gog_run` with `["calendar", "create", "primary",
"--summary", "Point Marc", "--from", "2026-09-17T10:00:00+02:00", "--to",
"2026-09-17T10:30:00+02:00"]`. A command's help lists the global flags next to its own, so
the model sees `--json`, `--dry-run` and `-y` there too. `gog_help` also sets `GOG_HELP=full`,
which turns `gog_help([])` from the top-level groups into the whole command tree.

## Cowork and the Chat tab

Both live in the same Claude Desktop application and both read the same
`claude_desktop_config.json`, so the server is declared once. What differs is where the model's
commands run. Cowork executes shell commands in a Linux VM, which is why it cannot reach a
Windows `gog.exe` on its own and why this bridge exists: the MCP server runs on the host, and
Cowork calls its two tools across the boundary. The Chat tab calls them directly.

If the `gog` connector shows its two tools in the Chat tab and not in a Cowork session, or if
Cowork reports the tools as disabled in the connector settings, the bridge is fine and the
question is on the client's side. Use the Chat tab for the request, and check the connector
settings of the Cowork session when it is next opened.

## Working on the source

```bash
git clone https://github.com/agelyhq/gog-bridge.git
cd gog-bridge
make install
make check
make e2e
```

`make check` runs lint and the unit suite, which drives the MCP surface against a fake gog and
needs no network. `make e2e` runs `scripts/fetch_gog.py`, which downloads the gog v0.40.0
release for the current OS, checks it against `checksums.txt`, and starts the installed
`gog-bridge` console script as a real subprocess over stdio, the way Claude Desktop starts it,
inside an isolated configuration directory: `HOME` and `XDG_CONFIG_HOME` on POSIX, `APPDATA`,
`LOCALAPPDATA` and `USERPROFILE` on Windows all point at a temporary directory, so the tier
never reads or writes your own gog configuration. Both tiers run in CI on `ubuntu-latest` and
`windows-latest`.

`make run` starts the server on stdio with whatever `GOG_BRIDGE_*` variables the shell holds. It
sits there reading its standard input and saying nothing, which is correct: an MCP server over
stdio has no console interface. Ctrl-C stops it.

## Next

[tools.md](tools.md) for the contract of the two tools and worked examples per service,
[policy.md](policy.md) for what is refused and why, [configuration.md](configuration.md) for
the variables in detail, and [troubleshooting.md](troubleshooting.md) the first time a call
comes back with an error.
