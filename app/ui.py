"""Presentation helpers for the Streamlit app: page styles and small HTML pieces.

Only formatting lives here. Every number shown is computed by the engines and
passed in as integer satang; nothing in this module does money arithmetic
beyond rounding for display.
"""

from datetime import date
from html import escape

import streamlit as st

from lifecfo.cashflow.forecast import CashEvent, EventKind, MonthSummary
from lifecfo.domain.money import SATANG_PER_THB

NAVY = "#1E3A8A"
TEAL = "#498E93"

_CSS = """
<style>
:root { --ink:#0F172A; --muted:#64748B; --soft:#94A3B8; --navy:#1E3A8A; --line:#E2E8F0; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.2rem; max-width: 1240px; }
section[data-testid="stSidebar"] > div { padding-top: 0.6rem; }

/* Underlined view tabs (the segmented control). */
.st-key-view { width: 100% !important; border-bottom: 1px solid var(--line);
  margin-bottom: 0.4rem; }
.st-key-view [role="radiogroup"] { gap: 1.7rem; }
.st-key-view button {
  border: 0 !important; background: transparent !important; border-radius: 0 !important;
  padding: 0 1px 0.75rem !important; min-height: 0 !important; color: var(--muted) !important;
  box-shadow: none !important;
}
.st-key-view button p { font-size: 0.875rem; font-weight: 500; }
.st-key-view button[aria-checked="true"] {
  color: var(--navy) !important; box-shadow: inset 0 -2px 0 var(--navy) !important;
}
.st-key-view button[aria-checked="true"] p { font-weight: 600; }
.st-key-horizon button { min-height: 1.9rem !important; padding: 0 0.8rem !important; }
.st-key-horizon button p { font-size: 0.8rem; }
[data-testid="stSidebarHeader"] { height: 2.2rem; min-height: 0; padding-top: 0.6rem; }

/* Alerts read as calm status bars. */
[data-testid="stAlert"] > div { border: 1px solid transparent; }
[data-testid="stAlertContentSuccess"] { color: #166534; }

/* Bordered containers become white cards. */
[data-testid="stVerticalBlockBorderWrapper"] { background: #FFFFFF; }
[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] { background: #FFFFFF; }

.lc-logo { display:flex; gap:10px; align-items:center; margin: 0 0 1.4rem; }
.lc-mark { width:31px; height:31px; border-radius:7px; background:var(--navy); color:#fff;
  display:flex; align-items:flex-end; justify-content:center; gap:3px; padding-bottom:9px; }
.lc-mark i { width:2px; background:#fff; border-radius:2px; display:block; }
.lc-logo span { font-size:18px; font-weight:700; letter-spacing:-.5px; color:var(--ink); }
.lc-logo em { font-style:normal; color:var(--navy); font-weight:500; }
.lc-kicker { text-transform:uppercase; letter-spacing:1.3px; color:var(--soft);
  font-size:10px; font-weight:700; }
.lc-plan { padding:12px; margin:8px 0 1.2rem; border-radius:7px; background:#F3F6FC;
  display:flex; gap:10px; align-items:center; }
.lc-plan b { font-size:13px; font-weight:600; color:var(--ink); }
.lc-plan small { display:block; font-size:11px; color:var(--muted); margin-top:2px; }
.lc-big { font-size:28px; font-weight:600; letter-spacing:-.8px; line-height:1.2;
  color:var(--ink); }
.lc-unit { font-size:11px; color:var(--muted); margin-top:2px; }

.lc-page-title { font-size:30px; letter-spacing:-.85px; line-height:1.15; font-weight:600;
  margin:4px 0 0; color:var(--ink); }
.lc-page-sub { font-size:13px; color:var(--muted); margin:6px 0 0; }
.lc-updated { color:var(--soft); font-size:12px; text-align:right; padding-top:14px; }

.lc-metric { border:1px solid var(--line); background:#fff; border-radius:8px; min-height:126px;
  padding:17px 18px; height:100%; }
.lc-metric.primary { border-color:#BCCBEC; box-shadow: inset 3px 0 var(--navy); }
.lc-metric-label { font-size:13px; font-weight:600; color:#475569; }
.lc-metric-value { font-size:31px; font-weight:600; letter-spacing:-1px; margin-top:10px;
  line-height:1.13; color:var(--ink); font-variant-numeric: tabular-nums; }
.lc-metric-value small { font-size:14px; letter-spacing:0; color:var(--muted); font-weight:500; }
.lc-metric-help { color:var(--muted); font-size:12px; margin-top:7px; }
.lc-metric-help strong { color:var(--navy); font-weight:600; }
.lc-metric-help strong.bad { color:#B91C1C; }

.lc-card-title { font-size:16px; line-height:1.3; font-weight:600; margin:0; color:var(--ink); }
.lc-card-sub { font-size:12px; color:var(--muted); margin:3px 0 0; }
.lc-legend { display:flex; gap:15px; color:var(--muted); font-size:11px; justify-content:flex-end;
  padding-top:4px; }
.lc-key { display:flex; align-items:center; gap:6px; }
.lc-swatch { width:15px; height:3px; border-radius:4px; display:inline-block; }
.lc-foot { display:flex; justify-content:space-between; font-size:11px; color:var(--soft); }
.lc-foot b { color:#475569; font-weight:600; }

.lc-event { display:flex; gap:10px; padding:11px 0; border-top:1px solid #EEF2F6; }
.lc-event-date { flex:0 0 46px; font-size:11px; font-weight:600; color:var(--muted);
  padding-top:1px; }
.lc-event-body { flex:1; min-width:0; }
.lc-event-body b { font-size:12px; font-weight:600; display:block; color:var(--ink); }
.lc-event-body small { display:block; color:var(--soft); font-size:11px; margin-top:2px; }
.lc-event-amount { font-size:12px; font-weight:600; white-space:nowrap; color:var(--ink);
  font-variant-numeric: tabular-nums; }
.lc-event-amount.positive { color:var(--navy); }

.lc-table { width:100%; border-collapse:collapse; font-size:13px; font-variant-numeric:tabular-nums;
  margin-top:10px; }
.lc-table th { color:var(--muted); background:#F8FAFC; font-size:12px; font-weight:600;
  text-align:right; padding:8px 11px; border-top:1px solid var(--line);
  border-bottom:1px solid var(--line); }
.lc-table th:first-child, .lc-table td:first-child { text-align:left; }
.lc-table td { padding:9px 11px; border-bottom:1px solid #EEF2F6; text-align:right; color:#334155; }
.lc-table td:first-child { font-weight:600; color:var(--ink); }
.lc-table td:last-child { font-weight:600; color:var(--navy); }
.lc-table tr:last-child td { border-bottom:0; }
.lc-mini { font-size:11px; color:var(--muted); text-align:right; padding-top:4px; }
</style>
"""

