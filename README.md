# 🌉 gog-bridge

**A Google Workspace MCP server built for the reply, not the inbox.**

Reading your mail from Claude is the easy part. The afternoon goes on what comes after it: the
answer that has to leave from the work address, and the meeting that has to move to Friday.
Every connector stops at the read and hands the rest back to you, in a browser tab, with the
draft on the clipboard.

Two tools, the whole [gog](https://github.com/openclaw/gogcli) command line behind them, and a
policy that decides what may not pass.

## 🧱 The problem

You ask Claude to answer Marc. It has read the thread, it has written the reply, and now it
needs something that can send. On a Windows machine the candidates are three, and none of them
does it.

Claude Cowork runs its shell commands inside a Linux VM, so the `gog.exe` sitting in your user
profile is out of reach: the VM has no Windows binary, no Credential Manager and no path to
either. gog ships its own MCP server, `gog mcp`, and it is deliberately narrow: measured on
v0.40.0 it exposes 8 tools by default, all reads, and 10 with `--allow-write`, which adds a Docs
write and a Sheets range update. Nothing in it sends a mail, creates an event or shares a file.
Anthropic's own Google connectors search and read the mailbox and the calendar, and the write
you need is not there either.

So the draft goes into Gmail by hand, and the model that did the thinking watches you do the
clicking.

This server takes the other route. Claude Desktop starts it on the host, from
`claude_desktop_config.json`, next to `gog.exe` and the signed-in accounts, and both Cowork and
the Chat tab reach it. `gog_run` hands the model the whole command line. What a raw shell would
let through, the policy stops: the model picks an account from the aliases you configured and
nothing in its arguments can name another, and the commands that administer gog itself, `auth`
first among them, never run.

## 📦 Install

```bash
uvx gog-bridge --version
```

That downloads the package into a throwaway environment, prints `gog-bridge 0.1.0` and exits.
Needs Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and gog v0.40 or newer with every
account already signed in through `gog auth add` in a terminal: the bridge never signs in for
you, since `auth` is one of the commands it refuses. Transport is stdio, and stdio is the only
one: there is no HTTP mode and nothing listening on a port.

## 🚀 Quickstart

In `claude_desktop_config.json`, on Windows `%APPDATA%\Claude\claude_desktop_config.json`:

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

`GOG_BRIDGE_ACCOUNTS` is the only place the accounts are listed. Each `alias=email` pair becomes
one value of the `account` parameter, and the address is what gog receives. One pair is enough;
with a single alias the model may leave `account` out.

**Windows note.** Claude Desktop does not inherit a PATH that changed after it started, and the
uv installer changes it. If the MCP log says `uvx` was not found, put the absolute path in
`command`: `C:\\Users\\you\\.local\\bin\\uvx.exe`, which is what `where uvx` prints in a new
terminal. Quit Claude Desktop from the tray icon and reopen it; the server named `gog` appears
with two tools.

Then ask for something:

```
What is in my work inbox this morning?
```

The model calls `gog_run(account="work", args=["gmail", "search", "newer_than:1d", "--json"])`
and gets back one text block:

```
exit_code: 0
--- stdout ---
{
  "nextPageToken": "",
  "threads": [...]
}
--- stderr ---
```

A non-zero exit comes back as a tool error carrying the same block, so gog's own message in
stderr reaches the model and it corrects its call.

## ✨ What you can do

**Send the mail from the right address.** "Answer Marc from my work account: yes for Thursday,
10 am, at their office." The model reads the thread with `gmail thread get`, then calls
`gog_run(account="work", args=["gmail", "reply", "<messageId>", "--body-file", "-"], stdin="Bonjour Marc, ...")`.
The body travels on stdin, so accents and line breaks arrive intact, and `--account` is
supplied by the bridge from the alias, never by the model.

**Move the meeting.** "Push Thursday's point with Léa to Friday, same time." A
`calendar events primary --from 2026-09-17 --to 2026-09-18 --json` finds the event id, then
`calendar update primary <eventId> --from 2026-09-18T10:00:00+02:00 --to 2026-09-18T10:30:00+02:00 --send-updates all`
moves it and tells Léa.

**Share the deck.** "Give Marie comment access to the Q3 deck." `drive search "Q3 deck" --json`
returns the file id, `drive share <fileId> --to user --email marie@company.com --role commenter --notify`
does the rest. Nothing in the bridge decides whether Marie should see it; that judgement stays
with the model and with you.

**Pull the numbers.** "What did we spend in March, from the budget sheet?"
`sheets get <spreadsheetId> "2026!A1:F40" --json` on the personal or the work account, and the
model reads the range like any JSON.

**Ask gog itself before guessing.** `gog_help(args=["calendar", "create"])` prints the flags of
the installed version, global ones included, so the model builds the call from what the binary
accepts rather than from memory. The flags above were all read that way on v0.40.0.

## 🧨 The things that will bite you

Six of them. None is a bug in this server, and each has cost someone an hour.

**Some commands are refused, and the refusal is in French.** `auth` and its top-level aliases
`login`, `logout` and `status`, plus `config`, `mcp`, `batch`, `schema`, `backup` and `update`,
come back as `Commande refusée par la politique du pont : « auth » ...` before anything runs.
They administer the local gog installation rather than your Google account, and each is a way
around the bridge. Same treatment for `--account`, `-a` in every spelling gog's parser accepts
(`-a x`, `-a=x`, `-ax`, `-ja`), `--home`,
`--client`, `--access-token`, `--quota-project`, `--enable-commands` and `--disable-commands`.
The full list and the reasoning are in [docs/policy.md](docs/policy.md).

**Nothing ever prompts, so destructive commands need `-y`.** Every call runs with `--no-input`,
and gog answers a confirmation it cannot ask with `exit_code: 2` and
`refusing to permanently delete drive file abc without --force (non-interactive)` in stderr.
The model adds `-y` on the next call, once the person has agreed. That is the whole
confirmation mechanism the bridge provides; the rule for when to ask belongs to the skill or
the person, not to this server.

**The first start is slow.** `uvx` downloads a Python and the package on its first run, about a
minute on a normal connection, and Claude Desktop may report the server as failed before it is
ready. Run `uvx gog-bridge --version` once in a terminal, then start the client. Later starts
come from uv's cache and take about a second.

**Output is bounded and time is bounded.** stdout is captured up to 200 000 bytes and stderr up
to 20 000, each cut with a marker where it stopped; a command that runs past 120 seconds is
killed and reported as `exit_code: -1` with a note. A Drive listing over a whole account or a
`gmail search` with no date term will hit one or the other. Narrow with `--max`, a `newer_than:`
term or a folder, rather than retrying the same call.

**The keyring may be unreadable from a process without a terminal.** gog stores its tokens in
the platform keyring, Windows Credential Manager on Windows. Under Claude Desktop that read can
fail, and the symptom is
`no TTY available for keyring file backend password prompt; set GOG_KEYRING_PASSWORD` in
stderr. The fix is gog's file keyring with `GOG_KEYRING_PASSWORD` in the same `env` block; the
bridge passes its environment to gog and adds nothing to it.
[docs/troubleshooting.md](docs/troubleshooting.md) has the steps.

**One alias per account, and no way around it from the arguments.** The model chooses an alias
from `GOG_BRIDGE_ACCOUNTS` and the bridge writes `--account <email>` itself. An alias that is
not configured is refused, in French, with the valid ones listed. If the person wants a third
mailbox, it is a third pair in the variable and a restart of the client, not a flag.

## ⚙️ Configuration

Environment variables only, set in the `env` block of the client config. No `.env` file is
read: a server started by Claude Desktop has no working directory worth trusting, and
`config.py` is the only module that touches the environment, so this table is complete.

| Variable | Required | Default | What it does |
|---|---|---|---|
| `GOG_BRIDGE_EXE` | yes | none | Absolute path of the gog executable. Checked at startup; the server refuses to start if the file is missing. |
| `GOG_BRIDGE_ACCOUNTS` | yes | none | Comma-separated `alias=email` pairs, `perso=you@gmail.com,work=you@company.com`. An alias matches `^[a-z][a-z0-9_-]{0,31}$`, aliases are unique, at least one pair. A value that does not parse stops the server at startup with the problem named on stderr. |
| `GOG_BRIDGE_TIMEOUT_SECONDS` | no | `120` | Seconds before a gog command is killed and reported as `exit_code: -1`. |

`GOG_KEYRING_PASSWORD` is gog's own variable, not the bridge's; it belongs in the same `env`
block when gog runs on its file keyring, because that block is the whole environment gog will
see. Details, the parsing rules and complete configs for one and for three accounts in
[docs/configuration.md](docs/configuration.md).

## 📚 Documentation

Full docs in [docs/](docs/). Start with [getting-started.md](docs/getting-started.md), then
[tools.md](docs/tools.md) for the two tools and the exact shape of what comes back,
[policy.md](docs/policy.md) for the security boundary and what is deliberately left open,
[configuration.md](docs/configuration.md) for every variable, and
[troubleshooting.md](docs/troubleshooting.md) when a call comes back with an error.

## 📜 Licence

[FSL-1.1-MIT](LICENSE). Source available, not open source: read it, fork it, run it, build on
it and ship products with it, with one restriction, you may not use it to make a competing
product. Every release converts to plain MIT 2 years after it ships, automatically.
