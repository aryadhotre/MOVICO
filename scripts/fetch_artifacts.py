"""Downloads and unpacks the catalogue and model artifacts.

Render's free tier gives a container no persistent disk, so anything written at
runtime is gone on the next deploy and on every wake from idle. The artifacts
therefore have to arrive with the image, and since they are too large for the
repository they are fetched from a release asset at *build* time -- one layer,
cached by Docker, re-run only when ``ARTIFACTS_URL`` changes.

Standard library only, deliberately: this runs in the Docker build before
``pip install``, so it cannot import requests.

    python scripts/fetch_artifacts.py --url https://.../movico-artifacts.tar.gz
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: A tar entry may not escape the destination. Without this check a crafted
#: archive containing "../../etc/cron.d/x" or an absolute path writes anywhere the
#: build user can reach -- the extraction traversal that CVE-2007-4559 tracked in
#: the standard library for fifteen years.
ALLOWED_PREFIXES = ("data/", "models_checkpoint/")


def _safe_members(tar: tarfile.TarFile, destination: Path):
    """Yields only regular files that land inside an expected directory."""
    root = destination.resolve()
    for member in tar.getmembers():
        if not (member.isfile() or member.isdir()):
            # No symlinks, no devices, no hardlinks: a symlink member is the other
            # half of the traversal trick.
            print(f"  ! skipping non-regular entry {member.name}")
            continue
        name = member.name.lstrip("./")
        if not name.startswith(ALLOWED_PREFIXES):
            print(f"  ! skipping unexpected entry {member.name}")
            continue
        target = (root / name).resolve()
        if not target.is_relative_to(root):
            print(f"  ! skipping escaping entry {member.name}")
            continue
        member.name = name
        yield member


def download(url: str, destination: Path, attempts: int = 3) -> None:
    """Streams a URL to disk, retrying transient failures.

    A build that fails because a CDN blipped is worse than one that waits four
    seconds, and Render retries the whole build rather than the step.
    """
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "movico-build"})
            with urllib.request.urlopen(request, timeout=120) as response:
                total = int(response.headers.get("Content-Length") or 0)
                done = 0
                last = 0.0
                with open(destination, "wb") as handle:
                    while chunk := response.read(1 << 20):
                        handle.write(chunk)
                        done += len(chunk)
                        now = time.time()
                        if total and now - last > 2:
                            print(f"  {done / 1048576:7.1f} / {total / 1048576:.1f} MB", flush=True)
                            last = now
            print(f"  downloaded {destination.stat().st_size / 1048576:.1f} MB")
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == attempts:
                raise
            wait = 2**attempt
            print(f"  attempt {attempt} failed ({exc}); retrying in {wait}s", flush=True)
            time.sleep(wait)


def verify(path: Path, expected: str) -> None:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            sha.update(chunk)
    actual = sha.hexdigest()
    if actual != expected.lower().strip():
        raise SystemExit(
            f"Checksum mismatch.\n  expected {expected}\n  actual   {actual}\n"
            "The download is corrupt or the asset was replaced."
        )
    print(f"  checksum ok ({actual[:16]}...)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("ARTIFACTS_URL", ""))
    parser.add_argument("--sha256", default=os.getenv("ARTIFACTS_SHA256", ""))
    parser.add_argument("--destination", type=Path, default=ROOT)
    parser.add_argument(
        "--optional",
        action="store_true",
        help="exit 0 when no URL is configured, for builds that seed another way",
    )
    args = parser.parse_args()

    if not args.url:
        message = (
            "ARTIFACTS_URL is not set. The API will start, but with an empty\n"
            "catalogue and no trained models: browse returns nothing and\n"
            "/api/recommendations returns 503."
        )
        if args.optional:
            print(message)
            return 0
        print(message, file=sys.stderr)
        return 1

    print(f"Fetching artifacts from {args.url}")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "artifacts.tar.gz"
        download(args.url, archive)

        if args.sha256:
            verify(archive, args.sha256)
        else:
            print("  ! ARTIFACTS_SHA256 not set; skipping integrity check")

        args.destination.mkdir(parents=True, exist_ok=True)
        print("Extracting...")
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(args.destination, members=_safe_members(tar, args.destination))

    for path in sorted(args.destination.rglob("*")):
        if path.is_file() and path.suffix in {".db", ".pkl", ".npz", ".json"}:
            rel = path.relative_to(args.destination)
            if str(rel).startswith(ALLOWED_PREFIXES):
                print(f"  {str(rel):48s} {path.stat().st_size / 1048576:7.1f} MB")

    database = args.destination / "data" / "movico.db"
    if not database.exists():
        raise SystemExit("Bundle did not contain data/movico.db")

    print("Artifacts ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
