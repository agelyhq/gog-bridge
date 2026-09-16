"""Download the gog v0.40.0 release binary for this machine and print its path.

Standard library only, so it runs before `uv sync` and on a bare CI runner. The
archive and checksums.txt land in .cache/gog/ (or --cache-dir), the SHA256 is
checked against checksums.txt before anything is extracted, and a second run
with a valid cache touches no network. A checksum mismatch removes the archive
and exits 1, so the next run downloads it again.
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import stat
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "0.40.0"
RELEASE_URL = f"https://github.com/openclaw/gogcli/releases/download/v{VERSION}"
CHECKSUMS_NAME = "checksums.txt"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "gog"

OS_NAMES = {"linux": "linux", "darwin": "darwin", "win32": "windows"}
ARCH_NAMES = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}

READ_CHUNK = 1 << 20


class FetchError(Exception):
    """Something about the download or the archive is wrong. Message names it."""


def asset_name() -> str:
    """`gogcli_0.40.0_<os>_<arch>.<tar.gz|zip>` for the interpreter's platform."""
    try:
        os_name = OS_NAMES[sys.platform]
        arch = ARCH_NAMES[platform.machine().lower()]
    except KeyError as exc:
        raise FetchError(f"no gog {VERSION} asset for {sys.platform}/{platform.machine()}") from exc
    extension = "zip" if os_name == "windows" else "tar.gz"
    return f"gogcli_{VERSION}_{os_name}_{arch}.{extension}"


def binary_name() -> str:
    return "gog.exe" if sys.platform == "win32" else "gog"


def download(name: str, into: Path) -> Path:
    target = into / name
    if target.is_file():
        return target
    url = f"{RELEASE_URL}/{name}"
    print(f"downloading {url}", file=sys.stderr)
    partial = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as out:
        shutil.copyfileobj(response, out)
    partial.replace(target)
    return target


def expected_sha256(checksums: Path, name: str) -> str:
    for line in checksums.read_text(encoding="utf-8").splitlines():
        digest, _, listed = line.strip().partition("  ")
        if listed == name:
            return digest
    raise FetchError(f"{name} is not listed in {checksums}")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(archive: Path, checksums: Path) -> None:
    expected = expected_sha256(checksums, archive.name)
    actual = sha256_of(archive)
    if actual != expected:
        archive.unlink()
        raise FetchError(
            f"SHA256 mismatch for {archive.name}: expected {expected}, got {actual}. "
            "The archive was removed; run again to download it afresh."
        )


def extract_binary(archive: Path, into: Path) -> Path:
    """Pull the single gog executable out of the archive, whatever directory it sits in."""
    wanted = binary_name()
    target = into / wanted
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            member = _find_member(bundle.namelist(), wanted, archive)
            with bundle.open(member) as source, target.open("wb") as out:
                shutil.copyfileobj(source, out)
    else:
        with tarfile.open(archive, "r:gz") as bundle:
            member = _find_member(bundle.getnames(), wanted, archive)
            extracted = bundle.extractfile(member)
            if extracted is None:
                raise FetchError(f"{member} in {archive.name} is not a regular file")
            with extracted, target.open("wb") as out:
                shutil.copyfileobj(extracted, out)
    if sys.platform != "win32":
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return target


def _find_member(names: list[str], wanted: str, archive: Path) -> str:
    for name in names:
        if Path(name).name == wanted:
            return name
    raise FetchError(f"{archive.name} holds no {wanted}; members: {', '.join(names)}")


def fetch(cache_dir: Path) -> Path:
    """Return the path of a verified gog binary, downloading only what is missing."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    binary = cache_dir / binary_name()
    checksums = download(CHECKSUMS_NAME, cache_dir)
    archive = download(asset_name(), cache_dir)
    verify(archive, checksums)
    if not binary.is_file():
        extract_binary(archive, cache_dir)
    return binary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"where the archive, checksums.txt and the binary live (default {DEFAULT_CACHE_DIR})",
    )
    options = parser.parse_args()
    try:
        binary = fetch(options.cache_dir.resolve())
    except FetchError as exc:
        print(f"fetch_gog: {exc}", file=sys.stderr)
        sys.exit(1)
    print(binary)


if __name__ == "__main__":
    main()
