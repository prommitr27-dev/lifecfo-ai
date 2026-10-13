"""Checks on the files teammates edit by hand, with messages they can act on."""

from pathlib import Path

import pytest
import yaml

from lifecfo.domain.loader import load_state, parse_state
from lifecfo.optimization import load_strategies

ROOT = Path(__file__).resolve().parents[2]
PROFILES = sorted((ROOT / "data" / "synthetic").glob("*.yaml"))
EXPECTED = sorted((ROOT / "tests" / "scenarios" / "expected").glob("*_daily.csv"))


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.name)
def test_every_synthetic_profile_loads(path: Path):
    try:
        load_state(path)
    except Exception as error:  # noqa: BLE001 - reported to a non-programmer
        pytest.fail(f"{path.name} has a problem: {error}")


@pytest.mark.parametrize("path", EXPECTED, ids=lambda p: p.name)
def test_every_expected_file_has_a_matching_profile(path: Path):
    profile = ROOT / "data" / "synthetic" / f"{path.stem.removesuffix('_daily')}.yaml"
    assert profile.exists(), (
        f"{path.name} needs a profile named {profile.name} in data/synthetic/"
    )


def test_profile_template_is_valid():
    template = ROOT / "docs" / "team" / "templates" / "profile_template.yaml"
    parse_state(yaml.safe_load(template.read_text(encoding="utf-8")))


def test_strategy_weights_file_is_valid():
    strategies = load_strategies()
    assert set(strategies) == {"SAFETY_FIRST", "BALANCED", "GOAL_FIRST"}, (
        "config/strategy_weights.yaml must define exactly SAFETY_FIRST, BALANCED, GOAL_FIRST"
    )


@pytest.mark.parametrize("name", ["risk_thresholds.yaml", "reward_rules.yaml"])
def test_config_files_are_valid_yaml(name: str):
    yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))
