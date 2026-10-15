"""Debt schedules with interest, minimum payments, and extra repayments.

Rules D5 decide how interest may be stated:

- CONTRACT_BASED: the rate and the contract's method are known, so the
  engine reproduces that method.
- ESTIMATED: the rate is known but the method is not. Interest is estimated
  as balance x rate x days / 365 on the balance between payments. The
  365-day basis and the constant balance between payments are disclosed.
- UNAVAILABLE: the rate is unknown. No interest figure and no payoff date
  are produced. For cash planning the minimum payment is assumed to continue
  for the whole horizon, which can only overstate outflows.

Within a payment date, accrued interest is added first, then the minimum
payment, then any extra repayment. A prepayment fee, when known, is charged
on top of the extra amount.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from lifecfo.domain.models import Debt, DebtStrategy, FinancialState, InterestMethod
from lifecfo.domain.schedule import monthly_occurrences


class InterestBasis(StrEnum):
    CONTRACT_BASED = "CONTRACT_BASED"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


ESTIMATE_ASSUMPTIONS = (
    "Interest is estimated as balance x annual rate x days / 365 (simple interest, "
    "365-day year), with the balance held constant between payments.",
    "The lender's actual interest can differ because of compounding, payment timing, "
    "day-count conventions, fees, or other contract terms.",
)


def interest_basis(debt: Debt) -> tuple[InterestBasis, tuple[str, ...]]:
    """How interest on `debt` can be stated, and the assumptions or gaps behind it."""
    if debt.apr is None:
        return InterestBasis.UNAVAILABLE, (
            "The interest rate is unknown. No interest or payoff date is shown; provide "
            "the rate or an estimate to get one. It is not assumed to be 0%.",
        )
    if debt.interest_method is None:
        return InterestBasis.ESTIMATED, ESTIMATE_ASSUMPTIONS
    method = {
        InterestMethod.DAILY_SIMPLE_ACT365: "daily simple interest on the outstanding "
                                            "balance, actual days / 365",
        InterestMethod.MONTHLY_ON_BALANCE: "monthly interest of rate / 12 on the "
                                           "balance at each due date",
    }[debt.interest_method]
    return InterestBasis.CONTRACT_BASED, (f"Contract method: {method}.",)


@dataclass(frozen=True)
class DebtPeriod:
    """One payment date of one debt."""

    on: date
    opening: int
    interest: int | None  # None when the rate is unknown
    minimum_paid: int
    extra_paid: int
    fee: int
    closing: int | None  # None when the rate is unknown


@dataclass(frozen=True)
class DebtSchedule:
    debt_id: str
    name: str
    basis: InterestBasis
    notes: tuple[str, ...]
    periods: tuple[DebtPeriod, ...] = field(default_factory=tuple)

    @property
    def total_interest(self) -> int | None:
        if self.basis is InterestBasis.UNAVAILABLE:
            return None
        return sum(p.interest or 0 for p in self.periods)

    @property
    def payoff_date(self) -> date | None:
        if self.basis is InterestBasis.UNAVAILABLE:
            return None
        return next((p.on for p in self.periods if p.closing == 0), None)

    @property
    def closing_balance(self) -> int | None:
        if self.basis is InterestBasis.UNAVAILABLE:
            return None
        return self.periods[-1].closing if self.periods else None


def _accrue(debt: Debt, balance: int, days: int, is_due_date: bool) -> int:
    assert debt.apr is not None
    if debt.interest_method is InterestMethod.MONTHLY_ON_BALANCE:
        return round(balance * debt.apr / 12) if is_due_date else 0
    return round(balance * debt.apr * days / 365)


def _schedule_one(debt: Debt, start: date, end: date,
                  extras: list[tuple[date, int]]) -> DebtSchedule:
    basis, notes = interest_basis(debt)
    due_dates = monthly_occurrences(debt.day_of_month, start, end)
    points = sorted({*due_dates, *(on for on, _ in extras)})
    extra_on: dict[date, int] = {}
    for on, amount in extras:
        extra_on[on] = extra_on.get(on, 0) + amount

    balance, last, pending = debt.balance, start, 0
    periods: list[DebtPeriod] = []
    for on in points:
        is_due = on in due_dates
        interest = None
        if basis is not InterestBasis.UNAVAILABLE:
            if debt.interest_method is InterestMethod.MONTHLY_ON_BALANCE:
                pending += _accrue(debt, balance, 0, is_due)
            else:
                pending += _accrue(debt, balance, (on - last).days, is_due)
            last = on
            if is_due or on in extra_on:
                interest, pending = pending, 0
                balance += interest
        opening = balance
        if not is_due:
            minimum = 0
        elif basis is InterestBasis.UNAVAILABLE:
            minimum = debt.minimum_payment  # payoff cannot be projected; keep paying
        else:
            minimum = min(debt.minimum_payment, balance)
        balance = max(0, balance - minimum)
        extra = min(extra_on.get(on, 0), balance) if debt.extra_payment_allowed else 0
        balance -= extra
        fee = round(extra * (debt.prepayment_fee_rate or 0))
        if minimum or extra or interest:
            periods.append(DebtPeriod(
                on=on, opening=opening, interest=interest, minimum_paid=minimum,
                extra_paid=extra, fee=fee,
                closing=None if basis is InterestBasis.UNAVAILABLE else balance,
            ))
    return DebtSchedule(debt.id, debt.name, basis, notes, tuple(periods))


def schedule_debts(
    state: FinancialState, start: date, end: date, *, include_extra: bool = True
) -> dict[str, DebtSchedule]:
    """Schedules for every debt over [start, end], with the state's extra payments."""
    out: dict[str, DebtSchedule] = {}
    for debt in state.debts:
        extras = [] if not include_extra else [
            (on, payment.amount)
            for payment in state.debt_payments if payment.debt_id == debt.id
            for on in payment.occurrences(start, end)
        ]
        out[debt.id] = _schedule_one(debt, start, end, extras)
    return out


