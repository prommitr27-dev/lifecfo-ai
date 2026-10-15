# Financial Model

Owner: Member 2 (Financial Modeling). Implementation: Member 1.

> Financial Rules v0.2 (D1 to D9) supersede the assumptions below where they
> differ. How each rule is implemented, and what is still open, is in
> [RULES_V0.2_STATUS.md](RULES_V0.2_STATUS.md).
This document states every modelling assumption so results can be checked by hand.

## 1. Cash flow forecast (implemented, M1)

Code: `lifecfo/cashflow/forecast.py`. Tests: `tests/unit/test_cashflow.py`.

### Ledger

One sandbox cash account is divided into envelopes: `UNALLOCATED`, `EMERGENCY`,
and one per goal. Income lands in `UNALLOCATED`. Expenses and debt minimums are
paid from `UNALLOCATED`. Savings are transfers from `UNALLOCATED` into another
envelope and do not change total cash.

### Assumptions

| # | Assumption | Consequence |
|---|---|---|
| A1 | Balances in a state are opening balances for `as_of`. | Items scheduled on `as_of` are still to come. |
| A2 | Within a day, events apply in this order: income, essential expenses, debt minimums, flexible expenses, savings transfers. | Income and a bill on the same day do not cause a shortfall. |
| A3 | A monthly item on day 29 to 31 falls on the last day of shorter months. | Day 31 becomes 28 February. |
| A4 | The forecast never draws on the emergency or goal envelopes by itself. | Negative `UNALLOCATED` is reported as a shortfall. Whether essentials can still be paid is checked against accessible cash (unallocated plus the emergency reserve); goal money is never counted. |
| A5 | Debt interest follows rules D5 (`lifecfo/debt/schedule.py`): contract-based, estimated, or unavailable. | A debt with an unknown rate keeps its minimum payment for the whole horizon. |
| A6 | Recurring amounts are constant; there is no inflation or income growth. | Shocks are modelled explicitly instead. |
| A7 | Essentials are modelled as monthly lump sums on a due day. | Daily spending such as food is front-loaded, which is conservative for liquidity. |

### Feasibility classification

Code: `lifecfo/cashflow/feasibility.py`.

Two forecasts are compared: the plan as written, and an essentials-only view
(flexible expenses at their floor, no savings transfers).

| Status | Condition | Meaning |
|---|---|---|
| `FEASIBLE` | `UNALLOCATED` never negative under the plan | The plan is funded every day. |
| `PLAN_INFEASIBLE` | The plan goes negative, but total cash in the essentials-only view never does | Replanning can fix it. `needs_reserves` says whether existing envelopes must be used. |
| `ESSENTIAL_SHORTFALL` | Total cash goes negative even in the essentials-only view | No feasible plan exists. The shortfall and its date are reported; nothing is invented. |

A fourth status, `GOAL_AT_RISK` (plan is funded but a goal misses its deadline),
arrives with goal projections in M2.

### Worked example (demo profile)

`data/synthetic/profile_demo.yaml`: salary 30,000 on day 1; essentials 18,000;
leisure 3,000 (floor 1,000); transfers 9,000 on day 2; emergency fund 6,000.

| Scenario | Result | Why |
|---|---|---|
| Baseline | `FEASIBLE`, lowest unallocated 0 | 30,000 in, 30,000 out |
| Income cut 20% | `PLAN_INFEASIBLE`, first shortfall 5 Nov, 18,000 short over three months | Plan overspends 6,000 a month; essentials plus floor (19,000) still fit in 24,000 |
| Salary moved to day 25 | `ESSENTIAL_SHORTFALL` of 13,000 from 2 Nov | Monthly totals balance, but 19,000 falls due before the first payday with only 6,000 saved |
| Income 15,000 | `ESSENTIAL_SHORTFALL` of 6,000 from 5 Dec | 4,000 short a month; the emergency fund covers the first month only |

Hand-calculated daily balances for the baseline are in
`tests/scenarios/expected/profile_demo_daily.csv` and are checked on every test run.

