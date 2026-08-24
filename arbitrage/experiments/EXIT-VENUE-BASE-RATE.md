# Exit-venue base rate — INTERIM (2026-08-24)

**Status: incomplete. 21 of 74 rows unresolved, including all four dealers —
the population the question is actually about. No base rate is claimed yet.**

`CLOSEOUT-GATE.md` showed one dual-channel dealer can manufacture ten false
PASSes. It could not show how common such sources are: 22 of those 30 rows
were itinstock. This measures that directly, over the sources the project
scans, before another cohort is spent.

## The question

Cause (C) predicts that a source clean enough to resolve by identifier is
already present in the exit venue for the same SKUs. If that is a property of
*machine-readable sources generally*, the discovery approach is broken. If it
is a property of *dealers specifically*, the finding is narrower and far more
actionable: it says where not to spend discovery budget.

## Resolved so far (53 of 74)

| state | n | share of resolved |
|---|---|---|
| confirmed_active | 0 | 0% |
| candidate_active | 3 | 5.7% |
| dormant | 32 | 60.4% |
| not_detected | 18 | 34.0% |

All 53 are consumer DTC brands. The three candidates:

| domain | handles | listings | brand in titles |
|---|---|---|---|
| rokform.com | `rokform` | 148 | yes |
| gymshark.com | `gymshark`, `gymshark-store` | 64 (63+1, unsplit) | yes |
| fromourplace.co.uk | `fromourplace` | 1 | no |

**Confirmed incidence is 0/53, not 3/53.** No row has independent evidence of
identity, so none may be called confirmed. See "Identity" below.

`hidie_gymshark` was initially counted as Gymshark's and is now
`rejected_reseller`: it matched only because "gymshark" is a substring. A
brand appends to its own name; a reseller prepends its own. Both contain the
brand.

## Identity: both evidence routes, and where they stand

Nothing eBay's Browse API exposes settles identity — feedback, category mix
and brand-heavy titles are all equally consistent with a dedicated reseller.

**Route 1, the brand's own site linking to its eBay store** (`storelink.py`).
That is the source asserting ownership rather than us inferring it. Measured,
and it is nearly empty for this population:

    gymshark.com         4 pages fetched, 0 eBay links
    rokform.com          7 pages fetched, 0 eBay links
    fromourplace.co.uk   4 pages fetched, 0 eBay links
    www.itinstock.com    5 pages fetched, 0 eBay links

itinstock runs 18,839 listings, so this ran as a known-positive check. The
parser is sound (unit-tested against real link shapes); the sites simply do
not link. itinstock's only "ebay" strings are product image filenames
(`product_13546_ebay_*.png`) — suggestive of a shared eBay/Shopify image
pipeline, but no assertion of ownership.

**Route 2, legal business identity.** UK/EU business sellers must publish
trading name, address and company/VAT number on their listings; UK retailers
publish the same on their terms pages. A match is conclusive. Source side
already harvested:

    www.itinstock.com    company 12704142   VAT GB483890250
    www.tier1online.com  company 03708416
    reboxed.co.uk        none found on probed pages

The eBay side is **untested** — the account was rate-limited. If Browse
`getItem` exposes business seller legal info, `confirmed_active` becomes
reachable. If it does not, both routes are closed and every active row stays
`candidate_active` permanently, which is itself a result worth recording.

## Why the run stopped

The sweep exhausted the daily Browse quota at ~2,488 calls. The last 21
domains returned all-HTTP-429 and, because an errored probe was treated as
"handle not real", **quota exhaustion printed as `not_detected`** — including
itinstock, confirmed active minutes earlier in the same session.

That is the fourth instance of one shape in this project: **a failure that
renders as a confident negative.**

| # | failure | rendered as |
|---|---|---|
| 1 | Browse drops an unknown seller filter | "this seller has 9.4M listings" |
| 2 | source's own listing used as a comp | "+£128 contribution" |
| 3 | HTTP 429 on every probe | "not present in the exit venue" |
| 4 | brand links no eBay store | "no eBay store" (route empty, not negative) |

Each was caught only by checking a known positive instead of trusting a
clean-looking zero. The known-positive check is now mandatory before any
output of this script is believed.

## Outstanding

21 rows, marked `inconclusive` and excluded from every denominator:
17 DTC brands (hexclad, skullcandy, jlab, rumpl, thehouseofmarley, umbra,
misen, case-mate, corkcicle, ugmonk, status.co, chromeindustries, hypershop,
moft, materialkitchen, distilunion, shopbala) and **all four dealers**
(itinstock, serverpartdeals, tier1online, reboxed).

## What would make this decisive

Calibration already showed both resolvable dealers active — itinstock 18,839
listings, serverpartdeals 783 on EBAY_US. If that reproduces while DTC settles
at 0–3 of 53 with at most 213 listings across all three candidates, the
contrast is not merely incidence but **intensity**: itinstock alone would hold
roughly 90x the listings of every active consumer brand combined.

That would mean exit-venue contamination is a property of the **source
class**, not of brands generally — and cause (C) narrows from "feed-reachable
sources are compromised" to "identifier-rich dealer sources are compromised,
and those are exactly the ones MPN matching depends on."

The falsifying outcome is equally clean: dealers coming back dormant or
not_detected on a run that passes its known-positive gate.

## Reproduce

    python3 -m unittest arbitrage.test_selfcomp arbitrage.test_storelink -v
    python3 -u -m arbitrage.exitvenue --stores arbitrage/stores.txt \
      --extra www.itinstock.com:GB,www.serverpartdeals.com:US,\
    www.tier1online.com:GB,reboxed.co.uk:GB \
      --out arbitrage/experiments/exit-venue-overlap.csv --resume
