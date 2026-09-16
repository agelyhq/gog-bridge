# CLAUDE.md, gog-bridge

## Purpose

MCP server that lets Claude Desktop drive the whole gog CLI (Google Workspace from the
command line) on the accounts the operator lists, through two tools: `gog_run` executes a
command, `gog_help` prints its full help. The bundled `gog mcp` exposes 8 read-only tools (10 with
`--allow-write`, measured on v0.40.0) and cannot send mail; this bridge exposes every command
and enforces a policy instead of an allowlist. Windows is the target platform; Linux and
macOS work the same and are where development happens.

## Architecture

Three layers, dependencies pointing inward only.

- **Domain** (`domain/`): `policy.py` is the security boundary, see below; `accounts.py`
  holds `Accounts`, the alias to address map parsed from `GOG_BRIDGE_ACCOUNTS`, with
  `email_for` raising the French `UnknownAccountError`; `commands.py` holds
  `CommandRequest`, `CommandOutcome`, the `CommandRunner` protocol, the capture caps and the
  two argv builders; `rendering.py` turns an outcome into the text report; `messages.py`
  holds every French sentence the model reads; `errors.py` the exception hierarchy. Imports
  neither `fastmcp` nor `subprocess`.
- **Adapters** (`adapters/process_runner.py`): `AsyncioProcessRunner`, the only module that
  spawns processes. asyncio subprocess, bounded stream capture, timeout with kill.
- **Tools** (`tools/`): one file per MCP tool, plus `_errors.py` (domain error to
  `ToolError`) and `_execute.py` (runner call, report, non-zero exit to error).
- **Composition root**: `server.py` builds `ToolDeps` (`deps.py`) and the `FastMCP`
  instance. `config.py` is the only module that reads the environment; `__main__.py`
  handles `--version` and turns a bad environment into a non-zero exit with the reason on
  stderr.

## The policy is the security boundary

`domain/policy.py`, run before any process exists. The caller must never be able to change
which account gog acts as, where it reads its configuration, or which commands it has. The
rules, all covered by `tests/test_policy.py` with a tripwire wrapper proving nothing spawned:

- The command in `auth`, `config`, `mcp`, `batch`, `schema`, `backup`, `update`, plus
  `login`, `logout` and `status`, which are top-level aliases of `auth add`, `auth remove` and
  `auth status` in gog v0.40.0. The aliases were found on 2026-09-16 by reading `gog --help`
  on the real binary; the original list did not have them. `update` (self-update of the
  binary) was added the same day by decision of Fabien: it replaces the executable the bridge
  points at, which is the installer's job. `api call` stays allowed. The command is what
  `leading_command` returns: the first argument that does not start with a dash, skipping the
  value after `--color` or `--select` (`VALUE_TAKING_GLOBAL_FLAGS`, the only value-taking
  global flags v0.40.0 lets through). Checking `args[0]` alone was a hole measured live on
  2026-09-16: `--json auth list` reached gog and returned its account list.
- Any argument starting with `--home`, `--client`, `--access-token`, `--quota-project`,
  `--account`, `--enable-commands`, `--disable-commands`. Prefix match on the whole
  argument, so `=value` forms and `--enable-commands-exact` fall under it.
- The short account flag in every kong form: `-a`, `-a=x`, `-ax`, and clusters `-ja`,
  `-jaX`. Rule: single dash, then letters until the first non-letter; an `a` among those
  letters refuses. `-n5a` passes because `5` ends the scan.
- Empty `args` on `gog_run` only. Any argument containing `\n` or `\r`.

Refusal messages, the unknown account, the timeout note, the truncation marker and the
spawn failure are the only French strings in the code base, all in `domain/messages.py`.
Everything else, tool descriptions included, is English.

## Accounts and the `account` parameter

One variable, `GOG_BRIDGE_ACCOUNTS`, holds `alias=email` pairs separated by commas
(`perso=me@gmail.com,work=me@company.com`). `Accounts.parse` refuses an empty list, an entry
without `=`, an alias outside `^[a-z][a-z0-9_-]{0,31}$`, an address without `@` and a
duplicate alias; the refusal reaches stderr through `SettingsLoadError` and the process
exits 2. The former `GOG_BRIDGE_ACCOUNT_PERSO` and `GOG_BRIDGE_ACCOUNT_WORK` are gone, with
no compatibility path.

