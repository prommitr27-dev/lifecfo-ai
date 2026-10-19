# Test Cases

The key test cases for reviewers, each with its input, the expected result, and
the automated test that checks it. Every case runs with synthetic data, a fixed
clock, no LLM, and no network.

Run all of them:

```bash
uv sync
uv run pytest              # 293 tests, about a minute
```

Run one case by its test name, for example:

```bash
uv run pytest -k test_twenty_percent_income_cut_makes_plan_infeasible_but_fixable
```

The baseline profile in most cases is `data/synthetic/profile_demo.yaml`:
salary 30,000 THB on day 1, essentials 18,000 THB, leisure 3,000 THB (minimum
2,000), emergency reserve 6,000 THB, goals New laptop 30,000 THB by 2027-08-31
and Vacation 15,000 THB by 2027-06-30 (flexible).

The full test inventory, evaluation method and known gaps are in
[TESTING_PLAN.md](TESTING_PLAN.md). Hand-checked numbers for six scenarios are in
[MANUAL_SCENARIOS.md](MANUAL_SCENARIOS.md), and the comparison against three
baselines over 40 seeded scenarios is in
[EVALUATION_RESULTS.md](EVALUATION_RESULTS.md).

## A. Cash flow and planning

| ID | Case | Input | Expected result | Test |
|---|---|---|---|---|
| TC-01 | Baseline plan is funded | Baseline profile, 12-month daily forecast | Every day funded; unallocated cash never below 0 | `tests/unit/test_cashflow.py::test_baseline_plan_is_exactly_funded` |
| TC-02 | Money is conserved | Baseline forecast | Total cash changes only by income and spending | `tests/unit/test_cashflow.py::test_total_cash_changes_only_by_income_and_spending` |
| TC-03 | Timing gap is caught | Bills due before payday, monthly totals balance | Reported as a cash-flow gap, not feasible | `tests/unit/test_cashflow.py::test_timing_gap_is_detected_even_when_monthly_totals_balance` |
| TC-04 | Hand-calculated balances | `tests/scenarios/expected/*_daily.csv` from the finance lead | Engine closing balances match every listed date | `tests/scenarios/test_expected_values.py` |
| TC-05 | Three valid, different plans | Baseline profile | Safety First, Balanced, Goal First all pass `validate_plan` and differ | `tests/unit/test_optimization.py::test_three_strategies_are_valid_and_genuinely_different` |
| TC-06 | No overfunding | Any generated plan | Allocations never exceed free cash or goal targets | `tests/unit/test_optimization.py::test_plan_never_overfunds_and_conserves_cash` |
| TC-07 | Random profiles | Seeded random profiles | Only valid plans, or no plan with the reason | `tests/unit/test_optimization.py::test_random_profiles_only_ever_get_valid_plans` |
| TC-08 | Same input, same plan | Run the optimiser twice | Identical output | `tests/unit/test_optimization.py::test_optimizer_is_deterministic` |
| TC-09 | Financial rules v0.2 | Acceptance tests AT1 to AT16 (deficits, buffer, reserve, debt, goal flexibility) | All pass | `tests/scenarios/test_acceptance_rules_v02.py` |

## B. Shocks and recovery

| ID | Case | Input | Expected result | Test |
|---|---|---|---|---|
| TC-10 | Income drops 20% | Baseline, income 30,000 to 24,000 THB | Plan becomes infeasible but fixable; essentials still payable | `tests/unit/test_cashflow.py::test_twenty_percent_income_cut_makes_plan_infeasible_but_fixable` |
| TC-11 | Replan after the cut | Income cut | Three new valid plans; goals at risk are flagged | `tests/unit/test_optimization.py::test_income_cut_yields_valid_plans_and_flags_goals_at_risk` |
| TC-12 | Income below essentials | Income less than essentials | Essential shortfall reported; no plan is invented | `tests/unit/test_optimization.py::test_no_plan_is_invented_when_essentials_cannot_be_paid` |
| TC-13 | Emergency expense | Confirmed 10,000 THB repair bill | Liquidity, reserve and buffer recalculated; explanation numbers come from the calculation | `tests/scenarios/test_acceptance_rules_v02.py::test_at12_expense_recalculates_liquidity_reserve_and_buffer` |
| TC-14 | Expense voids old proposals | Confirm an expense with a proposal pending | Earlier proposals can no longer be executed | `tests/unit/test_rewards.py::test_a_confirmed_expense_voids_earlier_proposals` |
| TC-15 | Reserve withdrawal | Withdraw 6,000 THB from the emergency reserve | Cash moves between envelopes and is logged | `tests/unit/test_rewards.py::test_withdrawal_moves_cash_between_envelopes_and_is_logged` |
| TC-16 | Goals and deadlines kept | Any shock | Targets and deadlines are never changed by a plan; a flexible goal may be offered a later date | `tests/scenarios/test_acceptance_rules_v02.py::test_at9_targets_and_deadlines_are_never_changed` |
| TC-17 | Streak survives a shock | Confirmed shock during a streak | Missions switch to recovery and the streak is protected | `tests/unit/test_rewards.py::test_shock_switches_to_recovery_missions_and_protects_the_streak` |

