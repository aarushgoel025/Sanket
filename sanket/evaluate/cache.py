"""SQLite response cache for model evaluations.

Caches raw model responses keyed by (model_id, task_id, mode, prompt_version)
to ensure idempotency, resumability, and cost efficiency.
"""

import json
import sqlite3
import time
from pathlib import Path

from sanket.schema import RawResponse

DEFAULT_CACHE_PATH = Path("data/cache/eval_cache.sqlite")


class ResponseCache:
    """Persistent SQLite cache for model outputs."""

    def __init__(self, db_path: Path | str = DEFAULT_CACHE_PATH) -> None:
        """Initialize SQLite response cache.

        Args:
            db_path: Path to the SQLite cache database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with timeout."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        """Create responses table and index if not already present."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS responses (
                    model_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    latency_s REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    meta_json TEXT,
                    PRIMARY KEY (model_id, task_id, mode, prompt_version)
                )
                """
            )
            conn.commit()

    def get(
        self, model_id: str, task_id: str, mode: str, prompt_version: str
    ) -> RawResponse | None:
        """Retrieve cached model response if present.

        Args:
            model_id: Identifier of the evaluated model.
            task_id: Unique task identifier.
            mode: Evaluation mode ('image' or 'text').
            prompt_version: Prompt template version.

        Returns:
            RawResponse if found in cache, else None.
        """
        query = """
            SELECT raw_text, latency_s, meta_json
            FROM responses
            WHERE model_id = ? AND task_id = ? AND mode = ? AND prompt_version = ?
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (model_id, task_id, mode, prompt_version))
            row = cursor.fetchone()
            if row is None:
                return None

            raw_text, latency_s, meta_json = row
            meta = json.loads(meta_json) if meta_json else {}
            return RawResponse(text=raw_text, latency_s=latency_s, meta=meta)

    def set(
        self,
        model_id: str,
        task_id: str,
        mode: str,
        prompt_version: str,
        response: RawResponse,
        timestamp: float | None = None,
    ) -> None:
        """Store a model response in the cache.

        Args:
            model_id: Identifier of the evaluated model.
            task_id: Unique task identifier.
            mode: Evaluation mode ('image' or 'text').
            prompt_version: Prompt template version.
            response: RawResponse model payload.
            timestamp: Epoch timestamp (defaults to current time).
        """
        ts = timestamp if timestamp is not None else time.time()
        meta_json = json.dumps(response.meta) if response.meta else "{}"
        query = """
            INSERT OR REPLACE INTO responses
            (model_id, task_id, mode, prompt_version, raw_text, latency_s, timestamp, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            conn.execute(
                query,
                (
                    model_id,
                    task_id,
                    mode,
                    prompt_version,
                    response.text,
                    response.latency_s,
                    ts,
                    meta_json,
                ),
            )
            conn.commit()

    def has(self, model_id: str, task_id: str, mode: str, prompt_version: str) -> bool:
        """Check if an entry exists in the cache.

        Args:
            model_id: Model identifier.
            task_id: Task identifier.
            mode: Mode string.
            prompt_version: Prompt template version.

        Returns:
            True if cached entry exists, False otherwise.
        """
        query = """
            SELECT 1 FROM responses
            WHERE model_id = ? AND task_id = ? AND mode = ? AND prompt_version = ?
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (model_id, task_id, mode, prompt_version))
            return cursor.fetchone() is not None

    def size(self) -> int:
        """Return total number of cached entries."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM responses")
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def clear(self) -> None:
        """Clear all entries from the cache table."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM responses")
            conn.commit()


_default_cache: ResponseCache | None = None


def get_cache(db_path: Path | str = DEFAULT_CACHE_PATH) -> ResponseCache:
    """Get or create singleton response cache instance.

    Args:
        db_path: Path to SQLite cache database.

    Returns:
        ResponseCache instance.
    """
    global _default_cache
    if _default_cache is None or _default_cache.db_path != Path(db_path):
        _default_cache = ResponseCache(db_path)
    return _default_cache


__all__ = ["DEFAULT_CACHE_PATH", "ResponseCache", "get_cache"]
