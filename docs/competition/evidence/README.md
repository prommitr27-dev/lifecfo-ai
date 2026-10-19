# Execution Evidence

Evidence that LifeCFO AI works end to end on a simulated account (sandbox),
for FinTechathon 2026, International Track, **Topic A: Personal Finance
Assistant**. Topic F (on-chain transaction hashes) does not apply: LifeCFO
makes no on-chain or real-money transactions.

Everything here uses synthetic data only. No bank, credential, or real money is
involved anywhere.

## What each file proves

| File | What it is | What it shows | How it was produced |
|---|---|---|---|
| [demo_15_steps.md](demo_15_steps.md) | Report of the 15-step demo, with a pass or fail check on every step | All 15 steps pass: profile, goals, plan, income shock, infeasibility, alternatives, trade-offs, user approval, sandbox execution, emergency expense, recovery plan, updated goals, recovery mission, protected streak, audit log | `uv run python scripts/demo_15_steps.py` (fixed clock, no LLM, no network) |
| [demo_15_steps.json](demo_15_steps.json) | Execution log of that run | Hash-chained audit log, sandbox transactions, reward events | Same script |
| [offline_demo_transcript.md](offline_demo_transcript.md) | Chat transcript: each user message, the tools the agent called with their permission tier, and the answer | The agent reads, simulates, proposes; it refuses to approve; execution is refused until the user approves; a repeated execution is blocked | `uv run python scripts/demo_offline.py --write` |
| [sandbox_operation_log.json](sandbox_operation_log.json) | Execution log of that run | Audit log including the refused execution attempts, transactions, reward events | Same script |
| [screenshots/](screenshots/) | 11 screenshots of the web app | The same story clicked through the real user interface | `scripts/capture_evidence_screenshots.py` against a fresh sandbox, 19 October 2026 |
| [web_app_audit_log.json](web_app_audit_log.json) | The audit log of that web session, exported with the app's own "Download audit log (JSON)" button | 13 audit entries, 3 approvals by the user, 3 executions, intact hash chain. Timestamps are the real time of the run | Same script |
| [../../testing/EVALUATION_RESULTS.md](../../testing/EVALUATION_RESULTS.md) | Evaluation on 40 seeded synthetic scenarios against three baselines, plus 20 routing and 10 prompt-injection prompts | Validated plans avoid missed payments and disclose when no plan exists | `uv run python scripts/run_evaluation.py` |

## The walkthrough in the screenshots

Synthetic profile: salary 30,000 THB, essentials 18,000 THB, flexible spending
3,000 THB (can be cut to 2,000), emergency reserve 6,000 THB, goals "New
laptop" 30,000 THB and "Vacation" 15,000 THB. Sandbox date 1 November 2026.

| # | Screenshot | Input | Result |
|---|---|---|---|
| 1 | [Home, before](screenshots/01-home-before.png) | Profile loaded | 3,000 THB to spend this month, bills due next, goal progress |
| 2 | [Three validated plans](screenshots/02-three-validated-plans.png) | Personal CFO view | The user's position first, then Safety First, Balanced, Goal First; each passed the validator and the daily cash check |
| 3 | [Approve and execute](screenshots/03-user-approves-and-executes.png) | User requests approval for Balanced, approves it, executes it | Plan active in the sandbox; audit entries for proposal, approval, execution |
| 4 | [New plans after an income cut](screenshots/04-new-plans-after-income-cut.png) | User confirms monthly income -20% | Earlier approvals lapse (state changed); new validated plans for 24,000 THB income |
| 5 | [AI what-if: repair bill](screenshots/05-ai-what-if-repair-bill.png) | Chat: "What if I get a 10,000 THB repair bill?" | Agent calls `simulate_unexpected_expense`: 6,000 THB not covered, reserve withdrawal needed, the plan becomes infeasible, recovery options with reasons per goal. Nothing saved |
| 6 | [Confirm the expense](screenshots/06-user-confirms-the-expense.png) | User confirms a 10,000 THB car repair due 12 November | Recorded as an essential bill (`SHOCK_CONFIRMED`) |
| 7 | [Reserve needed](screenshots/07-reserve-needed-before-replanning.png) | Personal CFO view | `REQUIRES_RESERVE_DRAWDOWN`: essentials need 4,000 THB from the reserve, 6,000 THB to keep flexible spending; no regular plan is offered until the user decides |
| 8 | [Recovery plans and affected goals](screenshots/08-recovery-plans-and-affected-goals.png) | User withdraws 6,000 THB from the reserve | New validated plans; each goal's completion and shortfall at its deadline |
| 9 | [Recovery plan executed](screenshots/09-recovery-plan-executed.png) | User approves and executes Safety First | Recovery plan active |
| 10 | [Audit log](screenshots/10-audit-log.png) | Sandbox view | Every proposal, approval, execution, confirmed event, and withdrawal, with actor and hash; chain intact |
| 11 | [Home, after](screenshots/11-home-after.png) | | 2,000 THB to spend this month; the repair bill in "Bills to pay"; plan funded every day for the next 92 days |

## How to check the evidence yourself

```bash
uv sync
uv run python scripts/verify_evidence.py          # independent check of the three logs
uv run python scripts/demo_15_steps.py            # regenerates demo_15_steps.md and .json
uv run python scripts/demo_offline.py --write     # regenerates the transcript and its log
git diff --exit-code docs/competition/evidence    # no difference: the evidence is reproducible
uv run pytest                                     # includes the same checks as tests
```

`scripts/verify_evidence.py` does not import the application code. It
recomputes each audit hash from its definition
(`SHA-256(prev_hash, ts, actor, action, sorted-JSON payload)` joined by
newlines, starting from 64 zeros) and checks that:

- the chain is unbroken and no entry was edited, inserted, or deleted;
- only the user approved, rejected, or confirmed real events;
- every execution followed a user approval for the same plan and the same
  financial state, and each approval was used once;
- sandbox transaction idempotency keys are unique.

Expected output:

```
PASS demo_15_steps.json: 14 audit entries, 3 approvals by the user, 3 executions, 1 refused or blocked attempts, 4 sandbox transactions
PASS sandbox_operation_log.json: 11 audit entries, 2 approvals by the user, 2 executions, 2 refused or blocked attempts, 9 sandbox transactions
PASS web_app_audit_log.json: 13 audit entries, 3 approvals by the user, 3 executions, 0 refused or blocked attempts, 4 sandbox transactions
```

The same script checks any log downloaded from the app's Sandbox view:
`uv run python scripts/verify_evidence.py path/to/lifecfo_sandbox_log.json`.
`tests/integration/test_evidence_files.py` runs these checks in the test suite,
confirms the committed files match a fresh run, and confirms that an edited
entry, a deleted entry, an approval by the agent, and a second execution are
each detected.

## Test run

| Command | Result on 19 October 2026 |
|---|---|
| `uv run pytest` | All tests pass (298, including the evidence tests above) |
| `uv run ruff check .` | All checks passed |

## Demo video

A 4 minute 36 second walkthrough of the same 15 steps, with English captions,
recorded from the web app. Link: *to be added by the team after upload*.

## Try it live

<https://lifecfo-ai.streamlit.app/> runs the same code. Each visitor gets a
private, temporary sandbox, so the steps above can be repeated without
affecting anyone else.
