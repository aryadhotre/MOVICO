"""Bundles the catalogue and trained models into one release asset.

Why a release asset rather than the repository: the catalogue is ~215 MB and the
model artifacts ~127 MB. GitHub rejects any single file over 100 MB, warns above
50 MB, and -- more to the point -- stores every version of a binary file forever,
so committing a database that is rebuilt after each enrichment run would add its
full size to the clone weight every time. A release asset has none of those
properties: 2 GB per file, replaceable in place, and not part of history.

Run this after retraining or a catalogue import::

    python -m scripts.package_artifacts

then upload ``dist/movico-artifacts.tar.gz`` to a GitHub release and point
``ARTIFACTS_URL`` at it. ``scripts/fetch_artifacts.py`` is the other half.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "dist" / "movico-artifacts.tar.gz"

#: Only these are shipped. The MovieLens source CSVs, the downloaded zip and the
#: 412 MB interaction matrix are training inputs -- the API never reads them, and
#: including them would quadruple the bundle.
CONTENTS = [
    ("data/movico.db", "data/movico.db"),
    ("models_checkpoint/ials.pkl", "models_checkpoint/ials.pkl"),
    ("models_checkpoint/itemknn.pkl", "models_checkpoint/itemknn.pkl"),
    ("models_checkpoint/content.pkl", "models_checkpoint/content.pkl"),
    ("models_checkpoint/catalogue_index.npz", "models_checkpoint/catalogue_index.npz"),
    ("models_checkpoint/evaluation_metrics.json", "models_checkpoint/evaluation_metrics.json"),
]


def compact(db_path: Path) -> None:
    """VACUUMs the catalogue so the bundle carries pages, not free space.

    Two details make this fail silently if got wrong. VACUUM cannot run inside a
    transaction, so the connection must be in autocommit (``isolation_level=None``);
    and in WAL mode it rewrites the file without releasing the freed pages, so the
    journal has to be switched to DELETE for the duration. Skipping either returns
    success and saves nothing.
    """
    before = db_path.stat().st_size
    connection = sqlite3.connect(db_path, isolation_level=None)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("VACUUM")
        connection.execute("PRAGMA optimize")
        connection.execute("PRAGMA journal_mode=WAL")
    finally:
        connection.close()
    after = db_path.stat().st_size
    print(f"  compacted {before / 1048576:.1f} MB -> {after / 1048576:.1f} MB")


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--no-vacuum", action="store_true", help="skip compacting the catalogue"
    )
    args = parser.parse_args()

    missing = [source for source, _ in CONTENTS if not (ROOT / source).exists()]
    required = [m for m in missing if "evaluation_metrics" not in m]
    if required:
        print("Missing artifacts:", file=sys.stderr)
        for item in required:
            print(f"  {item}", file=sys.stderr)
        print(
            "\nRun the pipeline first:\n"
            "  python -m app.pipeline.ingest\n"
            "  python -m app.ml.train\n",
            file=sys.stderr,
        )
        return 1

    db_path = ROOT / "data/movico.db"
    if not args.no_vacuum:
        print("Compacting catalogue...")
        compact(db_path)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Packing -> {args.output}")
    started = time.time()
    with tarfile.open(args.output, "w:gz", compresslevel=6) as tar:
        for source, arcname in CONTENTS:
            path = ROOT / source
            if not path.exists():
                print(f"  (skipping absent {source})")
                continue
            print(f"  + {arcname:48s} {path.stat().st_size / 1048576:7.1f} MB")
            tar.add(path, arcname=arcname)

    size = args.output.stat().st_size / 1048576
    print(f"\nBundle: {size:.1f} MB in {time.time() - started:.0f}s")
    print(f"sha256: {digest(args.output)}")
    print(
        "\nUpload it as a GitHub release asset, then set ARTIFACTS_URL to the\n"
        "asset's browser_download_url in the Render dashboard."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
