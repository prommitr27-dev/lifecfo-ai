# ShockProof Design

Owner: Member 3 (Risk and Evaluation).

> **Status: DRAFT for review by Member 3.** Drafted on 18 October 2026 for the
> submission package, from the code on `main` (commit `a0c4fa8`). It describes
> what the engine does today. Every threshold in section 2 is a **proposed
> assumption**: none is written to `config/risk_thresholds.yaml` until Member 3
> approves it.

ShockProof answers one question: *if something unexpected happens, does the
current plan still work?* It runs on a copy of the financial state, compares
the plan before and after the shock over the same horizon, and reports risk
indicators. Nothing is saved. Only a shock the user **confirms** changes the
stored state, and that hands over to the recovery engine
([RECOVERY_ENGINE.md](RECOVERY_ENGINE.md)).

Code: `lifecfo/agents/tools.py` (`simulate_income_change`,
`simulate_unexpected_expense`), `lifecfo/agents/views.py` (`expense_scenario`),
`lifecfo/agents/indicators.py` (`risk_data`), `lifecfo/services/sandbox.py`
(`confirm_income_change`, `confirm_expense`), and the seeded scenario
generator `lifecfo/evaluation/scenarios.py`.

## 1. Shock types

"Where it runs" says how each shock can be produced today: the **app** (agent
tool or sandbox action a user can trigger) or the **evaluation** generator
only (`scripts/run_evaluation.py`).

| # | Shock | What changes in the profile | Parameters | Example | Where it runs | Source or rationale |
|---|---|---|---|---|---|---|
| 1 | Income reduction | Every monthly income source is multiplied by (1 + p/100) from the profile date to the end of the horizon. One-off income is unchanged (rules AT13) | p from -100 to +100 % | -20 % (demo steps 4 and 5) | App: `simulate_income_change` (what-if), `confirm_income_change` (real). Evaluation: `INCOME_CUT` at -10, -20 or -30 % | Brief demo flow; the most common shock named in the brief |
| 2 | Delayed salary | Payday moves later by d days in every month | d (evaluation uses 10, capped at day 28) | Salary on day 11 instead of day 1 | Evaluation only: `SALARY_DELAY` | Timing risk: monthly totals balance but bills fall due before pay arrives |
| 3 | Emergency medical expense | One-off essential expense | amount (THB, or % of monthly income), due date | 10,000 THB on 12 Nov | App: `simulate_unexpected_expense`, `confirm_expense`. Evaluation: `EXPENSE` 5,000 to 20,000 THB | Brief demo flow (step 10) |
| 4 | Vehicle repair | Same mechanism as 3 | amount, due date | 10,000 THB car repair on 12 Nov (demo step 10) | As 3 | Brief demo flow |
| 5 | Job loss | Shock 1 with p = -100: recurring income stops for the whole horizon | p = -100 | Salary stops from today | App what-if only: the tool accepts -100 %. `confirm_income_change` refuses -100 %, so a job loss cannot be confirmed in the sandbox | Worst case for any household without a second income |
| 6 | Increased living costs | Every essential expense multiplied by (1 + p/100) | p (evaluation uses +10 %) | Rent and food +10 % | Evaluation only: `COST_RISE` | Inflation or a rent rise; the forecast itself assumes constant prices (assumption A6) |
| 7 | Unexpected debt obligation | A new monthly minimum payment | amount, months | 1,500 THB a month for 12 months | **Not implemented.** Can be approximated by adding a debt to the profile YAML | Listed in the brief; left for after the MVP |
| 8 | Multiple simultaneous shocks | Any combination | list of shocks | Income -20 % and a 10,000 THB repair | Evaluation: `COMBINED` (income cut then expense). App: shocks are confirmed one after another; the 15-step demo confirms -20 % income, then a 10,000 THB repair | Real emergencies cluster: a lost job often comes with other costs |