## 2. Goal optimization (implemented, M2)

Code: `lifecfo/optimization/`. Tests: `tests/unit/test_optimization.py`.
Parameters: `config/strategy_weights.yaml` (draft assumptions, owned by Member 2).

One linear program serves all three strategies; only the parameters differ. It
is solved with `scipy.optimize.linprog` (HiGHS) over calendar months.

### Variables (per month t)

| Symbol | Meaning |
|---|---|
| `x[e,t]` | Contribution to envelope `e` (emergency reserve or a goal), swept on the last day of the month |
| `th[t]` | Share of the cuttable part of flexible spending that is kept, from 0 to 1 |
| `s[e,t]` | How far envelope `e` is behind its ramp at the end of month t |

### Hard constraints

1. **Liquidity.** Unallocated cash is non-negative on every day with a scheduled
   event and after each month-end sweep. Essentials and debt minimums are always
   paid in full, so they appear as constants, not variables. This is what stops
   a sweep from taking money needed for bills due before the next payday.
2. **Caps.** An envelope never receives more than it still needs (goal target,
   or `reserve_target` for the emergency envelope).
3. **Flexible floor.** Flexible spending never drops below `min_amount`.

If cash runs out even with no savings and flexible spending at its floor, no
plan is produced. The result is `ESSENTIAL_SHORTFALL`, or
`REQUIRES_RESERVE_DRAWDOWN` when existing envelopes could cover the gap; using
savings is a recovery decision and is handled by the recovery engine (M5).

### Ramps

Each envelope has a ramp: the amount it should hold by the end of each month.
A goal's ramp rises linearly to its target at the last sweep on or before its
deadline (or the end of the horizon if it has no deadline). The reserve's ramp
rises to `reserve_target` over `reserve_ramp_months`.

### Objective (minimised)

```
sum over e,t of  weight[e] * s[e,t]                      being behind a ramp
+ sum over t of  flexible_cut_weight * cut[t]            cutting lifestyle spending
- sum over e,t of  scale * bonus[e] * (T - t) * x[e,t]   where surplus goes first
```

`weight[e]` is `reserve_weight` for the reserve and
`goal_weight * priority_decay^(priority - 1)` for a goal. The last term is tiny
by design: it only decides where money goes once every ramp is met.

| Strategy | Reserve ramp | What it does on the demo profile |
|---|---|---|
| Safety First | 1 month | Cuts leisure to its floor and fills the reserve first (reached Dec 2026), then goals |
| Balanced | 6 months | Keeps leisure, builds reserve and goals side by side (reserve reached Apr 2027) |
| Goal First | 12 months | Puts surplus into goals by priority (both done Apr 2027), reserve last (May 2027) |

### Rounding and validation

Cumulative contributions are rounded down to whole baht, which can only leave
more cash on hand than the LP solution. Flexible amounts are rounded down too.
Every plan is then passed to `validate_plan`, which checks the state hash, caps,
flexible bounds, and the daily forecast. A plan that fails is never returned.
The same validator will check any allocation proposed through the agent.

### Identical plans

When two strategies return the same allocations (for example a single goal and
no flexible spending), the result carries an `IdenticalPlans` record with the
facts that explain it: months in which all free cash is allocated, months with
flexible spending at its floor, and envelopes that reach their target. Nothing
is altered to make plans look different.

### Known limitations

- Linear objective: allocations move in priority order rather than being
  smoothed, and near-ties are decided by the solver deterministically.
- Savings are swept once, at month end. Earlier transfers are not modelled.
- Goals without a deadline are ramped to the end of the planning horizon.
- Weights are draft assumptions and have not been calibrated against user preferences.

## 3. Open questions for Member 2

1. Should the MVP accrue interest on debt (A5)? If yes, monthly on the balance at `apr / 12`?
2. Are the draft weights in `config/strategy_weights.yaml` reasonable, and how should they be justified?
3. How should an emergency reserve target be expressed: a fixed amount, or months of essential expenses?
4. Is front-loading daily essentials (A7) acceptable, or should food and transport be spread weekly?