`tools/gog_run.py` shapes the `account` parameter at registration from the parsed aliases:
the JSON schema carries `enum: [aliases]` and a description listing each alias with its
address; with exactly one alias the parameter gets that alias as default and leaves
`required`, otherwise it is required. The Python type stays `str`, on purpose: an alias
outside the enum reaches the tool and is refused there in French, naming the valid ones,
instead of dying in pydantic's English validation error. FastMCP builds the schema from the
function's annotations and `inspect.signature`, and `mcp.tool` takes no schema of its own,
so that module does not defer its annotations: the `Annotated[str, Field(...)]` built for
the aliases is a closure variable evaluated at `def` time, and the default is written into
`__kwdefaults__` (the parameters are keyword-only so `account` can have a default while
`args` has none). A deferred annotation would be an unresolvable string, and on Python 3.14
an assignment to `__annotations__` after the `def` is lost because `functools.wraps` copies
`__annotate__` instead. Measured on 2026-09-16 on 3.12 and 3.14.

## Key conventions

- **Tool discovery is automatic.** `tools/__init__.py` imports every module in the package
  not starting with `_` and calls its `register(mcp, deps)`. Helpers are underscore-prefixed.
- **One report shape.** `exit_code: N`, optional `note: ...`, `--- stdout ---`, the stream,
  `--- stderr ---`, the stream. Success returns it; a non-zero exit raises
  `CommandFailedError(report)` so the client sees `isError` with the same text. The server
  never crashes on a failed command.
- **Caps live in the domain, enforcement in the adapter.** `STDOUT_LIMIT` 200000 and
  `STDERR_LIMIT` 20000 bytes in `commands.py`; `_BoundedBuffer` keeps reading past the cap
  and discards, because a child blocked on a full pipe never exits. Decoding is UTF-8 with
  `errors="replace"` on every platform, in `rendering.py`.
- **Timeout means kill, then drain.** `TIMEOUT_EXIT_CODE` is -1. On timeout the pump tasks
  are cancelled and awaited (`_settle`) before the streams are read again, otherwise
  `StreamReader` raises "another coroutine is already waiting". On win32 the kill is
  `taskkill /T /F` on the pid first, then `process.kill()`.
- **Windows spawn.** `creationflags=CREATE_NO_WINDOW` under `sys.platform == "win32"`; mypy
  narrows on that check, so no `getattr` tricks. stdin is `DEVNULL` unless text was given,
  never inherited from the MCP stdio pipe.
- **Errors surface as `ToolError`.** `as_tool_errors` catches `GogBridgeError` only; a
  defect in this server crashes rather than being reported as the caller's mistake.
- **No `.env` file.** `Settings` reads the process environment only; Claude Desktop's
  working directory is not a place to pick up a file from. `.env.example` documents the
  variables and nothing reads it. `GOG_BRIDGE_EXE` is validated as an absolute existing file
  at startup, so tests must give `Settings` a real file. `GOG_BRIDGE_ACCOUNTS` is annotated
  `NoDecode` (pydantic-settings 2.7) so the raw string reaches `Accounts.parse` instead of
  the JSON decoding pydantic-settings applies to non-scalar fields.

## Commands

```bash
make install   # uv sync --all-extras
make check     # lint + test, what the CI check job runs
make lint      # ruff check, ruff format --check, mypy, on src tests scripts
make test      # pytest, real subprocesses, no network; the e2e directory skips
make e2e       # fetch gog v0.40.0 into .cache/gog/ (SHA256-checked), then pytest -m e2e
make run       # start the server on stdio
make build     # uv build
```

## Testing

Every test drives the real MCP surface with `fastmcp.Client(server)`, and the real
`AsyncioProcessRunner`: nothing patches the subprocess layer. The external dependency is the
gog process, played by `tests/fake_gog.py` behind a wrapper that `conftest.write_wrapper`
builds per platform (`.cmd` on Windows invoking `sys.executable`, a `#!/bin/sh` `exec` script
elsewhere). The fake echoes argv, stdin and `GOG_HELP` as JSON and obeys `FAKE_GOG_EXIT`,
`FAKE_GOG_SLEEP_MS`, `FAKE_GOG_STDOUT_BYTES`, `FAKE_GOG_STDERR_BYTES` and `FAKE_GOG_RAW_BYTES`
(hex, written to both streams, for the invalid UTF-8 scenario), set through
`monkeypatch.setenv` because the runner inherits `os.environ` at spawn time; a new knob goes
in `conftest.FAKE_ENV_VARS` too, or it leaks between tests. Policy tests use a second wrapper that appends
to a marker file before running the fake: no marker, no spawn. `create_server(settings,
runner=...)` exists as a seam for embedding, the suite does not use it.

