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


SHORTFALL_LABELS = {
    "CASH_FLOW_SHORTFALL": "Cash-flow shortfall",
    "RESERVE_WITHDRAWAL_NEEDED": "Reserve withdrawal needed",
    "FLEXIBLE_SPENDING_CONSTRAINT": "Flexible-spending constraint",
    "BUFFER_SHORTFALL": "Cash buffer shortfall",
    "SAVINGS_GOAL_SHORTFALL": "Savings-goal shortfall",
    "DEADLINE_RISK": "Deadline risk",
    "FLEXIBLE_GOAL_DELAY": "Flexible-goal delay",
}


def position(data: dict[str, Any]) -> str:
    """The user's own position, shown before any proposal (rules D2)."""
    budget, cash, month = data["monthly_budget"], data["current_cash"], data["coming_month"]
    reserve, buffer = data["emergency_reserve"], data["cash_buffer"]
    surplus = budget["surplus_under_original_budget"]
    lines = [
        "**Your position under your own budget** (before any proposal)",
        f"- Each month: income {thb(budget['income'])}, essentials {thb(budget['essentials'])}, "
        f"debt minimums {thb(budget['debt_minimums'])}, flexible budget "
        f"{thb(budget['flexible_budget'])}; "
        + (f"{thb(surplus)} left for savings." if surplus >= 0
           else f"a deficit of {thb(-surplus)} a month."),
        "- Original budget over the horizon: "
        + ("no cash gap." if not data["original_budget_deficit"] else
           f"short by up to {thb(data['original_budget_deficit'])} from "
           f"{data['original_budget_deficit_from']}."),
        f"- Cash now: {thb(cash['unallocated'])} unallocated, "
        f"{thb(cash['eligible_emergency_reserve'])} emergency reserve, "
        f"{thb(cash['committed_to_goals'])} already committed to goals.",
        f"- Until {month['until']}: {thb(month['income'])} income against "
        f"{thb(month['obligations_under_original_budget'])} of bills and flexible spending, "
        f"leaving {thb(month['uncommitted_funds'])} uncommitted.",
        f"- Emergency reserve target {thb(reserve['target'])} ({reserve['basis']}); "
        f"{thb(reserve['eligible_balance'])} saved, gap {thb(reserve['gap'])}.",
    ]
    if buffer["configured"]:
        lines.append(
            f"- Cash buffer {thb(buffer['target'])}: accessible cash is "
            f"{thb(buffer['accessible_now'])}"
            + (f", {thb(buffer['shortfall_now'])} below it." if buffer["shortfall_now"]
               else ", so it is met."))
    else:
        lines.append(
            f"- No cash buffer is set. The starting recommendation is one month of essentials "
            f"and debt minimums, {thb(buffer['recommended_if_not_configured'])}; please confirm "
            "or change it.")
    for shortfall in data["shortfalls"]:
        amount = f" of {thb(shortfall['amount'])}" if shortfall["amount"] is not None else ""
        lines.append(f"- **{SHORTFALL_LABELS[shortfall['kind']]}**{amount}: "
                     f"{shortfall['detail']}")
    return "\n".join(lines)


