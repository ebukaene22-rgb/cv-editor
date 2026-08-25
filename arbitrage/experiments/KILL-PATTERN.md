# The kill pattern — six mechanisms, three causes (2026-08-24)

Six acquisition mechanisms have now been tested to a documented kill. They
were chosen to be economically independent. They were not.

| # | mechanism | cohort | verdict | proximate cause |
|---|---|---|---|---|
| 1 | Broad retail clearance | 5 cohorts, ~700 comped | 1 viable / ~700 | eBay had already repriced |
| 2 | Fitment / compatibility | 227 candidates | 0 verified | shallow markdowns + identity |
| 3 | Small-goods liquidation | 10 Wyze parcel lots, 46 IDs | KILL_ECONOMICS | listed offer too high; unit value below floor |
| 4 | Open-box / refurb | 40 reboxed rows, median £795 | KILL_ECONOMICS | refurbisher already captured the condition discount |
| 5 | Bundle decomposition | 8,090 kits surveyed | blocked | splitting multiplies fulfilment by N |
| 6 | Dealer closeout / surplus | 30 MPN rows, median £712 | KILL_SELF_COMP | 9/10 PASS comps were the source's own eBay store |

## Three independent constraints, not six failures

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

(B) and (C) plausibly share a root. A dealer with a clean product feed and
stable MPNs has the operational maturity to run an eBay store, so a source
that looks good to the scanner may be more likely to already occupy the exit
venue for the same SKUs. **Working hypothesis: machine-accessible supply and
independent demand are anti-correlated.** The evidence for it is one cohort
and, within that cohort, largely one source — 22 of the 30 rows and all nine
self-comps are itinstock. Presence in the exit venue has not been measured
across sources, and that measurement is cheap: resolve each store in
`stores.txt` against its own eBay handle and count SKU overlap. Until then
this is a hypothesis with one supporting case, not a finding.

On that hypothesis a mechanism survives only if the seller's objective is
**not** price maximisation, the seller is **not** a pricing specialist, and
the seller is **not already in the exit venue**.

**Measured, 2026-08-25 — the prediction held.** `EXIT-VENUE-BASE-RATE.md`,
74/74 rows resolved, 0 inconclusive:

| | DTC brands (n=70) | dealer sources (n=4) |
|---|---|---|
| active in exit venue | 4 (5.7%) | 3 (75%) |
| listings | 398 | 19,630 |
| identity-confirmed as the source | 0 | 1 (itinstock) |

itinstock alone holds 47x the listings of every active consumer brand
combined, and its eBay contact email `ebay@itinstock.com` confirms the store
is the source itself. The falsifying outcome — dealers dormant or not_detected
on a run passing its known-positive gate — did not occur.

So (C) is **not** "feed-reachable sources are compromised". It is
**"identifier-rich dealer sources are compromised"** — and those are exactly
the sources MPN matching depends on. The property that makes a source
resolvable by identifier is the property that puts it in the exit venue at
scale. Consumer brands are overwhelmingly absent from it (41 of 70 register a
handle and list nothing at all), but they are also the sources that cannot be
resolved by identifier, which is why the earlier cohorts died on identity
instead.

Caveats: n=4 on the dealer arm, tier1online unresolvable by any enumerated
handle, and every figure is a lower bound since both probes key on the store's
own name.

Standing prediction for mechanism seven: a mechanism is more likely to survive
if it sources from somewhere structurally *barred* from the exit venue — not
merely absent from it.

If that holds, the honest conclusion is not "try mechanism eight". It is that
**automated public-feed sourcing and mispriced supply may be close to mutually
exclusive** — which would mean any physical-resale business here requires
exactly the relationship-building the project was designed to avoid. The
overlap measurement above is the cheapest way to test that before spending
another cohort on it.

## What survives regardless

The supply-observation infrastructure is sound and independently verified:
69 stores, ~113k variants/scan, depletion telemetry working (619 flips/26h),
restock signal 276/26h, cross-region gaps 155. The finding is about what that
observation is *worth for resale*, not about whether it works.
