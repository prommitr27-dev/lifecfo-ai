"""Presentation helpers for the Streamlit app: page styles and small HTML pieces.

Only formatting lives here. Every number shown is computed by the engines and
passed in as integer satang; nothing in this module does money arithmetic
beyond rounding for display.
"""

import base64
from datetime import date
from html import escape

import streamlit as st

from lifecfo.cashflow.forecast import CashEvent, EventKind, MonthSummary
from lifecfo.domain.money import SATANG_PER_THB

PRIMARY = "#6E5BD6"  # lavender
MINT = "#3FA387"

_CSS = """
<style>
:root { --ink:#2E2A47; --muted:#6E6889; --soft:#A39DBA; --navy:#6E5BD6; --line:#ECE6F5;
  --lav:#EFEAFD; --mint:#DDF3EA; --mint-ink:#2F8F6F; --peach:#FFE6D9; --peach-ink:#C2603A;
  --butter:#FFF3C9; --sky:#E1EEFB; --shadow:0 6px 24px rgba(110,91,214,.08); }
[data-testid="stHeader"] { background: transparent; }
/* Start below Streamlit's header. On Community Cloud its toolbar (Share, GitHub, ...)
   spans the full width and would sit on top of the view tabs, swallowing clicks. */
.block-container { padding-top: 4rem; max-width: 1300px; }
section[data-testid="stSidebar"] { width: 250px !important; min-width: 250px !important; }
section[data-testid="stSidebar"] > div { padding-top: 0.6rem; }

/* Underlined view tabs (the segmented control). */
.st-key-view { width: 100% !important; border-bottom: 1px solid var(--line);
  margin-bottom: 0.4rem; }
.st-key-view [role="radiogroup"] { gap: 0.5rem; flex-wrap: wrap; }
.st-key-view { border-bottom: 0 !important; }
.st-key-view button {
  border: 0 !important; background: transparent !important; border-radius: 999px !important;
  padding: 0.35rem 0.95rem !important; min-height: 0 !important; color: var(--muted) !important;
  box-shadow: none !important;
}
.st-key-view button p { font-size: 0.875rem; font-weight: 500; }
.st-key-view button[aria-checked="true"] {
  color: var(--navy) !important; background: var(--lav) !important;
}
.st-key-view button[aria-checked="true"] p { font-weight: 600; }
.st-key-horizon button { min-height: 1.9rem !important; padding: 0 0.8rem !important; }
.st-key-horizon button p { font-size: 0.8rem; }
[data-testid="stSidebarHeader"] { height: 2.2rem; min-height: 0; padding-top: 0.6rem; }

/* Alerts read as calm status bars. */
[data-testid="stAlert"] > div { border: 1px solid transparent; }
[data-testid="stAlertContentSuccess"] { color: #166534; }

/* Bordered containers become soft white cards. */
[data-testid="stVerticalBlockBorderWrapper"] { background: #FFFFFF; border-radius: 22px;
  box-shadow: var(--shadow); }
[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] { background: #FFFFFF; }

.lc-logo { display:flex; gap:10px; align-items:center; margin: 0 0 1.4rem; }
.lc-mark { width:31px; height:31px; border-radius:11px; background:var(--navy); color:#fff;
  display:flex; align-items:flex-end; justify-content:center; gap:3px; padding-bottom:9px; }
.lc-mark i { width:2px; background:#fff; border-radius:2px; display:block; }
.lc-logo span { font-size:18px; font-weight:700; letter-spacing:-.5px; color:var(--ink); }
.lc-logo em { font-style:normal; color:var(--navy); font-weight:500; }
.lc-kicker { text-transform:uppercase; letter-spacing:1.3px; color:var(--soft);
  font-size:10px; font-weight:700; }
.lc-plan { padding:12px; margin:8px 0 1.2rem; border-radius:16px; background:#FFFFFF;
  display:flex; gap:10px; align-items:center; }
.lc-plan b { font-size:13px; font-weight:600; color:var(--ink); }
.lc-plan small { display:block; font-size:11px; color:var(--muted); margin-top:2px; }
.lc-big { font-size:28px; font-weight:600; letter-spacing:-.8px; line-height:1.2;
  color:var(--ink); }
.lc-whatif { background:var(--butter); border-radius:14px; padding:10px 12px; color:#6B5310; }
.lc-whatif span, .lc-whatif small { display:block; font-size:11px; }
.lc-whatif b { display:block; font-size:20px; font-weight:800; color:var(--ink);
  font-variant-numeric:tabular-nums; }
.lc-unit { font-size:11px; color:var(--muted); margin-top:2px; }

.lc-page-head { display:flex; justify-content:space-between; align-items:flex-start;
  gap:12px 20px; flex-wrap:wrap; }
.lc-page-title { font-size:30px; letter-spacing:-.85px; line-height:1.15; font-weight:600;
  margin:4px 0 0; color:var(--ink); }
.lc-page-sub { font-size:13px; color:var(--muted); margin:6px 0 0; }
.lc-updated { color:var(--muted); font-size:12px; white-space:nowrap; padding-top:14px; }

.lc-metric { border:1px solid var(--line); background:#fff; border-radius:20px; min-height:126px;
  padding:17px 18px; height:100%; box-shadow:var(--shadow); }
.lc-metric.primary { background:var(--lav); border-color:#DCD3FA; }
.lc-metric-label { font-size:13px; font-weight:600; color:#475569; }
.lc-metric-value { font-size:31px; font-weight:600; letter-spacing:-1px; margin-top:10px;
  line-height:1.13; color:var(--ink); font-variant-numeric: tabular-nums; }
.lc-metric-value small { font-size:14px; letter-spacing:0; color:var(--muted); font-weight:500; }
.lc-metric-help { color:var(--muted); font-size:12px; margin-top:7px; }
.lc-metric-help strong { color:var(--navy); font-weight:600; }
.lc-metric-help strong.bad { color:#B91C1C; }

.lc-card-title { font-size:17px; line-height:1.3; font-weight:800; margin:0; color:var(--ink); }
.lc-card-sub { font-size:12px; color:var(--muted); margin:3px 0 0; }
.lc-legend { display:flex; gap:15px; color:var(--muted); font-size:11px;
  justify-content:flex-start; padding-top:7px; }
.lc-key { display:flex; align-items:center; gap:6px; }
.lc-swatch { width:15px; height:3px; border-radius:4px; display:inline-block; }
.lc-foot { display:flex; justify-content:space-between; font-size:11px; color:var(--soft); }
.lc-foot b { color:#475569; font-weight:600; }

.lc-event { display:grid; grid-template-columns:46px minmax(0,1fr) auto;
  gap:10px; align-items:start; padding:11px 0; border-top:1px solid #F1ECF8; }
.lc-event-date { flex:0 0 46px; font-size:11px; font-weight:600; color:var(--muted);
  padding-top:1px; }
.lc-event-body { flex:1; min-width:0; }
.lc-event-body b { font-size:12px; font-weight:600; display:block; color:var(--ink); }
.lc-event-body small { display:block; color:var(--soft); font-size:11px; margin-top:2px; }
.lc-event-amount { font-size:12px; font-weight:600; white-space:nowrap; color:var(--ink);
  font-variant-numeric: tabular-nums; }
.lc-event-amount.positive { color:var(--mint-ink); }

.lc-table-wrap { overflow-x:auto; scrollbar-width:thin; }
.lc-table { width:100%; border-collapse:collapse; font-size:13px; font-variant-numeric:tabular-nums;
  margin-top:10px; min-width:760px; }
.lc-table th { color:var(--muted); background:#F6F2FC; font-size:12px; font-weight:600;
  text-align:right; padding:8px 11px; border-top:1px solid var(--line);
  border-bottom:1px solid var(--line); }
.lc-table th:first-child, .lc-table td:first-child { text-align:left; }
.lc-table td { padding:9px 11px; border-bottom:1px solid #F1ECF8; text-align:right; color:#334155; }
.lc-table td:first-child { font-weight:600; color:var(--ink); }
/* Closing cash is the first amount column. */
.lc-table td:nth-child(2) { font-weight:600; color:var(--navy); }
.lc-table tr:last-child td { border-bottom:0; }
.lc-mini { font-size:11px; color:var(--muted); text-align:right; padding-top:4px; }

/* Home page. */
.lc-hello { display:flex; align-items:center; gap:14px; margin:2px 0 6px; }
.lc-hello img { width:64px; height:64px; flex:0 0 64px; }
.lc-hello h1 { font-size:30px; line-height:1.15; font-weight:800; letter-spacing:-.5px;
  margin:0; padding:0; color:var(--ink); }
.lc-hello p { margin:4px 0 0; color:var(--muted); font-size:14px; }
.lc-money { background:linear-gradient(135deg,#F1ECFE 0%,#FBF8F3 100%); border-radius:26px;
  border:1px solid #E6DEFB; padding:24px 26px; display:flex; gap:18px; align-items:center;
  justify-content:space-between; box-shadow:var(--shadow); }
.lc-money-label { font-size:14px; font-weight:700; color:var(--muted); }
.lc-money-value { font-size:46px; font-weight:800; letter-spacing:-1.2px; line-height:1.1;
  color:var(--ink); margin-top:6px; font-variant-numeric:tabular-nums; }
.lc-money-sub { color:var(--muted); font-size:13px; margin-top:4px; }
.lc-money img { width:112px; height:112px; flex:0 0 112px; }
.lc-chip { display:inline-flex; align-items:center; gap:6px; border-radius:999px;
  padding:5px 12px; font-size:12px; font-weight:700; margin-top:12px; }
.lc-chip.ok { background:var(--mint); color:var(--mint-ink); }
.lc-chip.warn { background:var(--peach); color:var(--peach-ink); }
.lc-chip.bad { background:#FDE2E2; color:#B91C1C; }
.lc-chip.info { background:var(--butter); color:#8A6412; }
.lc-row { display:flex; align-items:center; gap:12px; padding:12px 0;
  border-top:1px solid #F1ECF8; }
.lc-row:first-child { border-top:0; }
.lc-ico { width:40px; height:40px; flex:0 0 40px; border-radius:50%; display:flex;
  align-items:center; justify-content:center; font-size:19px; }
.lc-ico.c0 { background:var(--lav); } .lc-ico.c1 { background:var(--mint); }
.lc-ico.c2 { background:var(--peach); } .lc-ico.c3 { background:var(--butter); }
.lc-ico.c4 { background:var(--sky); }
.lc-row-body { flex:1; min-width:0; }
.lc-row-body b { display:block; font-size:14px; font-weight:700; color:var(--ink); }
.lc-row-body small { display:block; font-size:12px; color:var(--muted); margin-top:1px; }
.lc-row-amt { font-size:14px; font-weight:700; color:var(--ink); white-space:nowrap;
  font-variant-numeric:tabular-nums; text-align:right; }
.lc-row-amt small { display:block; margin-top:3px; }
.lc-pill { display:inline-block; border-radius:999px; padding:2px 9px; font-size:11px;
  font-weight:700; background:var(--lav); color:var(--navy); }
.lc-pill.soon { background:var(--peach); color:var(--peach-ink); }
.lc-bar { height:8px; border-radius:99px; background:#F1ECF8; margin-top:7px; overflow:hidden; }
.lc-bar i { display:block; height:100%; border-radius:99px; }
.lc-tip { display:flex; gap:12px; align-items:center; background:var(--butter);
  border-radius:20px; padding:14px 18px; color:#6B5310; font-size:13px; }
.lc-tip img { width:44px; height:44px; flex:0 0 44px; }
/* Motion and touch polish (Emil Kowalski's design-engineering rules): press feedback
   on every button, strong ease-out, only transform/opacity animate, a short one-time
   entrance for the home cards, and no motion when the user asks for reduced motion. */
:root { --ease-out: cubic-bezier(0.23, 1, 0.32, 1); }
html { -webkit-tap-highlight-color: transparent; }
button, [role="button"], [role="radio"] { touch-action: manipulation; }
.stButton button, .stDownloadButton button, .st-key-view button,
[data-testid="stFormSubmitButton"] button {
  transition: transform 160ms var(--ease-out), background-color 150ms ease, color 150ms ease;
}
.stButton button:active, .stDownloadButton button:active, .st-key-view button:active,
[data-testid="stFormSubmitButton"] button:active { transform: scale(0.97); }
@keyframes lc-rise { from { opacity: 0; transform: translateY(8px); } }
.lc-hello, .lc-money, .lc-row, .lc-tip { animation: lc-rise 260ms var(--ease-out) both; }
.lc-money { animation-delay: 40ms; }
.lc-row:nth-child(2) { animation-delay: 30ms; } .lc-row:nth-child(3) { animation-delay: 60ms; }
.lc-row:nth-child(4) { animation-delay: 90ms; }
/* After "Save as my real income": no second entrance. The card stays put, the new
   number and chip fade in, and a soft lavender ring settles around the card. */
@keyframes lc-fade { from { opacity: 0; transform: scale(0.98); } }
@keyframes lc-ring { from { box-shadow: 0 0 0 0 rgba(110,91,214,.35), var(--shadow); }
  to { box-shadow: 0 0 0 14px rgba(110,91,214,0), var(--shadow); } }
.lc-money.lc-updated { animation: lc-ring 900ms var(--ease-out) both; }
.lc-updated .lc-money-value, .lc-updated .lc-money-sub, .lc-updated .lc-chip {
  animation: lc-fade 420ms var(--ease-out) both; transform-origin: left center; }
.lc-updated .lc-money-sub { animation-delay: 60ms; }
.lc-updated .lc-chip { animation-delay: 120ms; }
/* Keep the page fully visible while Streamlit reruns, instead of dimming it. */
[data-stale="true"] { opacity: 1 !important; transition: none !important; }
@media (prefers-reduced-motion: reduce) {
  .lc-hello, .lc-money, .lc-row, .lc-tip { animation: none; }
  .lc-money.lc-updated, .lc-updated .lc-money-value, .lc-updated .lc-money-sub,
  .lc-updated .lc-chip { animation: none; }
  .stButton button, .st-key-view button { transition: background-color 150ms ease; }
  .stButton button:active, .st-key-view button:active { transform: none; }
}
@media (max-width:1100px) {
  .st-key-cash-visuals [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; }
  .st-key-cash-visuals [data-testid="stColumn"] {
    flex:1 1 100% !important; width:100% !important; min-width:100% !important;
  }
}
@media (max-width:700px) {
  /* Leave room for Streamlit's sidebar toggle above the page title. */
  .block-container { padding-top:4rem; padding-left:1rem; padding-right:1rem; }
  .lc-page-title { font-size:27px; }
  .lc-metric { min-height:112px; }
  .lc-money { padding:20px; }
  .lc-money-value { font-size:38px; }
  .lc-money img { width:78px; height:78px; flex-basis:78px; }
  .lc-hello h1 { font-size:25px; }
  /* 16px stops iOS from zooming into the field on focus. */
  input, textarea { font-size:16px !important; }
}
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
    st.html(
        '<div class="lc-page-head"><div>'
        '<div class="lc-kicker">LifeCFO AI / Your plan</div>'
        f'<div class="lc-page-title">{escape(title)}</div>'
        f'<div class="lc-page-sub">{escape(subtitle)}</div></div>'
        f'<div class="lc-updated">Sandbox date {as_of.isoformat()}</div></div>'
    )


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
        f'<span class="lc-key"><span class="lc-swatch" style="background:{PRIMARY}"></span>'
        "Total cash</span>"
        f'<span class="lc-key"><span class="lc-swatch" style="background:{MINT}"></span>'
        "Unallocated</span></div>"
    )


def chart_foot() -> None:
    st.html(
        '<div class="lc-foot"><span><b>Purple</b> includes reserved envelopes</span>'
        "<span><b>Green</b> is cash not yet assigned</span></div>"
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
    columns = [("Closing cash", "closing_total_cash"), *columns,
               ("Unallocated", "closing_unallocated")]

    head = "".join(f"<th>{label}</th>" for label, _ in columns)
    body = "".join(
        f"<tr><td>{month_label(m.month)}</td>"
        + "".join(f"<td>{baht_text(getattr(m, field))}</td>" for _, field in columns)
        + "</tr>"
        for m in months
    )
    st.html(f'<div class="lc-table-wrap" role="region" aria-label="Monthly summary" '
            f'tabindex="0"><table class="lc-table"><thead><tr><th>Month</th>{head}'
            f'</tr></thead><tbody>{body}</tbody></table></div>')


def mini_note(text: str) -> None:
    st.html(f'<div class="lc-mini">{escape(text)}</div>')


# --- Mascot: "Pocket", a small coin with a leaf sprout -------------------------------
# Drawn as SVG and embedded as an <img> data URI, because st.html strips inline <svg>.

_FACES = {
    "hello": ('<circle cx="49" cy="66" r="4.5" fill="#3B3355"/>'
              '<circle cx="71" cy="66" r="4.5" fill="#3B3355"/>'
              '<path d="M52 77 Q60 85 68 77" stroke="#3B3355" stroke-width="3.2" fill="none" '
              'stroke-linecap="round"/>'
              '<path d="M98 58 q10 -6 12 -18" stroke="#8B7CF6" stroke-width="5" fill="none" '
              'stroke-linecap="round"/><circle cx="110" cy="38" r="6" fill="#FFE39A" '
              'stroke="#8B7CF6" stroke-width="3"/>'),
    "happy": ('<path d="M44 67 q5 -7 10 0" stroke="#3B3355" stroke-width="3.2" fill="none" '
              'stroke-linecap="round"/><path d="M66 67 q5 -7 10 0" stroke="#3B3355" '
              'stroke-width="3.2" fill="none" stroke-linecap="round"/>'
              '<path d="M50 76 Q60 88 70 76 Z" fill="#3B3355"/>'
              '<path d="M104 30 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z" fill="#B9AEF8"/>'
              '<path d="M14 40 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z" fill="#9AD9C1"/>'),
    "worried": ('<circle cx="49" cy="67" r="4.5" fill="#3B3355"/>'
                '<circle cx="71" cy="67" r="4.5" fill="#3B3355"/>'
                '<path d="M42 56 l12 4 M78 56 l-12 4" stroke="#3B3355" stroke-width="3" '
                'stroke-linecap="round"/>'
                '<path d="M52 81 q4 -4 8 0 q4 4 8 0" stroke="#3B3355" stroke-width="3" '
                'fill="none" stroke-linecap="round"/>'
                '<path d="M101 44 q4 8 0 11 q-4 -3 0 -11z" fill="#9CC9F5"/>'),
    "thinking": ('<circle cx="49" cy="66" r="4.5" fill="#3B3355"/>'
                 '<circle cx="71" cy="64" r="4.5" fill="#3B3355"/>'
                 '<path d="M54 79 h12" stroke="#3B3355" stroke-width="3.2" '
                 'stroke-linecap="round"/><circle cx="104" cy="34" r="9" fill="#FFF3C9" '
                 'stroke="#E0B341" stroke-width="3"/><path d="M100 46 h8" stroke="#E0B341" '
                 'stroke-width="3" stroke-linecap="round"/>'),
}


def mascot_src(mood: str = "hello") -> str:
    """Data URI of the mascot in one of: hello, happy, worried, thinking."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">'
        '<path d="M60 30 V18" stroke="#3FA387" stroke-width="4" stroke-linecap="round"/>'
        '<ellipse cx="50" cy="16" rx="10" ry="6" fill="#9AD9C1" transform="rotate(-25 50 16)"/>'
        '<ellipse cx="70" cy="13" rx="11" ry="6.5" fill="#7FCFAF" transform="rotate(25 70 13)"/>'
        '<circle cx="60" cy="70" r="40" fill="#FFE39A" stroke="#8B7CF6" stroke-width="4.5"/>'
        '<circle cx="60" cy="70" r="31" fill="none" stroke="#F4CF6B" stroke-width="3"/>'
        '<ellipse cx="40" cy="77" rx="6.5" ry="4" fill="#FFB4C2" opacity=".75"/>'
        '<ellipse cx="80" cy="77" rx="6.5" ry="4" fill="#FFB4C2" opacity=".75"/>'
        + _FACES.get(mood, _FACES["hello"]) + "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _mascot(mood: str, alt: str) -> str:
    return f'<img src="{mascot_src(mood)}" alt="{escape(alt)}">'


