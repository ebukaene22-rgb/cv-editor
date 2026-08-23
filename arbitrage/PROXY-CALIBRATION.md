# Realised-price proxy calibration — first attempt (2026-08-23)

Goal (advisor spec): evaluate lower-tail active-ask proxies (min, p10/p20/
p25, median-of-cheapest-3/5, trimmed) against human-verified sold medians,
vs the current filtered-median × 0.75.

## Headline: the experiment is CONFOUNDED and cannot adjudicate the
## hypothesis with current data

Raw active-listing distributions were never archived at shortlist time
(comp caches were ephemeral), so distributions were re-fetched at analysis
time — days to a week after the sold evidence was gathered. On 7 usable
sold-observed cases:

- Today's active medians UNDERSHOOT the verified solds (median bias −36%),
  the OPPOSITE direction of the shortlist-time overshoot that motivated
  the experiment.
- Every lower-tail proxy does worse (min −69%, p20 −50%, cheapest-3 −46%).
- The one same-time pair (Twelve South: verified while listed) shows
  active median ≈ sold (30.4 vs 31.15) — near-zero error.

Most plausible reading: for clearance goods the active-ask distribution is
HIGHLY NON-STATIONARY — resale sellers reprice downward as source
clearance propagates (Allbirds and Stanley actives are now far below their
mid-August solds, and our own supply data shows those brands' clearances
deepening over exactly this window). Comparing last week's solds with this
week's asks measures drift, not proxy quality.

## What this run still established
1. **Time-alignment is a hard requirement.** Raw clean distributions are
   now archived at comp time (history/comps-*.json.gz) so cohort-5's
   verification produces properly paired data: same-day asks vs solds.
2. **Two identity-filter defects surfaced** (0 clean listings for products
   that demonstrably exist on eBay): the '+'-bundle rule rejects
   "Wallet+Keycase" listings even when the QUERY is itself a kit; and the
   Eddy query's "Merino" token over-restricts. Noted, NOT fixed — the
   pipeline is frozen until cohort 5 is labelled.
3. **Ask non-stationarity is itself signal.** If actives reprice down
   within days of source clearance, then time-since-markdown matters to
   realised price, and early detection (depletion telemetry) is worth
   more than any static proxy.

## Protocol for the real calibration (cohort 5)
Verify the holdout sheet; for each row the same-day archived clean
distribution now exists. Compute all candidate proxies on those paired
rows. Do not retune anything until the cohort is fully labelled.
