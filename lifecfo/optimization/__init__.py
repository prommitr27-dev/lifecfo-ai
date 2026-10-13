"""Multi-goal plan optimization, plan validation, and strategy comparison."""

from lifecfo.optimization.optimizer import generate_plans, optimize_plan
from lifecfo.optimization.plan import (
    GoalProjection,
    IdenticalPlans,
    Plan,
    PlanMonth,
    PlanningResult,
    PlanningStatus,
    PlanValidation,
    ReserveProjection,
    apply_plan,
    state_fingerprint,
    validate_plan,
)
from lifecfo.optimization.strategies import StrategyConfig, load_strategies

__all__ = [
    "GoalProjection",
    "IdenticalPlans",
    "Plan",
    "PlanMonth",
    "PlanValidation",
    "PlanningResult",
    "PlanningStatus",
    "ReserveProjection",
    "StrategyConfig",
    "apply_plan",
    "generate_plans",
    "load_strategies",
    "optimize_plan",
    "state_fingerprint",
    "validate_plan",
]
