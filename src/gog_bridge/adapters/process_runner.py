"""Asyncio implementation of CommandRunner.

Spawns gog without a shell, feeds stdin, captures both streams up to their caps
and kills the process when the timeout elapses. On Windows the process gets
CREATE_NO_WINDOW so no console flashes behind Claude Desktop, and a timeout
kills the whole tree, because a wrapper script's child would otherwise keep the
pipes open and hold the bridge hostage.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import subprocess
import sys
from typing import TYPE_CHECKING

from gog_bridge.domain.commands import (
    STDERR_LIMIT,
    STDOUT_LIMIT,
    TIMEOUT_EXIT_CODE,
    CommandOutcome,
)
from gog_bridge.domain.errors import CommandSpawnError

if TYPE_CHECKING:
    from asyncio.subprocess import Process

    from gog_bridge.domain.commands import CommandRequest

if sys.platform == "win32":
    CREATION_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    CREATION_FLAGS = 0

READ_CHUNK = 65_536
# Time allowed for a killed process to release its pipes before the bridge
# answers anyway. Only reached when a kill did not take.
KILL_GRACE_SECONDS = 5.0


class _BoundedBuffer:
    """Collects a stream up to a cap, then drains and discards the rest.

    Draining matters: a child blocked on a full pipe never exits, so the stream
    is read to EOF even after the cap is reached.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._data = bytearray()
        self.truncated = False

    @property
    def data(self) -> bytes:
        return bytes(self._data)

    async def drain(self, stream: asyncio.StreamReader | None) -> None:
        if stream is None:
            return
        while chunk := await stream.read(READ_CHUNK):
            room = self._limit - len(self._data)
            if room > 0:
                self._data += chunk[:room]
            if len(chunk) > room:
                self.truncated = True


class AsyncioProcessRunner:
    """Runs one gog command per call on the asyncio event loop."""

    def __init__(self, *, timeout_seconds: float) -> None:
        self._timeout = timeout_seconds

    @property
    def timeout_seconds(self) -> float:
        """Seconds a command may run before it is killed; the report's timeout note quotes it."""
        return self._timeout

    async def run(self, request: CommandRequest) -> CommandOutcome:
        """Spawn the process, feed stdin, capture both streams, wait for exit."""
        process = await self._spawn(request)
        stdout = _BoundedBuffer(STDOUT_LIMIT)
        stderr = _BoundedBuffer(STDERR_LIMIT)
        pumps = [
            asyncio.create_task(coro)
            for coro in (
                _feed_stdin(process, request.stdin),
                stdout.drain(process.stdout),
                stderr.drain(process.stderr),
            )
        ]

        try:
            async with asyncio.timeout(self._timeout):
                await asyncio.gather(*pumps, process.wait())
        except TimeoutError:
            await _settle(pumps)
            await _kill_and_drain(process, stdout, stderr)
            return _outcome(TIMEOUT_EXIT_CODE, stdout, stderr, timed_out=True)

        return _outcome(_returncode(process), stdout, stderr, timed_out=False)

    async def _spawn(self, request: CommandRequest) -> Process:
        env = dict(os.environ)
        env.update(request.env)
        stdin = asyncio.subprocess.PIPE if request.stdin is not None else asyncio.subprocess.DEVNULL
        try:
            return await asyncio.create_subprocess_exec(
                *request.argv,
                stdin=stdin,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                creationflags=CREATION_FLAGS,
            )
        except OSError as exc:
            raise CommandSpawnError(f"{exc.strerror or exc}") from exc


def _outcome(
    exit_code: int, stdout: _BoundedBuffer, stderr: _BoundedBuffer, *, timed_out: bool
) -> CommandOutcome:
    return CommandOutcome(
        exit_code=exit_code,
        stdout=stdout.data,
        stderr=stderr.data,
        stdout_truncated=stdout.truncated,
        stderr_truncated=stderr.truncated,
        timed_out=timed_out,
    )


def _returncode(process: Process) -> int:
    code = process.returncode
    if code is None:
        raise RuntimeError("process.wait() returned without a return code")
    return code


async def _feed_stdin(process: Process, data: str | None) -> None:
    if process.stdin is None or data is None:
        return
    try:
        process.stdin.write(data.encode("utf-8"))
        await process.stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        # The child exited before reading its input. Its exit code and stderr
        # carry the reason; the broken pipe itself is not the failure.
        pass
    finally:
        process.stdin.close()


async def _settle(pumps: list[asyncio.Task[None]]) -> None:
    """Let cancelled pump tasks finish, so the streams can be read again safely."""
    for pump in pumps:
        pump.cancel()
    await asyncio.gather(*pumps, return_exceptions=True)


async def _kill_and_drain(process: Process, stdout: _BoundedBuffer, stderr: _BoundedBuffer) -> None:
    """Kill the process, on Windows its whole tree, then collect what it left in the pipes.

    asyncio's Process.wait() only returns once every pipe is disconnected, so a
    surviving grandchild holding stdout would block here forever. taskkill /T
    takes the tree down; the grace period is the last resort, after which the
    outcome is reported as it stands.
    """
    if process.returncode is None:
        if sys.platform == "win32":
            await _taskkill_tree(process.pid)
        with contextlib.suppress(ProcessLookupError):
            process.kill()
    try:
        async with asyncio.timeout(KILL_GRACE_SECONDS):
            await asyncio.gather(
                stdout.drain(process.stdout), stderr.drain(process.stderr), process.wait()
            )
    except TimeoutError:
        pass


async def _taskkill_tree(pid: int) -> None:
    killer = await asyncio.create_subprocess_exec(
        "taskkill",
        "/T",
        "/F",
        "/PID",
        str(pid),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        creationflags=CREATION_FLAGS,
    )
    await killer.wait()
