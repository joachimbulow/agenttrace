from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from .models import Base


class Database:
    """Database connection manager."""

    def __init__(self, database_url: str) -> None:
        """Initialize database connection.

        Args:
            database_url: SQLAlchemy async database URL.
        """
        # For SQLite, we need StaticPool for same-thread usage
        if "sqlite" in database_url:
            self.engine = create_async_engine(
                database_url,
                echo=False,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
        else:
            self.engine = create_async_engine(database_url, echo=False)

        self.async_session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_tables(self) -> None:
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """Drop all tables (for testing)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session.

        Usage:
            async with db.session() as session:
                # Use session here

        Yields:
            AsyncSession instance.
        """
        session = self.async_session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Global database instance (initialized in main.py)
_db: Database | None = None


async def init_db(database_url: str) -> None:
    """Initialize database connection.

    Args:
        database_url: SQLAlchemy async database URL.
    """
    global _db
    _db = Database(database_url)
    await _db.create_tables()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session.

    Yields:
        AsyncSession instance.
    """
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _db.session() as session:
        yield session


def get_db() -> Database:
    """Get the global database instance.

    Returns:
        Database instance.

    Raises:
        RuntimeError: If database not initialized.
    """
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db