## C. AI agent

| ID | Case | Input | Expected result | Test |
|---|---|---|---|---|
| TC-18 | Routing | Questions on cash, goals, plans, what-ifs | Each reaches the right tool | `tests/unit/test_agent.py::test_offline_agent_routes_questions_to_tools` |
| TC-19 | What-ifs change nothing | Every tool on a stored state | Stored state is unchanged | `tests/unit/test_agent.py::test_tools_never_change_the_state` |
| TC-20 | No invented figures | Model answer with a number no tool produced | Answer replaced by the verified explanation | `tests/unit/test_agent.py::test_invented_figures_are_replaced_by_the_verified_explanation` |
| TC-21 | Provider outage | Every LLM provider error type | Falls back to the offline engine | `tests/unit/test_agent.py::test_every_provider_failure_falls_back_to_offline_mode` |
| TC-22 | Thai and English | Thai question | Answer requested in Thai; English stays English | `tests/unit/test_agent.py::test_llm_agent_sends_recent_history_and_asks_for_thai` |

## D. Security and permissions

| ID | Case | Input | Expected result | Test |
|---|---|---|---|---|
| TC-23 | Tier limit | Agent calls a tool above its tier | Refused before the tool runs | `tests/unit/test_agent.py::test_call_above_the_agents_tier_is_refused` |
| TC-24 | Agent cannot approve | "Approve the plan" to the agent | Refused; only the user can approve | `tests/unit/test_sandbox.py::test_agent_cannot_approve`, `tests/integration/test_api.py::test_chat_agent_cannot_approve` |
| TC-25 | No execution without approval | Execute with no approval | Refused and logged | `tests/unit/test_sandbox.py::test_execution_without_any_approval_is_refused` |
| TC-26 | Plan swapped after approval | Tamper with the stored plan | Not executed | `tests/unit/test_sandbox.py::test_tampered_stored_plan_is_not_executed` |
| TC-27 | Double execution | Execute the same approval twice | Second call changes nothing | `tests/unit/test_sandbox.py::test_duplicate_execution_changes_nothing` |
| TC-28 | Audit log tampering | Edit or delete an audit entry | Hash chain check fails | `tests/unit/test_sandbox.py::test_audit_chain_detects_tampering` |
| TC-29 | Prompt injection | Fake system message, claimed approval, "developer mode" | No higher tier reached; no transaction | `tests/unit/test_agent.py::test_prompt_injection_cannot_reach_a_higher_tier` and 10 prompts in `scripts/run_evaluation.py` |
| TC-30 | API client sends its own plan | POST a plan from the mobile client | Refused; the plan is regenerated from stored state | `tests/integration/test_api.py::test_client_cannot_send_its_own_plan_or_approve_without_a_proposal` |
| TC-31 | API token | Request without the bearer token when one is set | 401 | `tests/integration/test_api.py::test_token_is_required_when_configured` |
| TC-32 | Visitors are isolated | Two browser sessions on the public demo | Each has its own sandbox; nothing written to disk | `tests/integration/test_app_smoke.py::test_public_mode_gives_each_visitor_a_private_sandbox` |

## E. App and end to end

| ID | Case | Input | Expected result | Test |
|---|---|---|---|---|
| TC-33 | Home view | Open the app | Money left to spend, bills due, goal progress | `tests/integration/test_app_smoke.py::test_home_shows_money_bills_and_goals` |
| TC-34 | Approve and execute in the app | Request approval, Approve, Execute | Plan active; audit log shows each step | `tests/integration/test_app_sandbox.py::test_user_approves_and_executes_a_plan_through_the_app` |
| TC-35 | What-if slider | Move the income slider | Page and data unchanged until Save | `tests/integration/test_app_sandbox.py::test_moving_the_what_if_slider_leaves_the_page_alone` |
| TC-36 | Save a what-if | Save -20% as real income | Income change confirmed and audited | `tests/integration/test_app_sandbox.py::test_saving_the_what_if_records_a_real_income_change` |
| TC-37 | The brief's 15-step demo | `scripts/demo_15_steps.py` | 15 of 15 steps pass | `tests/integration/test_demo_15_steps.py::test_every_demo_step_passes` |
