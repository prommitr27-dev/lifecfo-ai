# System Architecture

Status: approved 2026-10-13. Sections marked *(planned)* describe milestones
that are not implemented yet; see the roadmap for the current state.

## 1. Principles

1. **Engines are pure functions.** They take an immutable `FinancialState`
   snapshot and return results. They never touch the database, so a simulation
   has no code path that could overwrite real data.
2. **Services are the only write path.** Both the UI and the agent change state
   through service functions that validate, require approval, and write an
   audit record. *(planned, M3)*
3. **The agent sees tools, not tables.** The LLM calls registered tools with
   typed inputs and outputs. It never computes money and has no tool that can
   approve a plan. *(planned, M8)*
4. **One shared state.** Personal CFO, ShockProof, Recovery, and Rewards all
   read the same verified state; none keeps a private copy of balances.

## 2. Layers

```
+--------------------------------------------------------------+
| app/  Streamlit pages         (the Approve button lives here) |
+---------------+------------------------------+---------------+
                |                              |
                |                 +------------v-------------+
                |                 | lifecfo/agents/          |
                |                 | Agent + tool registry    |
                |                 | (MockAgent | ClaudeAgent)|
                |                 +------------+-------------+
                |                              | registered tools only
+---------------v------------------------------v---------------+
| lifecfo/services/      the only way to change state          |
| Planning, Shock, Recovery, Approval, Sandbox, Rewards        |
+-------+-----------------------+----------------------+-------+
        | pure functions        | events               | read/write
+-------v--------------+ +------v--------+ +-----------v-------+
| Deterministic engines| | Event bus     | | lifecfo/database/ |
| cashflow/            | | -> rewards/   | | SQLite repos      |
| optimization/        | | -> audit      | | audit: append-only|
| shockproof/ recovery/| +---------------+ +-------------------+
+----------------------+
```

## 3. Main data flow

```
Profile + Goals
  -> cashflow.forecast (daily)
  -> optimization.generate_plans (3 strategies, monthly)
  -> validator (hard constraints + daily simulation)
  -> [user selects and approves] -> sandbox.execute -> audit + events
  -> shockproof.simulate (on a copy) -> risk indicators
       |- hypothetical: display only
       `- confirmed: record shock -> recovery.generate_options
            -> validator -> [approve] -> sandbox.execute -> audit + events
  -> rewards (subscribes to events) -> XP / badges / streak / missions
