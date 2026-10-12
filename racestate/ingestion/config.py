"""Exported environment variables; .env files are not loaded implicitly."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    log_path: str
    archive_dir: str
    s3_bucket: str
    openf1_token: str

    @classmethod
    def from_environment(cls):
        return cls(
            log_path=os.environ.get("RACESTATE_LOG_PATH", "data/events.sqlite3"),
            archive_dir=os.environ.get("RACESTATE_ARCHIVE_DIR", "data/raw"),
            s3_bucket=os.environ.get("RACESTATE_S3_BUCKET", ""),
            openf1_token=os.environ.get("OPENF1_TOKEN", ""),
        )
