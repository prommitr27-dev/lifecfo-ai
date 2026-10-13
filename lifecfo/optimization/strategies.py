"""Strategy parameters, loaded from config/strategy_weights.yaml."""

from pathlib import Path
from typing import Annotated

import yaml
from pydantic import Field

from lifecfo.domain.models import Frozen

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "strategy_weights.yaml"

Weight = Annotated[float, Field(ge=0)]


class StrategyConfig(Frozen):
    name: str
    label: str
    reserve_ramp_months: Annotated[int, Field(ge=1)]
    reserve_weight: Weight
    goal_weight: Weight
    flexible_cut_weight: Weight
    surplus_reserve: Weight
    surplus_goal: Weight
    priority_decay: Annotated[float, Field(gt=0, le=1)] = 0.5
    surplus_bonus_scale: Weight = 0.001

    def priority_factor(self, priority: int) -> float:
        return self.priority_decay ** (priority - 1)


def load_strategies(path: str | Path = DEFAULT_CONFIG) -> dict[str, StrategyConfig]:
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    shared = {key: raw[key] for key in ("priority_decay", "surplus_bonus_scale") if key in raw}
    return {
        name: StrategyConfig(name=name, **shared, **params)
        for name, params in raw["strategies"].items()
    }
