"""Deterministic cash flow forecasting and feasibility checks."""

from lifecfo.cashflow.feasibility import FeasibilityReport, FeasibilityStatus, check_feasibility
from lifecfo.cashflow.forecast import (
    CashEvent,
    DayBalance,
    EventKind,
    Forecast,
    MonthSummary,
    forecast_cash_flow,
    monthly_summary,
)

__all__ = [
    "CashEvent",
    "DayBalance",
    "EventKind",
    "FeasibilityReport",
    "FeasibilityStatus",
    "Forecast",
    "MonthSummary",
    "check_feasibility",
    "forecast_cash_flow",
    "monthly_summary",
]
