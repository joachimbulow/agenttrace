"""Shared test fixtures for Agent Trace backend tests."""
import asyncio

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_trace.main import app
from agent_trace.infrastructure.database import Base, get_session
from agent_trace.infrastructure.database.repositories import (
    RunRepository,
    SpanEventRepository,
    TraceNodeRepository,
)
from agent_trace.domain.interfaces.clock import MockClock
from agent_trace.application.services import RunService, IngestService
from agent_trace.presentation.dependencies import get_db_session


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """Create a fresh database session for each test."""
    # Create in-memory database
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Yield session
    session = async_session_factory()
    yield session

    # Cleanup
    await session.close()
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncClient:
    """Create test HTTP client with database session override."""

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_db_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_clock() -> MockClock:
    """Create mock clock for testing."""
    return MockClock()


@pytest_asyncio.fixture
async def run_service(db_session: AsyncSession) -> RunService:
    """Create RunService with test repositories."""
    return RunService(
        run_repo=RunRepository(db_session),
        node_repo=TraceNodeRepository(db_session),
        event_repo=SpanEventRepository(db_session),
    )


@pytest_asyncio.fixture
async def ingest_service(
    db_session: AsyncSession, mock_clock: MockClock
) -> IngestService:
    """Create IngestService with test repositories."""
    return IngestService(
        run_repo=RunRepository(db_session),
        node_repo=TraceNodeRepository(db_session),
        event_repo=SpanEventRepository(db_session),
        clock=mock_clock,
    )