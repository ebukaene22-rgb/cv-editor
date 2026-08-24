# The kill pattern — why five mechanisms died the same death (2026-08-24)

Five acquisition mechanisms have now been tested to a documented kill. They
were chosen to be economically independent. They were not.

| # | mechanism | cohort | verdict | proximate cause |
|---|---|---|---|---|
| 1 | Broad retail clearance | 5 cohorts, ~700 comped | 1 viable / ~700 | eBay had already repriced |
| 2 | Fitment / compatibility | 227 candidates | 0 verified | shallow markdowns + identity |
| 3 | Small-goods liquidation | 10 Wyze parcel lots, 46 IDs | KILL_ECONOMICS | auction cleared at market; unit value below floor |
| 4 | Open-box / refurb | 40 reboxed rows, median £795 | KILL_ECONOMICS | refurbisher already captured the condition discount |
| 5 | Bundle decomposition | 8,090 kits surveyed | structurally dead | splitting multiplies fulfilment by N |

## Two independent constraints, not five failures

### A. The unit-value floor (arithmetic)

Fees and fulfilment are near-fixed per unit; margin scales with price. For
£15 contribution at £5 shipping, exit must be ≥ £51 — **at any acquisition
discount**. Mechanisms 3 and 5 died substantially here. Now enforced as a
pre-gate (`unitfloor.py`) so it cannot be rediscovered a sixth time.

### B. The seller-sophistication selection effect (structural)

This is the deeper one, and it was invisible until mechanism 4.

Every source reachable by our automation is reachable **because it publishes
a structured public feed**. Publishing a structured public feed is a property
of a professional e-commerce operation. Professional e-commerce operations
price their inventory competently.

So the property that makes a source *machine-accessible* is correlated with
the property that makes it *efficiently priced*. We were not sampling the
market; we were sampling the subset of the market that had already solved
pricing.

The evidence is that each kill traces to the seller's own competence, not to
our measurement:

- **clearance** — retailer discounts to clear at retail-clearance value, and
  eBay sellers reprice within days (measured: asks decay fast after markdown)
- **liquidation** — auction is a price-discovery mechanism; it clears at
  market by construction. Forced disposal creates structured supply, not a
  structural discount, because competing bidders arbitrage it away.
- **open-box** — the refurbisher's entire business IS capturing the condition
  discount. Buying its output is buying at the end of that value chain.
- **bundles** — a multipack is priced by the same merchant that prices the
  singles, with full knowledge of both.

**Generalised: an intermediary that already specialises in a discount leaves
no spread for a reseller downstream of it.** Every mechanism tested placed us
downstream of exactly such an intermediary.

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