def plans(data: dict[str, Any]) -> str:
    head = position(data["original_position"]) + "\n\n" if data.get("original_position") else ""
    if data["status"] == "ESSENTIAL_SHORTFALL":
        return head + (
            "No plan can be offered: essential expenses and minimum debt payments cannot be "
            f"paid, and the shortfall reaches {thb(data['essential_shortfall'])} from "
            f"{data['essential_shortfall_on']}. They are not reduced to make a plan fit.")
    if data["status"] == "REQUIRES_RESERVE_DRAWDOWN":
        return head + (
            "No regular plan can be offered: essentials can only be paid by withdrawing from "
            "the emergency reserve, which is a recovery decision that needs your approval.")
    if data["status"] == "FLEXIBLE_SPENDING_CONSTRAINT":
        return head + (
            "No plan can be offered without changing one of your preferences: even with "
            "flexible spending at the minimum you allowed, the budget runs short. Options are "
            "a lower flexible minimum, more income, or lower costs, each your decision.")
    blocks = []
    for plan in data["plans"]:
        goal_lines = []
        for g in plan["goals"]:
            done = (f"projected to complete {g['completion_month']}" if g["completion_month"]
                    else f"not complete within the horizon ({thb(g['saved_in_horizon'])} saved, "
                         f"{thb(g['remaining_after_horizon'])} still to go)")
            risk = ""
            if g["on_track"] is False:
                kind = "flexible goal, a later date may be proposed" if g["flexible"] else (
                    "deadline risk")
                risk = f"; misses {g['deadline']} by {thb(g['shortfall_at_deadline'])} ({kind})"
            goal_lines.append(f"{g['name']} {done}{risk}")
        flex = plan["flexible_spending"]
        flex_line = (
            f"flexible spending {thb(flex['proposed_first_month'])}"
            + (f" (proposed cut of {thb(flex['reduction_first_month'])}, "
               f"{flex['reduction_percent_first_month']}% below your "
               f"{thb(flex['original_budget_first_month'])} budget)"
               if flex["reduction_first_month"] else " (your full budget)"))
        contributions = ", ".join(
            f"{name} {thb(amount)}" for name, amount in plan["first_month_contributions"].items()
        ) or "nothing"
        extra = plan["first_month_extra_debt_repayment"]
        block = [
            f"**{plan['strategy']}** (proposal, not approved)",
            f"- Emergency fund target reached: "
            f"{plan['emergency_fund_target_reached'] or 'not within the horizon'}",
            f"- Goals: {'; '.join(goal_lines) or 'none'}",
            f"- {plan['first_month']}: saves {contributions}; {flex_line}"
            + ("; extra debt repayment "
               + ", ".join(f"{k} {thb(v)}" for k, v in extra.items()) if extra else ""),
        ]
        buffer = plan["cash_buffer"]
        if buffer["months_below_buffer"]:
            block.append(
                f"- Below your {thb(buffer['target'])} cash buffer in "
                f"{len(buffer['months_below_buffer'])} month(s) "
                f"({', '.join(buffer['months_below_buffer'][:3])}), by up to "
                f"{thb(buffer['largest_shortfall'])}; goal contributions wait in those months.")
        for g in plan["goals"]:
            if g.get("why_late"):
                block.append(f"  - Why {g['name']} is late: {g['why_late']}")
            elif g.get("zero_allocation_note"):
                block.append(f"  - {g['zero_allocation_note']}")
            if g.get("no_deadline_note"):
                block.append(f"  - {g['name']}: about {thb(g['average_per_month'])} a month. "
                             f"{g['no_deadline_note']}")
        blocks.append("\n".join(block))
    text = head + (
        f"I generated {len(data['plans'])} plans over {data['horizon_months']} months. Each "
        "one passed the deterministic validator and the daily cash check.\n\n"
        + "\n\n".join(blocks))
    if data["tradeoffs"]:
        text += "\n\n**Trade-offs**\n" + "\n".join(f"- {fact}" for fact in data["tradeoffs"])
    for option in data.get("alternatives", []):
        if option.get("kind") == "KEEP_FLEXIBLE_BUDGET":
            text += ("\n\n**If you decline the flexible cut**\n"
                     + ("\n".join(f"- {e}" for e in option["effects"]) + "\n"
                        if option["possible"] else "")
                     + f"- {option['note']}")
            continue
        text += (
            f"\n\n**Option to consider: a later date for {option['goal']}** "
            f"(needs your approval)\n- Without its {option['current_deadline']} deadline, "
            f"{option['goal']} is projected to complete "
            f"{option['projected_completion_without_the_deadline'] or 'after the horizon'}.\n"
            + "\n".join(f"- {effect}" for effect in option["effects_on_other_goals"])
            + f"\n- {option['note']}")
    return text + "\n\nThese are proposals. Nothing changes until you approve a plan."


