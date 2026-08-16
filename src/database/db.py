"""
SQLite connection management.

Uses a plain stdlib `sqlite3` connection (no ORM) - the schema is small and
stable enough that raw SQL in `repository.py` stays readable, and it keeps
the dependency list short.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from config.settings import DB_PATH
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open a connection with sensible defaults for a small local app:
    - row_factory so query results behave like dicts
    - foreign_keys on (unused today, but safe default)
    - WAL journal mode so the Streamlit dashboard can read while a
      collection run is writing, without lock errors.

    `db_path` defaults to the module-level DB_PATH, looked up at call time
    (not baked in as a default argument) so tests can point this module at
    a temporary database via `monkeypatch.setattr(db, "DB_PATH", tmp_path)`.
    """
    resolved_path = Path(db_path) if db_path is not None else DB_PATH
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(resolved_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialize_database(db_path: Optional[Path] = None) -> None:
    """Create tables/indexes if they don't already exist. Safe to call on
    every startup.
    """
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
        logger.info("Database ready at %s", db_path or DB_PATH)
    finally:
        conn.close()


@contextmanager
def db_transaction(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    """Context manager that commits on success and rolls back on any
    exception, so a failure partway through a batch write can't leave the
    database in a half-updated state.
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Transaction rolled back due to an error")
        raise
    finally:
        conn.close()
