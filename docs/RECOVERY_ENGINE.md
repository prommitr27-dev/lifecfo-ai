# Recovery Engine

Owner: Member 2 (Financial Modeling). Implementation: Member 1.

> **Status: DRAFT for review by Member 2.** Drafted on 18 October 2026 for the
> submission package, from the code on `main` (commit `a0c4fa8`). Sections 2
> to 6 describe what the engine does today and cite the code and tests.
> Section 7 lists the decisions Member 2 still has to make. Nothing here
> changes `config/strategy_weights.yaml`.

The recovery engine answers: *an emergency has really happened, so how should
the plan change?* It is not a separate optimizer. It reuses the planning
engine of the Personal CFO page (`generate_plans`, the same linear program and
the same three strategies) starting from the state **after** a confirmed
shock, with the reserve withdrawal the user chose.

Code: `lifecfo/services/sandbox.py` (`confirm_expense`, `withdraw_reserve`,
`confirm_income_change`), `lifecfo/cashflow/position.py` (`assess_position`),
`lifecfo/optimization/optimizer.py` (`generate_plans`),
`lifecfo/agents/views.py` (`expense_scenario`, `flexible_goal_alternatives`),
`lifecfo/rewards/service.py` (recovery missions).

## 1. Flow

1. **What-if (optional).** `simulate_unexpected_expense` shows on a copy how
   much unallocated cash cannot cover, the reserve withdrawal that would be
   needed, the reserve and buffer gaps afterwards, and three recovery options.
   Nothing is saved.
2. **Confirm.** The user records the real expense (or income change) in the
   Sandbox view or the mobile app. Only the user can do this; it is audited
   (`SHOCK_CONFIRMED`) and changes the state hash, so earlier proposals and
   approvals can no longer be executed.
3. **Position first.** `assess_position` classifies the new state before any
   plan is made:

   | Planning status | Condition | What the user sees |
   |---|---|---|
   | `OK` | Essentials, debt minimums and the flexible budget fit | Three plans |
   | `FLEXIBLE_SPENDING_CONSTRAINT` | Fits only below the user's own flexible budget | A preference change is needed; the user decides |
   | `REQUIRES_RESERVE_DRAWDOWN` | Essentials can be paid only from the emergency reserve | No regular plan; a reserve withdrawal is a recovery decision |
   | `ESSENTIAL_SHORTFALL` | Essentials cannot be paid even with the whole reserve | No plan is offered; the shortfall and its date are reported |

4. **Withdraw (user decision).** The user moves money from the emergency
   reserve to unallocated cash (`withdraw_reserve`). Audited as
   `RESERVE_WITHDRAWN` with the reserve balance and its gap afterwards.
5. **Recovery plans.** `generate_plans` runs again on the new state and
   returns Safety First, Balanced and Goal First, each validated by
   `validate_plan`. Each is a proposal (`PROPOSED_NOT_APPROVED`).
6. **Approve and execute.** The user approves one plan; the agent can execute
   it only with that approval (security controls S1 to S3).
7. **Missions.** `SHOCK_CONFIRMED` protects the streak for up to 14 days and
   switches missions to "review your recovery options" and "approve a
   feasible recovery plan". Approving one pays `RECOVERY_MISSION_COMPLETED`
   (75 XP, once per shock). See [REWARDS_SYSTEM.md](REWARDS_SYSTEM.md).

## 2. Reserve usage rules (as implemented)

