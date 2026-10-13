"""Compare engine output with hand-calculated expected values.

Each CSV in tests/scenarios/expected/ named `<profile>_daily.csv` is checked
against data/synthetic/<profile>.yaml. Columns: date, unallocated_thb,
total_cash_thb (closing balances). Only the listed dates are checked, so a
reviewer can verify a scenario by listing the days that matter.
"""

import csv
from datetime import date
from pathlib import Path

import pytest

from lifecfo.cashflow import forecast_cash_flow
from lifecfo.domain import thb
from lifecfo.domain.loader import load_state

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = sorted((ROOT / "tests" / "scenarios" / "expected").glob("*_daily.csv"))


@pytest.mark.parametrize("csv_path", EXPECTED, ids=lambda p: p.stem)
def test_daily_balances_match_expected(csv_path: Path):
    profile = ROOT / "data" / "synthetic" / f"{csv_path.stem.removesuffix('_daily')}.yaml"
    state = load_state(profile)
    with open(csv_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, "expected-values file is empty"

    last = max(date.fromisoformat(row["date"]) for row in rows)
    forecast = forecast_cash_flow(state, (last - state.as_of).days + 1)
    by_date = {day.on: day for day in forecast.days}

    for row in rows:
        day = by_date[date.fromisoformat(row["date"])]
        assert day.unallocated == thb(row["unallocated_thb"]), row["date"]
        assert day.total_cash == thb(row["total_cash_thb"]), row["date"]
