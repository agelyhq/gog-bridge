# The policy

`gog mcp` protects you with an allowlist: a fixed set of typed tools, each reviewed, and nothing
else. That is the right shape for an agent you do not trust with your mailbox, and the wrong one
for a person who wants their own assistant to do what they would do at the keyboard, send
included. This bridge hands the whole command line to the model and draws one line instead: the
model may do anything the signed-in user could do with their own account, and nothing that
changes who that user is, where gog reads its configuration, or which commands gog has.

That line is `domain/policy.py`, and it runs before any process is spawned. The tests prove the
second half of that sentence with a tripwire: a refused call never reaches the executable.

## What is refused

Five rules, each for a reason that fits in a sentence.

**The command may not be one of `auth`, `login`, `logout`, `status`, `config`, `mcp`, `batch`,
`schema`, `backup`, `update`.** These administer the local gog installation, and none of them is
a Google Workspace operation. `auth` and its top-level aliases `login`, `logout` and `status`
(aliases of `auth add`, `auth remove` and `auth status` in v0.40.0, found by reading `gog --help`
on the binary) touch the stored credentials: sign in another address, remove one, export a
token. `config` rewrites the file that holds account aliases and defaults. `mcp` starts a second
MCP server inside the first. `batch` persists Google Docs request batches on disk and submits
them later, a state machine the policy cannot see into. `schema` is harmless in itself and exists
for tooling, not for a conversation. `backup` writes encrypted exports of a whole account to disk
and decrypts them to stdout. `update` concerns the gog binary itself, the file `GOG_BRIDGE_EXE`
points at, and only the installer may touch that file (decision of 2026-09-16).

"The command" means the first argument that is not a global flag. kong, gog's argument parser,
accepts global flags before the command, so `--json auth list` runs `auth list`, and checking
`args[0]` alone was a hole measured live on 2026-09-16: it reached gog and returned the account
list. The lookup skips every argument starting with a dash, and the value after `--color` or
`--select` when they come as two arguments, those being the only value-taking global flags in
v0.40.0 that the policy lets through. So `auth list`, `--json auth list`, `-j config get` and
`--color auto auth list` are all refused, while `drive ls --parent auth` passes because `auth` is
a value there, and `calendar update` or `sheets update` pass because `update` is a subcommand,
not the command.

**No argument may start with `--home`, `--client`, `--access-token`, `--quota-project`,
`--account`, `--enable-commands` or `--disable-commands`.** `--home` points gog at another
configuration root and therefore at other credentials. `--client` selects another stored OAuth
client. `--access-token` bypasses the stored tokens with one the model supplies. `--quota-project`
bills another project. `--account` is the whole point of the bridge. `--enable-commands` and
`--disable-commands` rewrite which commands exist; gog offers them to whoever restricts the CLI,
and the model is not that person. The match is a prefix on the whole argument, so
`--account=x`, `--client=""` and `--enable-commands-exact` fall under it, wherever they appear in
`args`.

**No single-dash argument may carry the letter `a` among its flag letters.** kong parses `-a`,
`-a=x`, `-ax` and clusters such as `-ja` or `-jaX`, where every letter is a flag until one takes
a value. The policy scans the letters after the dash until the first non-letter and refuses if an
`a` is among them. `-n5a` passes because `5` ends the scan, and `-` alone passes. The rule is
wider than the flag it targets, and that is on purpose: a cluster that might mean `--account` is
not worth the guess.

**`args` may not be empty on `gog_run`.** There is nothing to run. `gog_help` accepts an empty
list and prints the top-level help.

**No argument may contain a newline.** `\n` or `\r` in an argument is refused, because a
multi-line body belongs in `stdin` and a newline in an argument is more often a mistake than a
choice.

Each refusal is a tool error whose message is in French and quotes the offending argument. The
prefixes are fixed, `Commande refusée par la politique du pont : « ... »` for the command rule
and `Argument refusé par la politique du pont : « ... »` for the other three, so a skill can match
on them.

## How the account lock works

The account is decided in three places, and the model controls none of them.

