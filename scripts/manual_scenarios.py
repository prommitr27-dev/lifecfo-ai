"""Manual scenario validation (Financial Rules v0.2, section 6).

Runs the six end-to-end scenarios on synthetic data and writes their inputs,
outputs, assumptions, and pass/fail checks to docs/testing/MANUAL_SCENARIOS.md.
The economics team can compare these numbers with their own hand calculations.

    uv run python scripts/manual_scenarios.py
"""

import sys
from datetime import date
from pathlib import Path

from lifecfo.agents.views import debt_comparison, expense_scenario, planning_data
from lifecfo.cashflow import forecast_cash_flow, monthly_summary
from lifecfo.cashflow.position import ShortfallKind, assess_position
from lifecfo.domain.loader import load_state
from lifecfo.domain.money import thb
from lifecfo.optimization import PlanningStatus, generate_plans, validate_plan
from lifecfo.optimization.optimizer import horizon_days

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "synthetic" / "profile_demo.yaml"
DEBT = ROOT / "data" / "synthetic" / "profile_debt_demo.yaml"
OUT = ROOT / "docs" / "testing" / "MANUAL_SCENARIOS.md"


def money(value) -> str:
    return "n/a" if value is None else f"{value:,} THB"


def checks_table(checks: list[tuple[str, bool]]) -> list[str]:
    return ["| Check | Result |", "|---|---|"] + [
        f"| {name} | {'PASS' if ok else 'FAIL'} |" for name, ok in checks]


def section(number: int, title: str, inputs: list[str], outputs: list[str],
            assumptions: list[str], checks: list[tuple[str, bool]]) -> tuple[list[str], bool]:
    passed = all(ok for _, ok in checks)
    lines = [f"## Scenario {number}: {title}", "", f"**Status: {'PASS' if passed else 'FAIL'}**",
             "", "**Inputs**", *[f"- {i}" for i in inputs], "", "**Outputs**",
             *[f"- {o}" for o in outputs], "", "**Assumptions**",
             *[f"- {a}" for a in assumptions], "", *checks_table(checks), ""]
    return lines, passed


def plan_line(plan: dict) -> str:
    goals = "; ".join(
        f"{g['name']} {g['completion_month'] or 'not within horizon'}"
        + (f" (late by {money(g['shortfall_at_deadline'])})" if g["on_track"] is False else "")
        for g in plan["goals"])
    return (f"{plan['strategy']}: reserve target reached "
            f"{plan['emergency_fund_target_reached'] or 'not within horizon'}; {goals}; "
            f"first-month flexible {money(plan['flexible_spending']['proposed_first_month'])}"
            f" of {money(plan['flexible_spending']['original_budget_first_month'])}")


def scenario_2(state):
    data = planning_data(state, 12)
    pos = data["original_position"]
    budget = pos["monthly_budget"]
    outputs = [
        f"Monthly: income {money(budget['income'])}, essentials {money(budget['essentials'])}, "
        f"flexible budget {money(budget['flexible_budget'])}, surplus under the original "
        f"budget {money(budget['surplus_under_original_budget'])}",
        f"Available (uncommitted) until {pos['coming_month']['until']}: "
        f"{money(pos['coming_month']['uncommitted_funds'])}",
        f"Reserve: target {money(pos['emergency_reserve']['target'])} "
        f"({pos['emergency_reserve']['basis']}), eligible "
        f"{money(pos['emergency_reserve']['eligible_balance'])}, gap "
        f"{money(pos['emergency_reserve']['gap'])}",
        f"Buffer: {money(pos['cash_buffer']['target'])}, accessible now "
        f"{money(pos['cash_buffer']['accessible_now'])}, short by "
        f"{money(pos['cash_buffer']['shortfall_now'])}",
        *[plan_line(p) for p in data["plans"]],
    ]
    checks = [
        ("Surplus = 30,000 - 18,000 - 0 - 3,000 = 9,000",
         budget["surplus_under_original_budget"] == 9000),
        ("Uncommitted funds for November = 9,000",
         pos["coming_month"]["uncommitted_funds"] == 9000),
        ("Reserve target = 3 x 18,000 = 54,000; gap 48,000",
         pos["emergency_reserve"]["target"] == 54000
         and pos["emergency_reserve"]["gap"] == 48000),
        ("Buffer = 1 x 18,000; short by 12,000 against 6,000 accessible",
         pos["cash_buffer"]["target"] == 18000 and pos["cash_buffer"]["shortfall_now"] == 12000),
        ("Three plans, each validated", len(data["plans"]) == 3 and all(
            validate_plan(state, p).ok for p in generate_plans(state).plans)),
        ("Flexible proposals stay within 2,000 to 3,000", all(
            2000 <= p["flexible_spending"]["proposed_first_month"] <= 3000 for p in data["plans"])),
    ]
    return section(2, "Baseline demo",
                   ["`data/synthetic/profile_demo.yaml`: salary 30,000 on day 1; essentials "
                    "18,000; leisure budget 3,000 (minimum 2,000, reduction permitted); "
                    "emergency reserve 6,000; laptop 30,000 by 2027-08-31 (priority 1); "
                    "vacation 15,000 by 2027-06-30 (priority 2, flexible); reserve 3 months; "
                    "buffer 1 month", "Horizon 12 months"],
                   outputs,
                   ["Savings are swept on the last day of each month",
                    "Essentials are monthly lump sums on their due day",
                    "Strategy weights are draft values in config/strategy_weights.yaml"],
                   checks)


