# Rewards System

Code: `lifecfo/rewards/` (state machine in `streaks.py`, engine in `service.py`).
Rules: `config/reward_rules.yaml`. Tests: `tests/unit/test_rewards.py` and the
Rewards tests in `tests/integration/test_app_sandbox.py`.

## Principles

1. **Only validated events count.** The engine listens to the sandbox after a
   change has succeeded (a plan the user approved, a plan executed, time
   posted, a shock the user confirmed) and to the user's own daily check-in.
   Opening the app earns nothing.
2. **Deterministic rules.** XP values and limits come from the config file.
   No model decides rewards, and the agent has no tool that can grant them;
   it can only read the status.
3. **No double rewards.** Every reward event has an id that names what it is
   for and its period (`review:2026-11-02`, `mission:approve_plan:2026-11-02`,
   `milestone:laptop:50`, `recovery:shock-1`). The store keeps each id once.
4. **No effect on money.** XP and levels never change balances, plans,
   credit, or access to any feature.
5. **Never reward spending or risk.** There are no missions to spend or to
   save beyond a validated plan, and nothing asks the user to cut essentials to
   keep a streak.
6. **Opt-out means nothing is recorded.** Goal progress bars stay visible
   because they are plain information.
7. **No shame.** A broken streak says "start again any time"; there are no
   penalty messages and no notifications.

## XP (draft values from the brief)

| Event | XP | Limit |
|---|---|---|
| Financial review (daily check-in) | 10 | once per day |
| Weekly mission completed | 20 | once per mission per ISO week |
| Goal milestone (25, 50, 75, 100%) | 50 | once per goal per milestone, ever |
| Recovery mission completed | 75 | once per confirmed shock |
| Plan approved, shock confirmed, protection activated | 0 | recorded for missions, badges, and streaks |

Levels start at the thresholds 0, 100, 250, 500, 1,000, 2,000 XP.

## Streaks

Two streaks run side by side: **daily** (any meaningful action that day) and
**weekly** (any meaningful action in the ISO week). Days and weeks are
measured in the user's time zone (default Asia/Bangkok), weeks start on Monday.

A missed period does not break a streak when it is covered by:

| Cover | Rule (draft values) |
|---|---|
| Grace | One missed day per ISO week, daily streak only |
| Protection | After a confirmed shock, up to 14 days, ending early when a recovery mission is completed |
| Pause | Any period inside a pause the user started; an action or "Resume" ends it |

Covered periods freeze the count: they neither add to it nor reset it. Only an
earned period adds one, so a protected streak is always distinguishable from
earned progress. A shock on its own completes nothing.

States: `NOT_STARTED`, `ACTIVE`, `PROTECTED`, `PAUSED`, `BROKEN`.

## Missions

| Mode | Missions | Completed by |
|---|---|---|
| Normal | Weekly check-in: review bills and plan | the user's check-in |
| Normal | Approve a plan for this month | a plan approved by the user |
| Recovery (after a confirmed shock) | Review your recovery options | the user's check-in |
| Recovery | Approve a feasible recovery plan | a plan approved by the user; pays the recovery XP and ends protection |

The recovery mode is the adaptive part: instead of expecting savings while the
user deals with an emergency, the missions become reviewing and approving a
feasible recovery plan, and the streak is protected meanwhile.

## Confirmed shocks and reserve withdrawals

`SandboxService.confirm_expense` records a real unexpected expense as an
essential bill, and `SandboxService.withdraw_reserve` moves money from the
emergency reserve to unallocated cash. Both are user-only, audited, and change
the state hash, so any earlier proposal or approval must be redone. These are
the actions behind "a confirmed event" in ShockProof; simulations never call
them.

## Badges

First plan approved; each goal milestone; Bounced back (a recovery mission);
7-day streak; 4-week streak.

## Time

The engine uses the clock it is given. The app uses the real date, so daily
streaks follow real days; the offline demo uses a fixed clock it moves forward,
so its output is identical on every run.

## Open questions for the team

- Grace of one day per week and protection of 14 days are draft values.
- Should a daily check-in remain a button press, or require looking at a
  specific screen first?
- Claims about motivation are not made anywhere: no user study has been run.
