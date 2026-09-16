# CLAUDE.md, gog-bridge

## Purpose

MCP server that lets Claude Desktop drive the whole gog CLI (Google Workspace from the
command line) on two fixed accounts, through two tools: `gog_run` executes a command,
`gog_help` prints its full help. The bundled `gog mcp` exposes 8 read-only tools (10 with
`--allow-write`, measured on v0.40.0) and cannot send mail; this bridge exposes every command
and enforces a policy instead of an allowlist. Windows is the target platform; Linux and
macOS work the same and are where development happens.

## Architecture

Three layers, dependencies pointing inward only.

- **Domain** (`domain/`): `policy.py` is the security boundary, see below; `commands.py`
  holds `Accounts`, `CommandRequest`, `CommandOutcome`, the `CommandRunner` protocol, the
  capture caps and the two argv builders; `rendering.py` turns an outcome into the text
  report; `messages.py` holds every French sentence the model reads; `errors.py` the
  exception hierarchy. Imports neither `fastmcp` nor `subprocess`.
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

- First argument in `auth`, `config`, `mcp`, `batch`, `schema`, `backup`, plus `login`,
  `logout` and `status`, which are top-level aliases of `auth add`, `auth remove` and
  `auth status` in gog v0.40.0. The aliases were found on 2026-09-16 by reading `gog --help`
  on the real binary; the original list did not have them.
- Any argument starting with `--home`, `--client`, `--access-token`, `--quota-project`,
  `--account`, `--enable-commands`, `--disable-commands`. Prefix match on the whole
  argument, so `=value` forms and `--enable-commands-exact` fall under it.
- The short account flag in every kong form: `-a`, `-a=x`, `-ax`, and clusters `-ja`,
  `-jaX`. Rule: single dash, then letters until the first non-letter; an `a` among those
  letters refuses. `-n5a` passes because `5` ends the scan.
- Empty `args` on `gog_run` only. Any argument containing `\n` or `\r`.

Refusal messages, the timeout note, the truncation marker and the spawn failure are the
only French strings in the code base, all in `domain/messages.py`. Everything else, tool
descriptions included, is English.

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
  working directory is not a place to pick up a file from. `GOG_BRIDGE_EXE` is validated as
  an absolute existing file at startup, so tests must give `Settings` a real file.

## Commands

```bash
make install   # uv sync --all-extras
make check     # lint + test, what CI runs
make lint      # ruff check, ruff format --check, mypy
make test      # pytest, real subprocesses, no network
make run       # start the server on stdio
make build     # uv build
```

## Testing

Every test drives the real MCP surface with `fastmcp.Client(server)`, and the real
`AsyncioProcessRunner`: nothing patches the subprocess layer. The external dependency is the
gog process, played by `tests/fake_gog.py` behind a wrapper that `conftest.write_wrapper`
builds per platform (`.cmd` on Windows invoking `sys.executable`, a `#!/bin/sh` `exec` script
elsewhere). The fake echoes argv, stdin and `GOG_HELP` as JSON and obeys `FAKE_GOG_EXIT`,
`FAKE_GOG_SLEEP_MS`, `FAKE_GOG_STDOUT_BYTES`, set through `monkeypatch.setenv` because the
runner inherits `os.environ` at spawn time. Policy tests use a second wrapper that appends
to a marker file before running the fake: no marker, no spawn. `create_server(settings,
runner=...)` exists as a seam for embedding, the suite does not use it.

`test_main.py` runs `python -m gog_bridge` as a subprocess for `--version` and the bad
environment cases. On the shell wrapper, `exec` matters: without it the kill on timeout hits
the shell and leaves Python holding the pipes.

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
- 2026-09-16: GNU make is not guaranteed on the `windows-latest` runner image, so `ci.yml`
  spells out the lint and test recipes as `uv run` commands. Keep them identical to the
  Makefile; `release.yml` runs on Ubuntu and keeps calling make.

## Publishing

Version lives in `pyproject.toml` only. A published GitHub release triggers `release.yml`,
which checks the tag against that version, runs the gates, builds, then uploads through PyPI
trusted publishing (environment `pypi`, no token anywhere). Bump the version and add the
CHANGELOG entry in the same commit, tag `vX.Y.Z`, publish the release.
