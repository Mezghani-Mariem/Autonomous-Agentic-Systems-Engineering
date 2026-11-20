import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .models import ReviewRun, now


class StaleRunError(RuntimeError):
    """Another session saved this review first."""


def digest(value):
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class DiskStore:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "slr.sqlite3"
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, payload TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, version INTEGER, updated TEXT, payload TEXT
                );
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def cache_get(self, key):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM cache WHERE key = ? AND expires > ?",
                             (key, time.time())).fetchone()
        return json.loads(row[0]) if row else None

    def cache_put(self, key, value, ttl):
        if ttl <= 0:
            return
        with self.connection() as db:
            db.execute("DELETE FROM cache WHERE expires <= ?", (time.time(),))
            db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
                       (key, json.dumps(value, ensure_ascii=False), time.time() + ttl))

    def save(self, run: ReviewRun):
        updated = run.model_copy(update={"version": run.version + 1, "updated": now()})
        payload = updated.model_dump_json()
        with self.connection() as db:
            if run.version == 0:
                cursor = db.execute("INSERT OR IGNORE INTO runs VALUES (?, ?, ?, ?)",
                                    (run.id, updated.version, updated.updated, payload))
            else:
                cursor = db.execute("UPDATE runs SET version=?, updated=?, payload=? WHERE id=? AND version=?",
                                    (updated.version, updated.updated, payload, run.id, run.version))
            if not cursor.rowcount:
                raise StaleRunError("This review was updated in another session. Reload it to continue.")
        run.version = updated.version
        run.updated = updated.updated

    def load(self, run_id):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
        return ReviewRun.model_validate_json(row[0]) if row else None

    def recent(self, limit=25):
        with self.connection() as db:
            rows = db.execute("SELECT payload FROM runs ORDER BY updated DESC LIMIT ?", (limit,)).fetchall()
        return [ReviewRun.model_validate_json(payload) for (payload,) in rows]
