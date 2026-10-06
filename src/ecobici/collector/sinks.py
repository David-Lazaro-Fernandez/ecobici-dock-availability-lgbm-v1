"""Where raw captures are written: a local directory or an S3 prefix."""

from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse


class Sink(Protocol):
    def put(self, key: str, body: bytes) -> str:
        """Store ``body`` under ``key`` and return its full location."""


class LocalSink:
    def __init__(self, root: Path):
        self.root = root

    def put(self, key: str, body: bytes) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(body)
        tmp.replace(path)
        return str(path)


class S3Sink:
    def __init__(self, bucket: str, prefix: str, client=None):
        if client is None:
            import boto3

            client = boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = client

    def put(self, key: str, body: bytes) -> str:
        full_key = f"{self.prefix}/{key}" if self.prefix else key
        self.client.put_object(
            Bucket=self.bucket,
            Key=full_key,
            Body=body,
            ContentType="application/json",
            ContentEncoding="gzip",
        )
        return f"s3://{self.bucket}/{full_key}"


def sink_from_uri(uri: str) -> Sink:
    """``s3://bucket/prefix`` or a local path (``file://`` optional)."""
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        return S3Sink(parsed.netloc, parsed.path)
    if parsed.scheme in ("", "file"):
        return LocalSink(Path(parsed.path if parsed.scheme else uri))
    raise ValueError(f"Unsupported sink: {uri}")
