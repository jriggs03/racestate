"""SQLite is an embedded durable log, not the future analytics database."""
from dataclasses import dataclass
from pathlib import Path
import json
import sqlite3
from typing import Iterable, List, Protocol

from .models import SourceEvent, canonical_json


@dataclass(frozen=True)
class LogEntry:
    offset: int
    event: dict


class EventLog(Protocol):
    def append_batch(self, events: Iterable[SourceEvent], raw_body: bytes, archive_key: str) -> int: ...
    def read_after(self, offset: int, limit: int = 100) -> List[LogEntry]: ...


class SQLiteEventLog:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                offset INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                body TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS archive_outbox (
                object_key TEXT PRIMARY KEY,
                raw_body BLOB NOT NULL,
                uploaded INTEGER NOT NULL DEFAULT 0
            );
        """)

    def append_batch(self, events: Iterable[SourceEvent], raw_body: bytes, archive_key: str) -> int:
        inserted = 0
        # Both writes commit together. A failure leaves neither partially saved.
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO archive_outbox(object_key, raw_body) VALUES (?, ?)",
                (archive_key, raw_body),
            )
            for event in events:
                cursor = self.connection.execute(
                    "INSERT OR IGNORE INTO events(event_id, body) VALUES (?, ?)",
                    (event.event_id, canonical_json(event.to_dict())),
                )
                inserted += cursor.rowcount
        return inserted

    def read_after(self, offset: int, limit: int = 100) -> List[LogEntry]:
        if type(offset) is not int or offset < 0 or not 1 <= limit <= 1000:
            raise ValueError("offset >= 0 and limit between 1 and 1000 required")
        rows = self.connection.execute(
            "SELECT offset, body FROM events WHERE offset > ? ORDER BY offset LIMIT ?",
            (offset, limit),
        )
        return [LogEntry(offset, json.loads(body)) for offset, body in rows]

    def pending_archives(self, limit=100):
        return self.connection.execute(
            "SELECT object_key, raw_body FROM archive_outbox WHERE uploaded=0 ORDER BY rowid LIMIT ?",
            (limit,),
        ).fetchall()

    def mark_archived(self, key):
        with self.connection:
            self.connection.execute(
                "UPDATE archive_outbox SET uploaded=1 WHERE object_key=?", (key,)
            )

    def close(self):
        self.connection.close()
