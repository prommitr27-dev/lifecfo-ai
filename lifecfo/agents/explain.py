"""Deterministic explanations: turn tool results into text without an LLM.

Every sentence is assembled from fields of a tool result, so the wording can
never state a number the engines did not produce.
"""

from typing import Any


def thb(value: int | float | None) -> str:
    return "n/a" if value is None else f"{value:,} THB"


def profile(data: dict[str, Any]) -> str:
    return (
        f"As of {data['as_of']} you hold {thb(data['total_cash'])} in the sandbox account: "
        f"{thb(data['unallocated_cash'])} unallocated and {thb(data['emergency_fund'])} in the "
        f"emergency fund (target {thb(data['emergency_fund_target'])}).\n\n"
        f"- Monthly income: {thb(data['monthly_income'])}\n"
        f"- Essential expenses: {thb(data['monthly_essential_expenses'])}\n"
        f"- Debt minimums: {thb(data['monthly_debt_minimums'])}\n"
        f"- Flexible budget: {thb(data['monthly_flexible_budget'])} "
        f"(can be cut to {thb(data['monthly_flexible_minimum'])})\n"
        f"- Planned savings: {thb(data['monthly_planned_savings'])}"
    )


def goals(data: dict[str, Any]) -> str:
    if not data["goals"]:
        return "You have no goals yet."
    lines = [
        f"- {g['name']} (priority {g['priority']}): {thb(g['saved'])} of {thb(g['target'])}, "
        f"{g['progress_percent']}% done"
        + (f", deadline {g['deadline']}" if g["deadline"] else ", no deadline")
        for g in data["goals"]
    ]
    return "Your goals, by priority:\n\n" + "\n".join(lines)


def forecast(data: dict[str, Any]) -> str:
    status = data["status"]
    if status == "FEASIBLE":
        return (
            f"Your current plan is funded on every day of the next {data['horizon_days']} "
            f"days. The lowest unallocated balance is {thb(data['lowest_unallocated_cash'])} "
            f"on {data['lowest_unallocated_cash_on']}."
        )
    if status == "PLAN_INFEASIBLE":
        text = (
            f"Your current plan cannot be funded. Unallocated cash first goes negative on "
            f"{data['first_shortfall_on']} and the plan ends up {thb(data['largest_shortfall'])} "
            f"short within {data['horizon_days']} days. Essential bills can still be paid, so "
            "this can be fixed by replanning."
        )
        if data["needs_existing_savings"]:
            text += " Paying essentials on time would require using existing savings."
        return text
    return (
        f"Essential bills cannot be paid. Even with flexible spending at its minimum and all "
        f"savings used, you would be {thb(data['essential_shortfall'])} short within "
        f"{data['horizon_days']} days. I will not suggest a plan that does not exist; income "
        "or essential costs have to change first."
    )


def plans(data: dict[str, Any]) -> str:
    if data["status"] == "ESSENTIAL_SHORTFALL":
        return (
            "No plan can be offered: essential bills cannot be paid, and the shortfall "
            f"reaches {thb(data['essential_shortfall'])} from {data['essential_shortfall_on']}."
        )
    if data["status"] == "REQUIRES_RESERVE_DRAWDOWN":
        return (
            "No regular plan can be offered: essentials can only be paid by using existing "
            "savings, which is a recovery decision that needs your explicit approval."
        )
    blocks = []
    for plan in data["plans"]:
        goal_lines = "; ".join(
            f"{g['name']} "
            + (f"done {g['completion_month']}" if g["completion_month"]
               else "not finished within the horizon")
            + ("" if g["on_track"] is not False
               else f" (misses its deadline by {thb(g['shortfall_at_deadline'])})")
            for g in plan["goals"]
        )
        contributions = ", ".join(
            f"{name} {thb(amount)}" for name, amount in plan["first_month_contributions"].items()
        ) or "nothing"
        blocks.append(
            f"**{plan['strategy']}**\n"
            f"- Emergency fund target reached: "
            f"{plan['emergency_fund_target_reached'] or 'not within the horizon'}\n"
            f"- Goals: {goal_lines or 'none'}\n"
            f"- {plan['first_month']}: saves {contributions}; flexible spending "
            f"{thb(plan['first_month_flexible_spending'])}"
        )
    text = (
        f"I generated {len(data['plans'])} plans over {data['horizon_months']} months. Each "
        "one passed the deterministic validator and the daily cash check.\n\n"
        + "\n\n".join(blocks)
    )
    if data["tradeoffs"]:
        text += "\n\n**Trade-offs**\n" + "\n".join(f"- {fact}" for fact in data["tradeoffs"])
    return text + "\n\nThese are proposals. Nothing changes until you approve a plan."


def income_change(data: dict[str, Any]) -> str:
    direction = "drop" if data["income_change_percent"] < 0 else "rise"
    return (
        f"Hypothetical scenario (nothing was saved): a {abs(data['income_change_percent']):g}% "
        f"income {direction} puts monthly income at {thb(data['new_monthly_income'])}.\n\n"
        f"**Effect on the current plan**\n{forecast(data['current_plan'])}\n\n"
        f"**Replanning**\n{plans(data['replanning'])}"
    )


def insights(data: dict[str, Any]) -> str:
    bills = "\n".join(
        f"- {b['date']}: {b['name']}, {thb(b['amount'])}" for b in data["upcoming_bills"]
    ) or "- none"
    largest = ", ".join(f"{e['name']} ({thb(e['amount'])})"
                        for e in data["largest_monthly_expenses"])
    share = data["committed_share_of_income_percent"]
    return (
        f"Bills due {data['period']}, {thb(data['upcoming_bills_total'])} in total:\n\n{bills}\n\n"
        f"Largest monthly expenses: {largest or 'none'}.\n"
        + (f"Essentials and debt minimums take {share}% of your income, leaving "
           f"{thb(data['free_cash_per_month_after_essentials'])} a month to allocate."
           if share is not None else "No regular income is recorded.")
    )


RENDERERS = {
    "get_financial_profile": profile,
    "get_financial_goals": goals,
    "get_cash_flow_forecast": forecast,
    "optimize_financial_plan": plans,
    "simulate_income_change": income_change,
    "get_spending_insights": insights,
}

HELP = (
    "I can help with the following, always from calculated results:\n\n"
    "- **Overview**: \"Show my financial summary\"\n"
    "- **Goals**: \"How are my goals doing?\"\n"
    "- **Bills and spending**: \"What bills are coming up?\"\n"
    "- **Cash flow**: \"Can I afford my current plan?\"\n"
    "- **Plans**: \"Compare the three plans\"\n"
    "- **What-if**: \"What if my income drops 20%?\""
)

CANNOT_EXECUTE = (
    "I can't approve or execute anything on my own. I can prepare and explain plans; a "
    "plan only takes effect after you approve it in the app, and it is then applied in "
    "the sandbox, never to a real account. Approval and sandbox execution are being added "
    "in the next milestone."
)
