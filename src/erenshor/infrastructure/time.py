"""Time abstraction for testable time-dependent code.

This module provides a Clock protocol that can be mocked in tests to simulate
time passing instantly without actual delays.
"""

import asyncio
import time
from typing import Protocol


class Clock(Protocol):
    """Protocol for time operations that can be mocked in tests."""

    def sleep(self, seconds: float) -> None:
        """Sleep for the specified number of seconds.

        Args:
            seconds: Number of seconds to sleep
        """
        ...

    async def async_sleep(self, seconds: float) -> None:
        """Async sleep for the specified number of seconds.

        Args:
            seconds: Number of seconds to sleep
        """
        ...

    def time(self) -> float:
        """Get current time in seconds since epoch.

        Returns:
            Current time as float
        """
        ...


class RealClock:
    """Production clock implementation using actual time operations."""

    def sleep(self, seconds: float) -> None:
        """Sleep for the specified number of seconds."""
        time.sleep(seconds)

    async def async_sleep(self, seconds: float) -> None:
        """Async sleep for the specified number of seconds."""
        await asyncio.sleep(seconds)

    def time(self) -> float:
        """Get current time in seconds since epoch."""
        return time.time()


class MockClock:
    """Mock clock for testing that simulates time instantly.

    Example:
        >>> clock = MockClock()
        >>> start = clock.time()
        >>> clock.sleep(30)  # Returns instantly
        >>> elapsed = clock.time() - start
        >>> assert elapsed >= 30  # Mock clock advanced by 30 seconds
    """

    def __init__(self) -> None:
        """Initialize mock clock with current time."""
        self._current_time = time.time()

    def sleep(self, seconds: float) -> None:
        """Simulate sleep by advancing internal clock."""
        self._current_time += seconds

    async def async_sleep(self, seconds: float) -> None:
        """Simulate async sleep by advancing internal clock."""
        self._current_time += seconds

    def time(self) -> float:
        """Get simulated current time."""
        return self._current_time

    def advance(self, seconds: float) -> None:
        """Manually advance the clock by specified seconds.

        Args:
            seconds: Number of seconds to advance
        """
        self._current_time += seconds
