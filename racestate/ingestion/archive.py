"""Explicit side-path draining; ingestion never waits for AWS."""
import os
from pathlib import Path
import tempfile


class LocalArchive:
    def __init__(self, root):
        self.root = Path(root)

    def put(self, key, body):
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replacement avoids a half-written archive after interruption.
        name = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
                name = output.name
                output.write(body)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, target)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)


class S3Archive:
    def __init__(self, bucket, client=None):
        if client is None:
            import boto3  # Optional; local ingestion needs only the standard library.
            from botocore.config import Config
            client = boto3.client("s3", config=Config(
                connect_timeout=5, read_timeout=20,
                retries={"mode": "standard", "total_max_attempts": 3},
            ))
        self.bucket = bucket
        self.client = client

    def put(self, key, body):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body,
                               ContentType="application/json")


def drain_archives(log, archive, limit=100):
    uploaded = 0
    for key, body in log.pending_archives(limit):
        # Mark only AFTER upload. A crash here repeats the same deterministic key.
        archive.put(key, body)
        log.mark_archived(key)
        uploaded += 1
    return uploaded
