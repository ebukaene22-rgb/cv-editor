# The kill pattern — six mechanisms, three causes (2026-08-24)

Six acquisition mechanisms have now been tested to a documented kill. They
were chosen to be economically independent. They were not.

| # | mechanism | cohort | verdict | proximate cause |
|---|---|---|---|---|
| 1 | Broad retail clearance | 5 cohorts, ~700 comped | 1 viable / ~700 | eBay had already repriced |
| 2 | Fitment / compatibility | 227 candidates | 0 verified | shallow markdowns + identity |
| 3 | Small-goods liquidation | 10 Wyze parcel lots, 46 IDs | KILL_ECONOMICS | auction cleared at market; unit value below floor |
| 4 | Open-box / refurb | 40 reboxed rows, median £795 | KILL_ECONOMICS | refurbisher already captured the condition discount |
| 5 | Bundle decomposition | 8,090 kits surveyed | structurally dead | splitting multiplies fulfilment by N |
| 6 | Dealer closeout / surplus | 30 MPN rows, median £712 | KILL_SELF_COMP | 9/10 PASS comps were the source's own eBay store |

## Three independent constraints, not six failures

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

### C. The comp is the source (measurement)

Found by mechanism 6, and invisible before it — because every earlier cohort
returned zero PASSes, so (A) and (B) were killing rows before (C) could show
itself. Full working in `CLOSEOUT-GATE.md`.

Dealer closeout produced the project's first ten PASSes, at +£93 to +£128
contribution. Nine were the same artefact: **the only eBay listing for the
part was the source's own eBay store**, at a constant 1.263158× its own web
price — a dual-channel markup sized to cover eBay fees and VAT on those fees.
The gate had measured a seller's fee markup and reported it as spread. (The
tenth had independent comps and died on an unmodelled US→GB landed cost.)

That is not a takeable spread. The dealer holds the unit at a cost basis lower
than yours by exactly the markup you are chasing, is already in the exit venue
with the listing live, and can reprice below you at will.

Now guarded two ways in `selfcomp.py`: name matching against the source domain
(a lower bound — it proves presence, never absence), and a name-blind
structural detector that flags any seller whose comp/source ratio is constant
across ≥3 distinct products.

## What this predicts

The prediction recorded here — that dealer closeout would fail *if* feed-
reachable dealers are professional operations — **was confirmed, by a
mechanism the prediction did not anticipate.** Nine of those rows cleared the
unit-value floor honestly, and the sources are not sophisticated repricers.
They failed because the source was standing in the exit venue.

That makes (B) and (C) two faces of one thing. A dealer with a clean product
feed and stable MPNs has the operational maturity to run an eBay store. So the
better a source looks to the scanner, the more likely it already occupies the
exit venue for the same SKUs. **Machine-accessible supply and independent
demand are anti-correlated.**

A mechanism only survives if the seller's objective is **not** price
maximisation, the seller is **not** a pricing specialist, and the seller is
**not already in the exit venue**. That combination is rare and anti-correlates
with having a public feed.

Testable prediction for mechanism seven: any source whose catalogue is clean
enough to resolve by identifier will already be present in the exit venue for
the same SKUs. A mechanism survives only if it sources from somewhere
structurally *barred* from the exit venue — not merely absent from it.

If that holds, the honest conclusion is not "try mechanism eight". It is that
**automated public-feed sourcing and mispriced supply are close to mutually
exclusive** — and any physical-resale business here requires exactly the
relationship-building the project was designed to avoid.

## What survives regardless

The supply-observation infrastructure is sound and independently verified:
69 stores, ~113k variants/scan, depletion telemetry working (619 flips/26h),
restock signal 276/26h, cross-region gaps 155. The finding is about what that
observation is *worth for resale*, not about whether it works.
