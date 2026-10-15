"""Rewards engine: XP, levels, badges, missions, and streaks from validated events.

Rules are deterministic and come from config/reward_rules.yaml; no model
decides anything here. Every reward event has an id that encodes what it is
for and the period it belongs to, and the store keeps each id once, so the same
review, milestone, or mission can never pay XP twice.

The engine only listens to events the sandbox emits after a state change has
succeeded (a plan approved by the user, a plan executed, time posted, a shock
confirmed) and to the user's own check-in. XP and levels never touch money,
plans, or access to any safety feature. When the user opts out, nothing is
recorded at all; goal progress is still shown because it is plain information.
"""

import json
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from lifecfo.database.store import Store
from lifecfo.domain.clock import Clock, SystemClock, local_date
from lifecfo.domain.models import FinancialState
from lifecfo.rewards.streaks import (
    Streak,
    StreakKind,
    end_protection,
    pause,
    period_start,
    protect,
    record_activity,
    resume,
    status,
)

DEFAULT_RULES = Path(__file__).resolve().parents[2] / "config" / "reward_rules.yaml"
SETTINGS_KEY = "rewards_settings"

WEEKLY_MISSIONS = {
    "weekly_review": "Weekly check-in: review your upcoming bills and your plan",
    "approve_plan": "Approve a plan for this month",
}
RECOVERY_MISSIONS = {
    "recovery_review": "Review your recovery options after the unexpected expense",
    "recovery_plan": "Approve a feasible recovery plan",
}


def load_rules(path: str | Path = DEFAULT_RULES) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _to_streak(kind: StreakKind, data: dict[str, Any] | None) -> Streak:
    if not data:
        return Streak(kind=kind)

    def day(value: str | None) -> date | None:
        return date.fromisoformat(value) if value else None

    return Streak(
        kind=kind, count=data["count"], best=data["best"],
        last_earned=day(data["last_earned"]), protected_from=day(data["protected_from"]),
        protected_until=day(data["protected_until"]),
        pauses=tuple((day(a), day(b)) for a, b in data["pauses"]),
        grace_used=tuple(day(g) for g in data["grace_used"]),
    )


