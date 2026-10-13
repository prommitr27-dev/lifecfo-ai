"""Load a FinancialState from a human-editable YAML profile.

Profiles write money in baht with a `_thb` suffix (`amount_thb: 30000`); the
loader converts those keys to satang so teammates never handle satang by hand.
"""

from pathlib import Path
from typing import Any

import yaml

from lifecfo.domain.models import FinancialState
from lifecfo.domain.money import thb

_SUFFIX = "_thb"


def _to_satang(node: Any) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if isinstance(key, str) and key.endswith(_SUFFIX):
                out[key[: -len(_SUFFIX)]] = None if value is None else thb(value)
            else:
                out[key] = _to_satang(value)
        return out
    if isinstance(node, list):
        return [_to_satang(item) for item in node]
    return node


def parse_state(raw: dict[str, Any]) -> FinancialState:
    return FinancialState.model_validate(_to_satang(raw))


def load_state(path: str | Path) -> FinancialState:
    with open(path, encoding="utf-8") as handle:
        return parse_state(yaml.safe_load(handle))