def with_salary(state, amount):
    first, *rest = state.incomes
    return state.model_copy(update={"incomes": (first.model_copy(update={"amount": amount}),
                                                *rest)})


def scenario_4(state):
    from lifecfo.agents.tools import _compare  # the same comparison the agent uses

    cut = with_salary(state, thb(24000))
    months = monthly_summary(forecast_cash_flow(cut, horizon_days(cut.as_of, 12)))

    compared = _compare(state, cut, 12)
    data = planning_data(cut, 12)
    outputs = [*[f"Change over the same {compared['horizon_months']}-month horizon: {c}"
                 for c in compared["changes"]],
               *[plan_line(p) for p in data["plans"]]]
    checks = [
        ("Baseline and shock use the same horizon",
         compared["horizon_days"] == horizon_days(state.as_of, 12)),
        ("Income is 24,000 in each of the 12 months",
         len(months) == 12 and all(m.income == thb(24000) for m in months)),
        ("New goal shortfalls are disclosed",
         any("misses its deadline" in c for c in compared["changes"])),
        ("Every plan still validates", all(
            validate_plan(cut, p).ok for p in generate_plans(cut).plans)),
        ("Original budget not in deficit (24,000 - 18,000 - 3,000 = 3,000)",
         data["original_position"]["monthly_budget"]["surplus_under_original_budget"] == 3000),
    ]
    return section(4, "Income shock (-20%)",
                   ["Baseline profile with salary reduced from 30,000 to 24,000 from today",
                    "Horizon 12 months for both baseline and shock"],
                   outputs,
                   ["The change applies to recurring income only; one-off income is unchanged"],
                   checks)


def scenario_6(state):
    data = expense_scenario(state, thb(10000), date(2026, 11, 12), 12)
    reserve = data["emergency_reserve"]
    outputs = [
        f"Not covered by unallocated cash in {data['period_checked']}: "
        f"{money(data['not_covered_by_unallocated_cash'])}",
        f"Reserve withdrawal needed: {money(data['reserve_withdrawal_needed'])}; reserve "
        f"{money(reserve['balance_before'])} -> {money(reserve['balance_after_withdrawal'])}; "
        f"gap {money(reserve['gap_before'])} -> {money(reserve['gap_after'])}",
        f"Accessible cash on {data['accessible_cash']['on']}: "
        f"{money(data['accessible_cash']['with_expense'])} (without the expense "
        f"{money(data['accessible_cash']['without_expense'])})",
        f"Buffer shortfall after the expense: "
        f"{money(data['cash_buffer']['shortfall_after_expense'])}",
        *[plan_line(p) for p in data["recovery_options"]["plans"]],
    ]
    checks = [
        ("12 Nov: 30,000 - 11,000 - 9,000 - 10,000 = 0; the 1,000 bill on 15 Nov is uncovered",
         data["not_covered_by_unallocated_cash"] == 1000),
        ("Withdrawal 1,000; reserve 6,000 -> 5,000; gap 48,000 -> 49,000",
         data["reserve_withdrawal_needed"] == 1000 and reserve["gap_after"] == 49000),
        ("Recovery options are proposals only", all(
            p["status"] == "PROPOSED_NOT_APPROVED" for p in data["recovery_options"]["plans"])),
    ]
    return section(6, "Unexpected expense of 10,000",
                   ["Baseline profile; essential one-off expense 10,000 due 2026-11-12",
                    "Horizon 12 months"],
                   outputs,
                   [data["limitation"],
                    "The liquidity check runs on the original budget with no savings, up to the "
                    "next income date"],
                   checks)