_LOGO = (
    '<div class="lc-logo"><div class="lc-mark"><i style="height:9px"></i><i style="height:5px">'
    '</i><i style="height:12px"></i><i style="height:8px"></i></div>'
    "<span>LifeCFO <em>AI</em></span></div>"
)

_EVENT_LABELS = {
    EventKind.INCOME: "Income",
    EventKind.ESSENTIAL_EXPENSE: "Essentials",
    EventKind.DEBT_MINIMUM: "Debt minimum",
    EventKind.FLEXIBLE_EXPENSE: "Flexible spending",
    EventKind.SAVINGS_TRANSFER: "Planned transfer",
    EventKind.EXTRA_DEBT_PAYMENT: "Extra repayment",
}


def baht_text(satang: int) -> str:
    """Whole baht with separators, e.g. 33,000. Satang are shown only when present."""
    whole, frac = divmod(abs(satang), SATANG_PER_THB)
    sign = "-" if satang < 0 else ""
    return f"{sign}{whole:,}" + (f".{frac:02d}" if frac else "")


def short_date(day: date) -> str:
    return f"{day.day} {day:%b}"


def month_label(month: str) -> str:
    """'2026-11' -> 'Nov 2026'."""
    year, number = month.split("-")
    return f"{date(int(year), int(number), 1):%b} {year}"


