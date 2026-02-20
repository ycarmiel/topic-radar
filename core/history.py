"""
SQLite-backed search history for Topic Radar.

Schema
──────
table: searches
  id         INTEGER PRIMARY KEY AUTOINCREMENT
  topic      TEXT NOT NULL
  created_at TEXT NOT NULL  (ISO-8601 UTC)
  summary    TEXT NOT NULL  (TopicSummary serialised as JSON)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from core.models import HistoryEntry, TopicSummary

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "history.db"


def _db_path() -> Path:
    """Return the database file path, honouring a DB_PATH env var if set."""
    env = os.getenv("DB_PATH")
    return Path(env) if env else DEFAULT_DB_PATH


@contextmanager
def _connect():
    """Yield a connected sqlite3.Connection, creating the file/dir if needed."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create the searches table if it doesn't exist yet."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS searches (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                topic      TEXT NOT NULL,
                created_at TEXT NOT NULL,
                summary    TEXT NOT NULL
            )
            """
        )
    logger.info("History DB initialised at %s", _db_path())


def save(topic: str, summary: TopicSummary) -> int:
    """Persist a research result and return its new row ID.

    Args:
        topic: The search topic string.
        summary: The structured TopicSummary to store.

    Returns:
        The integer primary key of the inserted row.
    """
    now = datetime.now(timezone.utc).isoformat()
    summary_json = summary.model_dump_json()

    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO searches (topic, created_at, summary) VALUES (?, ?, ?)",
            (topic, now, summary_json),
        )
        row_id = cursor.lastrowid

    logger.info("Saved history entry id=%d for topic=%r", row_id, topic)
    return row_id


def get_all(limit: int = 50) -> list[HistoryEntry]:
    """Return the most recent *limit* history entries (newest first).

    Args:
        limit: Maximum number of entries to return.

    Returns:
        A list of HistoryEntry objects.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, topic, created_at, summary FROM searches "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    entries: list[HistoryEntry] = []
    for row in rows:
        try:
            summary = TopicSummary.model_validate_json(row["summary"])
            entries.append(
                HistoryEntry(
                    id=row["id"],
                    topic=row["topic"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    summary=summary,
                )
            )
        except Exception as exc:
            logger.warning("Skipping corrupt history entry id=%d: %s", row["id"], exc)

    return entries


def get_by_id(entry_id: int) -> HistoryEntry | None:
    """Fetch a single history entry by its primary key.

    Args:
        entry_id: The row ID to look up.

    Returns:
        A HistoryEntry, or None if not found.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, topic, created_at, summary FROM searches WHERE id = ?",
            (entry_id,),
        ).fetchone()

    if row is None:
        return None

    summary = TopicSummary.model_validate_json(row["summary"])
    return HistoryEntry(
        id=row["id"],
        topic=row["topic"],
        created_at=datetime.fromisoformat(row["created_at"]),
        summary=summary,
    )


def delete(entry_id: int) -> bool:
    """Delete a history entry by ID.

    Args:
        entry_id: The row ID to delete.

    Returns:
        True if a row was deleted, False if not found.
    """
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM searches WHERE id = ?", (entry_id,)
        )
    deleted = cursor.rowcount > 0
    if deleted:
        logger.info("Deleted history entry id=%d", entry_id)
    return deleted
