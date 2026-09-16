# Getting started

From a machine where gog already works to a Google command answered inside Claude Desktop. Ten
minutes, most of it opening files.

## What you need

Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and [gog](https://github.com/openclaw/gogcli)
v0.40 or newer with both accounts signed in. The bridge never signs in for you: `auth` is one of
the commands it refuses, so this check happens in a terminal, before anything else:

```bash
gog auth list
```

Two addresses should come back. If they do not, `gog auth add <address>` in that same terminal
is the fix, and nothing in this document changes it.

## Install

The published package is `gog-bridge` and the console script has the same name, so nothing
needs to be installed permanently:

```bash
uvx gog-bridge --version
```

That downloads the package into a throwaway environment, prints `gog-bridge 0.1.0` (or newer)
and exits. If it prints a version, the install story is over. Your MCP client will run the same
command.

To work on the source instead:

```bash
git clone https://github.com/agelyhq/gog-bridge.git
cd gog-bridge
make install
GOG_BRIDGE_EXE=/usr/local/bin/gog \
GOG_BRIDGE_ACCOUNT_PERSO=you@gmail.com \
GOG_BRIDGE_ACCOUNT_WORK=you@company.com \
make run
```

`make run` starts the server on stdio. It sits there reading its standard input and saying
nothing, which is correct: an MCP server over stdio has no console interface. Ctrl-C stops it.
There is no `.env` file to copy: the bridge reads the process environment and nothing else.

## Register it with Claude Desktop

Open `claude_desktop_config.json` (on Windows, `%APPDATA%\Claude\claude_desktop_config.json`)
and add the server:

```json
{
  "mcpServers": {
    "gog": {
      "command": "uvx",
      "args": ["gog-bridge"],
      "env": {
        "GOG_BRIDGE_EXE": "C:\\Users\\you\\gog\\gog.exe",
        "GOG_BRIDGE_ACCOUNT_PERSO": "you@gmail.com",
        "GOG_BRIDGE_ACCOUNT_WORK": "you@company.com"
      }
    }
  }
}
```

Three things to get right, each checked at startup so a mistake shows once, in the client's
MCP log, rather than on every call:

- `GOG_BRIDGE_EXE` is the absolute path of the gog executable, and the file must exist.
- The two addresses are the ones `gog auth list` printed. `perso` and `work` are the only names
  the model will use; the bridge maps them to the addresses itself.
- On Windows, if the log says `uvx` was not found, replace `"command": "uvx"` with the absolute
  path `where uvx` prints in a terminal, for example `C:\\Users\\you\\.local\\bin\\uvx.exe`.
  Claude Desktop does not always see the PATH your terminal sees.

Quit Claude Desktop completely (on Windows, from the tray icon) and reopen it. The server named
`gog` appears with two tools.

## A first command

Ask something the model can answer with one read:

```
What is in my work inbox this morning?
```

The model calls `gog_run(account="work", args=["gmail", "search", "newer_than:1d", "--json"])`
and gets back:

```
exit_code: 0
--- stdout ---
{"messages": [...]}
--- stderr ---
```

That report shape never changes, so the [tools.md](tools.md) reference is short.

## A first discovery

Then ask for something whose flags the model may not know:

```
Put a 30-minute call with Marc on the work calendar tomorrow at 10.
```

A careful model calls `gog_help(args=["calendar", "create"])` first, reads the flags of the
installed version, and only then calls `gog_run`. `gog_help` runs with `GOG_HELP=full`, the
only mode in which gog prints its global flags along with the command's own, so the model sees
`--json` and `--dry-run` there too.

## Where to go next

[tools.md](tools.md) for the contract of the two tools and the policy rule by rule;
[troubleshooting.md](troubleshooting.md) the first time a call comes back with an error.
