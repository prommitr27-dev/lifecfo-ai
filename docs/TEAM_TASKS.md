# Team Tasks and Interfaces

## Roles

| Member | Role | Owns |
|---|---|---|
| Member 1 | AI and Software Engineer | Architecture, all Python code, agent, database, sandbox, tests, CI |
| Member 2 | Financial Modeling | Optimization method, allocation rules, assumptions, hand-calculated expected values, model validation |
| Member 3 | Risk and Evaluation | Shock definitions, risk thresholds, scenario datasets, metrics, baselines, security test cases, competitor analysis |

## How to contribute without writing Python

All of these files can be edited in the GitHub web editor. CI runs the tests on
every push, so a wrong number shows up as a failed check.

| File | Owner | Purpose |
|---|---|---|
| `tests/scenarios/expected/<profile>_daily.csv` | Member 2 | Hand-calculated closing balances. Columns: `date, unallocated_thb, total_cash_thb`. List only the dates you want checked. The file name must match a profile in `data/synthetic/`. |
| `data/synthetic/<profile>.yaml` | Member 3 | A synthetic profile. Copy `profile_demo.yaml`; write money in baht with the `_thb` suffix. |
| `data/scenarios/*.yaml` | Member 3 | A profile plus one or more shocks and the expected classification (format defined in M4). |
| `config/strategy_weights.yaml` | Member 2 | Objective weights for the three strategies. |
| `config/risk_thresholds.yaml` | Member 3 | Thresholds for risk indicators. |
| `config/reward_rules.yaml` | Member 1 drafts, Members 2 and 3 review | XP values, levels, grace periods. |
| `docs/**/*.md` | See below | Written deliverables. |

## Deliverables by milestone

| Milestone | Member 1 | Member 2 | Member 3 |
|---|---|---|---|
| M1 | Models, ledger, forecast, feasibility (done) | Verify `profile_demo_daily.csv`; add four more hand-calculated cases | First 5 to 10 synthetic profiles |
| M2 | LP, validator, Goals and Personal CFO pages | Own `FINANCIAL_MODEL.md`: objective, weights, priority rules, opportunity cost | Define the three baselines |
| M3 | Services, idempotency, audit chain, tool tiers | Check post-execution balances on sample cases | First security test cases: unapproved, duplicate, invalid values |
| M4 | Simulation on snapshots, indicators, ShockProof page | Review indicator formulas | Own `SHOCKPROOF_DESIGN.md`: eight shock types, thresholds, multi-shock cases |
| M5 | Recovery options, goal delays, reserve rebuild | Own `RECOVERY_ENGINE.md`: reserve usage rules, order of cuts | Emergency scenarios with expected outcomes |
| M6 | Event bus, rules engine, streak state machine | Check that no rule rewards risky behaviour | Streak test cases (missed day, grace, time zone); gamification literature |
| M7 | Dashboard, demo script, log export | Check all numbers in the demo flow | Demo scenario and narration |
| M8 | Tool registry, agents, explanation checker, Chat page | Check trade-off explanations for correctness | Prompt-injection and conflicting-instruction test set; agent metrics |
| M9 | Scenario runner, CI report | Economic interpretation of results | Own `TESTING_PLAN.md`, `COMPETITOR_ANALYSIS.md`, security self-assessment, experiment log |

## Working agreement

- `main` must always pass CI. Larger changes go through a pull request.
- Use only synthetic data. Never commit `.env`, API keys, or real financial data.
- Every modelling assumption is written in a document with its owner. Draft
  values are labelled as assumptions, not findings.
- Results are reproduced from seeds and committed scenario files. No result is
  reported that the repository cannot regenerate.
