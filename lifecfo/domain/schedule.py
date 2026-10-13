"""Calendar helpers for recurring items."""

import calendar
from datetime import date


def clamp_day(year: int, month: int, day: int) -> date:
    """Day `day` of the month, or the last day when the month is shorter."""
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def monthly_occurrences(
    day_of_month: int,
    start: date,
    end: date,
    active_from: date | None = None,
    active_to: date | None = None,
) -> list[date]:
    """Monthly dates within [start, end] and the optional active window, all inclusive."""
    lo = max(start, active_from) if active_from else start
    hi = min(end, active_to) if active_to else end
    out: list[date] = []
    year, month = lo.year, lo.month
    while (year, month) <= (hi.year, hi.month):
        occurrence = clamp_day(year, month, day_of_month)
        if lo <= occurrence <= hi:
            out.append(occurrence)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out