def debts(data: dict[str, Any]) -> str:
    if "error" in data:
        return "No debts are recorded, so there is nothing to compare."
    lines = [
        f"**Debt repayment comparison**, {data['period']} (proposal, not approved)",
        f"- Required minimum payments: {thb(data['required_minimums_per_month'])} a month.",
        f"- Extra repayment compared: {thb(data['extra_available_per_month'])} a month "
        f"({data['extra_source']}).",
    ]
    if not data["extra_available_per_month"]:
        lines.append("- No money is genuinely left for extra repayment, so none is "
                     "allocated; the orders below differ only once extra money exists.")
    for comparison in data["comparisons"]:
        lines.append(f"\n**{comparison['strategy']}**: order "
                     f"{' then '.join(comparison['order']) or 'none eligible'}")
        for debt in comparison["debts"]:
            interest = ("unavailable (rate unknown)" if debt["interest_in_period"] is None
                        else f"{thb(debt['interest_in_period'])} "
                             f"({debt['interest_basis'].lower().replace('_', ' ')})")
            lines.append(
                f"- {debt['debt']}: interest {interest}; minimum {thb(debt['minimum_paid'])}, "
                f"extra {thb(debt['extra_paid'])}"
                + (f", fees {thb(debt['fees'])}" if debt["fees"] else "")
                + (f"; paid off {debt['paid_off_on']}" if debt["paid_off_on"] else "")
                + (f"; owed at the end {thb(debt['balance_at_end'])}"
                   if debt["balance_at_end"] is not None else "; balance not projectable"))
    if data["facts"]:
        lines.append("\n**What differs**\n" + "\n".join(f"- {f}" for f in data["facts"]))
    lines.append("\n**Assumptions and limitations**\n"
                 + "\n".join(f"- {n}" for n in data["assumptions_and_limitations"]))
    lines.append(f"\n{data['note']}")
    return "\n".join(lines)


def unexpected_expense(data: dict[str, Any]) -> str:
    if "error" in data:
        return "I could not size that expense because no monthly income is recorded."
    reserve, access, buffer = (data["emergency_reserve"], data["accessible_cash"],
                               data["cash_buffer"])
    lines = [
        f"Hypothetical scenario (nothing was saved): an unexpected expense of "
        f"{thb(data['expense_amount'])} due on {data['expense_due_on']}.",
        "",
        f"**Liquidity, {data['period_checked']}**",
        f"- Unallocated cash cannot cover {thb(data['not_covered_by_unallocated_cash'])} "
        "of it on your original budget."
        if data["not_covered_by_unallocated_cash"] else
        "- Unallocated cash covers it on your original budget.",
        f"- Accessible cash (unallocated plus reserve) on {access['on']}: "
        f"{thb(access['with_expense'])} instead of {thb(access['without_expense'])}.",
    ]
    if data["reserve_withdrawal_needed"]:
        lines.append(
            f"- That needs a withdrawal of {thb(data['reserve_withdrawal_needed'])} from the "
            f"emergency reserve: {thb(reserve['balance_before'])} becomes "
            f"{thb(reserve['balance_after_withdrawal'])}, and the gap to the "
            f"{thb(reserve['target'])} target grows from {thb(reserve['gap_before'])} to "
            f"{thb(reserve['gap_after'])}.")
    if data["still_uncovered_after_reserve"]:
        lines.append(f"- Even after the reserve, {thb(data['still_uncovered_after_reserve'])} "
                     "remains uncovered: a cash-flow shortfall.")
    if buffer["target"] is not None:
        lines.append(f"- Against your {thb(buffer['target'])} cash buffer: "
                     + (f"{thb(buffer['shortfall_after_expense'])} short after the expense."
                        if buffer["shortfall_after_expense"] else "still met."))
    lines += ["", f"**Effect on the current plan**\n{forecast(data['current_plan'])}", "",
              comparison(data["compared_with_current"]), "",
              "**Recovery options (proposals)**",
              plans(data["recovery_options"]), "", f"Note: {data['limitation']}"]
    return "\n".join(lines)


def comparison(data: dict[str, Any]) -> str:
    changes = "\n".join(f"- {fact}" for fact in data["changes"])
    return (f"**Compared with your current situation** (same {data['horizon_months']}-month "
            f"horizon)\n{changes}")


