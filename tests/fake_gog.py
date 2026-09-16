"""A stand-in for the gog executable, driven by environment variables.

It echoes its argv, its stdin and the GOG_HELP variable as one JSON object on
stdout, writes one line on stderr, then exits. The variables:

- FAKE_GOG_EXIT: exit status, default 0.
- FAKE_GOG_SLEEP_MS: milliseconds to sleep before answering, default 0.
- FAKE_GOG_STDOUT_BYTES: extra bytes of padding appended after the JSON line.
- FAKE_GOG_STDERR_BYTES: extra bytes of padding appended after the stderr line.
- FAKE_GOG_RAW_BYTES: hex-encoded raw bytes written to both streams after the
  padding, for bytes that are not valid UTF-8 (`fffe`).

It is a plain script rather than a pytest helper because the runner under test
spawns it as a real process through a platform wrapper.
"""

from __future__ import annotations

import json
import os
import sys
import time


def main() -> None:
    sleep_ms = int(os.environ.get("FAKE_GOG_SLEEP_MS", "0"))
    if sleep_ms:
        time.sleep(sleep_ms / 1000)

    payload = {
        "argv": sys.argv[1:],
        "stdin": sys.stdin.read(),
        "gog_help": os.environ.get("GOG_HELP"),
    }
    raw = bytes.fromhex(os.environ.get("FAKE_GOG_RAW_BYTES", ""))

    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.write("x" * int(os.environ.get("FAKE_GOG_STDOUT_BYTES", "0")))
    sys.stdout.flush()
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()

    sys.stderr.write("fake gog: done\n")
    sys.stderr.write("e" * int(os.environ.get("FAKE_GOG_STDERR_BYTES", "0")))
    sys.stderr.flush()
    sys.stderr.buffer.write(raw)
    sys.stderr.buffer.flush()
    sys.exit(int(os.environ.get("FAKE_GOG_EXIT", "0")))


if __name__ == "__main__":
    main()