`test_main.py` runs `python -m gog_bridge` as a subprocess for `--version` and the bad
environment cases, the malformed `GOG_BRIDGE_ACCOUNTS` values included. On the shell
wrapper, `exec` matters: without it the kill on timeout hits the shell and leaves Python
holding the pipes. `tests/reports.py` holds `report_text` and `parse_report`, shared with
the e2e tier; `tests/conftest.py` keeps the fixtures and `echoed`.

### The end-to-end tier

`tests/e2e/` starts the installed console script `gog-bridge` as a real subprocess over
stdio, the way Claude Desktop starts it, through `fastmcp.client.transports.StdioTransport`,
against the real gog v0.40.0 binary named by `GOG_BRIDGE_E2E_GOG`. Without that variable, or
if it names no file, every test in the directory is skipped with the reason; the marker
`e2e` is added by the directory's `pytest_collection_modifyitems`, so `pytest -m e2e`
selects the tier and a plain `pytest` runs it too when the variable is set.
`scripts/fetch_gog.py` (stdlib only, `--cache-dir` to relocate `.cache/gog/`) downloads the
asset for the current platform plus `checksums.txt`, verifies the SHA256, extracts the
binary and prints its path; a mismatch deletes the archive and exits 1.

The bridge process gets `GOG_BRIDGE_ACCOUNTS=perso=...,work=...` on `example.invalid`
addresses and an isolated home under `tmp_path`: `HOME` and the four `XDG_*_HOME` on POSIX,
`USERPROFILE`, `APPDATA`, `LOCALAPPDATA` on Windows, all set on every platform. The mcp
stdio client starts from its own short allowlist of inherited variables, so the developer's
`GOG_*` never reach the bridge. No credential exists there, so `drive ls` and `gmail send`
fail inside gog with exit 10 and "OAuth client credentials missing" on stderr, naming a path
under the isolated home, which the test asserts. Every call is held under 30 s, far from
the 120 s default timeout. The tier runs in CI as the `e2e` job on `ubuntu-latest` and
`windows-latest` after `check`.

`tests/e2e/__init__.py` exists so the directory's conftest imports as `e2e.conftest`;
without it pytest loads both conftest modules under the bare name `conftest` and the unit
tier's `from conftest import ...` lands in the wrong file (measured 2026-09-16).

## Gotchas, dated

- 2026-09-16: `asyncio.subprocess.Process.wait()` returns only once every pipe is
  disconnected (`base_subprocess._try_finish`). Killing a `.cmd` wrapper kills `cmd.exe` and
  not its Python child, which keeps stdout open, so the timeout path on Windows needs the
  tree kill. `KILL_GRACE_SECONDS` bounds the wait either way.
- 2026-09-16: ruff's TC003 wants `pathlib.Path` under `TYPE_CHECKING` in `config.py`, but
  pydantic needs it at runtime; `runtime-evaluated-base-classes` lists `BaseSettings`.
- 2026-09-16: mypy requires literal `alias=` strings on pydantic fields, so the env names
  are spelled twice, once in `Field(alias=...)` and once in the `ENV_*` constants used by
  the startup message.
- 2026-09-16: a stdlib dataclass used as a pydantic field must annotate with builtins
  (`dict[str, str]`), not `Mapping` imported under `TYPE_CHECKING`, or pydantic raises
  "not fully defined" at the first `Settings()`.
- 2026-09-16: GNU make is not guaranteed on the `windows-latest` runner image, so `ci.yml`
  spells out the lint and test recipes as `uv run` commands. Keep them identical to the
  Makefile; `release.yml` runs on Ubuntu and keeps calling make.
- 2026-09-16: first Windows run went red because `tests/fake_gog.py` used text-mode streams
  (CRLF, cp1252); the fake now uses binary streams and the `windows-latest` jobs are green
  (run 35086557317). Keep the fake byte-exact.

## Publishing

Version lives in `pyproject.toml` only. A published GitHub release triggers `release.yml`,
which checks the tag against that version, runs the gates, builds, then uploads through PyPI
trusted publishing (environment `pypi`, no token anywhere). Bump the version and add the
CHANGELOG entry in the same commit, tag `vX.Y.Z`, publish the release.
