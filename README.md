# 🌉 gog-bridge

**The whole gog CLI, in Claude Desktop, behind a policy.**

[gog](https://github.com/openclaw/gogcli) is a command line tool for Google Workspace:
Gmail, Calendar, Drive, Docs, Sheets, Slides, Contacts, Tasks, Keep and more, on as many
accounts as you have signed in. It ships its own MCP server, `gog mcp`, and that server is
deliberately small: measured on v0.40.0, it exposes 8 read-only tools by default and 10 with
`--allow-write`, none of which sends an email, creates an event or uploads a file.

This bridge takes the other route. Two tools, `gog_run` and `gog_help`, hand the complete
command line to the model, and a policy decides what may not pass: the account is fixed by the
bridge, the flags that would change it or point gog at another configuration are refused, and
the commands that administer the local installation never run.

## 🧱 The problem

Claude Desktop can drive an MCP server, and `gog mcp` is one. Ask it to read your unread mail
and it works. Ask it to reply, to put the meeting in the calendar, to share the document with
the person who asked for it, and it cannot: those commands exist in the CLI and not in the MCP
surface. The typed, allowlisted server is the right design for an agent you do not trust with
your mailbox. It is the wrong one for a person who wants their own assistant to do what they
would do themselves at the keyboard.

Handing over the raw CLI has a different failure: a model that can pass any flag can pass
`--account` and act as someone else, `--home` and read another configuration, or `auth` and
touch the credentials. The bridge exists to draw that line once, in code, and to let everything
on the safe side of it through.

## 📦 Install

In `claude_desktop_config.json`:

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

Needs Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and gog v0.40 or newer with
both accounts already signed in through `gog auth add` in a terminal. The bridge never signs
in for you: `auth` is one of the commands it refuses. Transport is stdio and stdio only.

**Windows note.** Claude Desktop does not always see the PATH your terminal sees. If the
server fails to start because `uvx` is not found, put the absolute path of `uvx.exe` in
`command`, for example `C:\\Users\\you\\.local\\bin\\uvx.exe`. `where uvx` in a terminal prints
it. The bridge starts gog with `CREATE_NO_WINDOW`, so no console should flash behind the
application.

## 🚀 Quickstart

Ask for something the read-only server could do:

```
What is in my work inbox this morning?
```

The model calls `gog_run(account="work", args=["gmail", "search", "newer_than:1d", "--json"])`
and reads the result. Then ask for something it could not:

```
Reply to the one from Marc: yes for Thursday, 10 am, at their office.
```

The model calls `gog_help(["gmail", "send"])` if it needs the flags, then
`gog_run(account="work", args=["gmail", "send", "--reply-to-message-id", "<id>", "--reply-all", "--body", "..."])`.
`gog` runs with `--no-input`, so nothing ever waits on a prompt the model cannot see.

Every call returns one text block:

```
exit_code: 0
--- stdout ---
{"messages": [...]}
--- stderr ---
```

A non-zero exit comes back as a tool error carrying the same block, so the model reads gog's
own message in stderr and corrects its call.

## ✨ What you can do

**Any gog command, on either account.** `gog_run(account, args, stdin=None)` runs
`gog --account <address> --no-input <args...>`. `account` is `perso` or `work`; the bridge
maps the alias to the address from its environment, and no argument can change it. `stdin`
feeds text to commands that read from standard input, such as `--body-file -`.

**Discover flags without guessing.** `gog_help(args=[])` runs `gog <args...> --help` with
`GOG_HELP=full`, the mode that prints global flags as well as the command's own. Empty `args`
gives the top-level command list.

**Bounded output.** stdout is captured up to 200000 bytes and stderr up to 20000, each with a
marker where it was cut, so a runaway listing cannot flood the conversation. A command that
runs past the timeout, 120 seconds by default, is killed and reported with `exit_code: -1`
and a note.

**Failures you can act on.** The bridge never crashes on a failed command. Policy refusals,
non-zero exits and timeouts are all tool errors with a message the model can quote.

## 🛡️ The policy

Checked before any process is spawned. The messages are in French, for the model to relay.

| Refused | Why |
|---|---|
| The command `auth`, `config`, `mcp`, `batch`, `schema`, `backup`, `update`, or the `auth` aliases `login`, `logout`, `status` | Administration of the local gog installation, not Workspace operations; `update` replaces the very binary the bridge points at. The command is the first argument that is not a global flag, so `--json auth list` and `--color auto auth list` are refused too, while `calendar update` passes because `update` is a subcommand there. |
| Any argument starting with `--account`, `--home`, `--client`, `--access-token`, `--quota-project`, `--enable-commands`, `--disable-commands` | Each one changes who gog acts as, where it reads its configuration, or which commands exist. Prefix match, so `--account=x` and `--enable-commands-exact` are covered. |
| The short account flag in every form kong parses: `-a`, `-a=x`, `-ax`, and clusters such as `-ja` or `-jaX` | Same as `--account`. A single dash followed by letters with an `a` among them is refused; `-n5a` is a value and passes. |
| Empty `args` on `gog_run` | Nothing to run. `gog_help` accepts it and prints the top-level help. |
| An argument containing a newline | Multi-line text belongs in `stdin`. |

Everything else passes, including `gmail send`, `calendar create`, `drive upload` and
`--force`. The policy is about identity and configuration, not about what the signed-in user
may do with their own account.

## ⚙️ Configuration

Environment variables only, set in the `env` block of the client config. No `.env` file is
read: a server started by Claude Desktop has no working directory worth trusting.

| Variable | Required | Default | What it does |
|---|---|---|---|
| `GOG_BRIDGE_EXE` | yes | none | Absolute path of the gog executable. Checked at startup: the server refuses to start if the file is missing. |
| `GOG_BRIDGE_ACCOUNT_PERSO` | yes | none | Address behind `account="perso"`. |
| `GOG_BRIDGE_ACCOUNT_WORK` | yes | none | Address behind `account="work"`. |
| `GOG_BRIDGE_TIMEOUT_SECONDS` | no | `120` | Seconds before a gog command is killed. |

A missing or invalid variable stops the server at startup with the list of what is required on
stderr, which Claude Desktop shows in its MCP log.

## 🔧 Development

```bash
make install   # uv sync --all-extras
make check     # lint + test, what CI runs
make lint      # ruff check, ruff format --check, mypy
make test      # pytest: real subprocesses against a fake gog, no network
make run       # start the server on stdio
make build     # uv build
```

The tests spawn `tests/fake_gog.py` through a platform wrapper, a `.cmd` on Windows and a
shell script elsewhere, so the same asyncio runner is under test on both. The suite passes on
`ubuntu-latest` and `windows-latest`, Python 3.12 and 3.13.

## 📚 Documentation

Full docs in [docs/](docs/). Start with [getting-started.md](docs/getting-started.md), then
[tools.md](docs/tools.md) for the two tools, their parameters, the report format and the
policy in detail, and [troubleshooting.md](docs/troubleshooting.md) when a call comes back
with an error.

## 📜 Licence

[FSL-1.1-MIT](LICENSE). Source available, not open source: read it, fork it, run it, build on
it and ship products with it, with one restriction, you may not use it to make a competing
product. Every release converts to plain MIT 2 years after it ships, automatically.
