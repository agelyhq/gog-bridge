# Configuration

Everything is configured through environment variables, set in the `env` block of the client
config. There is no config file and no command line option beyond `--version`, because an MCP
server started by a client has nowhere to read options from except its environment. No `.env`
file is read either: Claude Desktop starts the server in a working directory you did not choose,
and a file picked up from there would be a surprise rather than a convenience. `config.py` is the
only module that touches the environment, so the table below is the complete list.

## The variables

| Variable | Type | Required | Default | Example |
|---|---|---|---|---|
| `GOG_BRIDGE_EXE` | absolute path | yes | none | `C:\Users\you\gog\gog.exe`, `/usr/local/bin/gog` |
| `GOG_BRIDGE_ACCOUNTS` | `alias=email` pairs, comma-separated | yes | none | `perso=you@gmail.com,work=you@company.com` |
| `GOG_BRIDGE_TIMEOUT_SECONDS` | number greater than 0 | no | `120` | `300` |

Names are matched case-insensitively and an empty value counts as unset, so an `env` block
copied from an example and only half filled in fails on the missing variable rather than on an
empty string. Unknown variables are ignored, which is what lets `GOG_KEYRING_PASSWORD` and
anything else gog needs sit in the same block.

Settings are read once, when the process starts. Changing a variable means restarting the
server, which for Claude Desktop means quitting it from the tray icon and reopening it.

## GOG_BRIDGE_EXE

The absolute path of the gog executable. Two checks run at startup: the path is absolute, and a
file exists there. A relative path is refused even when it would resolve, because the working
directory it would resolve against belongs to the client. A path to a directory, or to nothing,
is refused with `no file at <path>`.

Point it at the binary itself, `gog.exe` or `gog`, not at a `.cmd` or shell wrapper around it.
The timeout path kills the process it started, and on Windows killing a `.cmd` kills `cmd.exe`
while the real gog keeps the pipes open; the bridge runs `taskkill /T /F` on the tree to cover
that case, and still waits up to five seconds more than it would otherwise. Pointing at the
executable avoids the whole path.

The file is checked once. If you replace gog after the server has started, restart the client so
the check runs again on the new file, and so that a file that is missing during the swap fails
at startup rather than at the first call.

## GOG_BRIDGE_ACCOUNTS

One variable holds every account the bridge may act on, as `alias=email` pairs separated by
commas:

```
perso=you@gmail.com,work=you@company.com
```

Parsing is strict, and every failure is a startup failure with the problem named on stderr,
never a server that starts and refuses every call. The value is split on commas, each entry is
split on its first `=`, spaces around an entry or around the `=` are ignored, and the rules are:

An alias matches `^[a-z][a-z0-9_-]{0,31}$`: a lowercase letter first, then up to 31 lowercase
letters, digits, underscores or hyphens. `perso`, `work`, `agely-care` and `w2` pass; `Perso`,
`2nd`, `mon compte` and an empty alias do not, and the message reads
`alias 'Perso' must match ^[a-z][a-z0-9_-]{0,31}$: lowercase letters, digits, _ and -, starting with a letter, 32 characters at most`.
The pattern is what lets the alias be a clean enum value in the tool schema and a clean word in
a French sentence.

The email is whatever follows the `=` and must contain an `@`; `address 'foo' for alias 'work'
has no @` otherwise. An entry with no `=` at all fails with
`entry 'work' is not of the form alias=email`. The bridge does not check that the address is one
gog knows: `gog auth list` is the reference, and a mismatch shows up at the first call as an auth
error from gog rather than at startup.

At least one pair is required, and no entry may be empty, so a trailing comma fails with
`entry 3 is empty; expected perso=me@gmail.com,work=me@company.com`.

Aliases are unique. `work=a@x.com,work=b@x.com` is refused with `alias 'work' appears twice`
rather than letting the second silently win. Two aliases for the same address are allowed, since
nothing breaks, though the model gains nothing from them.

The aliases become the `account` parameter of `gog_run`: the schema lists them as an enum, so
the model cannot invent one, and the parameter description names each alias with its address so
the model picks the right one from context. With exactly one pair, `account` becomes optional
and defaults to that alias; with two or more it is required. Adding a mailbox is a new pair and a
restart of the client, and nothing in a tool call can add one.

