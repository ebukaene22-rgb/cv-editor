# Liquidation-first exact-identity exit gate

Audit time: 2026-08-24
Source universe: 80 deterministic manifest models with valid GTINs
Exit market: eBay US active fixed-price listings

## Frozen rules

- The 83 manifest-derived models remain separate from the closed 16-MPN parts
  universe.
- Only the 80 identities with check-digit-valid GTINs enter this test.
- One US-oriented GTIN is selected per model; the only dual-GTIN model uses its
  12-digit UPC.
- Source condition maps conservatively: `Used` to used, `Untested Customer
  Returns` to for-parts/not-working, and like-new/open-box to open box.
- A usable market requires exact GTIN confirmation, exact condition, coherent
  item details, and at least three active listings.
- No fuzzy search or manual review fallback is allowed.

## Result

| Source condition family | Identities | Any active result | Usable market |
|---|---:|---:|---:|
| Used | 53 | 0 | 0 |
| For parts / untested | 25 | 0 | 0 |
| Open box / like new | 2 | 0 | 0 |
| **Total** | **80** | **0** | **0** |

All 80 eBay Browse API queries returned `NOT_FOUND` before item-detail
verification. There is therefore no deterministic active exit price, coherent
market depth, or candidate that can advance to sold velocity or lot economics.

## Decision

**KILL_EXIT_RESOLUTION: liquidation GTIN -> condition-matched eBay US.**

Buyer premium, freight, tax, eBay fees, outbound postage, sellable-rate
assumptions, and the mandatory 15% manifest-accuracy haircut were not estimated.
Those costs can only worsen a row and cannot rescue a missing exit market.

This materially downgrades liquidation for the GBP 500/month target. The
source provides excellent structured identity, but eBay does not expose a
condition-matched GTIN market for this inventory. A future liquidation test
would need a different deterministic exit resolver, or a pre-registered exact
model-number architecture; rerunning GTIN against eBay with looser identity or
condition rules is closed.

## Evidence

- `liquidation-exit-resolution.csv.gz`: all 80 source identities, condition
  mappings, query counts, exact-identity counts, prices, and statuses.
- `mpn-manifest-unmatched-identities.csv`: frozen input universe.

Re-run with live eBay credentials:

```bash
python3 scan.py liquidation-exit-audit
```
