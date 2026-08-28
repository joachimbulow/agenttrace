"""Tests for SQLite database path handling."""
from pathlib import Path

from agent_trace.infrastructure.database.connection import (
    Database,
    _ensure_sqlite_parent_dir,
)


def test_ensure_sqlite_parent_dir_creates_missing_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "dir" / "agent_trace.db"
    assert not db_path.parent.exists()

    _ensure_sqlite_parent_dir(f"sqlite+aiosqlite:///{db_path}")

    assert db_path.parent.is_dir()
    assert not db_path.exists()


def test_ensure_sqlite_parent_dir_skips_memory() -> None:
    _ensure_sqlite_parent_dir("sqlite+aiosqlite:///:memory:")


def test_database_init_creates_parent_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "agent_trace.db"

    Database(f"sqlite+aiosqlite:///{db_path}")

    assert db_path.parent.is_dir()
