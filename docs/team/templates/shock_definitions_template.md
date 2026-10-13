# ShockProof Design

Owner: Member 3. Copy this file to `docs/SHOCKPROOF_DESIGN.md` and fill it in.
Write in English (submission language). Label every number as an assumption
unless it has a source.

## 1. Shock types

Fill one row per shock. "Parameters" are what the user or the simulator sets.

| Shock | What changes in the profile | Parameters | Example | Source or rationale |
|---|---|---|---|---|
| Income reduction | Income amount is multiplied by (1 - p) from a start date | p (%), start date, duration | 20% from 1 Dec for 3 months | |
| Delayed salary | Payday moves later by d days | d, which month | 10 days late in Dec | |
| Emergency medical expense | One-off essential expense | amount, date | 10,000 THB on 12 Nov | |
| Vehicle repair | One-off essential expense | amount, date | | |
| Job loss | Income stops for n months | n, start date | | |
| Increased living costs | Essential expenses multiplied by (1 + p) | p (%), start date | | |
| Unexpected debt obligation | New monthly minimum payment | amount, months | | |
| Multiple simultaneous shocks | Any combination of the above | list | Income -20% and repair 10,000 | |

## 2. Risk indicators and thresholds

These values go into `config/risk_thresholds.yaml`.

| Indicator | Definition | Low risk | Medium risk | High risk | Rationale |
|---|---|---|---|---|---|
| Days until projected cash shortfall | Days from today to the first day unallocated cash is negative | | | | |
| Minimum projected cash balance | Lowest unallocated balance in the horizon | | | | |
| Essential bill coverage | Cash available divided by essentials due in the next 30 days | | | | |
| Emergency reserve adequacy | Reserve divided by one month of essential expenses | | | | |
| Goal completion risk | Goals projected to miss their deadline | | | | |

## 3. Confirmed, hypothetical, and forecast

Describe in two or three sentences each how the product should treat:

- a confirmed event (it happened; the stored plan must change),
- a hypothetical scenario (the user is exploring; nothing is saved),
- a forecast risk (the system noticed it; the user should be warned).

## 4. Assumptions and limits

List what the model ignores (for example interest, inflation, taxes).