At startup, `GOG_BRIDGE_ACCOUNTS` is parsed into alias and address pairs, and the aliases become
the enum behind the `account` parameter of `gog_run`. The tool schema the client sees lists
exactly those values, so a model that follows the schema cannot name another. A model that does
not follow it, and sends an alias that is not configured, is refused before a process exists
with `Compte inconnu : « pro » n'est pas configuré sur ce pont. Comptes disponibles : perso, work.`
With a single alias the parameter is optional and defaults to it; the lock is the same, there is
simply nothing to choose.

At call time, the bridge looks the alias up and assembles the argv itself:
`gog --account <email> --no-input <args...>`. The address comes from the environment, `--account`
is the second argument, and `args` follows. Nothing the model wrote precedes the account flag.

And `args` cannot contradict it, because the second and third rules above refuse every spelling of
the account flag gog accepts, `--account`, `--account=`, `-a`, `-a=`, `-ax` and every cluster with
an `a`, while `--home`, `--client` and `--access-token` close the routes that would reach another
identity without naming an account. The policy does not rely on how gog would arbitrate between
two account flags, because a second one never gets as far as gog.

What the lock does not do is verify that the address in `GOG_BRIDGE_ACCOUNTS` is one gog has a
token for. That is `gog auth list`'s job, and a mismatch surfaces at the first call as
`exit_code: 4` from gog.

## What is deliberately allowed

Everything else, and the list below is written out because each item has been questioned.

`gmail send`, `gmail reply`, `gmail reply-all`, `gmail forward` and `gmail drafts send`. Sending
is the reason the bridge exists; `gog mcp` cannot, and the person asked for an assistant that can.

`calendar create`, `calendar update`, `calendar delete`, `calendar respond`. Writing to the
calendar is an ordinary thing to ask of an assistant.

`drive share`, `drive upload`, `drive delete`, `drive move`. Sharing outside the organisation is
the one that gives pause, and the answer is the same as for send: the bridge cannot tell a
legitimate share from a leak, and pretending it can would be worse than saying it cannot.

`api call`, the raw Discovery-described API on the signed-in account, present in v0.40.0. It is
bounded by the same account and the same token scopes as every other command, and its own
`--allow-write` plus the confirmation `--no-input` turns into a refusal make an accidental write
unlikely.

`-y` and `--force`. gog asks for confirmation on the commands it considers destructive, and
`--no-input` turns that question into `exit_code: 2` with
`refusing to ... without --force (non-interactive)` in stderr. The model may add `-y` on the next
call. Refusing the flag would make those commands unreachable rather than deliberate, and the
decision to run them belongs one level up.

`--dry-run`, `--readonly` and `--gmail-no-send`. Each narrows what a call may do, and a skill that
wants a read-only mode can put `--readonly` on every call in that mode without asking the bridge
for a feature.

`--color`, `--select`, `--json`, `--plain`, `--max`, `--fields`, `--results-only` and the rest of
the global flags that shape output. `--color` and `--select` are the two value-taking ones the
command lookup knows to skip.

## What the bridge does not check

It does not check recipients, so a mail to the wrong address sends. It does not check the target
of a share, so `--to anyone` is as easy as `--to user`. It does not distinguish a trash from a
permanent delete beyond what gog's own confirmation does. It does not know which account a
request meant when the person did not say; the model picks the alias, and the bridge runs what it
was given. It does not rate-limit, retry, or queue.

Each of those is a judgement about intent, and a process spawner has no access to intent. The
bridge guarantees that the model acts as the configured user and nobody else; whether the
configured user wanted this particular action is the skill's rule or the person's word. A skill
built on these tools should say when the model must ask before `gmail send`, before `drive share`
to an address outside the company, before any `-y`, and the person should expect to be asked. The
`--dry-run` flag exists for exactly that conversation: run it, show the person what gog would do,
then run it for real.

## Next

[tools.md](tools.md) for the examples these rules were checked against,
[troubleshooting.md](troubleshooting.md) for the refusal messages worked through by symptom.
