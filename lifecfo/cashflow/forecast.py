"""Daily cash flow forecast over the envelope ledger.

The forecast is a pure function of a FinancialState. It never taps the
emergency or goal envelopes on its own: a negative unallocated balance is
reported as a shortfall, and deciding how to fund it belongs to the planner.

Modelling assumptions (documented in docs/financial_model/FINANCIAL_MODEL.md):
- Balances in the state are opening balances for `as_of`.
- Within a day, income lands first, then essentials, debt minimums, flexible
  spending, savings transfers, and finally extra debt repayments.
- Debt payments follow lifecfo.debt.schedule_debts: interest is accrued where the
  rate is known, and a debt with an unknown rate keeps its minimum payment for the
  whole horizon (rules D5).
"""

from datetime import date, timedelta
from enum import StrEnum

from lifecfo.debt.schedule import schedule_debts
from lifecfo.domain.models import ExpenseCategory, FinancialState, Frozen


class EventKind(StrEnum):
    INCOME = "INCOME"
    ESSENTIAL_EXPENSE = "ESSENTIAL_EXPENSE"
    DEBT_MINIMUM = "DEBT_MINIMUM"
    FLEXIBLE_EXPENSE = "FLEXIBLE_EXPENSE"
    SAVINGS_TRANSFER = "SAVINGS_TRANSFER"
    EXTRA_DEBT_PAYMENT = "EXTRA_DEBT_PAYMENT"


_ORDER = {kind: index for index, kind in enumerate(EventKind)}


class CashEvent(Frozen):
    on: date
    kind: EventKind
    ref_id: str
    name: str
    amount: int  # positive magnitude in satang
    envelope_id: str | None = None  # destination, for SAVINGS_TRANSFER only

    @property
    def unallocated_delta(self) -> int:
        return self.amount if self.kind is EventKind.INCOME else -self.amount


class DayBalance(Frozen):
    """Closing balances for one day."""

    on: date
    unallocated: int  # may be negative: that is a shortfall
    envelopes: int  # emergency + goal envelopes
    events: tuple[CashEvent, ...] = ()

    @property
    def total_cash(self) -> int:
        return self.unallocated + self.envelopes


class Forecast(Frozen):
    start: date
    end: date
    opening_unallocated: int
    opening_envelopes: int
    days: tuple[DayBalance, ...]
    closing_envelopes: dict[str, int]

    @property
    def min_unallocated(self) -> int:
        return min(day.unallocated for day in self.days)

    @property
    def min_unallocated_on(self) -> date:
        return min(self.days, key=lambda day: (day.unallocated, day.on)).on

    @property
    def min_total_cash(self) -> int:
        return min(day.total_cash for day in self.days)

    @property
    def first_shortfall_on(self) -> date | None:
        return next((day.on for day in self.days if day.unallocated < 0), None)

    @property
    def max_shortfall(self) -> int:
        """Largest amount by which unallocated cash goes negative (0 if never)."""
        return max(0, -self.min_unallocated)


class MonthSummary(Frozen):
    month: str  # YYYY-MM
    income: int
    essential: int
    debt_minimum: int
    flexible: int
    transfers: int
    extra_debt: int = 0
    closing_unallocated: int
    closing_total_cash: int