### Proposed multi-shock cases (for Member 3 to confirm)

These can be run with the existing tools by applying one shock after another
on the demo profile (`data/synthetic/profile_demo.yaml`).

| Case | Shocks | Already covered by |
|---|---|---|
| M1 | Income -20 %, then a 10,000 THB repair | `scripts/demo_15_steps.py` steps 4 to 12 |
| M2 | Income -10 to -30 %, plus a 5,000 to 20,000 THB expense in November | 6 seeded `COMBINED` scenarios in `docs/testing/EVALUATION_RESULTS.md` |
| M3 | Salary delay of 10 days and essentials +10 % | Not yet generated; needs a new shock kind in `scenarios.py` (Member 1) |

### Known gaps in shock modelling

- An income change has no end date: it lasts for the whole horizon. A
  temporary cut ("20 % for 3 months") cannot be expressed yet.
- Delayed salary and cost rises exist only in the evaluation generator, not as
  agent tools or sandbox actions.
- Job loss can be simulated but not confirmed (the sandbox accepts changes
  strictly above -100 %).
- No probability is attached to any shock. ShockProof tests "what if", it does
  not forecast how likely a shock is.

## 2. Risk indicators and thresholds

The indicators are computed by `risk_data` and shown by the
`assess_financial_risk` tool. Ratings come only from
`config/risk_thresholds.yaml`. While a value there is `null`, the indicator is
shown with the rating `NO_THRESHOLD_SET`; the system never invents a rating.
All values below are **null today**.

| Indicator | Definition in code | Proposed: high risk | Proposed: medium risk | Proposed: low risk | Rationale (assumption) |
|---|---|---|---|---|---|
| Days until projected cash shortfall | Days from the profile date to the first day unallocated cash is negative under the current plan | below 7 days | below 30 days | 30 days or more, or no shortfall in the horizon | 30 days is one monthly pay cycle: a shortfall inside it cannot wait for a replan at the next payday. Under 7 days leaves no time to act before the bill is due |
| Lowest projected unallocated cash | Minimum unallocated balance in the horizon | (information only) | | | Shown in THB with its date; it has no rating in code |
| Essential bill coverage | (accessible cash + income in the next 30 days) / (essentials + debt minimums due in the next 30 days) | below 1.0 | | 1.0 or more | Below 1.0 the bills of the next 30 days cannot be paid even using the reserve |
| Emergency reserve adequacy | Emergency envelope / one month of essentials and debt minimums | below 1 month (`LOW`) | 1 to 3 months (no label) | 3 months or more (`ADEQUATE`) | 3 months matches the engine's default reserve target (`reserve_months: 3`, rules D4); under one month a single month without income cannot be bridged |
| Goal completion risk | Goals that cannot reach their target by the deadline even if every spare baht went to them alone | any | | none | Counted directly; not configurable |
| Income volatility | Not measurable | | | | Profiles hold fixed scheduled income only; there is no income history |

The proposed values in `config/risk_thresholds.yaml` form would be:

```yaml
days_until_shortfall:
  high_risk_below: 7
  medium_risk_below: 30
emergency_reserve_months_of_essentials:
  adequate_at_or_above: 3
  low_below: 1
essential_bill_coverage_ratio:
  at_risk_below: 1.0
```

Note for Member 1: `tests/unit/test_indicators.py::test_indicators_are_shown_without_ratings_until_thresholds_are_set`
reads the real config file and expects `NO_THRESHOLD_SET`. When Member 3
approves values, that test has to switch to an explicit empty rules dict in
the same commit.

### How the proposed thresholds behave on the seeded scenarios

Computed on the 40 seeded scenarios used in
[EVALUATION_RESULTS.md](testing/EVALUATION_RESULTS.md) (master seed 2026),
after the shock, under each profile's own fixed savings plan. The commands are
in section 5, so the counts can be regenerated.

