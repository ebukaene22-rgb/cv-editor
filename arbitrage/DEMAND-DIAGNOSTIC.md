# Demand-signal diagnostic — Browse `estimatedSoldQuantity` (2026-08-23)

## 1. The field exists and is usable — no scraping required

eBay's Browse **getItem** returns, per listing:
`estimatedAvailabilities[].estimatedSoldQuantity` — units actually sold.
Verified live on our existing production keyset. This obtains the exact
signal the deleted webpage harvester was built for, through the licensed
API, with no disguise and no login.

Access notes learned by testing:
- **single** `getItem` works; **batch** `getItems?item_ids=` returns
  403 `ACCESS/1100` (higher Buy-API permission tier) — so details cost one
  call per listing.
- Mitigation: identity-filter the SEARCH titles first, fetch details only
  for real matches. Typical candidate spends 1–25 calls of the 5,000/day.
- eBay docs caveat retained: multi-variation listings may aggregate sold
  quantity across variations. Rows are archived per listing so this stays
  visible.

## 2. Diagnostic result on the 20-product labelled universe

Does sold evidence separate known winners from known failures? **No —
not on its own.**

| group | n | with any sold evidence |
|---|---|---|
| winners (SuitCase REAL, Cashmere promising) | 2 | **1/2** |
| known failures | 13 | **3/13** |
| holds / unverified | 3 | 2/3 |

- The one REAL winner shows only **1 unit** sold.
- The biggest sold counts belong to **failures and holds**: Skullcandy 44,
  Chrome Mini Kadet 29, M Dasher 8.
- Coverage is thin: most listings on most products carry no counter at all
  (it only appears on multi-quantity listings), and several products
  returned zero identity-matched listings entirely.

## 3. What this means

Sold quantity answers "does this move?" and it does that honestly — Chrome
and Skullcandy genuinely move. But every one of those movers was
classified a **price_fail**: they sell, at prices that leave no margin.
Demand volume and margin are close to orthogonal in this dataset.

So `estimatedSoldQuantity` is **a real feature, not a decision rule**. It
belongs in the funnel as a cheap veto (no demand anywhere → don't spend a
Product Research lookup) and as the transaction-velocity term the latency
experiment needs. It does not replace sold-PRICE verification, which
remains the human Product Research step.

## 4. Also observed: identity coverage is worse than assumed

Two labelled products returned **zero** identity-matched listings
(Eddy Cardigan, Ridge Daily Driver) and Basecamp 4 returned no listings at
all — the over-restrictive filter defects logged in PROXY-CALIBRATION.md,
now confirmed to cost real coverage. Capers again returned 6/6 "matched"
listings that the human review established are the wrong product. Both
directions of identity error are live.
