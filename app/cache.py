import json
import os
import sqlite3
import time
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(settings.cache_dir, "cache.db")


def _ensure_dir() -> None:
    os.makedirs(settings.cache_dir, exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    _ensure_dir()
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache "
        "(key TEXT PRIMARY KEY, value TEXT, expires_at REAL)"
    )
    return conn


def get(key: str) -> Any | None:
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        conn.close()
        if row is None:
            return None
        value, expires_at = row
        if time.time() > expires_at:
            delete(key)
            return None
        return json.loads(value)
    except Exception:
        logger.exception("Cache get error for key=%s", key)
        return None


def set(key: str, value: Any, ttl: int | None = None) -> None:
    if ttl is None:
        ttl = settings.cache_ttl
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(value, ensure_ascii=False), time.time() + ttl),
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Cache set error for key=%s", key)


def delete(key: str) -> None:
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Cache delete error for key=%s", key)


def clear() -> None:
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM cache")
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Cache clear error")


def cleanup() -> None:
    """Remove expired entries."""
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM cache WHERE expires_at < ?", (time.time(),))
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Cache cleanup error")
