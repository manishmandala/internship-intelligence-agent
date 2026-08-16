"""
Shared pytest fixtures.

`temp_db` points the database layer at a fresh temporary SQLite file for
the duration of one test, so tests never touch the real
`data/internships.db` the collector writes to.
"""
from __future__ import annotations

import pytest

from src.database import db as db_module


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_internships.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.initialize_database()
    return db_path
