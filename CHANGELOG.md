# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0 - 2026-09-16

First release. A Python rewrite of a Go bridge that was never published, with the same tool
surface, so a client already configured for the Go one only changes its `command` line.

### Added

- **`gog_run(account, args, stdin=None)`.** Runs `gog --account <address> --no-input <args...>`
  on `perso` or `work`, the two addresses fixed by the environment, and returns one text report:
  `exit_code: N`, stdout under `--- stdout ---`, stderr under `--- stderr ---`. A non-zero exit is
  returned as a tool error carrying the same report, so the calling model reads gog's own
  message. The server never crashes on a failed command.
- **`gog_help(args=[])`.** Runs `gog <args...> --help` with `GOG_HELP=full`, the only mode that
  prints the global flags along with the command's own. Empty `args` gives the top-level list.
- **The policy, checked before anything is spawned.** Refused: the commands `auth`, `config`,
  `mcp`, `batch`, `schema`, `backup`, `update` (self-update of the gog binary, which replaces
  the executable the bridge points at) and the `auth` aliases `login`, `logout`, `status`
  (top-level aliases in gog v0.40.0, found by reading `gog --help` on the binary), where the
  command is the first argument that is not a global flag, so `--json auth list` and
  `--color auto auth list` are refused like `auth list`, while `calendar update` passes
  because `update` is a subcommand there; any argument starting with `--home`, `--client`, `--access-token`, `--quota-project`, `--account`,
  `--enable-commands`, `--disable-commands`; the short account flag in every form kong parses,
  `-a`, `-a=x`, `-ax`, `-ja`, `-jaX`; empty `args` on `gog_run`; any argument containing a
  newline. Messages are in French, for the model to relay to a French user.
- **Bounded capture and a timeout.** stdout up to 200000 bytes, stderr up to 20000, each with a
  marker where it was cut, and both streams drained past the cap so a child blocked on a full
  pipe still exits. `GOG_BRIDGE_TIMEOUT_SECONDS`, 120 by default, kills the process and reports
  `exit_code: -1` with a note. On Windows the kill takes the whole process tree, because a
  wrapper's surviving child would otherwise keep the pipes open and `Process.wait()` never
  returns.
- **Windows as the target.** The spawn passes `CREATE_NO_WINDOW` under `sys.platform == "win32"`
  so no console should flash behind Claude Desktop, and the timeout path calls `taskkill /T /F`
  there; stdout and stderr are decoded as UTF-8 with replacement on every platform, which the
  suite checks with invalid bytes. The suite passes on `ubuntu-latest` and `windows-latest`,
  on Python 3.12 and 3.13 (run 35086557317).
- **Startup validation.** `GOG_BRIDGE_EXE`, `GOG_BRIDGE_ACCOUNT_PERSO` and
  `GOG_BRIDGE_ACCOUNT_WORK` are required, and the executable must be an absolute path to an
  existing file. A bad environment exits with status 2 and the list of what is expected on
  stderr. `gog-bridge --version` prints `gog-bridge 0.1.0`.
- **A test suite that spawns real processes.** `tests/fake_gog.py` behind a shell wrapper on
  POSIX and a `.cmd` wrapper on Windows, written so the same asyncio runner runs on both, with a
  tripwire wrapper proving that a refused call never reached the executable. Covered: both
  capture caps with their French marker, invalid UTF-8, timeout, non-zero exit, stdin delivery.