def payoff_order(state: FinancialState, strategy: DebtStrategy | None = None) -> list[str]:
    """Debts that may receive extra repayments, in the order they should get them.

    The user's explicit `debt_order` wins. Otherwise Avalanche puts the highest rate
    first (debts with an unknown rate last, since their cost cannot be compared) and
    Snowball puts the smallest balance first. Ties keep the order given by the user.
    """
    eligible = [d for d in state.debts if d.balance > 0 and d.extra_payment_allowed]
    if state.debt_order and strategy is None:
        ranked = [d for d_id in state.debt_order for d in eligible if d.id == d_id]
        ranked += [d for d in eligible if d.id not in state.debt_order]
        return [d.id for d in ranked]
    strategy = strategy or state.debt_strategy
    if strategy is DebtStrategy.SNOWBALL:
        ranked = sorted(eligible, key=lambda d: d.balance)
    else:
        ranked = sorted(eligible, key=lambda d: (d.apr is None, -(d.apr or 0)))
    return [d.id for d in ranked]


def balance_after(state: FinancialState, debt_id: str, day: date) -> int:
    """What is owed on `debt_id` at the end of `day`, given the state's extra payments.

    For a debt with an unknown rate the true balance cannot be known; the principal
    still unpaid (balance less payments) is returned, which is a lower bound and so
    can never lead to an extra repayment larger than the debt.
    """
    debt = next(d for d in state.debts if d.id == debt_id)
    if day < state.as_of:
        return debt.balance
    schedule = schedule_debts(state, state.as_of, day)[debt_id]
    if schedule.basis is InterestBasis.UNAVAILABLE:
        paid = sum(p.minimum_paid + p.extra_paid for p in schedule.periods)
        return max(0, debt.balance - paid)
    if not schedule.periods:
        return debt.balance
    closing = schedule.periods[-1].closing
    assert closing is not None
    return closing
