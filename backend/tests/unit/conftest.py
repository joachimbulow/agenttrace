"""Shared fixtures for unit tests."""
import pytest

from agent_trace.domain.interfaces.clock import MockClock


@pytest.fixture
def mock_clock() -> MockClock:
    """Create mock clock for unit tests."""
    return MockClock()