| Indicator | Rating under the proposed thresholds | Scenarios (of 40) |
|---|---|---|
| Days until shortfall | No shortfall in the horizon | 5 |
| | High risk (below 7 days) | 26 |
| | Medium risk (7 to 29 days) | 6 |
| | Within thresholds (30 days or more) | 3 |
| Essential bill coverage | At risk (below 1.0) | 0 (lowest value 1.11) |
| Emergency reserve | Low (below 1 month) | 34 |
| | Between 1 and 3 months | 6 |
| | Adequate (3 months or more) | 0 |

On the two demo profiles (no shock): `profile_demo` has no shortfall,
coverage 2.0 and a reserve of 0.33 months (`LOW`); `profile_debt_demo` has no
shortfall, coverage 4.75 and a reserve of 3.0 months (`ADEQUATE`).

What this shows, for Member 3 to weigh:

- **Coverage never triggers** on these scenarios. It counts the next 30 days
  of income, so a profile whose salary arrives late in the window looks
  covered even when a bill falls due before payday. The days-until-shortfall
  indicator catches those timing problems instead. A tighter coverage ratio
  (for example cash only, without income) is a design choice to make.
- **Most generated reserves are low**, because the generator draws the
  starting reserve from 0 to 30,000 THB regardless of essentials. That is a
  property of the synthetic data, not a finding about households.
- Days until shortfall is measured on the user's **current plan**, so a plan
  that saves too much is flagged even when essentials alone are safe. That is
  intended: the warning says the plan, not the household, needs to change.

## 3. Confirmed, hypothetical, and forecast

- **Hypothetical scenario** (the user is exploring). Every what-if runs on a
  copy of the frozen state and returns `"hypothetical": true` with the note
  "Simulated on a copy". Before and after use the same horizon (rules AT13).
  Nothing is saved, no approval is voided, no reward event is sent. Tested by
  `test_tools_never_change_the_state` and
  `test_decision_6_simulated_withdrawal_is_on_the_profile_date_and_not_recorded`.
- **Confirmed event** (it happened). Only the user can confirm one, in the
  Sandbox view or the mobile app (`confirm_expense`, `confirm_income_change`;
  the agent is refused with `ONLY_USER_CAN_CONFIRM`). The change is saved and
  audited with the state hash before and after. Because the state hash
  changes, every earlier proposal and approval no longer matches and cannot be
  executed. A confirmed expense also sends `SHOCK_CONFIRMED` to the rewards
  engine, which protects the streak and switches missions to recovery.
- **Forecast risk** (the system noticed it). Risk indicators and the
  position report flag problems in the stored state without any shock: a
  shortfall date, `RESERVE_WITHDRAWAL_NEEDED`, `BUFFER_SHORTFALL`,
  `DEADLINE_RISK`. The user is warned and offered plans; nothing changes until
  the user approves one.

## 4. Assumptions and limits

- Amounts are constant over the horizon: no inflation, no wage growth
  (assumption A6). Cost rises are modelled only as an explicit shock.
- Essentials are monthly lump sums on their due day (A7), which is
  conservative for liquidity.
- No income tax, social security, or interest on savings.
- Debt interest follows rules D5; an unknown rate keeps the minimum payment
  for the whole horizon.
- Shocks are deterministic and have no probabilities; there is no Monte Carlo.
- Thresholds are draft assumptions, not calibrated on Thai household data.
- All profiles and scenarios are synthetic.

## 5. Regenerating the numbers

```bash
uv run python scripts/run_evaluation.py --count 40 --seed 2026
uv run python - <<'EOF'
from lifecfo.agents.indicators import risk_data
from lifecfo.evaluation.scenarios import generate_scenarios
for s in generate_scenarios(40, 2026):
    values = [i["value"] for i in risk_data(s.after, 12, thresholds={})["indicators"]]
    print(s.seed, s.shock, "days", values[0], "coverage", values[2], "reserve_months", values[3])
EOF
```