def apply_styles() -> None:
    st.html(_CSS)


def sidebar_brand(as_of: date, horizon_label: str) -> None:
    st.html(
        _LOGO
        + '<div class="lc-kicker">Current workspace</div>'
        f'<div class="lc-plan"><div><b>Personal plan</b>'
        f"<small>Sandbox date {short_date(as_of)} {as_of.year} · {escape(horizon_label)}</small>"
        "</div></div>"
    )


def page_header(title: str, subtitle: str, as_of: date) -> None:
    left, right = st.columns([4, 1], vertical_alignment="top")
    with left:
        st.html(
            '<div class="lc-kicker">LifeCFO AI / Your plan</div>'
            f'<div class="lc-page-title">{escape(title)}</div>'
            f'<div class="lc-page-sub">{escape(subtitle)}</div>'
        )
    with right:
        st.html(f'<div class="lc-updated">Sandbox date {as_of.isoformat()}</div>')


def metric_card(label: str, value: str, help_html: str = "", *, unit: str = "THB",
                primary: bool = False) -> None:
    unit_html = f" <small>{escape(unit)}</small>" if unit else ""
    st.html(
        f'<div class="lc-metric{" primary" if primary else ""}">'
        f'<div class="lc-metric-label">{escape(label)}</div>'
        f'<div class="lc-metric-value">{escape(value)}{unit_html}</div>'
        f'<div class="lc-metric-help">{help_html}</div></div>'
    )


def card_head(title: str, subtitle: str = "") -> None:
    sub = f'<div class="lc-card-sub">{escape(subtitle)}</div>' if subtitle else ""
    st.html(f'<div class="lc-card-title">{escape(title)}</div>{sub}')


def chart_legend() -> None:
    st.html(
        '<div class="lc-legend">'
        f'<span class="lc-key"><span class="lc-swatch" style="background:{NAVY}"></span>'
        "Total cash</span>"
        f'<span class="lc-key"><span class="lc-swatch" style="background:{TEAL}"></span>'
        "Unallocated</span></div>"
    )


def chart_foot() -> None:
    st.html(
        '<div class="lc-foot"><span><b>Blue</b> includes reserved envelopes</span>'
        "<span><b>Teal</b> is cash not yet assigned</span></div>"
    )


def upcoming_events(events: list[CashEvent]) -> None:
    rows = []
    for event in events:
        positive = event.kind is EventKind.INCOME
        sign = "+" if positive else "−"
        rows.append(
            '<div class="lc-event">'
            f'<div class="lc-event-date">{short_date(event.on)}</div>'
            f'<div class="lc-event-body"><b>{escape(event.name)}</b>'
            f"<small>{_EVENT_LABELS[event.kind]}</small></div>"
            f'<div class="lc-event-amount{" positive" if positive else ""}">'
            f"{sign}฿{baht_text(event.amount)}</div></div>"
        )
    if not rows:
        rows.append('<div class="lc-event"><div class="lc-event-body">'
                    "<small>No scheduled events in this horizon.</small></div></div>")
    st.html("".join(rows))


def monthly_table(months: list[MonthSummary]) -> None:
    columns = [("Income", "income"), ("Essentials", "essential")]
    if any(m.debt_minimum for m in months):
        columns.append(("Debt minimum", "debt_minimum"))
    columns += [("Flexible", "flexible"), ("Transfers", "transfers")]
    if any(m.extra_debt for m in months):
        columns.append(("Extra debt", "extra_debt"))
    columns += [("Unallocated", "closing_unallocated"), ("Closing cash", "closing_total_cash")]

    head = "".join(f"<th>{label}</th>" for label, _ in columns)
    body = "".join(
        f"<tr><td>{month_label(m.month)}</td>"
        + "".join(f"<td>{baht_text(getattr(m, field))}</td>" for _, field in columns)
        + "</tr>"
        for m in months
    )
    st.html(f'<table class="lc-table"><thead><tr><th>Month</th>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table>")


def mini_note(text: str) -> None:
    st.html(f'<div class="lc-mini">{escape(text)}</div>')
