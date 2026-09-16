# mcp-gog-bridge documentation

The [project README](../README.md) says what this server is and why it exists. These pages say
how to drive it, what it refuses, and what to do when a call comes back wrong.

## The set

**[getting-started.md](getting-started.md)** takes you from a machine where gog already answers
in a terminal to a first command answered inside Claude Desktop: uv, the accounts signed in with
`gog auth add`, the server declared in `claude_desktop_config.json`, a first `gog_run`, then a
first `gog_help`. It also says where Cowork and the Chat tab differ, and which Windows paths to
type. Read it first. Everything else assumes you have seen one report come back.

**[tools.md](tools.md)** is the reference for `gog_run` and `gog_help`: every parameter with its
type, its allowed values and its default, the exact shape of the report, what a non-zero exit
looks like on the client side, the capture caps and the timeout. It ends with worked examples
per Google service, written as the `args` arrays the model actually sends, each checked against
gog v0.40.0 and against the policy. Open it when you know what you want and need the contract.

**[policy.md](policy.md)** covers the part that has no equivalent in `gog mcp`: the security
boundary. Which commands and flags are refused and why each one is on the list, how the account
lock works from the alias down to the argv, what is deliberately allowed, `gmail send` included,
and what the bridge does not check because it is a question for the skill or the person rather
than for a process spawner.

**[configuration.md](configuration.md)** lists the three environment variables, explains how
`GOG_BRIDGE_ACCOUNTS` is parsed and every way it can fail at startup, gives a complete client
config for one account and for three, and says where uv puts the Python and the package it
downloads, since that is where the first slow start goes.

**[troubleshooting.md](troubleshooting.md)** is organised by symptom rather than by cause,
because the symptom is what you have when something breaks. A connector that does not show up,
`uvx` not found, a first start that looks like a failure, a refusal in French, `exit_code: -1`,
a stream that ends with a truncation marker, `invalid_grant`, a 403, a keyring that asks for a
password with no terminal to ask on, a console window flashing behind Claude Desktop.

## Reading order

For a first install, getting-started.md and then troubleshooting.md if anything on the way
disagrees with what the page says you should see. For someone writing a skill or a prompt that
drives the tools, tools.md and policy.md together: the first says what a call looks like, the
second says which calls never reach gog and what the model reads instead. For the person who
maintains the machine, configuration.md, and the two entries of troubleshooting.md about the
keyring and about `uvx`.

## When something goes wrong

Go to [troubleshooting.md](troubleshooting.md) first. Every failure this server reports arrives
as an MCP tool error with a readable message, and the message says which of three things
happened: the policy refused the call before anything ran, gog ran and exited non-zero, or gog
could not be started at all. The first two are for the calling model to act on, and their text
is in French so that a French user can be quoted the exact sentence. The third is for whoever
wrote the configuration, and so are the startup checks, which fail before the server exists and
therefore show in the client's MCP log rather than in a tool result.

Two conventions hold across every page. A gog exit code means what gog's own table says it
means, 1 error, 2 usage, 3 empty, 4 auth, 5 not found, 6 denied, 7 rate limited, 8 retryable,
10 config, and the bridge adds one of its own, -1, for a command it killed on timeout. And an
`args` array is written the way the model sends it, one argv entry per item, without the
leading `gog` and without `--account`, because the bridge adds both.

Every gog command and flag quoted in these pages was checked against the v0.40.0 binary with
`<command> --help` on 2026-09-16. Every French sentence quoted from the bridge is the text in
`domain/messages.py` at the same date, and every English startup message is the text in
`domain/accounts.py` and `config.py`; when a page and the code disagree, the code is newer.

## What is not here

There is no deployment guide, because there is nothing to deploy: the server speaks MCP over
stdio and your client starts it.

There is no guide to gog itself. `gog_help` prints the help of the installed version, which is
the only version that matters on that machine, and the
[gogcli repository](https://github.com/openclaw/gogcli) holds the rest. The examples in
tools.md were read from v0.40.0 and a later gog may rename a flag; when a page and the binary
disagree, the binary wins, and `gog_help` is how the model finds out.

There is no confirmation policy. The bridge does not know whether a mail should be sent or a
file shared outside the company; it knows that `--no-input` is on every call, so a command gog
considers destructive fails until `-y` is added. When to add it is the skill's rule or the
person's word, and [policy.md](policy.md) says exactly where that line is drawn.
