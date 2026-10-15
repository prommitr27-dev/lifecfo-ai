"""Seeded synthetic scenarios: a profile before a shock and the same profile after it.

Every scenario is generated from one integer seed, so the whole set can be
rebuilt exactly. Profiles are synthetic; amounts are round numbers in THB.
"""

import random
from dataclasses import dataclass
from datetime import date

from lifecfo.domain.models import (
    Debt,
    Envelope,
    EnvelopeKind,
    Expense,
    ExpenseCategory,
    FinancialState,
    Frequency,
    Goal,
    IncomeSource,
    SavingsTransfer,
)
from lifecfo.domain.money import thb

AS_OF = date(2026, 11, 1)
SHOCK_KINDS = ("NONE", "INCOME_CUT", "EXPENSE", "SALARY_DELAY", "COST_RISE", "COMBINED")


@dataclass(frozen=True)
class Scenario:
    seed: int
    shock: str
    description: str
    before: FinancialState  # the profile, with the user's own fixed savings plan
    after: FinancialState  # the same profile once the shock is known


def _profile(rng: random.Random) -> FinancialState:
    income = rng.randrange(18, 61) * 1000
    essentials_total = round(income * rng.uniform(0.45, 0.72) / 1000) * 1000
    rent = round(essentials_total * 0.5 / 1000) * 1000
    food = essentials_total - rent
    flexible = rng.randrange(1, 6) * 1000
    minimum = flexible - rng.randrange(0, flexible // 1000 + 1) * 500
    expenses = [
        Expense(id="rent", name="Rent", category=ExpenseCategory.ESSENTIAL, amount=thb(rent),
                day_of_month=5),
        Expense(id="food", name="Food and transport", category=ExpenseCategory.ESSENTIAL,
                amount=thb(food), day_of_month=2),
        Expense(id="leisure", name="Leisure", category=ExpenseCategory.FLEXIBLE,
                amount=thb(flexible), min_amount=thb(max(0, minimum)),
                reduction_allowed=rng.random() < 0.7, day_of_month=2),
    ]
    debts = []
    if rng.random() < 0.4:
        debts.append(Debt(id="card", name="Credit card", balance=thb(rng.randrange(5, 41) * 1000),
                          minimum_payment=thb(rng.randrange(5, 21) * 100), day_of_month=20,
                          apr=rng.choice([None, 0.16, 0.25])))
    goals, envelopes = [], [
        Envelope(id="unallocated", kind=EnvelopeKind.UNALLOCATED,
                 balance=thb(rng.randrange(0, 11) * 1000)),
        Envelope(id="emergency", kind=EnvelopeKind.EMERGENCY,
                 balance=thb(rng.randrange(0, 31) * 1000)),
    ]
    for index in range(rng.randint(1, 3)):
        goal_id = f"goal{index + 1}"
        deadline = None if rng.random() < 0.25 else date(
            2027 + rng.randint(0, 1), rng.randint(1, 12), 28)
        goals.append(Goal(id=goal_id, name=f"Goal {index + 1}",
                          target=thb(rng.randrange(5, 61) * 1000), priority=index + 1,
                          deadline=deadline, flexible=rng.random() < 0.5))
        envelopes.append(Envelope(id=f"env-{goal_id}", kind=EnvelopeKind.GOAL, goal_id=goal_id,
                                  balance=thb(rng.randrange(0, 6) * 1000)))
    state = FinancialState(
        as_of=AS_OF, reserve_months=3,
        buffer_months=1 if rng.random() < 0.6 else None,
        envelopes=tuple(envelopes),
        incomes=(IncomeSource(id="salary", name="Salary", amount=thb(income),
                              day_of_month=rng.choice([1, 1, 1, 25])),),
        expenses=tuple(expenses), debts=tuple(debts), goals=tuple(goals),
    )
    return state.model_copy(update={"transfers": _fixed_savings_plan(state)})


def _fixed_savings_plan(state: FinancialState) -> tuple[SavingsTransfer, ...]:
    """The user's own static plan: 40% of the monthly surplus to the reserve, the rest
    to goals in proportion to their targets, every month on payday."""
    surplus = (sum(i.amount for i in state.incomes) - state.monthly_essentials
               - state.monthly_debt_minimums
               - sum(e.amount for e in state.expenses
                     if e.category is ExpenseCategory.FLEXIBLE))
    if surplus <= 0:
        return ()
    day = state.incomes[0].day_of_month
    reserve = (surplus * 4 // 10) // 100 * 100
    total_targets = sum(g.target for g in state.goals)
    transfers = [SavingsTransfer(id="fixed-reserve", envelope_id="emergency", amount=reserve,
                                 day_of_month=day)] if reserve else []
    for goal in state.goals:
        share = ((surplus - reserve) * goal.target // total_targets) // 100 * 100
        if share:
            transfers.append(SavingsTransfer(id=f"fixed-{goal.id}", envelope_id=f"env-{goal.id}",
                                             amount=share, day_of_month=day))
    return tuple(transfers)


def _shock(state: FinancialState, kind: str, rng: random.Random) -> tuple[FinancialState, str]:
    if kind == "NONE":
        return state, "no shock"
    if kind == "INCOME_CUT":
        cut = rng.choice([10, 20, 30])
        incomes = tuple(i.model_copy(update={"amount": i.amount * (100 - cut) // 100})
                        for i in state.incomes)
        return state.model_copy(update={"incomes": incomes}), f"income -{cut}%"
    if kind == "EXPENSE":
        amount = rng.randrange(5, 21) * 1000
        due = date(2026, 11, rng.randint(3, 25))
        shock = Expense(id="shock", name="Emergency expense", category=ExpenseCategory.ESSENTIAL,
                        amount=thb(amount), frequency=Frequency.ONE_TIME, on_date=due)
        return (state.model_copy(update={"expenses": (*state.expenses, shock)}),
                f"emergency expense {amount:,} THB on {due}")
    if kind == "SALARY_DELAY":
        incomes = tuple(i.model_copy(update={"day_of_month": min(28, i.day_of_month + 10)})
                        for i in state.incomes)
        return state.model_copy(update={"incomes": incomes}), "salary paid 10 days later"
    if kind == "COST_RISE":
        expenses = tuple(e.model_copy(update={"amount": e.amount * 11 // 10})
                         if e.category is ExpenseCategory.ESSENTIAL else e
                         for e in state.expenses)
        return state.model_copy(update={"expenses": expenses}), "essential costs +10%"
    first, text_a = _shock(state, "INCOME_CUT", rng)
    second, text_b = _shock(first, "EXPENSE", rng)
    return second, f"{text_a} and {text_b}"


def generate_scenarios(count: int = 40, seed: int = 2026) -> list[Scenario]:
    """`count` scenarios, cycling through the shock kinds, all from one master seed."""
    out = []
    for index in range(count):
        rng = random.Random(seed * 1000 + index)
        before = _profile(rng)
        kind = SHOCK_KINDS[index % len(SHOCK_KINDS)]
        after, description = _shock(before, kind, rng)
        out.append(Scenario(seed=seed * 1000 + index, shock=kind, description=description,
                            before=before, after=after))
    return out
