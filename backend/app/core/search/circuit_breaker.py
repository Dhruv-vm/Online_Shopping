from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    """3-State Circuit Breaker state model."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is attempted while the circuit is OPEN."""

    pass


class SearchCircuitBreaker:
    """
    Resilient 3-state Circuit Breaker protecting OpenSearch and ensuring fast-fail
    to PostgreSQL SQL fallback.

    Parameters:
        failure_threshold: Consecutive failures required to trip the circuit to OPEN (default 5).
        recovery_seconds: Seconds to remain OPEN before allowing a HALF_OPEN probe (default 30.0s).
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_seconds: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._state: CircuitState = CircuitState.CLOSED
        self._consecutive_failures: int = 0
        self._last_state_change: float = time.monotonic()
        self._lock = asyncio.Lock()
        self._half_open_in_flight: bool = False

    @property
    def state(self) -> CircuitState:
        """Current circuit state, taking recovery window into account."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_state_change
            if elapsed >= self.recovery_seconds:
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    async def allow_request(self) -> bool:
        """Check whether a request is allowed through without executing it."""
        async with self._lock:
            current = self.state
            if current == CircuitState.CLOSED:
                return True
            if current == CircuitState.HALF_OPEN:
                if not self._half_open_in_flight:
                    self._half_open_in_flight = True
                    self._state = CircuitState.HALF_OPEN
                    return True
                return False
            return False

    async def record_success(self) -> None:
        """Record a successful execution."""
        async with self._lock:
            prev = self._state
            self._consecutive_failures = 0
            self._state = CircuitState.CLOSED
            self._half_open_in_flight = False
            self._last_state_change = time.monotonic()
            if prev != CircuitState.CLOSED:
                logger.info(
                    "SearchCircuitBreaker recovered from %s to CLOSED",
                    prev.value,
                )

    async def record_failure(self, exc: Exception | None = None) -> None:
        """Record an execution failure."""
        async with self._lock:
            self._consecutive_failures += 1
            prev = self._state
            self._half_open_in_flight = False
            self._last_state_change = time.monotonic()

            if prev == CircuitState.HALF_OPEN:
                # Probe failed, return immediately to OPEN
                self._state = CircuitState.OPEN
                logger.warning(
                    "SearchCircuitBreaker probe failed in HALF_OPEN: %s. Tripping back to OPEN for %.1fs",
                    exc or "Unknown error",
                    self.recovery_seconds,
                )
            elif self._consecutive_failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.error(
                    "SearchCircuitBreaker tripped to OPEN after %d consecutive failures. Last error: %s. Fallback active for %.1fs",
                    self._consecutive_failures,
                    exc or "Threshold reached",
                    self.recovery_seconds,
                )
            else:
                logger.debug(
                    "Search failure recorded (%d/%d): %s",
                    self._consecutive_failures,
                    self.failure_threshold,
                    exc,
                )

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute an async callable guarded by the circuit breaker.
        Raises CircuitBreakerOpenError if circuit is OPEN.
        """
        allowed = await self.allow_request()
        if not allowed:
            raise CircuitBreakerOpenError(
                f"Search circuit breaker is {self.state.value}; fast-failing to fallback"
            )

        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as exc:
            await self.record_failure(exc)
            raise

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_in_flight = False
        self._last_state_change = time.monotonic()