The former `GOG_BRIDGE_ACCOUNT_PERSO` and `GOG_BRIDGE_ACCOUNT_WORK` are gone, without a
compatibility path. A config that still sets them and not `GOG_BRIDGE_ACCOUNTS` fails at startup
on the missing variable, which is the signal to rewrite the `env` block.

## GOG_BRIDGE_TIMEOUT_SECONDS

Seconds before a running gog command is killed and reported as `exit_code: -1`. The default of
120 covers every ordinary command with room to spare: a `gmail search` with a date window, a
calendar listing, a Drive share, a `sheets get` on a few hundred rows. What it does not cover is
a listing over a whole Drive or a `gmail search --all` on years of mail, and raising the timeout
is rarely the right answer there; narrowing the command is, and
[troubleshooting.md](troubleshooting.md) says how.

Raise it when a legitimate command really needs longer, a large `drive upload` or a `docs
export` of a long document over a slow line. The value is a number, fractions allowed, and it
must be greater than zero. `0`, a negative number or a word is refused at startup.

## Variables that belong to gog

The bridge passes its whole environment to gog and adds nothing to it except `GOG_HELP=full`
on `gog_help` calls. So anything gog reads from the environment goes in the same `env` block.

`GOG_KEYRING_PASSWORD` is the one that matters. gog stores refresh tokens in the platform
keyring, and when that keyring is the encrypted file backend (`gog auth keyring file`), gog needs
the password to open it and prompts on the terminal when the variable is unset. A process started
by Claude Desktop has no terminal, and the prompt becomes the error
`no TTY available for keyring file backend password prompt; set GOG_KEYRING_PASSWORD`. Put the
same value in the `env` block that the terminal session uses, and the prompt never happens.

`GOG_ACCESS_TOKEN` and `GOG_QUOTA_PROJECT` also exist on gog's side. Setting them in the `env`
block is a decision about your machine that the bridge does not make for you, and the matching
flags `--access-token` and `--quota-project` are refused in `args`, so the environment is the only
way to use them.

## Where uv puts things

`uvx gog-bridge` does not install anything permanently. On its first run uv downloads a Python
if none suitable is present, resolves the package and its dependencies, and builds an
environment in its cache: `%LOCALAPPDATA%\uv\cache` on Windows, `~/.cache/uv` on Linux and
macOS unless `UV_CACHE_DIR` says otherwise. Later runs reuse that environment and start in about
a second without touching the network.

Because the package is unpinned, uv resolves the latest published `gog-bridge` when its cache
does not already have one; `uv cache clean gog-bridge` makes the next start fetch the newest
release. To hold a version still, write `"args": ["gog-bridge@0.1.0"]`.

## A complete client config, one account

```json
{
  "mcpServers": {
    "gog": {
      "command": "C:\\Users\\you\\.local\\bin\\uvx.exe",
      "args": ["gog-bridge"],
      "env": {
        "GOG_BRIDGE_EXE": "C:\\Users\\you\\gog\\gog.exe",
        "GOG_BRIDGE_ACCOUNTS": "work=you@company.com"
      }
    }
  }
}
```

With one pair the model may omit `account`, and every call goes to `you@company.com`. The
absolute `uvx.exe` path is the Windows form; on Linux and macOS `"command": "uvx"` is enough.

## A complete client config, three accounts

```json
{
  "mcpServers": {
    "gog": {
      "command": "uvx",
      "args": ["gog-bridge"],
      "env": {
        "GOG_BRIDGE_EXE": "/usr/local/bin/gog",
        "GOG_BRIDGE_ACCOUNTS": "perso=you@gmail.com,work=you@company.com,asso=tresorier@club.org",
        "GOG_BRIDGE_TIMEOUT_SECONDS": "300",
        "GOG_KEYRING_PASSWORD": "the value gog auth keyring file was set up with"
      }
    }
  }
}
```

Here `account` is required on every `gog_run` and accepts `perso`, `work` or `asso`. The
`GOG_KEYRING_PASSWORD` line is only there because this machine runs gog on the file keyring;
leave it out on a machine whose platform keyring works from Claude Desktop. The password is in
that file in plain text, and the file usually lives in your profile directory; keep it out of
version control and out of screenshots.

## Next

[tools.md](tools.md) for what `account` looks like from the model's side,
[troubleshooting.md](troubleshooting.md) when a setting turns out to be the cause.