def what_if_preview(flexible: int, min_unallocated: int) -> None:
    """Two numbers in the what-if card: spending money this month and the lowest point."""
    low = (f"฿{baht_text(min_unallocated)} spare at the lowest point" if min_unallocated >= 0
           else f"Short by ฿{baht_text(-min_unallocated)} at the lowest point")
    st.html(f'<div class="lc-whatif"><span>Yours to spend this month</span>'
            f'<b>฿{baht_text(flexible)}</b><small>{low}</small></div>')


def home_greeting(name: str, subtitle: str) -> None:
    st.html(f'<div class="lc-hello">{_mascot("hello", "LifeCFO mascot waving")}<div>'
            f"<h1>Hi {escape(name)}, here is your month</h1><p>{escape(subtitle)}</p></div></div>")


def money_card(label: str, amount: int, sub: str, chip_kind: str, chip_text: str,
               mood: str, *, updated: bool = False) -> None:
    """The one big number on the home page, with a status chip and the mascot.

    `updated` swaps the entrance animation for a quiet fade, for the rerun right after
    the user saved a change.
    """
    st.html(
        f'<div class="lc-money{" lc-updated" if updated else ""}"><div>'
        f'<div class="lc-money-label">{escape(label)}</div>'
        f'<div class="lc-money-value">฿{baht_text(amount)}</div>'
        f'<div class="lc-money-sub">{sub}</div>'
        f'<span class="lc-chip {chip_kind}">{escape(chip_text)}</span></div>'
        f'{_mascot(mood, "LifeCFO mascot")}</div>'
    )


