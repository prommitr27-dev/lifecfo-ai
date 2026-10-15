"""Streak state machine (pure functions, no storage).

A streak counts consecutive periods (days or ISO weeks) in which the user did
something meaningful: a review, an approved plan, a completed mission. Opening
the app does not count.

A missed period does not break the streak when it is covered by:
- protection after a confirmed financial shock (rules: adaptive protection),
- a grace day (daily streaks only, limited per ISO week), or
- a pause the user started.

Covered periods freeze the count: they neither add to it nor reset it. Only an
earned period adds one. A broken streak simply starts again at 1, without any
penalty or shaming message.
"""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from enum import StrEnum


class StreakKind(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class StreakStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    ACTIVE = "ACTIVE"
    PROTECTED = "PROTECTED"
    PAUSED = "PAUSED"
    BROKEN = "BROKEN"


@dataclass(frozen=True)
class Streak:
    kind: StreakKind
    count: int = 0
    best: int = 0
    last_earned: date | None = None  # for WEEKLY, the Monday of the week
    protected_from: date | None = None
    protected_until: date | None = None
    # Pauses the user started: (first day, last day or None while still paused).
    pauses: tuple[tuple[date, date | None], ...] = ()
    grace_used: tuple[date, ...] = ()  # missed days covered by grace


def period_start(kind: StreakKind, day: date) -> date:
    return day - timedelta(days=day.weekday()) if kind is StreakKind.WEEKLY else day


def _step(kind: StreakKind) -> timedelta:
    return timedelta(days=7 if kind is StreakKind.WEEKLY else 1)


def _protected(streak: Streak, period: date) -> bool:
    if streak.protected_from is None or streak.protected_until is None:
        return False
    end = period + _step(streak.kind) - timedelta(days=1)
    return period <= streak.protected_until and end >= streak.protected_from


def _paused(streak: Streak, period: date) -> bool:
    end = period + _step(streak.kind) - timedelta(days=1)
    return any(start <= end and (stop is None or stop >= period) for start, stop in streak.pauses)


def is_paused(streak: Streak) -> bool:
    return bool(streak.pauses) and streak.pauses[-1][1] is None


def _missed(streak: Streak, today: date) -> list[date]:
    """Periods between the last earned one and `today` (exclusive) with no activity."""
    if streak.last_earned is None:
        return []
    step, current, out = _step(streak.kind), streak.last_earned + _step(streak.kind), []
    while current < period_start(streak.kind, today):
        out.append(current)
        current += step
    return out


def _cover(streak: Streak, missed: list[date], grace_per_week: int) -> tuple[bool, Streak]:
    """Whether every missed period is covered, and the streak with any grace spent."""
    grace = list(streak.grace_used)
    for period in missed:
        if _protected(streak, period) or _paused(streak, period):
            continue
        week = period_start(StreakKind.WEEKLY, period)
        used = sum(1 for g in grace if period_start(StreakKind.WEEKLY, g) == week)
        if streak.kind is StreakKind.DAILY and used < grace_per_week:
            grace.append(period)
            continue
        return False, streak
    return True, replace(streak, grace_used=tuple(grace))


def record_activity(streak: Streak, day: date, grace_per_week: int) -> tuple[Streak, bool]:
    """Apply a meaningful action on `day`. Returns the new streak and whether it grew."""
    period = period_start(streak.kind, day)
    if streak.last_earned is not None and period <= streak.last_earned:
        return streak, False  # already earned this period
    covered, updated = _cover(streak, _missed(streak, day), grace_per_week)
    count = (streak.count + 1) if (streak.last_earned is not None and covered) else 1
    base = updated if covered else replace(streak, grace_used=())
    # Doing something meaningful ends a pause.
    updated = resume(replace(base, count=count, best=max(streak.best, count),
                             last_earned=period), day - timedelta(days=1))
    return updated, True


def status(streak: Streak, today: date, grace_per_week: int) -> StreakStatus:
    """How the streak stands on `today`, without changing it."""
    if streak.last_earned is None:
        return StreakStatus.NOT_STARTED
    if is_paused(streak):
        return StreakStatus.PAUSED
    covered, _ = _cover(streak, _missed(streak, today), grace_per_week)
    if not covered:
        return StreakStatus.BROKEN
    if (streak.protected_from is not None and streak.protected_until is not None
            and streak.protected_from <= today <= streak.protected_until):
        return StreakStatus.PROTECTED
    return StreakStatus.ACTIVE


def protect(streak: Streak, start: date, max_days: int) -> Streak:
    return replace(streak, protected_from=start,
                   protected_until=start + timedelta(days=max_days - 1))


def end_protection(streak: Streak, day: date) -> Streak:
    """Stop protecting from `day` on; days before it stay covered."""
    if streak.protected_until is None or streak.protected_until < day:
        return streak
    return replace(streak, protected_until=day - timedelta(days=1))


def pause(streak: Streak, day: date) -> Streak:
    if is_paused(streak):
        return streak
    return replace(streak, pauses=(*streak.pauses, (day, None)))


def resume(streak: Streak, last_paused_day: date) -> Streak:
    if not is_paused(streak):
        return streak
    start, _ = streak.pauses[-1]
    return replace(streak, pauses=(*streak.pauses[:-1], (start, max(start, last_paused_day))))
