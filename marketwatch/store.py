"""SQLite store of listings we've already seen, so we alert only once."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from .models import Listing


class SeenStore:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen (
                key         TEXT PRIMARY KEY,
                source      TEXT NOT NULL,
                listing_id  TEXT NOT NULL,
                title       TEXT,
                price       REAL,
                url         TEXT,
                first_seen  REAL NOT NULL,
                last_seen   REAL NOT NULL,
                notified    INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.conn.commit()

    def get(self, listing: Listing) -> tuple[bool, Optional[float], bool]:
        """Return (seen_before, last_known_price, already_notified)."""
        row = self.conn.execute(
            "SELECT price, notified FROM seen WHERE key = ?", (listing.key,)
        ).fetchone()
        if row is None:
            return False, None, False
        return True, row[0], bool(row[1])

    def upsert(self, listing: Listing, notified: bool) -> None:
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO seen (key, source, listing_id, title, price, url, first_seen, last_seen, notified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                title = excluded.title,
                price = excluded.price,
                url = excluded.url,
                last_seen = excluded.last_seen,
                notified = MAX(seen.notified, excluded.notified)
            """,
            (
                listing.key,
                listing.source,
                listing.listing_id,
                listing.title,
                listing.price,
                listing.url,
                now,
                now,
                1 if notified else 0,
            ),
        )
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
