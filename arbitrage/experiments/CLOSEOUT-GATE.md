# Dealer closeout gate — KILL_SELF_COMP

**Verdict: 0/30 survive.** The gate reported 10 PASS. Adversarial verification
killed all ten: nine were the source's own eBay listing, one was a missing
landed-cost term.

This was the falsifiable prediction recorded in `KILL-PATTERN.md` — that dealer
closeout would behave differently from the five already-killed mechanisms. It
did behave differently. It failed for a new reason.

## Cohort

40 MPN-identified in-stock rows from `serverpartdeals.com`, `itinstock.com`,
`tier1online.com`. Band £598–799, median £712. Frozen before resolution:

    closeout-universe.csv
    sha256 7ca048b0ffd0b72c539aa8aec9cdd6e8341f371ffea25c5968b20969f6bfb6e4

30 reached the economics stage. Gate order, pre-registered: unit-value floor
first (CM ≥ £15 at £8 outbound ⇒ exit ≥ £57), then MPN-exact title matching,
then condition-tolerant resolution (`conditionIds:{3000|2750|1000}`),
then economics at `category="computers"` (eBay's *lowest* FVF band — every
number below is therefore conservative), £8 out, £5 in, 10% return reserve.

## As-run result

    PASS 10 | REJECT_CM 10 | BELOW_FLOOR 5 | NO_MPN_MATCH 5

By source: itinstock 9 PASS of 22, serverpartdeals 1 of 4, tier1online 0 of 4.

Top PASSes ran +£93 to +£128 contribution. After five consecutive mechanism
kills this is exactly the result that should not be believed on sight.

## What broke it

Two things in the PASS block were wrong-looking before anything was re-queried:

* six of ten had `n_exact = 1` — a single comp;
* `p25 / source_price` was **1.263158 to six figures** on eight separate
  products (960/760, 984/779, 924/731.5, 900/712.5, 840/665).

A market does not price eight unrelated parts at one identical multiple of one
dealer's web price. Re-querying Browse with the seller field attached
(`closeout-selfcomp-audit.csv`, 21 comps across the 10 PASSes) explained it:

| MPN | gate p25 | seller setting p25 | independent? |
|---|---|---|---|
| TSZ1535987 | 960.00 | itinstock | no — sole comp |
| FAN-7130-1U-R | 960.00 | itinstock | no — sole comp |
| P9K04A | 960.00 | itinstock | no — sole comp |
| CA07670-E236 | 960.00 | itinstock | no — sole comp |
| CA08226-E906 | 984.00 | itinstock | no — sole comp |
| P9K08A | 924.00 | itinstock | no (other comp: etontech 1670) |
| 55949BX | 900.00 | itinstock | no (all 3 comps itinstock) |
| QFX10000-RE | 900.00 | itinstock | no (all 3 comps itinstock) |
| N9K-C93108TC-FX | 840.00 | itinstock | no (nearest independent: 965) |
| VCNRTXA4000 | 791.24 | haubrich-it | **yes** |

**9 of the 10 p25s were published by itinstock — the same seller whose website
supplied the buy price.** The 1.263158 constant is itinstock's own dual-channel
markup: web price ÷ 0.7917, sized to cover eBay fees and VAT on those fees.
The gate measured a seller's fee markup and reported it as arbitrage.

That is not a spread you can take:

* the dealer holds the unit at a cost basis lower than yours by exactly the
  markup you are trying to capture, and can reprice below you at will;
* the dealer is already in the exit venue with the listing live — if it sold at
  £960, it would have sold for them;
* with n=1 the comp is one ask by one seller, with no evidence anyone pays it.

## The one independent row also fails

`VCNRTXA4000` (PNY RTX A4000) is the only PASS with genuinely independent
comps — three EU/DE sellers, none of them serverpartdeals. It fails on a
different defect: the gate set `buy_gbp = price_usd × fx` and modelled no
landed cost for a US → GB physical import.

    freight (US→UK)      non-VAT-reg CM      VAT-registered CM
             £0                 +16.26                  +12.08
            £10                  +4.26                   +2.08
            £25                 -13.74                  -12.92
            £40                 -31.74                  -27.92
            £60                 -55.74                  -47.92

Break-even (CM ≥ £15, £25 freight) needs an exit of **£822.51**. The best
independent comp observed is £791.24 — and that one is a German-marketplace
listing whose headline price is not the GB-delivered price. Even at *zero*
freight, which is not a thing that happens to a boxed GPU crossing the
Atlantic, contribution is £16.26 against a £15 target.

## Guards added

`arbitrage/selfcomp.py`, with `test_selfcomp.py` pinned to this cohort:

1. **`is_self_comp(source_domain, seller)`** — name matching, noise-suffix
   tolerant (`itinstock-uk`, `itinstock_store`, `itinstock2024` all match;
   `haubrich-it`, `inetgrouponline`, `etontech`, `partsbuego` do not). This is
   a **lower bound**: a source trading on eBay under an unrelated handle is
   invisible to it. It proves presence, never absence.
2. **`fixed_ratio_sellers(rows)`** — structural and name-blind. Flags any
   seller whose comp/source ratio is constant across ≥3 distinct products.
   On this cohort it independently recovers `itinstock @ 1.263158, n=9` with
   no false positives. This is the detector that generalises.

`clean_comp(..., source_domain=...)` now strips self-comps before computing
p25 and reports what it dropped in a `self_comps` field. Comps with no seller
attached are **kept and counted as `unattributed`** — silence about the seller
is not evidence of independence, and the caller has to see how much of the set
could not be checked. `comp.py` now captures `seller.username` and the comp
cache version is bumped to `v4`, because a cached payload without a seller
cannot be audited.

## What this changes

The prediction in `KILL-PATTERN.md` was that dealer closeout would evade
causes (A) unit-value floor and (B) seller sophistication. It did. Nine of
these rows cleared the floor honestly — £665–779 units are well above the
£57 threshold — and the sources are not sophisticated repricers.

They failed on a third cause, **(C) the comp is the source**, which had been
invisible in every prior cohort because every prior cohort returned zero
PASSes. Causes (A) and (B) were killing rows before (C) could show itself.

Cause (C) may be *selected for* by the same thing that makes a source
machine-readable: a dealer with a clean product feed and stable MPNs has the
operational maturity to run an eBay store. If so, the better a source looks to
the scanner, the more likely it already occupies the exit venue, and (B) and
(C) share a root.

Stated as a hypothesis rather than a finding, because the evidence is thin in
a specific way: **22 of the 30 rows, and all nine self-comps, are itinstock.**
This cohort establishes that one dual-channel dealer can manufacture ten
false PASSes. It does not establish how common dual-channel dealers are.

**Cheap next measurement:** resolve each of the 69 stores in `stores.txt`
against its own eBay handle and count SKU overlap. That gives a base rate
directly, without spending another cohort.

**Falsifiable prediction, for the next mechanism tested:** a source whose
catalogue is clean enough to resolve by identifier will already be present in
the exit venue for a material share of the same SKUs. A mechanism is more
likely to survive if it sources from somewhere structurally barred from the
exit venue — not merely absent from it.

## Reproduce

    python3 -m unittest arbitrage.test_selfcomp -v
    # audit ledger, 21 comps with seller attribution:
    #   arbitrage/experiments/closeout-selfcomp-audit.csv
