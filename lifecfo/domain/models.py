"""Immutable financial state shared by all modules.

Every amount is integer satang. Models are frozen so that simulations work on
copies and can never write back to the state they were given.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lifecfo.domain.schedule import monthly_occurrences

Amount = Annotated[int, Field(ge=0)]
PositiveAmount = Annotated[int, Field(gt=0)]
DayOfMonth = Annotated[int, Field(ge=1, le=31)]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Frequency(StrEnum):
    MONTHLY = "MONTHLY"
    ONE_TIME = "ONE_TIME"


class ExpenseCategory(StrEnum):
    ESSENTIAL = "ESSENTIAL"
    FLEXIBLE = "FLEXIBLE"


class InterestMethod(StrEnum):
    """Contractual interest methods the engine can reproduce exactly (rules D5, case A)."""

    DAILY_SIMPLE_ACT365 = "DAILY_SIMPLE_ACT365"  # interest = balance x rate x days / 365
    MONTHLY_ON_BALANCE = "MONTHLY_ON_BALANCE"  # interest = balance x rate / 12 each due date


class DebtStrategy(StrEnum):
    AVALANCHE = "AVALANCHE"  # highest interest rate first
    SNOWBALL = "SNOWBALL"  # smallest balance first


class EnvelopeKind(StrEnum):
    UNALLOCATED = "UNALLOCATED"
    EMERGENCY = "EMERGENCY"
    GOAL = "GOAL"


class Scheduled(Frozen):
    """Something that happens monthly on a day, or once on a date."""

    frequency: Frequency = Frequency.MONTHLY
    day_of_month: DayOfMonth | None = None
    on_date: date | None = None
    active_from: date | None = None
    active_to: date | None = None

    @model_validator(mode="after")
    def _check_schedule(self) -> Self:
        if self.frequency is Frequency.MONTHLY and self.day_of_month is None:
            raise ValueError("MONTHLY items need day_of_month")
        if self.frequency is Frequency.ONE_TIME and self.on_date is None:
            raise ValueError("ONE_TIME items need on_date")
        return self

    def occurrences(self, start: date, end: date) -> list[date]:
        """Dates this item falls on within [start, end], both inclusive."""
        if self.frequency is Frequency.ONE_TIME:
            assert self.on_date is not None
            return [self.on_date] if start <= self.on_date <= end else []
        assert self.day_of_month is not None
        return monthly_occurrences(
            self.day_of_month, start, end, self.active_from, self.active_to
        )


class IncomeSource(Scheduled):
    id: str
    name: str
    amount: PositiveAmount


class Expense(Scheduled):
    id: str
    name: str
    category: ExpenseCategory
    # For FLEXIBLE expenses `amount` is the user's original budget (rules D1).
    amount: PositiveAmount
    # The user's minimum acceptable amount for a FLEXIBLE expense.
    min_amount: Amount | None = None
    # Whether the planner may propose a cut down to min_amount. A proposal is never
    # applied without approval; without this permission the budget is a constraint.
    reduction_allowed: bool = False

    @model_validator(mode="after")
    def _check_floor(self) -> Self:
        if self.min_amount is not None:
            if self.category is ExpenseCategory.ESSENTIAL and self.min_amount != self.amount:
                raise ValueError("ESSENTIAL expenses cannot have a reduced min_amount")
            if self.min_amount > self.amount:
                raise ValueError("min_amount cannot exceed amount")
        if self.reduction_allowed:
            if self.category is ExpenseCategory.ESSENTIAL:
                raise ValueError("ESSENTIAL expenses cannot be reduced")
            if self.min_amount is None:
                raise ValueError("reduction_allowed needs the user's min_amount")
        return self

    @property
    def floor(self) -> int:
        """Lowest amount a plan may propose for this expense."""
        if self.category is ExpenseCategory.FLEXIBLE and self.reduction_allowed:
            assert self.min_amount is not None
            return self.min_amount
        return self.amount


class Debt(Frozen):
    id: str
    name: str
    balance: Amount
    minimum_payment: PositiveAmount
    day_of_month: DayOfMonth
    # Annual rate as a decimal (0.25 = 25%). None means unknown: never treated as 0%.
    apr: Annotated[float, Field(ge=0, le=5)] | None = None
    # The contract's method, when the user knows it. Without it, interest is estimated.
    interest_method: InterestMethod | None = None
    extra_payment_allowed: bool = True
    # Fee charged on an early (extra) repayment, as a fraction of the amount repaid.
    prepayment_fee_rate: Annotated[float, Field(ge=0, le=1)] | None = None


class Goal(Frozen):
    id: str
    name: str
    target: PositiveAmount
    priority: Annotated[int, Field(ge=1)]  # 1 is the highest priority
    deadline: date | None = None
    # Rules D7: a flexible goal may be offered a later date; a non-flexible one may not.
    flexible: bool = False


class Envelope(Frozen):
    """A virtual sub-balance of the single sandbox cash account."""

    id: str
    kind: EnvelopeKind
    balance: Amount
    goal_id: str | None = None

    @model_validator(mode="after")
    def _check_goal_link(self) -> Self:
        if (self.kind is EnvelopeKind.GOAL) != (self.goal_id is not None):
            raise ValueError("goal_id is required for GOAL envelopes and forbidden otherwise")
        return self


class SavingsTransfer(Scheduled):
    """A planned move from the unallocated envelope into another envelope."""

    id: str
    envelope_id: str
    amount: PositiveAmount


class ExtraDebtPayment(Scheduled):
    """A planned payment above the contractual minimum, from unallocated cash."""

    id: str
    debt_id: str
    amount: PositiveAmount


class FinancialState(Frozen):
    """Snapshot of one user's finances at the start of `as_of`.

    Balances are opening balances: anything scheduled on `as_of` has not happened yet.
    """

    as_of: date
    timezone: str = "Asia/Bangkok"
    currency: str = "THB"
    # Rules D4: reserve target = reserve_months x (essentials + debt minimums),
    # unless the user sets a custom amount.
    reserve_months: Annotated[float, Field(ge=0, le=36)] = 3
    reserve_target: Amount | None = None
    # Rules D3: minimum cash buffer, as months of (essentials + debt minimums) or a
    # fixed amount. None of the two means the user has not configured a buffer yet.
    buffer_months: Annotated[float, Field(ge=0, le=12)] | None = None
    buffer_amount: Amount | None = None
    # Rules D6: payoff order for extra repayments; debt_order overrides it.
    debt_strategy: DebtStrategy = DebtStrategy.AVALANCHE
    debt_order: tuple[str, ...] = ()
    envelopes: tuple[Envelope, ...]
    incomes: tuple[IncomeSource, ...] = ()
    expenses: tuple[Expense, ...] = ()
    debts: tuple[Debt, ...] = ()
    goals: tuple[Goal, ...] = ()
    transfers: tuple[SavingsTransfer, ...] = ()
    debt_payments: tuple[ExtraDebtPayment, ...] = ()

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        for label, items in (
            ("envelope", self.envelopes),
            ("income", self.incomes),
            ("expense", self.expenses),
            ("debt", self.debts),
            ("goal", self.goals),
            ("transfer", self.transfers),
            ("debt payment", self.debt_payments),
        ):
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {label} id")

        unallocated = [e for e in self.envelopes if e.kind is EnvelopeKind.UNALLOCATED]
        if len(unallocated) != 1:
            raise ValueError("exactly one UNALLOCATED envelope is required")
        if sum(e.kind is EnvelopeKind.EMERGENCY for e in self.envelopes) > 1:
            raise ValueError("at most one EMERGENCY envelope is allowed")

        goal_ids = {g.id for g in self.goals}
        linked = [e.goal_id for e in self.envelopes if e.goal_id is not None]
        if not set(linked) <= goal_ids:
            raise ValueError("envelope references an unknown goal")
        if len(linked) != len(set(linked)):
            raise ValueError("a goal can have only one envelope")

        targets = {e.id for e in self.envelopes if e.kind is not EnvelopeKind.UNALLOCATED}
        if not {t.envelope_id for t in self.transfers} <= targets:
            raise ValueError("transfer targets an unknown or UNALLOCATED envelope")

        debt_ids = {d.id for d in self.debts}
        if not {p.debt_id for p in self.debt_payments} <= debt_ids:
            raise ValueError("extra payment targets an unknown debt")
        if not set(self.debt_order) <= debt_ids:
            raise ValueError("debt_order names an unknown debt")
        if self.buffer_months is not None and self.buffer_amount is not None:
            raise ValueError("give buffer_months or buffer_amount, not both")
        return self

    @property
    def unallocated(self) -> Envelope:
        return next(e for e in self.envelopes if e.kind is EnvelopeKind.UNALLOCATED)

    @property
    def total_cash(self) -> int:
        """Balance of the sandbox account: the sum of all envelopes."""
        return sum(e.balance for e in self.envelopes)

    @property
    def emergency(self) -> Envelope | None:
        return next((e for e in self.envelopes if e.kind is EnvelopeKind.EMERGENCY), None)

    @property
    def monthly_essentials(self) -> int:
        """E in the rules: recurring essential expenses per month."""
        return sum(e.amount for e in self.expenses
                   if e.category is ExpenseCategory.ESSENTIAL and e.frequency is Frequency.MONTHLY)

    @property
    def monthly_debt_minimums(self) -> int:
        """D in the rules: contractual minimum payments on debts that are not paid off."""
        return sum(d.minimum_payment for d in self.debts if d.balance > 0)

    @property
    def emergency_target(self) -> int:
        """Rules D4: the user's custom target, else reserve_months x (E + D)."""
        if self.reserve_target is not None:
            return self.reserve_target
        return round(self.reserve_months * (self.monthly_essentials + self.monthly_debt_minimums))

    @property
    def recommended_buffer(self) -> int:
        """Rules D3 starting recommendation: one month of (E + D)."""
        return self.monthly_essentials + self.monthly_debt_minimums

    @property
    def buffer_target(self) -> int | None:
        """The configured minimum cash buffer, or None when the user has not set one."""
        if self.buffer_amount is not None:
            return self.buffer_amount
        if self.buffer_months is not None:
            return round(self.buffer_months * (self.monthly_essentials
                                               + self.monthly_debt_minimums))
        return None
