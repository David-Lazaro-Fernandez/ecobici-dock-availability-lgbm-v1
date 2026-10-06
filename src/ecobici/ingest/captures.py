"""Own GBFS captures: mirror the collector's S3 prefix into ``raw/`` (M7).

The EC2 collector writes ``<feed>/YYYY/MM/DD/<feed>_<ts>Z.json.gz`` under ``raw/`` in the
bucket named by ``S3_BUCKET_NAME`` (environment or ``.env``). Files are immutable, so a
local copy with the same size is never fetched again.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

PREFIX = "raw"
DEFAULT_DIR = Path("raw")
BUCKET_ENV = "S3_BUCKET_NAME"


@dataclass(frozen=True)
class RemoteObject:
    key: str
    size: int


def bucket_from_env(dotenv: Path = Path(".env")) -> str:
    """``S3_BUCKET_NAME`` from the environment, else from a ``KEY=value`` line in ``.env``."""
    if bucket := os.environ.get(BUCKET_ENV):
        return bucket
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == BUCKET_ENV:
                return value.strip().strip("'\"")
    raise SystemExit(f"{BUCKET_ENV} is not set (environment or {dotenv})")


def list_remote(client, bucket: str, prefix: str = PREFIX) -> list[RemoteObject]:
    paginator = client.get_paginator("list_objects_v2")
    objects = [
        RemoteObject(o["Key"], int(o["Size"]))
        for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix.strip('/')}/")
        for o in page.get("Contents", [])
        if not o["Key"].endswith("/")
    ]
    return sorted(objects, key=lambda o: o.key)


def download(
    bucket: str,
    dest: Path = DEFAULT_DIR,
    prefix: str = PREFIX,
    feed: str | None = None,
    client=None,
) -> tuple[int, int]:
    """Fetch every object not already present with the same size.

    ``feed`` (e.g. ``station_status``) limits the sync to one feed. Returns
    ``(downloaded, total)``.
    """
    if client is None:
        import boto3

        client = boto3.client("s3")
    root = prefix.strip("/")
    scope = f"{root}/{feed}" if feed else root
    objects = list_remote(client, bucket, scope)
    downloaded = 0
    for o in objects:
        path = dest / o.key.removeprefix(f"{root}/")
        if path.exists() and path.stat().st_size == o.size:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        client.download_file(bucket, o.key, str(tmp))
        tmp.replace(path)
        downloaded += 1
    return downloaded, len(objects)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync own GBFS captures from S3")
    parser.add_argument("command", choices=["download"])
    parser.add_argument("--bucket", help=f"default: ${BUCKET_ENV} or .env")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--feed", help="only this feed, e.g. station_status")
    args = parser.parse_args(argv)
    new, total = download(args.bucket or bucket_from_env(), args.dir, feed=args.feed)
    print(f"{new} new of {total} objects in {args.dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
