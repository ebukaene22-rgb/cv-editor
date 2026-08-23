# Which demand market should sit behind the source scanner? (2026-08-23)

Tests A / B / C as specified. B is complete; A is blocked on a signup; C
hit two structural blockers that change the strategic picture.

## Test B — eBay Browse `estimatedSoldQuantity` — COMPLETE

Works on our existing licensed keyset (see DEMAND-DIAGNOSTIC.md). Verdict:
real transaction evidence, but it does **not** discriminate. The one REAL
winner shows 1 unit sold; the largest sold counts (Skullcandy 44, Chrome
29, Dasher 8) all belong to human-verified `price_fail` products. Demand
volume and margin are near-orthogonal here. Use as a cheap veto and as the
velocity term for the latency test; not as a ranking or valuation rule.

## Test A — structured third-party eBay sold rows — BLOCKED ON SIGNUP

sold-comps.com is reachable; the API requires an account key. The
retrospective benchmark (20-30 labelled products -> their individual sold
rows -> OUR identity matcher -> compare against known verdicts) is written
and ready to run the moment a key exists. Their published free tier (100
req/month) covers the whole benchmark at zero cash.

## Test C — Amazon / Keepa — TWO STRUCTURAL BLOCKERS

**C1. We have no GTINs, so deterministic ASIN mapping is impossible.**
Measured across six source stores: **0 of 2,060 variants carry a
barcode/GTIN**. Shopify's public products.json omits the field entirely
(it is Admin-API only). Our identifiers are retailer style codes
(A11718M080, B5C9W-PCQR-M) which are brand-internal, not GTINs. So
mapping source products to ASINs would be brand+model TEXT matching --
the identical fuzzy problem that produced every identity_fail in the
ledger, merely pointed at a different catalogue.

**C2. Amazon forbids Claude agents outright.** Their robots.txt:

    User-agent: Claude-User      Disallow: /
    User-agent: Claude-SearchBot Disallow: /
    User-agent: ClaudeBot        Disallow: /

This is the exact inverse of eBay, which publishes `Allow: /sch/` for
Claude-User. So no direct Amazon page access of any kind, and Test C
would depend entirely on Keepa's paid API as the sole data path.

**Consequence:** the "Amazon is more machine-friendly" intuition is half
right and half wrong. Amazon's CATALOGUE is more machine-friendly
(canonical ASINs, one product page, rank history). Amazon's ACCESS is
strictly less friendly to us than eBay's, and the identity bridge we would
need to reach that catalogue is precisely the bridge we do not have.
Pivoting there costs a Keepa subscription and does not solve identity.

## Comparison

| | A: 3rd-party eBay sold rows | B: Browse sold qty | C: Amazon/Keepa |
|---|---|---|---|
| identity coverage | our matcher, on sold rows | our matcher, on active | **blocked: no GTIN** |
| human intervention | none once keyed | none | high (manual ASIN mapping) |
| demand observability | sold price + count | units only, no price | rank/offer history (strong) |
| valuation accuracy | potentially high | none | high if mapped |
| detects historical failures | testable retrospectively | **no** (measured) | untestable without mapping |
| cost / 1,000 candidates | ~$9/mo tier | £0 | Keepa subscription |
| scalability | good | good | good IF identity solved |
| **status** | ready, needs key | **done** | blocked twice |

## Recommendation

Test A is the only remaining path that could make the demand layer
machine-readable at low cost, and it is one signup away. Run it before any
market pivot: it reuses the labelled ledger as its answer key, so it
validates or kills itself in a single afternoon with no new cohorts and no
manual eBay research.

Do not pivot to Amazon on current evidence. The blocker there is not
opportunity density, it is that we cannot identify our own products in
their catalogue -- and no subscription fixes that. If a GTIN source ever
appears (supplier feeds, distributor catalogues, brand press kits), C
becomes worth revisiting immediately, because its demand data really is
better.