```

## 4. Module responsibilities

| Package | Responsibility | Milestone |
|---|---|---|
| `lifecfo/domain` | Pydantic models, integer money, injectable clock, YAML loader | M1 (done) |
| `lifecfo/cashflow` | Daily forecast over the envelope ledger, feasibility classification | M1 (done) |
| `lifecfo/optimization` | LP formulation, three strategies, plan validator | M2 (done) |
| `lifecfo/services`, `lifecfo/sandbox`, `lifecfo/database` | Approval, idempotent execution, audit log, persistence | M3 |
| `lifecfo/shockproof` | Shock definitions, simulation, risk indicators | M4 |
| `lifecfo/recovery` | Recovery options, goal delays, reserve rebuild schedule | M5 |
| `lifecfo/events`, `lifecfo/rewards` | Event bus, XP rules, streak state machine, missions | M6 |
| `lifecfo/agents`, `lifecfo/security` | Tool registry with permission tiers, agents, explanation checker | M8 |
| `lifecfo/evaluation` | Baselines and scenario runner | M9 |

Changes from the structure proposed in the brief: `financial/` became
`cashflow/` (it names what the package does); `domain/`, `services/`,
`events/`, and `evaluation/` were added; a top-level `config/` holds the
assumptions that the modelling and risk leads tune without editing code.

## 5. Financial data model

Money is integer satang. Timestamps are UTC, with the user's time zone
(default `Asia/Bangkok`) used for calendar dates.

The **envelope model** is the core of the ledger: there is one sandbox cash
account, divided into virtual envelopes (`UNALLOCATED`, `EMERGENCY`, one per
goal). The envelopes always sum to the account balance. Savings are transfers
from `UNALLOCATED` into another envelope, so the emergency fund balance and
this month's contribution can never be counted twice.

| Entity | Key fields | Notes |
|---|---|---|
| `FinancialState` | as_of, timezone, reserve_target, envelopes, incomes, expenses, debts, goals, transfers | Immutable snapshot; opening balances for `as_of` |
| `IncomeSource` | amount, frequency, day_of_month / on_date, active window | |
| `Expense` | category (`ESSENTIAL` / `FLEXIBLE`), amount, min_amount | `min_amount` is the floor a flexible expense can be cut to |
| `Debt` | balance, minimum_payment, day_of_month, apr | Minimum payment is a hard obligation; extra payoff is a goal |
| `Envelope` | kind, balance, goal_id | Saved amount of a goal is read from its envelope |
| `Goal` | target, priority, deadline | |
| `Plan`, `PlanAllocation` *(M2)* | strategy, kind, status, state_hash | `DRAFT -> PROPOSED -> APPROVED -> EXECUTED / REJECTED / SUPERSEDED` |
| `ShockEvent` *(M4)* | type, params, effective_date, status | `HYPOTHETICAL` shocks are never applied to stored state |
| `Approval` *(M3)* | plan_id, plan_hash, state_hash, decision | Invalid if the plan or the state changed; single use |
| `SandboxTransaction` *(M3)* | idempotency_key (unique), from, to, amount | Blocks duplicate execution at the database level |
| `AuditLog` *(M3)* | ts, actor, action, payload, prev_hash | Append-only, hash-chained |
| `RewardEvent`, `Streak`, `Mission`, `Badge` *(M6)* | event_id (unique), xp, status | Streak status: `ACTIVE / PROTECTED / PAUSED / BROKEN` |

## 6. Agent tools and permission tiers *(planned)*

Every tool has Pydantic input and output schemas and is written to the audit log.

| Tier | Tools | Effect |
|---|---|---|
| 0 Read | `get_financial_profile`, `get_financial_goals`, `get_cash_flow_forecast`, `get_reward_status`, `get_audit_history` | Read-only |
| 1 Compute | `calculate_goal_feasibility`, `optimize_financial_plan`, `simulate_financial_shock`, `assess_financial_risk`, `generate_recovery_options`, `explain_financial_tradeoffs`, `suggest_financial_mission` | No state change; results stored as `DRAFT` |
| 2 Propose | `propose_budget_changes`, `request_plan_approval` | Creates a `PROPOSED` item for the UI; cannot mark it approved |
| 3 Execute | `execute_approved_sandbox_plan(approval_id)` | Runs only with an approval the user gave in the UI whose hashes match the current plan and state |

`explain_financial_tradeoffs` returns structured facts (which goal slips by how
many periods, which constraint binds). The LLM only words them.

## 7. Safety boundaries

1. The LLM does not calculate money; any allocation it suggests must pass the validator.
2. Approval comes only from the UI, is bound to `plan_hash` and `state_hash`, and is single use.
3. Execution uses a unique idempotency key, so repeating a request creates no second transaction.
4. Simulations run on snapshots; hypothetical shocks are never persisted as real events.
5. No bank credentials, no real transactions, no borrowing. Everything is a sandbox ledger.
6. User-entered text reaches the LLM as data, with length limits. Tool permissions do not depend on what the LLM decides.
7. Data is sent to an external LLM only when the user enables it; the default is mock mode with synthetic data.
8. Secrets live in `.env`, which is git-ignored. Only `.env.example` is committed.
9. Missing or uncertain data yields a `MISSING_DATA` result listing what is absent; values are never guessed.

## 8. Rewards integration *(planned)*

- Services emit events only after a state change succeeds.
- `event_id` is a hash of (type, subject, period), so XP cannot be granted twice.
- XP values, level thresholds, and grace periods live in `config/reward_rules.yaml`.
- A confirmed shock moves the streak to `PROTECTED`: the count is frozen, neither
  increased nor reset, and the mission becomes a recovery mission. The count
  grows again only when a mission is actually completed.
- Day and week boundaries follow the user's time zone; weeks start on Monday (ISO).
- Opting out stops all streak and XP records; goal progress is still shown.
- XP never affects money or access to safety features.

## 9. Technology choices

| Area | Choice | Reason |
|---|---|---|
| UI | Streamlit | Fastest route to a working demo; single-user is acceptable for the MVP |
| Optimization | `scipy.optimize.linprog` (HiGHS) | Small LP, solved in milliseconds, reproducible |
| Core types | Pydantic v2, integer satang | Tool schemas for free; no float drift |
| Storage | SQLite via `sqlite3` behind repositories | No extra dependency; can move to another database later |
| Agent | LLM with tool calling behind an `LLMClient` interface, plus a deterministic `MockAgent` | Tests and the demo run without an API key |
| Tooling | uv, ruff, pytest, GitHub Actions | One command to install, lint, and test |
