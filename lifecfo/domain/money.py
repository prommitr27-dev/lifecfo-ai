"""Money is stored as integer satang (1 THB = 100 satang) to avoid float drift."""

from decimal import ROUND_HALF_UP, Decimal

SATANG_PER_THB = 100


def thb(amount: int | float | str | Decimal) -> int:
    """Convert a baht amount to integer satang, rounding half up."""
    satang = (Decimal(str(amount)) * SATANG_PER_THB).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(satang)


def format_thb(satang: int) -> str:
    """Render satang as a baht string, e.g. -1,234.50 THB."""
    sign = "-" if satang < 0 else ""
    whole, frac = divmod(abs(satang), SATANG_PER_THB)
    return f"{sign}{whole:,}.{frac:02d} THB"