def scenario_8(state):
    near = state.model_copy(update={"goals": tuple(
        g.model_copy(update={"deadline": date(2026, 12, 31)}) if g.id == "laptop" else g
        for g in state.goals)})
    data = planning_data(near, 12)
    laptop = [next(g for g in p["goals"] if g["name"] == "New laptop") for p in data["plans"]]
    outputs = [plan_line(p) for p in data["plans"]] + [
        f"Why late ({data['plans'][0]['strategy']}): {laptop[0]['why_late']}"]
    checks = [
        ("Every plan reports the laptop as late", all(g["on_track"] is False for g in laptop)),
        ("Shortfall at least 10,000 (at most 20,000 of 30,000 can be saved by 31 Dec)",
         all(g["shortfall_at_deadline"] >= 10000 for g in laptop)),
        ("Deadline unchanged", all(g["deadline"] == "2026-12-31" for g in laptop)),
        ("Laptop is not flexible, so the risk is DEADLINE_RISK and no later date is offered",
         all("DEADLINE_RISK" in g["shortfall_kinds"] for g in laptop)
         and all(a["goal"] != "New laptop" for a in data["alternatives"])),
    ]
    return section(8, "Near-term goal (laptop due in two months)",
                   ["Baseline profile with the laptop deadline moved to 2026-12-31"],
                   outputs,
                   ["The reachability ceiling counts essentials, debt minimums, and the "
                    "flexible minimum only; it ignores bills after the deadline"],
                   checks)


def scenario_10():
    state = load_state(DEBT)
    data = debt_comparison(state, 6, None)
    outputs = [f"Extra repayment per month: {money(data['extra_available_per_month'])} "
               f"({data['extra_source']})"]
    for comparison in data["comparisons"]:
        outputs.append(f"{comparison['strategy']} ({' then '.join(comparison['order'])}): "
                       f"interest where calculable "
                       f"{money(comparison['total_interest_where_calculable'])}")
        for debt in comparison["debts"]:
            outputs.append(f"{comparison['strategy']}, {debt['debt']}: "
                           f"{debt['interest_basis']}, interest "
                           f"{money(debt['interest_in_period'])}, paid off "
                           f"{debt['paid_off_on'] or 'not projected'}")
    outputs += data["facts"]
    plans = generate_plans(state, horizon_months=6).plans
    checks = [
        ("Minimum payments 3,000 a month are accounted for",
         data["required_minimums_per_month"] == 3000),
        ("Extra repayment only from residual cash (12,500 = 35,000 - 17,000 - 3,000 - 2,500)",
         data["extra_available_per_month"] == 12500),
        ("Plans keep cash non-negative and the buffer met",
         all(validate_plan(state, p).ok and not p.months_below_buffer for p in plans)),
        ("Each debt's interest basis is labelled; unknown rate shows no interest",
         {d["interest_basis"] for d in data["comparisons"][0]["debts"]}
         == {"CONTRACT_BASED", "ESTIMATED", "UNAVAILABLE"}),
        ("Avalanche and Snowball orders differ", data["comparisons"][0]["order"]
         != data["comparisons"][1]["order"]),
    ]
    return section(10, "High-APR debt, six-month forecast, Avalanche vs Snowball",
                   ["`data/synthetic/profile_debt_demo.yaml`: personal loan 12,000 at 15% "
                    "(daily simple, actual/365, contract method given); credit card 20,000 at "
                    "25% (method not given); store installment 4,000 (rate unknown); income "
                    "35,000; essentials 17,000; flexible 2,500; reserve funded; buffer met",
                    "Period 6 months"],
                   outputs, data["assumptions_and_limitations"], checks)


def scenario_12(state):
    low = with_salary(state, thb(15000))
    result = generate_plans(low)
    position = assess_position(low, horizon_days(low.as_of, 12))
    shortfall = next(s for s in position.shortfalls
                     if s.kind is ShortfallKind.CASH_FLOW_SHORTFALL)
    outputs = [f"Planning status: {result.status.value}",
               f"Cash-flow shortfall: {money(shortfall.amount // 100)} from {shortfall.on}",
               f"Detail: {shortfall.detail}"]
    checks = [
        ("No plan is offered", result.status is PlanningStatus.ESSENTIAL_SHORTFALL
         and result.plans == ()),
        ("Essentials stay at 18,000 a month (not reduced)", low.monthly_essentials == thb(18000)),
        ("The deficit is reported", shortfall.amount > 0),
    ]
    return section(12, "Essential-expense shortfall",
                   ["Baseline profile with salary reduced to 15,000 (essentials 18,000)"],
                   outputs,
                   ["Money already saved for goals is not counted as available for "
                    "essentials; using it is the user's decision"],
                   checks)


def main() -> int:
    state = load_state(DEMO)
    lines = [
        "# Manual Scenario Validation",
        "",
        "Generated by `scripts/manual_scenarios.py` from synthetic profiles. Re-running it "
        "reproduces every number. Numbers are in THB. Scenario numbers follow section 6 of "
        "Financial Rules v0.2.",
        "",
    ]
    results = []
    for build in (lambda: scenario_2(state), lambda: scenario_4(state),
                  lambda: scenario_6(state), lambda: scenario_8(state), scenario_10,
                  lambda: scenario_12(state)):
        body, passed = build()
        lines += body
        results.append(passed)
    summary = f"**{sum(results)} of {len(results)} scenarios pass.**"
    lines.insert(4, summary + "\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(summary.strip("*"), f"Written to {OUT.relative_to(ROOT)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
