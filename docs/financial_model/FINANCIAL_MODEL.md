# Financial Model

Owner: Member 2 (Financial Modeling). Implementation: Member 1.
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
| A4 | The forecast never draws on the emergency or goal envelopes by itself. | Negative `UNALLOCATED` is reported as a shortfall; funding it is a planning decision. |
| A5 | Debt minimum payments stop when the balance is cleared. Interest is not accrued. | Understates long-run debt cost. **Open question for Member 2.** |
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

## 2. Goal optimization (draft for review, M2)

- **Variables**: monthly contribution to each envelope `x[g,t]`, flexible
  spending `f[t]`, and a shortfall variable per goal.
- **Hard constraints**: essentials and debt minimums paid in full; cash never
  negative; contributions never exceed the remaining target; flexible spending
  not below its floor.
- **Priority tiers**: (0) essentials, and if these cannot be met the solver stops
  and reports the shortfall; (1) emergency reserve floor; (2) goals by priority
  and deadline.
- **Three strategies** are the same LP with different objective weights from
  `config/strategy_weights.yaml`. If two strategies return the same allocation,
  the system reports the binding constraints instead of manufacturing a difference.
- **After solving**: round to whole baht, re-check hard constraints, then run the
  daily forecast. Only a plan that passes all three is offered to the user.
- **Baselines for evaluation**: fixed budget, simple priority waterfall, no replanning.

## 3. Open questions for Member 2

1. Should the MVP accrue interest on debt (A5)? If yes, monthly on the balance at `apr / 12`?
2. Are the draft weights in `config/strategy_weights.yaml` reasonable, and how should they be justified?
3. How should an emergency reserve target be expressed: a fixed amount, or months of essential expenses?
4. Is front-loading daily essentials (A7) acceptable, or should food and transport be spread weekly?
