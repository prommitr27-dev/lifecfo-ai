# Financial Rules v0.2: Implementation Status

Status date: 15 October 2026. Every item marked Complete is implemented and
covered by automated tests that pass; manual scenarios are in
[docs/testing/MANUAL_SCENARIOS.md](../testing/MANUAL_SCENARIOS.md).

## 1. Work items

| ID | Work item | Status | Where | Tests |
|---|---|---|---|---|
| C1 | Cash-flow and deficit accounting | Complete | `lifecfo/cashflow/position.py`, `feasibility.py` | AT2, AT3, AT6 |
| C2 | Configurable reserve target | Complete | `FinancialState.emergency_target`, `reserve_months`, `reserve_target` | AT5 |
| C3 | Forecast consistency | Complete | `agents/tools.py` (`_compare`), `agents/views.py` | AT13 |
| C4 | Minimum cash buffer | Complete | `buffer_months` / `buffer_amount`; LP constraint in `optimizer.py` | AT4, AT6 |
| C5 | Debt interest and extra repayment | Complete for the two supported contract methods; others are estimated | `lifecfo/debt/schedule.py`, `views.debt_comparison` | AT7, AT8, AT15 |
| C6 | Goal flexibility and allocation | Complete for proposals; applying a changed date is done by the user | `Goal.flexible`, `views.flexible_goal_alternatives`, `reasons.py` | AT9, AT10, AT14 |
| C7 | Goals without deadlines | Complete | `optimizer.py` (no ramp, residual only) | AT11 |
| C8 | Explanation layer | Complete | `agents/views.py`, `agents/explain.py`, `optimization/reasons.py` | AT2, AT12, AT13, AT14 |
| C9 | Unexpected expenses and reserve withdrawals | Complete: simulation with withdrawal, gaps, and recovery proposals; the user can record a confirmed expense and a reserve withdrawal in the sandbox (both user-only and audited), then approve a recovery plan | `views.expense_scenario`, `SandboxService.confirm_expense`, `withdraw_reserve` | AT12, `test_rewards.py` |
| C10 | Approval and safe execution | Complete | `lifecfo/services/sandbox.py` | AT1, AT8, AT16 |

## 2. How each decision is implemented

**D1 Flexible spending.** `Expense.amount` is the original budget,
`min_amount` the user's minimum, and `reduction_allowed` the permission to
propose a cut. Without permission the budget is a constraint. Plans show the
original and proposed amounts with the reduction in THB and percent; a cut
takes effect only when the user approves and executes the plan.

**D2 Deficits.** `assess_position` runs before any plan and is shown first.
Shortfall kinds: `CASH_FLOW_SHORTFALL`, `RESERVE_WITHDRAWAL_NEEDED` (added:
essentials payable only from the reserve), `FLEXIBLE_SPENDING_CONSTRAINT`,
`BUFFER_SHORTFALL` (added, for D3), and per goal `SAVINGS_GOAL_SHORTFALL`,
`DEADLINE_RISK`, `FLEXIBLE_GOAL_DELAY`. No plan is offered when essentials
and debt minimums cannot be paid, or when the permitted flexible minimum still
leaves a deficit.

**D3 Buffer.** `buffer_months` x (E + D) or `buffer_amount`. Unconfigured
means no buffer is enforced and the one-month recommendation is shown for the
user to confirm. The buffer is checked against accessible cash (unallocated
plus reserve), the same cash the reserve uses, never added to it.

**D4 Reserve.** `reserve_months` x (E + D), default 3, or the user's custom
`reserve_target`. Eligible reserve is the emergency envelope only; goal
money is excluded.

**D5 Interest.** `CONTRACT_BASED` when the rate and one of the supported
methods (`DAILY_SIMPLE_ACT365`, `MONTHLY_ON_BALANCE`) are given;
`ESTIMATED` (balance x rate x days / 365, constant balance between payments,
disclosed) when only the rate is known; `UNAVAILABLE` when the rate is
unknown. An unknown rate is never treated as 0%.

**D6 Extra repayment.** Funded only from money left after essentials,
minimums, the flexible budget, the buffer, and the reserve and goal schedules.
Split by Avalanche, Snowball, or the user's `debt_order`, capped at what is
owed, honouring `extra_payment_allowed` and `prepayment_fee_rate`.

**D7, D8.** `Goal.flexible`. A flexible goal that misses its deadline gets a
later-date option computed with its deadline set aside; a non-flexible goal
gets a deadline-risk disclosure. Zero months are explained and never cancel a
goal. Targets, deadlines, and priorities are never changed by the system.

**D9.** Goals without a deadline have no ramp and take residual money only,
so their allocation does not depend on the horizon. Completion months are
labelled projections; contributions and the remaining amount are reported.

## 3. Known issues from section 7, rechecked

| Issue | Result |
|---|---|
| Available cash may not account for flexible spending | Fixed: one definition in `position.py` (AT6) |
| Original deficit not disclosed before reductions | Fixed: position shown first (AT2) |
| Reserve target from a fixed amount | Fixed: formula with custom override (AT5) |
| Cash buffer not enforced | Fixed (AT4) |
| Debt APR stored but unused | Fixed (AT7) |
| Extra repayment not separate from goals | Fixed: own allocation and payment events (AT8) |
| Goal flexibility not represented | Fixed (AT9) |
| No-deadline goals change with the horizon | Fixed (AT11) |
| Shock explanations mix horizons | Fixed (AT13) |
| Balanced rounding discrepancy | Kept, explained: contributions are rounded down to whole baht on their running total, so up to 1 THB per envelope can stay unallocated. It never overspends. |
| One-off income changed incorrectly in a shock | Fixed: income shocks apply to recurring income only (AT13) |
| Month-end sweeps and monthly lump-sum essentials | Kept as documented modelling assumptions |

## 4. Decisions that need economics input

1. **Buffer versus flexible spending.** When accessible cash is below the
   buffer, plans may propose flexible cuts (within the permitted range) to
   restore it, because the buffer is weighted far above lifestyle spending.
   Should restoring the buffer be allowed to propose flexible cuts, or should
   it only hold back goal contributions?
2. **Order of residual uses.** Extra debt repayment currently ranks below
   the reserve and goal schedules, and surplus is shared by the draft
   `surplus_*` weights. Is that the intended order under D6.2?
3. **Unknown-rate debts.** For cash planning the minimum payment is assumed
   to continue for the whole horizon, and extra repayment is capped at the
   unpaid principal. Is that acceptable?
4. **Prepayment fee.** It is charged on top of the extra amount. Some
   contracts deduct it instead. Which should be the default?
5. **Avalanche with unknown rates.** Debts with an unknown rate are ranked
   last. Confirm.
6. **Reserve withdrawal timing.** In the expense scenario the withdrawal is
   modelled on the profile date, before the expense. Confirm, or specify.

## 5. Not implemented yet

- An in-app flow for proposing and approving preference changes (a later
  goal date, a new buffer, a new flexible budget). The system proposes these;
  the user changes them in the profile.
- Contract interest methods other than the two listed in D5 notes.
