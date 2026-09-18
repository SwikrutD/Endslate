"""A tiny SQLite key-value cache so a rescan costs no network calls."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    fetched_at INTEGER NOT NULL
);
"""


class Cache:
    def __init__(self, path: Path, ttl_days: int = 180):
        self.path = Path(path)
        self.ttl = ttl_days * 86400
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.execute(SCHEMA)
        self._conn.commit()

    def get(self, key: str) -> Optional[Any]:
        row = self._conn.execute(
            "SELECT value, fetched_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, fetched_at = row
        if self.ttl and time.time() - fetched_at > self.ttl:
            return None
        try:
            return json.loads(value)
        except ValueError:
            return None

    def put(self, key: str, value: Any) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), int(time.time())),
        )
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM cache")
        self._conn.commit()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