def icon_rows(rows: list[dict]) -> None:
    """Rows of icon + title + note + right-hand value; optional progress bar.

    Each row: icon, title, note, value (HTML-safe text), color index, and optional
    pill (text, soon flag) or percent (0-100) for a bar.
    """
    html = []
    for i, row in enumerate(rows):
        color = row.get("color", i) % 5
        bar = ""
        if row.get("percent") is not None:
            fill = ["#8B7CF6", "#3FA387", "#E28A5B", "#E0B341", "#6FA8E8"][color]
            bar = (f'<div class="lc-bar"><i style="width:{min(100, max(2, row["percent"]))}%;'
                   f'background:{fill}"></i></div>')
        pill = ""
        if row.get("pill"):
            pill = (f'<small><span class="lc-pill{" soon" if row.get("soon") else ""}">'
                    f'{escape(row["pill"])}</span></small>')
        html.append(
            f'<div class="lc-row"><div class="lc-ico c{color}">{row["icon"]}</div>'
            f'<div class="lc-row-body"><b>{escape(row["title"])}</b>'
            f'<small>{escape(row["note"])}</small>{bar}</div>'
            f'<div class="lc-row-amt">{escape(row["value"])}{pill}</div></div>'
        )
    if not html:
        html.append('<div class="lc-row"><div class="lc-row-body"><small>Nothing here yet.'
                    "</small></div></div>")
    st.html("".join(html))


def tip(text: str, mood: str = "thinking") -> None:
    st.html(f'<div class="lc-tip">{_mascot(mood, "LifeCFO mascot")}<div>{escape(text)}</div>'
            "</div>")
