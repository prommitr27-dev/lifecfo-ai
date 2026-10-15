"""Debt interest, payoff schedules, and extra-repayment strategies (rules D5, D6)."""

from lifecfo.debt.schedule import (
    DebtPeriod,
    DebtSchedule,
    InterestBasis,
    allocate_extra,
    balance_after,
    interest_basis,
    payoff_order,
    schedule_debts,
)

__all__ = [
    "DebtPeriod",
    "DebtSchedule",
    "InterestBasis",
    "allocate_extra",
    "balance_after",
    "interest_basis",
    "payoff_order",
    "schedule_debts",
]
