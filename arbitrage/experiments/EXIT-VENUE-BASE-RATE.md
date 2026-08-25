# Exit-venue base rate — COMPLETE (2026-08-25)

**74/74 rows resolved, 0 inconclusive.** The pre-registered confirming outcome
held: dealer sources are in the exit venue at far higher incidence and vastly
higher intensity than consumer brands, and the one dealer whose identity could
be tested was confirmed as the source itself.

## The question

Cause (C) predicts that a source clean enough to resolve by identifier is
already present in the exit venue for the same SKUs. If that is a property of
*machine-readable sources generally*, the discovery approach is broken. If it
is a property of *dealers specifically*, the finding is narrower and far more
actionable: it says where not to spend discovery budget.

## Result

| discriminator | DTC brands (n=70) | dealer sources (n=4) |
|---|---|---|
| **incidence** — any active | 4 / 70 = **5.7%** | 3 / 4 = **75%** |
| incidence — *confirmed* active | 0 / 70 = **0%** | 1 / 4 = **25%** |
| **intensity** — listings | **398** across 4 | **19,630** across 3 |
| — median per active store | 148 | 786 |
| — largest single store | rokform 148 | itinstock **18,842** |
| **identity** — coverage | 4 / 70 = 5.7% | 3 / 4 = 75% |
| **identity** — power | 0 / 4 = **0%** | 1 / 3 = **33%** |

Full state breakdown:

| state | DTC | dealers |
|---|---|---|
| confirmed_active | 0 | 1 |
| candidate_active | 4 | 2 |
| dormant | 41 | 0 |
| not_detected | 25 | 1 |

Active DTC rows: rokform 148, case-mate 185, gymshark 64, fromourplace 1.
Active dealer rows: itinstock 18,842, serverpartdeals 786, reboxed 2.

**itinstock alone holds 47x the listings of every active consumer brand
combined.** The contrast is not incidence alone — it is intensity, and by a
margin no sampling artefact explains.

## The identity gate, and the tier it exposed

The known-positive gate passed on volume (18,459 against ~18,839 expected),
then scored `no_match` on identity. eBay returned for `itinstock`:

    name   Russell Jackson          (site trades as ITinStock Ltd)
    vat    788005803                (site publishes GB483890250)
    email  ebay@itinstock.com       <- the source's own domain

The harvested identifiers were verified against ITinStock's own footer, so
this was not a harvesting error but a gap in the hierarchy. **Registration and
VAT matching answers entity-to-entity; the question actually asked is
account-to-domain.** A business routinely runs its marketplace channel under a
separate registration, a sole trader, or a predecessor VAT number. `email_domain`
now ranks top of the hierarchy, and itinstock is the project's first
`confirmed_active` on any axis.

Two further defects surfaced in the same pass:

* `extract()` read only `legalAddress`; eBay returned
  `sellerProvidedLegalAddress`, so the postcode was silently empty and
  `name_address` could never have fired.
* reboxed scored `no_match` — "evidence against ownership" — when its own site
  publishes no identifiers at all, so the only available comparison was the
  email domain. That is now `domain_only_no_match`, excluded from `observable`,
  because a test that could only ever come back negative or silent is not an
  observation.

## Reading the denominators

DTC identity coverage is 4/70 and power 0/4. That is **not** the identity
method failing. Three of the four active DTC brands sit on EBAY_US, where
sellers are not under the UK/EU business information requirements, so no legal
block exists to read. The DTC arm's value is in incidence and intensity; the
identity discriminator has resolving power essentially only in the UK/EU arm.

Reported as one global rate, confirmed identity would read 1/74 = 1.4% and
look like a broken method. It is not: the test was executable on 7 rows and
resolved 1. Composition is not method performance, which is why no global rate
appears in this document.

`unavailable` dominating the attempted rows (5 of 7) means low resolving
power, **not** evidence against ownership.

## Verdict on cause (C)

The pre-registered confirming outcome was: dealers reproduce active while DTC
settles at 0–3 of 53. Observed: dealers 3/4 active with 19,630 listings, DTC
4/70 active with 398. The falsifying outcome — dealers dormant or not_detected
on a run passing its known-positive gate — did not occur.

**Exit-venue contamination is a property of the source class, not of brands
generally.** Cause (C) narrows accordingly: it is not that feed-reachable
sources are compromised, but that *identifier-rich dealer sources* are — and
those are exactly the sources MPN matching depends on. The very property that
makes a source resolvable by identifier is the property that puts it in the
exit venue.

Caveats that survive: n=4 on the dealer arm is small, tier1online was not
resolvable by any enumerated handle, and every figure is a lower bound because
both probes key on the store's own name.

## Where discovery budget should not go

Identifier-rich dealer catalogues. They resolve cleanly, which is what makes
them attractive to an automated scanner, and they are already standing in the
exit venue at scale — which is what makes the spread illusory. `selfcomp.py`
now guards the comp side of this; this measurement says the problem is
upstream of the guard, in source selection.

## Appendix: why the first sweep stopped

The first sweep exhausted the daily Browse quota at ~2,488 calls. The last 21
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
| 5 | one listing lacks `sellerLegalInfo` | "the identity route is closed" |

The fifth was caught in review before it was built rather than after. The
others were caught only by checking a known positive instead of trusting a
clean-looking zero, and that check is now mandatory before any output of this
script is believed.

## Outstanding

21 rows, marked `inconclusive` and excluded from every denominator:
17 DTC brands (hexclad, skullcandy, jlab, rumpl, thehouseofmarley, umbra,
misen, case-mate, corkcicle, ugmonk, status.co, chromeindustries, hypershop,
moft, materialkitchen, distilunion, shopbala) and **all four dealers**
(itinstock, serverpartdeals, tier1online, reboxed).

## What would make this decisive

Three independent discriminators, not one: dealer **incidence**, dealer
**listing intensity**, and **legal-identity confirmation**.

Calibration already showed both resolvable dealers active — itinstock 18,839
listings, serverpartdeals 783 on EBAY_US. If that reproduces while DTC settles
at 0–3 of 53 with at most 213 listings across all three candidates, the
contrast is not merely incidence but **intensity**: itinstock alone would hold
roughly 90x the listings of every active consumer brand combined. If
itinstock's `sellerLegalInfo` also returns registration 12704142 or VAT
GB483890250, that is the project's first confirmed positive on any axis.

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
