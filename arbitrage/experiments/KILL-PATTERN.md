# The kill pattern — why five mechanisms died the same death (2026-08-24)

Five acquisition mechanisms have now been tested to a documented kill. They
were chosen to be economically independent. They were not.

| # | mechanism | cohort | verdict | proximate cause |
|---|---|---|---|---|
| 1 | Broad retail clearance | 5 cohorts, ~700 comped | 1 viable / ~700 | eBay had already repriced |
| 2 | Fitment / compatibility | 227 candidates | 0 verified | shallow markdowns + identity |
| 3 | Small-goods liquidation | 10 Wyze parcel lots, 46 IDs | KILL_ECONOMICS | listed offer too high; unit value below floor |
| 4 | Open-box / refurb | 40 reboxed rows, median £795 | KILL_ECONOMICS | refurbisher already captured the condition discount |
| 5 | Bundle decomposition | 8,090 kits surveyed | blocked | splitting multiplies fulfilment by N |

## Two independent constraints, not five failures

### A. The unit-value floor (arithmetic)

Fees and fulfilment are near-fixed per unit; margin scales with price. For
£15 contribution at £5 shipping and a 40% buy-to-exit ratio requires an exit
of about £51. A better acquisition ratio lowers that threshold. Mechanisms 3
and 5 were substantially constrained here. This scenario is now enforced as a
pre-gate (`unitfloor.py`) so it is not rediscovered a sixth time.

### B. The seller-sophistication selection effect (structural)

This is the deeper one, and it was invisible until mechanism 4.

The sources reached most easily by our automation publish structured public
feeds. That is commonly a property of professional e-commerce operations,
which are also more likely to price inventory competently.

The evidence supports a working hypothesis that machine accessibility is
correlated with efficient pricing. The tests sampled the public-feed subset of
the market, not all distressed or surplus supply; the correlation itself has
not yet been measured independently.

The evidence is that each kill traces to the seller's own competence, not to
our measurement:

- **clearance** — retailer discounts to clear at retail-clearance value, and
  eBay sellers reprice within days (measured: asks decay fast after markdown)
- **liquidation** — the sampled Direct Liquidation lots were listed at offer
  prices that left no spread. No auction-winning-price series was observed, so
  bidder competition remains a plausible explanation rather than a measured
  result.
- **open-box** — the refurbisher's entire business IS capturing the condition
  discount. Buying its output is buying at the end of that value chain.
- **bundles** — a multipack is priced by the same merchant that prices the
  singles, with full knowledge of both.

**Working generalisation: an intermediary that already specialises in a
discount is unlikely to leave spread for a reseller downstream of it.** The
professional-refurbisher cohort directly supports this; the broader claim
remains falsifiable.

## What this predicts

A mechanism only survives if the seller's objective is **not** price
maximisation AND the seller is **not** a pricing specialist. That combination
is rare, and — critically — it anti-correlates with having a public feed.

Testable prediction for the next mechanism: dealer closeout / surplus will
fail *if* the dealers reachable by feed are professional e-commerce
operations, and can only succeed via sources that are not machine-readable
(phone, email, trade portals, relationships).

If that prediction holds, the honest conclusion is not "try mechanism seven".
It is that **automated public-feed sourcing and mispriced supply are close to
mutually exclusive** — and any physical-resale business here requires exactly
the relationship-building the project was designed to avoid.

## What survives regardless

The supply-observation infrastructure is sound and independently verified:
69 stores, ~113k variants/scan, depletion telemetry working (619 flips/26h),
restock signal 276/26h, cross-region gaps 155. The finding is about what that
observation is *worth for resale*, not about whether it works.
