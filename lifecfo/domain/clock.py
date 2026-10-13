"""Injectable clock so demos and tests can move time deterministically."""

from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    def now(self) -> datetime:
        """Current instant as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """A clock that only moves when told to."""

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        self._now = start.astimezone(UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, *, days: int = 0, hours: int = 0) -> None:
        self._now += timedelta(days=days, hours=hours)


def local_date(clock: Clock, timezone: str) -> date:
    """The user's calendar date, which is what streaks and due dates are measured in."""
    return clock.now().astimezone(ZoneInfo(timezone)).date()
