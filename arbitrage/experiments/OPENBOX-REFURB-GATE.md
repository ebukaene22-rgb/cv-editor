# Open-box / refurb gate — £50–£200 discipline applied at £700+ (2026-08-24)

Audit date: 2026-08-24
Source: reboxed.co (UK refurbisher, public Shopify feed)
Exit market: eBay UK active fixed-price, **condition-matched** (conditionIds
2750 Excellent-Refurbished / 3000 Used — never NEW)
Verdict: **KILL_ECONOMICS**

## Why this cohort is a fair test of the mechanism

It clears every objection raised against the small-goods liquidation cohort:

- **Unit value far above the floor.** Cohort median buy £795, band £670–£1,044.
  The unit-value floor for £15 contribution at £5 shipping is £51. Fulfilment
  is ~0.6% of value here, versus 47–100% in the Wyze cohort.
- **Explicit condition segmentation at source** (Pristine / Excellent / Great /
  Good / New Battery / Standard Battery) matched to eBay condition IDs.
- **Deterministic identity**: brand + model + generation + storage + colour.
- Frozen before any eBay query. 40 rows, SHA-256
  `a5acf8640b385f63ac89eb8ff94fba25e1770b2bd9c3deee0350326e2eb2e3cf`.

## Result: 0 / 30

| status | n |
|---|---:|
| REJECT_CM | 22 |
| NO_MATCH | 8 |
| **PASS** | **0** |

Not one row was rejected by the unit-value floor — every matched product's
eBay p25 cleared £51 comfortably. **They failed on spread.** Every single
contribution is deeply negative:

| product | source buy | eBay p25 (cond-matched) | CM |
|---|---:|---:|---:|
| Galaxy Z Fold7 5G 1TB (Good) | £916 | £950 | **-£51** |
| Tab S9 Ultra 1TB (Good) | £792 | £799 | **-£66** |
| Tab S10+ WiFi 512GB (Excellent) | £730 | £720 | **-£77** |
| Galaxy S25 Ultra 1TB (Excellent) | £760 | £710 | **-£115** |
| iPhone 15 Pro 256GB (New Battery) | £759 | £415 | **-£386** |

Best case in the entire cohort is -£51. The source is not selling below the
condition-matched resale market; it is selling **at or above** it.

## Interpretation

This is the cleanest mechanism kill yet, precisely because unit value cannot
be blamed. A professional refurbisher prices its output *at* the refurbished
market — that is its business. Buying refurbished retail to resell
refurbished is not arbitrage; the refurbisher has already captured the
condition discount between broken/traded-in acquisition and refurbished
resale. There is no second discount left for us.

The generalisable rule: **an intermediary that already specialises in the
condition discount leaves no spread for a reseller downstream of it.** Any
open-box/refurb source that is itself a refurbishing business is
structurally dead for this purpose. A test of the mechanism would need
open-box stock sold by a party whose business is NOT refurbishment —
manufacturer outlet clearing returns, or retailer ex-display — where
disposal, not margin, is the objective.

## Status of the mechanism

Not a full kill of open-box, but a kill of **refurbisher-as-source**, which
is the only open-box substrate with a public machine-readable feed we located
(13 of 14 probed refurb/outlet domains expose no product feed at all).
Without a non-refurbisher open-box feed, this mechanism is not testable at
automation scale.

## Evidence
- `openbox-universe.csv` — frozen 40-row cohort
- `openbox-economics.csv` — condition-matched resolution + economics, 30 rows
