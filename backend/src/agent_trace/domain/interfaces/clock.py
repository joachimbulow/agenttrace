from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta


class IClock(ABC):
    """Abstract clock for time operations (testability)."""

    @abstractmethod
    def utcnow(self) -> datetime:
        """Get current UTC time.

        Returns:
            Current datetime in UTC.
        """
        ...

    @abstractmethod
    def now(self) -> datetime:
        """Get current local time.

        Returns:
            Current datetime in local timezone.
        """
        ...


class SystemClock(IClock):
    """Production implementation using system clock."""

    def utcnow(self) -> datetime:
        """Get current UTC time from system."""
        return datetime.utcnow()

    def now(self) -> datetime:
        """Get current local time from system."""
        return datetime.now()


class MockClock(IClock):
    """Test implementation with fixed time."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        """Initialize with a fixed time.

        Args:
            fixed_time: The fixed time to return. Defaults to current time.
        """
        self._fixed_time = fixed_time or datetime.utcnow()

    def utcnow(self) -> datetime:
        """Return the fixed time."""
        return self._fixed_time

    def now(self) -> datetime:
        """Return the fixed time."""
        return self._fixed_time

    def advance(self, seconds: float) -> None:
        """Advance the fixed time.

        Args:
            seconds: Number of seconds to advance.
        """
        self._fixed_time += timedelta(seconds=seconds)
