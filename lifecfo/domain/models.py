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
    amount: PositiveAmount
    # Lowest amount a FLEXIBLE expense can be cut to. Essentials cannot be cut.
    min_amount: Amount | None = None

    @model_validator(mode="after")
    def _check_floor(self) -> Self:
        if self.min_amount is not None:
            if self.category is ExpenseCategory.ESSENTIAL and self.min_amount != self.amount:
                raise ValueError("ESSENTIAL expenses cannot have a reduced min_amount")
            if self.min_amount > self.amount:
                raise ValueError("min_amount cannot exceed amount")
        return self

    @property
    def floor(self) -> int:
        if self.category is ExpenseCategory.ESSENTIAL:
            return self.amount
        return self.min_amount if self.min_amount is not None else 0


class Debt(Frozen):
    id: str
    name: str
    balance: Amount
    minimum_payment: PositiveAmount
    day_of_month: DayOfMonth
    # Recorded for the financial model; interest is not accrued in the M1 forecast.
    apr: Annotated[float, Field(ge=0)] | None = None


class Goal(Frozen):
    id: str
    name: str
    target: PositiveAmount
    priority: Annotated[int, Field(ge=1)]  # 1 is the highest priority
    deadline: date | None = None


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


class FinancialState(Frozen):
    """Snapshot of one user's finances at the start of `as_of`.

    Balances are opening balances: anything scheduled on `as_of` has not happened yet.
    """

    as_of: date
    timezone: str = "Asia/Bangkok"
    currency: str = "THB"
    reserve_target: Amount = 0
    envelopes: tuple[Envelope, ...]
    incomes: tuple[IncomeSource, ...] = ()
    expenses: tuple[Expense, ...] = ()
    debts: tuple[Debt, ...] = ()
    goals: tuple[Goal, ...] = ()
    transfers: tuple[SavingsTransfer, ...] = ()

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        for label, items in (
            ("envelope", self.envelopes),
            ("income", self.incomes),
            ("expense", self.expenses),
            ("debt", self.debts),
            ("goal", self.goals),
            ("transfer", self.transfers),
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
        return self

    @property
    def unallocated(self) -> Envelope:
        return next(e for e in self.envelopes if e.kind is EnvelopeKind.UNALLOCATED)

    @property
    def total_cash(self) -> int:
        """Balance of the sandbox account: the sum of all envelopes."""
        return sum(e.balance for e in self.envelopes)
