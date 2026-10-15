from datetime import UTC, date, datetime, timedelta

import pytest

from lifecfo.database import Store
from lifecfo.domain import FixedClock, thb
from lifecfo.optimization import generate_plans
from lifecfo.rewards.streaks import (
    Streak,
    StreakKind,
    StreakStatus,
    pause,
    protect,
    record_activity,
    resume,
    status,
)
from lifecfo.services import SandboxService
from lifecfo.services.sandbox import AGENT

D = date(2026, 11, 2)  # a Monday


def days(n: int) -> date:
    return D + timedelta(days=n)


def run(streak: Streak, offsets: list[int], grace: int = 1) -> Streak:
    for offset in offsets:
        streak, _ = record_activity(streak, days(offset), grace)
    return streak


# --- streak state machine --------------------------------------------------------------


def test_consecutive_days_count_and_repeats_do_not():
    streak, grew = record_activity(Streak(StreakKind.DAILY), D, 1)
    assert grew and streak.count == 1
    again, grew = record_activity(streak, D, 1)
    assert not grew and again.count == 1  # opening the app twice is not two days
    assert run(Streak(StreakKind.DAILY), [0, 1, 2, 3]).count == 4


def test_one_missed_day_a_week_is_covered_by_grace_without_adding_to_the_count():
    streak = run(Streak(StreakKind.DAILY), [0, 1, 3])  # Wednesday (day 2) missed
    assert streak.count == 3 and streak.grace_used == (days(2),)


def test_two_missed_days_in_one_week_restart_the_streak_without_penalty():
    streak = run(Streak(StreakKind.DAILY), [0, 1, 4])  # days 2 and 3 missed
    assert streak.count == 1 and streak.best == 2
    assert status(run(Streak(StreakKind.DAILY), [0, 1]), days(4), 1) is StreakStatus.BROKEN


def test_protection_freezes_the_count_through_a_shock():
    streak = run(Streak(StreakKind.DAILY), list(range(30)), grace=0)
    assert streak.count == 30
    streak = protect(streak, days(30), 14)
    assert status(streak, days(35), 0) is StreakStatus.PROTECTED
    resumed = run(streak, [36], grace=0)  # six days missed, all protected
    assert resumed.count == 31  # protected days add nothing and take nothing away


def test_protection_has_a_limit():
    streak = protect(run(Streak(StreakKind.DAILY), [0], grace=0), days(1), 3)  # days 1 to 3
    assert run(streak, [5], grace=0).count == 1  # day 4 was not covered


def test_a_pause_covers_the_paused_days_even_after_resuming():
    streak = pause(run(Streak(StreakKind.DAILY), [0, 1], grace=0), days(2))
    assert status(streak, days(6), 0) is StreakStatus.PAUSED
    streak = resume(streak, days(6))
    assert run(streak, [7], grace=0).count == 3


def test_weekly_streak_counts_iso_weeks():
    streak = run(Streak(StreakKind.WEEKLY), [0, 3, 7, 14])  # weeks 1, 1, 2, 3
    assert streak.count == 3
    assert run(streak, [28]).count == 1  # week 4 missed; no grace for weekly streaks


# --- rewards service ------------------------------------------------------------------


@pytest.fixture
def clock():
    return FixedClock(datetime(2026, 11, 2, 3, 0, tzinfo=UTC))  # 10:00 in Bangkok


@pytest.fixture
def sandbox(demo_state, clock):
    service = SandboxService(Store(), clock)
    service.reset(demo_state)
    return service


def xp_by_type(sandbox) -> dict[str, int]:
    out: dict[str, int] = {}
    for event in sandbox.store.list_reward_events():
        out[event["type"]] = out.get(event["type"], 0) + event["xp"]
    return out


def approve(sandbox, strategy="BALANCED"):
    plan = next(p for p in generate_plans(sandbox.state).plans if p.strategy == strategy)
    plan_id = sandbox.propose(plan, AGENT).data["plan_id"]
    return sandbox.decide(plan_id, True)


def test_review_pays_once_a_day_and_completes_the_weekly_mission(sandbox, clock):
    rewards = sandbox.rewards
    assert rewards.record_review() is True
    assert rewards.record_review() is False  # same day: nothing more
    status_now = rewards.status()
    assert status_now["xp"] == 10 + 20
    assert next(m for m in status_now["missions"]["items"]
                if m["id"] == "weekly_review")["done"]
    clock.advance(days=1)
    rewards.record_review()
    assert rewards.status()["xp"] == 10 + 20 + 10  # the weekly mission pays once a week
    assert rewards.status()["streaks"]["DAILY"]["count"] == 2


def test_plan_approval_counts_for_missions_but_not_xp_by_itself(sandbox):
    approve(sandbox)
    totals = xp_by_type(sandbox)
    assert totals["PLAN_APPROVED"] == 0
    assert totals["WEEKLY_PLANNING_MISSION_COMPLETED"] == 20
    assert "First plan approved" in sandbox.rewards.status()["badges"]


