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

Every stream goes through its binary buffer. The text-mode streams depend on
the locale and on the platform: on Windows, `sys.stdin.read()` decodes with the
console code page (cp1252 on the CI runner, which mangles UTF-8), and a text
`write("\\n")` comes out as `\\r\\n`. The bridge under test sends UTF-8 and
expects `\\n`, and the assertions are byte-exact, so the fake must be too.
"""

from __future__ import annotations

import json
import os
import sys
import time

NEWLINE = b"\n"


def main() -> None:
    sleep_ms = int(os.environ.get("FAKE_GOG_SLEEP_MS", "0"))
    if sleep_ms:
        time.sleep(sleep_ms / 1000)

    payload = {
        "argv": sys.argv[1:],
        "stdin": sys.stdin.buffer.read().decode("utf-8"),
        "gog_help": os.environ.get("GOG_HELP"),
    }
    raw = bytes.fromhex(os.environ.get("FAKE_GOG_RAW_BYTES", ""))

    stdout = sys.stdout.buffer
    stdout.write(json.dumps(payload).encode("utf-8") + NEWLINE)
    stdout.write(b"x" * int(os.environ.get("FAKE_GOG_STDOUT_BYTES", "0")))
    stdout.write(raw)
    stdout.flush()

    stderr = sys.stderr.buffer
    stderr.write(b"fake gog: done" + NEWLINE)
    stderr.write(b"e" * int(os.environ.get("FAKE_GOG_STDERR_BYTES", "0")))
    stderr.write(raw)
    stderr.flush()
    sys.exit(int(os.environ.get("FAKE_GOG_EXIT", "0")))


if __name__ == "__main__":
    main()