def income_change(data: dict[str, Any]) -> str:
    direction = "drop" if data["income_change_percent"] < 0 else "rise"
    return (
        f"Hypothetical scenario (nothing was saved): a {abs(data['income_change_percent']):g}% "
        f"income {direction} puts monthly income at {thb(data['new_monthly_income'])}.\n\n"
        f"**Effect on the current plan**\n{forecast(data['current_plan'])}\n\n"
        f"{comparison(data['compared_with_current'])}\n\n"
        f"**Replanning**\n{plans(data['replanning'])}\n\n"
        f"Assumption: {data['assumption']}"
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


def approval_request(data: dict[str, Any]) -> str:
    if "error" in data:
        return f"I could not propose a plan: {data['detail']}"
    if not data["ok"]:
        return f"The plan was not stored: {data['message']}"
    return (
        f"I stored the **{data['strategy']}** plan as proposal `{data['plan_id']}`. "
        "It is waiting for your decision: open the Sandbox view and press Approve or "
        "Reject. I cannot approve it for you, and nothing has changed yet."
    )


def execution(data: dict[str, Any]) -> str:
    if "error" in data:
        return f"I could not execute anything: {data['detail']}"
    if data["ok"]:
        return (
            f"Done. {data['message']} Plan `{data['plan_id']}` was executed under your "
            "approval and recorded in the audit log. No real account was touched."
        )
    return f"Nothing was executed ({data['code']}): {data['message']}"


def audit(data: dict[str, Any]) -> str:
    if "error" in data:
        return f"The audit log is not available here: {data['detail']}"
    lines = [
        f"- #{entry['seq']} {entry['time']} {entry['actor']}: {entry['action']}"
        + (f" ({entry['code']})" if entry["code"] else "")
        + (f" {entry['plan_id']}" if entry["plan_id"] else "")
        for entry in data["entries"]
    ]
    chain = "intact" if data["chain_intact"] else "BROKEN: the log was altered"
    return f"Audit log hash chain: {chain}.\n\n" + ("\n".join(lines) or "- no entries yet")


def rewards(data: dict[str, Any]) -> str:
    if "error" in data:
        return f"Rewards are not available here: {data['detail']}"
    progress = "\n".join(f"- {g['goal']}: {g['percent']}%" for g in data["goal_progress"])
    if not data["opted_in"]:
        return f"{data['note']}\n\nGoal progress:\n{progress or '- no goals'}"
    streak_lines = []
    for kind, s in data["streaks"].items():
        label = {"DAILY": "Daily streak", "WEEKLY": "Weekly streak"}[kind]
        state = {"NOT_STARTED": "not started yet", "ACTIVE": "active",
                 "PROTECTED": f"protected until {s['protected_until']}",
                 "PAUSED": "paused", "BROKEN": "ready to start again"}[s["status"]]
        streak_lines.append(f"- {label}: {s['count']} ({state}; best {s['best']})")
    missions = "\n".join(f"- [{'x' if m['done'] else ' '}] {m['title']}"
                         for m in data["missions"]["items"])
    text = (f"Level {data['level']}, {data['xp']} XP"
            + (f" ({data['next_level_at_xp']} for the next level)"
               if data["next_level_at_xp"] else "")
            + ".\n\n" + "\n".join(streak_lines)
            + f"\n\n**This week's missions** ({data['missions']['mode'].lower()})\n{missions}")
    if data["missions"].get("note"):
        text += f"\n{data['missions']['note']}"
    if data["badges"]:
        text += "\n\n**Badges**: " + ", ".join(data["badges"])
    return text + f"\n\n**Goal progress**\n{progress or '- no goals'}\n\n{data['note']}"


def goal_feasibility(data: dict[str, Any]) -> str:
    lines = [f"Free cash under your original budget: "
             f"{thb(data['free_cash_per_month_under_original_budget'])} a month. Your goals "
             f"with deadlines need {thb(data['required_per_month_by_all_deadline_goals'])} a "
             f"month together, and the emergency reserve gap is {thb(data['reserve_gap'])}.", ""]
    labels = {"ALREADY_FUNDED": "already funded", "NO_DEADLINE": "no deadline",
              "NOT_REACHABLE_ON_TIME": "not reachable on time",
              "REACHABLE_ON_ITS_OWN": "reachable on its own",
              "REACHABLE_ONLY_WITH_CUTS": "reachable only with cuts or other goals waiting"}
    for g in data["goals"]:
        line = (f"- **{g['goal']}** (priority {g['priority']}): "
                f"{labels[g['status']]}; {thb(g['remaining'])} still needed")
        if "required_per_month" in g:
            line += (f", {thb(g['required_per_month'])} a month over "
                     f"{g['month_end_sweeps_before_deadline']} month(s) to {g['deadline']}; "
                     f"if it took every spare baht, at most "
                     f"{thb(g['most_possible_by_deadline'])} could be saved by then")
        if g.get("months_if_all_free_cash_went_to_it"):
            line += (f"; about {g['months_if_all_free_cash_went_to_it']} month(s) if all free "
                     "cash went to it alone")
        if g.get("note"):
            line += f". {g['note']}"
        lines.append(line)
    return "\n".join(lines + ["", data["note"]])


def risk(data: dict[str, Any]) -> str:
    labels = {"NO_THRESHOLD_SET": "no threshold set yet", "INFORMATION": "for information",
              "NO_SHORTFALL_IN_HORIZON": "no shortfall in the horizon",
              "NOT_MEASURABLE": "not measurable", "NONE": "none", "AT_RISK": "at risk",
              "NOTHING_DUE": "nothing due", "NO_ESSENTIALS": "no essentials recorded"}
    lines = [f"**Risk indicators** (as of {data['as_of']}, {data['horizon_days']} days)"]
    for item in data["indicators"]:
        if item["value"] is None:
            value = "n/a"
        elif item.get("unit") == "THB":
            value = thb(item["value"])
        else:
            value = f"{item['value']:,}"
        extra = f" on {item['on']}" if item.get("on") else ""
        goals = f" ({', '.join(item['goals'])})" if item.get("goals") else ""
        rating = labels.get(item["rating"], item["rating"].lower().replace("_", " "))
        lines.append(f"- {item['name']}: {value}{extra}{goals} [{rating}]")
        if item.get("note"):
            lines.append(f"  - {item['note']}")
    return "\n".join(lines + ["", data["note"]])


RENDERERS = {
    "get_financial_profile": profile,
    "get_financial_goals": goals,
    "get_cash_flow_forecast": forecast,
    "optimize_financial_plan": plans,
    "simulate_income_change": income_change,
    "simulate_unexpected_expense": unexpected_expense,
    "request_plan_approval": approval_request,
    "execute_approved_sandbox_plan": execution,
    "get_audit_history": audit,
    "get_financial_position": position,
    "compare_debt_strategies": debts,
    "get_reward_status": rewards,
    "calculate_goal_feasibility": goal_feasibility,
    "assess_financial_risk": risk,
    "get_spending_insights": insights,
}

HELP = (
    "I can help with the following, always from calculated results:\n\n"
    "- **Overview**: \"Show my financial summary\"\n"
    "- **Goals**: \"How are my goals doing?\"\n"
    "- **Bills and spending**: \"What bills are coming up?\"\n"
    "- **Cash flow**: \"Can I afford my current plan?\"\n"
    "- **Plans**: \"Compare the three plans\"\n"
    "- **What-if**: \"What if my income drops 20%?\" or \"What if I get a 10,000 THB "
    "repair bill?\"\n"
    "- **Position**: \"Where do I stand?\" (available cash, deficit, reserve, buffer)\n"
    "- **Debts**: \"Compare Avalanche and Snowball\"\n"
    "- **Goal check**: \"Can I reach my goals on time?\"\n"
    "- **Risk**: \"How risky is my plan?\"\n"
    "- **Propose**: \"Propose the Balanced plan\" (you then approve it in the Sandbox view)\n"
    "- **Execute**: \"Execute the approved plan\"\n"
    "- **Rewards**: \"Show my streak and missions\"\n"
    "- **Audit**: \"Show the audit log\""
)

CANNOT_APPROVE = (
    "I can't approve a plan or move money on my own. I can prepare, explain, and propose "
    "plans; a plan only takes effect after you press Approve in the Sandbox view, and it "
    "is then applied in the sandbox, never to a real account."
)