def test_goal_milestones_pay_once_from_the_stored_state(sandbox):
    envelopes = tuple(e.model_copy(update={"balance": thb(16000)}) if e.id == "env-laptop"
                      else e for e in sandbox.state.envelopes)
    with sandbox.store.transaction():
        sandbox.store.save_state(sandbox.state.model_copy(update={"envelopes": envelopes}))
    sandbox.rewards.on_state_changed()
    sandbox.rewards.on_state_changed()
    milestones = [e for e in sandbox.store.list_reward_events()
                  if e["type"] == "GOAL_MILESTONE_REACHED"]
    assert [e["payload"]["percent"] for e in milestones] == [25, 50]  # 16,000 of 30,000
    assert xp_by_type(sandbox)["GOAL_MILESTONE_REACHED"] == 100


def test_rewards_never_change_the_financial_state(sandbox):
    before = sandbox.state
    sandbox.rewards.record_review()
    sandbox.rewards.on_state_changed()
    sandbox.rewards.pause_streaks()
    assert sandbox.state == before


def test_opting_out_records_nothing(sandbox):
    sandbox.rewards.set_opt_in(False)
    sandbox.rewards.record_review()
    approve(sandbox)
    sandbox.confirm_expense("Car repair", thb(10000), date(2026, 11, 12))
    assert sandbox.store.list_reward_events() == []
    status_now = sandbox.rewards.status()
    assert status_now["opted_in"] is False and status_now["goal_progress"]
    assert "xp" not in status_now


def test_shock_switches_to_recovery_missions_and_protects_the_streak(sandbox, clock):
    for _ in range(5):
        sandbox.rewards.record_review()
        clock.advance(days=1)
    result = sandbox.confirm_expense("Car repair", thb(10000), date(2026, 11, 12))
    assert result.ok
    status_now = sandbox.rewards.status()
    assert status_now["missions"]["mode"] == "RECOVERY"
    assert "saving is not expected" in status_now["missions"]["note"]
    assert status_now["streaks"]["DAILY"]["status"] == "PROTECTED"
    assert status_now["streaks"]["DAILY"]["count"] == 5

    clock.advance(days=4)  # four days with no activity, all protected
    assert sandbox.rewards.status()["streaks"]["DAILY"]["status"] == "PROTECTED"

    # The confirmed expense needs 1,000 from the reserve before any plan exists.
    assert sandbox.withdraw_reserve(thb(1000)).ok
    assert approve(sandbox).ok  # the recovery plan, approved by the user
    status_now = sandbox.rewards.status()
    assert status_now["missions"]["mode"] == "NORMAL"
    assert status_now["streaks"]["DAILY"]["count"] == 6  # earned, not inflated
    assert xp_by_type(sandbox)["RECOVERY_MISSION_COMPLETED"] == 75
    assert "Bounced back" in status_now["badges"]


def test_a_shock_does_not_count_as_a_completed_mission(sandbox):
    sandbox.confirm_expense("Medical bill", thb(5000), date(2026, 11, 20))
    types = {e["type"] for e in sandbox.store.list_reward_events()}
    assert types == {"SHOCK_CONFIRMED", "STREAK_PROTECTION_ACTIVATED"}
    assert sum(e["xp"] for e in sandbox.store.list_reward_events()) == 0


def test_levels_follow_the_configured_thresholds(sandbox, clock):
    for _ in range(10):
        sandbox.rewards.record_review()
        clock.advance(days=1)
    status_now = sandbox.rewards.status()
    # 10 reviews (100) + two weekly missions (40) = 140 XP: level 2 of thresholds 0/100/250.
    assert status_now["xp"] == 140 and status_now["level"] == 2
    assert status_now["next_level_at_xp"] == 250


# --- confirmed expenses and reserve withdrawals ---------------------------------------


def test_only_the_user_can_confirm_an_expense_or_withdraw(sandbox):
    before = sandbox.state
    assert sandbox.confirm_expense("x", thb(100), date(2026, 11, 12), actor=AGENT).code == (
        "ONLY_USER_CAN_CONFIRM")
    assert sandbox.withdraw_reserve(thb(100), actor=AGENT).code == "ONLY_USER_CAN_WITHDRAW"
    assert sandbox.withdraw_reserve(thb(999999)).code == "INVALID_AMOUNT"
    assert sandbox.state == before


def test_a_confirmed_expense_voids_earlier_proposals(sandbox):
    plan = generate_plans(sandbox.state).plans[0]
    plan_id = sandbox.propose(plan, AGENT).data["plan_id"]
    sandbox.confirm_expense("Car repair", thb(10000), date(2026, 11, 12))
    assert sandbox.decide(plan_id, True).code == "STALE_PLAN"
    assert any(e.id == "shock-1" and e.amount == thb(10000) for e in sandbox.state.expenses)


def test_withdrawal_moves_cash_between_envelopes_and_is_logged(sandbox):
    total = sandbox.state.total_cash
    result = sandbox.withdraw_reserve(thb(1000))
    assert result.ok and sandbox.state.total_cash == total
    assert sandbox.state.emergency.balance == thb(5000)
    assert sandbox.state.unallocated.balance == thb(1000)
    assert [r["kind"] for r in sandbox.store.list_transactions()] == ["RESERVE_WITHDRAWAL"]
    assert sandbox.store.list_audit()[-1].payload["gap_after"] == thb(49000)