| # | Rule | Where | Test |
|---|---|---|---|
| RV1 | The planner never draws on the reserve by itself. If essentials need it, no plan is offered and the decision goes to the user | `generate_plans` returns `REQUIRES_RESERVE_DRAWDOWN` | `test_reserve_drawdown_is_left_to_recovery` |
| RV2 | Only the emergency envelope counts as reserve. Goal money is never counted as available and never withdrawn (rules D4) | `CashPools.eligible_reserve` | AT5, AT6 |
| RV3 | Only the user can withdraw, and never more than the reserve holds | `withdraw_reserve` refuses other actors (`ONLY_USER_CAN_WITHDRAW`) and amounts above the balance | `test_only_the_user_can_confirm_an_expense_or_withdraw`, `test_withdrawal_moves_cash_between_envelopes_and_is_logged` |
| RV4 | A simulated withdrawal is taken on the profile date, before the expense, and is never recorded (economics decision 6) | `expense_scenario` | `test_decision_6_simulated_withdrawal_is_on_the_profile_date_and_not_recorded` |
| RV5 | If the reserve is not enough, the rest is reported as still uncovered and no plan is invented | `still_uncovered_after_reserve`; `ESSENTIAL_SHORTFALL` | `test_no_plan_is_invented_when_essentials_cannot_be_paid` |

### How much to withdraw

Two figures are shown today, and they answer slightly different questions:

- **What-if view** (`expense_scenario`): the most unallocated cash falls below
  zero between the due date and the next income, under the original budget
  with no savings. The suggested withdrawal is that gap, capped at the reserve.
- **After confirmation** (`assess_position`, used by the demo script and the
  evaluation runner): the essentials-only gap over the horizon
  (`RESERVE_WITHDRAWAL_NEEDED`) and the gap with flexible spending at the
  user's minimum (`adjusted_deficit`). The demo and the evaluation withdraw
  `min(reserve, max(essentials gap, adjusted deficit))`, which pays essentials
  and keeps flexible spending at the user's own minimum.

In the 15-step demo (income already cut to 24,000 THB, 10,000 THB repair due
12 November) both give 6,000 THB: essentials alone need 4,000 THB, keeping
flexible spending at its minimum needs 6,000 THB, and the user withdraws
6,000 THB, leaving the reserve at 0 with a gap of 54,000 THB
([demo_15_steps.md](competition/evidence/demo_15_steps.md), steps 10 and 11).

## 3. Order of cuts (as implemented)

When money is short, the engine gives things up in this order. Items higher in
the list are protected longer.

1. **Essentials and debt minimums are never reduced.** They are constants in
   the optimizer, not variables (rules D2).
2. **New savings stop first.** Reserve and goal contributions are allocations,
   not obligations; the position report is computed with none.
3. **Flexible spending down to the user's minimum**, only if the user allowed
   a reduction, and only as a proposal that needs approval (rules D1). Every
   plan with a cut also shows the "keep your flexible budget" option and its
   effect on goals and the reserve (economics decision 1).
4. **The emergency reserve**, by the user's own withdrawal (section 2).
5. **Goal envelopes are never used.** Targets, deadlines and priorities are
   never changed by the system. A flexible goal that now misses its deadline
   gets a later-date proposal (`LATER_DATE_FOR_FLEXIBLE_GOAL`); a fixed one
   gets a deadline-risk disclosure (rules D7, D8).

When money comes back, it is used in this order (economics decision 2):
the cash buffer, then the reserve and goals on each strategy's schedule, then
extra debt repayment from what is genuinely left.

## 4. Reserve rebuild

There is no separate rebuild schedule. After a withdrawal the reserve gap is
larger, and each strategy closes it on its own ramp from
`config/strategy_weights.yaml` (draft assumptions owned by Member 2):

| Strategy | `reserve_ramp_months` | Behaviour |
|---|---|---|
| Safety First | 1 | Refills the reserve as fast as cash allows, cutting flexible spending to its floor if allowed |
| Balanced | 6 | Refills the reserve and funds goals side by side |
| Goal First | 12 | Funds goals by priority; the reserve refills last |

Example on `data/synthetic/profile_demo.yaml` (salary 30,000 THB on day 1,
reserve 6,000 THB, target 54,000 THB) with a 10,000 THB expense due
12 November 2026. Computed by `expense_scenario` over 12 months; the
first three figures are checked in `test_at12_expense_recalculates_liquidity_reserve_and_buffer`.

