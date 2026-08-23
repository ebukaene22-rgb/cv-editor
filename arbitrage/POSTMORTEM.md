# Label post-mortem — cohorts 1–4 (2026-08-23)

35 outcome-classified candidates (`labels-ledger.csv`), 32 human-reviewed,
14 with verified realised prices. Winners: 1 confirmed (Twelve South
SuitCase 16"), 1 promising (Brooklinen Heathered Cashmere King).

## Outcome taxonomy
price_fail 18 · identity_fail 5 · condition_fail 2 · bundle_fail 1 ·
hold 4 · real 1 · promising 1 · unverified 3

Price failure dominates. Identity/condition/bundle failures (8) are
largely already addressed by comp v2 filters; price failure is the
economics of the market itself.

## H1: markdown depth does NOT discriminate
Winners at 50%/60% source discount; fails median 50%, range 12–75%.
Deep markdown is where candidates come from, not what makes them win.

## H2: dislocation separates almost perfectly
Test: realised sold price ABOVE the product's own original list price.
- Both winners: ABOVE (SuitCase £31.15 vs £14.64 list; Cashmere £60 vs £58)
- 13 of 14 fails: below. The exception (Basecamp 4, +0.9%) dies with a
  5% margin: **realised > 1.05 × list** separates perfectly on this sample.

Interpretation: the winning products are ones whose resale price never
depended on the storefront's pricing — the source collapsed while the
resale market didn't reprice. Exactly the advisor's Relative Price
Dislocation formulation. Caveat: n=2 winners; this is a candidate prior,
not a validated model.

## Shortlist-stage rule evaluation (32 reviewed rows)
| rule | reviews | winners kept |
|---|---|---|
| R1 filtered ask-median > 1.2× list | 32→22 | 2/2 |
| R2 clean comps ≥ 3 | 32→18 | 2/2 |
| R3 not purchasable at target-market retail | 32→25 | 2/2 |
| **R1+R2+R3** | **32→9 (72% saved)** | **2/2** |
| R0 null: markdown ≥ 50% | 32→12 | 2/2 |

R0's apparent performance is luck of a tiny sample — H1 shows no
distributional separation, and it keeps fails without any mechanism.
R1+R2+R3 keeps 9 rows: both winners, the Skullcandy hold, and 6 fails of
which 5 are identity/condition types the current comp v2 stack already
rejects. Realistic current-stack estimate: ~4–5 reviews per cohort with
both winners retained.

## Feature notes
- SKU presence: near-universal in shortlists; no discrimination.
- Store/brand: Brooklinen produced both the promising winner and five
  fails — store is not the signal; the product-level dislocation is.
- Competition: winners at 4–10 clean comps (low but not thin).

## Recommended next change (NOT yet implemented)
1. Verification protocol: check realised-vs-original-list FIRST — one
   glance kills most price fails before any economics.
2. Funnel: add R1 (premium vs list) + R2 (n≥3) as shortlist gates and
   surface R3 as a required manual check where no UK feed exists.
3. Then resume cohorts at scale.