class RewardsService:
    def __init__(self, store: Store, clock: Clock | None = None,
                 rules: dict[str, Any] | None = None) -> None:
        self.store = store
        self.clock = clock or SystemClock()
        self.rules = rules or load_rules()

    # --- settings ------------------------------------------------------------------

    @property
    def settings(self) -> dict[str, Any]:
        raw = self.store.get_meta(SETTINGS_KEY)
        return json.loads(raw) if raw else {"opted_in": True, "open_shock": None}

    def _save_settings(self, settings: dict[str, Any]) -> None:
        self.store.set_meta(SETTINGS_KEY, json.dumps(settings, sort_keys=True))

    @property
    def opted_in(self) -> bool:
        return bool(self.settings["opted_in"])

    def set_opt_in(self, opted_in: bool) -> None:
        settings = self.settings
        settings["opted_in"] = opted_in
        self._save_settings(settings)

    # --- helpers -------------------------------------------------------------------

    def _state(self) -> FinancialState | None:
        return self.store.load_state()

    def _today(self) -> date:
        state = self._state()
        return local_date(self.clock, state.timezone if state else "Asia/Bangkok")

    def _grace(self) -> int:
        return int(self.rules["streak"].get("grace_days_per_week") or 0)

    def _streak(self, kind: StreakKind) -> Streak:
        return _to_streak(kind, self.store.load_streak(kind.value))

    def _save_streak(self, streak: Streak) -> None:
        data = asdict(streak)
        data.pop("kind")
        self.store.save_streak(streak.kind.value, data)

    def _record(self, event_id: str, kind: str, day: date, **payload: Any) -> bool:
        xp = int(self.rules["xp"].get(kind, 0))
        return self.store.insert_reward_event({
            "event_id": event_id, "type": kind, "xp": xp, "occurred_on": day.isoformat(),
            "recorded_at": self.clock.now().isoformat(timespec="seconds"), "payload": payload,
        })

    def _activity(self, day: date) -> None:
        for kind in StreakKind:
            streak, grew = record_activity(self._streak(kind), day, self._grace())
            if grew:
                self._save_streak(streak)

    def _complete_mission(self, mission: str, day: date) -> None:
        week = period_start(StreakKind.WEEKLY, day).isoformat()
        self._record(f"mission:{mission}:{week}", "WEEKLY_PLANNING_MISSION_COMPLETED", day,
                     mission=mission, title=WEEKLY_MISSIONS[mission])

    # --- inputs --------------------------------------------------------------------

    def record_review(self) -> bool:
        """The user's own check-in: they reviewed their bills and plan today."""
        if not self.opted_in:
            return False
        day = self._today()
        new = self._record(f"review:{day.isoformat()}", "FINANCIAL_REVIEW_COMPLETED", day)
        if new:
            self._activity(day)
            if self.settings["open_shock"]:
                self._record(f"recovery_review:{self.settings['open_shock']}",
                             "RECOVERY_REVIEW_DONE", day)
            else:
                self._complete_mission("weekly_review", day)
        return new

    def on_plan_approved(self, plan_id: str) -> None:
        if not self.opted_in:
            return
        day = self._today()
        if not self._record(f"approved:{plan_id}", "PLAN_APPROVED", day, plan_id=plan_id):
            return
        self._activity(day)
        shock = self.settings["open_shock"]
        if shock:
            self._record(f"recovery:{shock}", "RECOVERY_MISSION_COMPLETED", day,
                         shock_id=shock, plan_id=plan_id)
            for kind in StreakKind:
                self._save_streak(end_protection(self._streak(kind), day))
            settings = self.settings
            settings["open_shock"] = None
            self._save_settings(settings)
        else:
            self._complete_mission("approve_plan", day)

    def on_shock_confirmed(self, shock_id: str) -> None:
        if not self.opted_in:
            return
        day = self._today()
        if not self._record(f"shock:{shock_id}", "SHOCK_CONFIRMED", day, shock_id=shock_id):
            return
        days = int(self.rules["streak"].get("protection_max_days") or 14)
        for kind in StreakKind:
            self._save_streak(protect(self._streak(kind), day, days))
        self._record(f"protection:{shock_id}", "STREAK_PROTECTION_ACTIVATED", day,
                     shock_id=shock_id, days=days)
        settings = self.settings
        settings["open_shock"] = shock_id
        self._save_settings(settings)

    def on_state_changed(self) -> None:
        """Award goal milestones reached in the stored (validated) state."""
        if not self.opted_in:
            return
        state = self._state()
        if state is None:
            return
        day = self._today()
        saved = {e.goal_id: e.balance for e in state.envelopes if e.goal_id}
        for goal in state.goals:
            progress = 100 * saved.get(goal.id, 0) / goal.target
            for pct in self.rules["goal_milestones_percent"]:
                if progress >= pct:
                    self._record(f"milestone:{goal.id}:{pct}", "GOAL_MILESTONE_REACHED", day,
                                 goal_id=goal.id, goal=goal.name, percent=pct)

    def pause_streaks(self) -> None:
        day = self._today()
        for kind in StreakKind:
            self._save_streak(pause(self._streak(kind), day))

    def resume_streaks(self) -> None:
        last = self._today() - timedelta(days=1)
        for kind in StreakKind:
            self._save_streak(resume(self._streak(kind), last))

    # --- output --------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        state = self._state()
        today = self._today()
        progress = []
        if state:
            saved = {e.goal_id: e.balance for e in state.envelopes if e.goal_id}
            progress = [{"goal": g.name, "saved": saved.get(g.id, 0), "target": g.target,
                         "percent": round(100 * saved.get(g.id, 0) / g.target, 1)}
                        for g in state.goals]
        if not self.opted_in:
            return {"opted_in": False, "today": today.isoformat(), "goal_progress": progress,
                    "note": "Rewards and streaks are off. Nothing is being recorded."}

        events = self.store.list_reward_events()
        xp = sum(e["xp"] for e in events)
        thresholds = self.rules["level_thresholds"]
        level = sum(1 for t in thresholds if xp >= t)
        next_at = thresholds[level] if level < len(thresholds) else None
        streaks = {}
        for kind in StreakKind:
            streak = self._streak(kind)
            streaks[kind.value] = {
                "count": streak.count, "best": streak.best,
                "status": status(streak, today, self._grace()).value,
                "last_earned": streak.last_earned.isoformat() if streak.last_earned else None,
                "protected_until": (streak.protected_until.isoformat()
                                    if streak.protected_until and streak.protected_until >= today
                                    else None),
            }
        return {
            "opted_in": True,
            "today": today.isoformat(),
            "xp": xp,
            "level": level,
            "next_level_at_xp": next_at,
            "streaks": streaks,
            "missions": self._missions(today, events),
            "badges": self._badges(events, streaks),
            "goal_progress": progress,
            "recent_events": [
                {"type": e["type"], "xp": e["xp"], "on": e["occurred_on"]}
                for e in events[-8:]
            ],
            "note": "XP and levels are for motivation only. They never affect money, plans, "
                    "or access to any feature.",
        }

    def _missions(self, today: date, events: list[dict[str, Any]]) -> dict[str, Any]:
        shock = self.settings["open_shock"]
        ids = {e["event_id"] for e in events}
        if shock:
            return {"mode": "RECOVERY", "items": [
                {"id": "recovery_review", "title": RECOVERY_MISSIONS["recovery_review"],
                 "done": f"recovery_review:{shock}" in ids},
                {"id": "recovery_plan", "title": RECOVERY_MISSIONS["recovery_plan"],
                 "done": f"recovery:{shock}" in ids},
            ], "note": "Your missions changed because of a confirmed expense. Your streak is "
                       "protected meanwhile; saving is not expected this week."}
        week = period_start(StreakKind.WEEKLY, today).isoformat()
        return {"mode": "NORMAL", "items": [
            {"id": key, "title": title, "done": f"mission:{key}:{week}" in ids}
            for key, title in WEEKLY_MISSIONS.items()
        ]}

    def _badges(self, events: list[dict[str, Any]],
                streaks: dict[str, Any]) -> list[str]:
        names = self.rules.get("badges", {})
        badges = [f"{e['payload']['goal']} {e['payload']['percent']}%"
                  for e in events if e["type"] == "GOAL_MILESTONE_REACHED"]
        if any(e["type"] == "PLAN_APPROVED" for e in events):
            badges.insert(0, names.get("first_plan_approved", "First plan approved"))
        if any(e["type"] == "RECOVERY_MISSION_COMPLETED" for e in events):
            badges.append(names.get("recovery_completed", "Bounced back"))
        if streaks["DAILY"]["best"] >= 7:
            badges.append(names.get("daily_streak_7", "7-day streak"))
        if streaks["WEEKLY"]["best"] >= 4:
            badges.append(names.get("weekly_streak_4", "4-week streak"))
        return badges


__all__ = ["RewardsService", "load_rules"]