def build_events(
    state: FinancialState,
    start: date,
    end: date,
    *,
    flexible_at_floor: bool = False,
    include_transfers: bool = True,
    exclude_flexible: bool = False,
) -> list[CashEvent]:
    """All scheduled cash events within [start, end], in processing order.

    `include_transfers` covers every allocation: savings transfers and extra debt
    repayments. `exclude_flexible` leaves out flexible spending entirely, which is
    the view used to test whether essentials and debt minimums alone can be paid.
    """
    events: list[CashEvent] = []

    for income in state.incomes:
        events += [
            CashEvent(on=d, kind=EventKind.INCOME, ref_id=income.id, name=income.name,
                      amount=income.amount)
            for d in income.occurrences(start, end)
        ]

    for expense in state.expenses:
        essential = expense.category is ExpenseCategory.ESSENTIAL
        amount = expense.floor if flexible_at_floor else expense.amount
        if amount == 0 or (exclude_flexible and not essential):
            continue
        kind = EventKind.ESSENTIAL_EXPENSE if essential else EventKind.FLEXIBLE_EXPENSE
        events += [
            CashEvent(on=d, kind=kind, ref_id=expense.id, name=expense.name, amount=amount)
            for d in expense.occurrences(start, end)
        ]

    for schedule in schedule_debts(state, start, end, include_extra=include_transfers).values():
        for period in schedule.periods:
            if period.minimum_paid:
                events.append(CashEvent(
                    on=period.on, kind=EventKind.DEBT_MINIMUM, ref_id=schedule.debt_id,
                    name=schedule.name, amount=period.minimum_paid))
            if period.extra_paid:
                events.append(CashEvent(
                    on=period.on, kind=EventKind.EXTRA_DEBT_PAYMENT, ref_id=schedule.debt_id,
                    name=f"Extra repayment: {schedule.name}",
                    amount=period.extra_paid + period.fee))

    if include_transfers:
        for transfer in state.transfers:
            events += [
                CashEvent(on=d, kind=EventKind.SAVINGS_TRANSFER, ref_id=transfer.id,
                          name=f"Transfer to {transfer.envelope_id}", amount=transfer.amount,
                          envelope_id=transfer.envelope_id)
                for d in transfer.occurrences(start, end)
            ]

    events.sort(key=lambda e: (e.on, _ORDER[e.kind], e.ref_id))
    return events


def forecast_cash_flow(
    state: FinancialState,
    horizon_days: int = 90,
    *,
    flexible_at_floor: bool = False,
    include_transfers: bool = True,
    exclude_flexible: bool = False,
) -> Forecast:
    """Simulate `horizon_days` days starting at `state.as_of` (inclusive).

    `flexible_at_floor` and `include_transfers=False` give the essentials-only
    view used to tell a fixable plan apart from a true essential shortfall.
    """
    if horizon_days < 1:
        raise ValueError("horizon_days must be at least 1")

    start = state.as_of
    end = start + timedelta(days=horizon_days - 1)
    by_day: dict[date, list[CashEvent]] = {}
    for event in build_events(
        state, start, end, flexible_at_floor=flexible_at_floor,
        include_transfers=include_transfers, exclude_flexible=exclude_flexible,
    ):
        by_day.setdefault(event.on, []).append(event)

    unallocated_id = state.unallocated.id
    unallocated = state.unallocated.balance
    envelopes = {e.id: e.balance for e in state.envelopes if e.id != unallocated_id}
    opening_envelopes = sum(envelopes.values())

    days: list[DayBalance] = []
    for offset in range(horizon_days):
        today = start + timedelta(days=offset)
        todays = by_day.get(today, [])
        for event in todays:
            unallocated += event.unallocated_delta
            if event.envelope_id is not None:
                envelopes[event.envelope_id] += event.amount
        days.append(
            DayBalance(on=today, unallocated=unallocated, envelopes=sum(envelopes.values()),
                       events=tuple(todays))
        )

    return Forecast(
        start=start,
        end=end,
        opening_unallocated=state.unallocated.balance,
        opening_envelopes=opening_envelopes,
        days=tuple(days),
        closing_envelopes=envelopes,
    )


def monthly_summary(forecast: Forecast) -> list[MonthSummary]:
    """Roll the daily forecast up by calendar month (partial months included)."""
    totals: dict[str, dict[EventKind, int]] = {}
    closing: dict[str, DayBalance] = {}
    for day in forecast.days:
        key = f"{day.on:%Y-%m}"
        bucket = totals.setdefault(key, dict.fromkeys(EventKind, 0))
        for event in day.events:
            bucket[event.kind] += event.amount
        closing[key] = day

    return [
        MonthSummary(
            month=key,
            income=bucket[EventKind.INCOME],
            essential=bucket[EventKind.ESSENTIAL_EXPENSE],
            debt_minimum=bucket[EventKind.DEBT_MINIMUM],
            flexible=bucket[EventKind.FLEXIBLE_EXPENSE],
            transfers=bucket[EventKind.SAVINGS_TRANSFER],
            extra_debt=bucket[EventKind.EXTRA_DEBT_PAYMENT],
            closing_unallocated=closing[key].unallocated,
            closing_total_cash=closing[key].total_cash,
        )
        for key, bucket in totals.items()
    ]