- Not covered by unallocated cash: 1,000 THB (the 1,000 THB utilities bill on
  15 November). Reserve withdrawal: 1,000 THB. Reserve afterwards 5,000 THB,
  gap 49,000 THB.

| Strategy | Reserve target reached: no shock | after the expense | Vacation (flexible, due 2027-06-30): no shock | after the expense |
|---|---|---|---|---|
| Safety First | 2027-03 | 2027-04 | 2027-08 | 2027-09 |
| Balanced | 2027-04 | 2027-04 | 2027-08 | 2027-09 |
| Goal First | 2027-09 | 2027-10 | 2027-06 | 2027-06 |

The laptop goal (priority 1, fixed deadline 2027-08-31) stays on time in all
three. In Safety First and Balanced the vacation is 15,000 THB short at its
deadline, so a later date (2027-09) is offered for the user to approve.

## 5. Expense before or after payday

The same 10,000 THB expense on the demo profile, by due date (salary arrives on
day 1):

| Due date | Not covered by unallocated cash | Reserve withdrawal | Period checked |
|---|---|---|---|
| 3 Nov 2026 | 1,000 THB | 1,000 THB | 3 to 30 Nov |
| 12 Nov 2026 | 1,000 THB | 1,000 THB | 12 to 30 Nov |
| 30 Nov 2026 | 1,000 THB | 1,000 THB | 30 Nov |
| 1 Dec 2026 (payday) | 0 | 0 | 1 to 31 Dec |

An expense due on payday is paid from that day's salary (income is applied
first within a day, assumption A2), so the reserve is untouched. Any date
before payday needs the same 1,000 THB, because November's surplus of
9,000 THB covers all but 1,000 THB of it. The recovery plans for 12 November
and 1 December are the same, since the withdrawal restores exactly the cash
the expense took.

## 6. Evaluation

On the 40 seeded scenarios in
[EVALUATION_RESULTS.md](testing/EVALUATION_RESULTS.md), LifeCFO offered a
plan directly in 22, a recovery plan after a reserve withdrawal in 8, and
disclosed that no plan exists in 10 (essentials cannot be paid even with the
whole reserve). In the 30 scenarios where a plan exists, LifeCFO had no
missed essential payment and no negative unallocated cash; the other methods
had 0 to 9 missed payments and 14 to 25 scenarios with negative cash. The
lower reserve at month 12 (89.7 % of target against 114.9 % for the fixed
budget) comes from the reserve withdrawals in the recovery scenarios and from
goal allocations under the draft Balanced weights.

## 7. Decisions for Member 2

1. **Withdrawal size.** Should the suggested withdrawal cover essentials only
   (4,000 THB in the demo) or essentials plus the flexible minimum
   (6,000 THB)? The code shows both; the demo uses the larger.
2. **Floor on the reserve.** The demo leaves the reserve at 0. Should a
   recovery keep a minimum (for example half a month of essentials) and cut
   flexible spending further instead?
3. **Rebuild speed.** Is reusing each strategy's normal ramp acceptable, or
   should a recovery plan use a faster ramp until the withdrawn amount is
   back?
4. **Cuts before withdrawal.** Should a flexible cut the user allowed always
   be proposed before a reserve withdrawal, or only offered side by side?
5. **Separate objective.** The MVP plan describes a recovery objective that
   differs from normal planning. Today the same three strategies are reused.
   Is that enough for the submission?

## 8. Limits

- Only one-off expenses and recurring income changes can be confirmed. A
  delayed salary, a cost rise, or a new debt cannot be confirmed in the
  sandbox (see [SHOCKPROOF_DESIGN.md](SHOCKPROOF_DESIGN.md), section 1).
- An income change lasts for the whole horizon; there is no end date.
- No borrowing is modelled as a way out of a shortfall.
- Weights and ramps are draft assumptions, not calibrated values.
- Synthetic data only.
