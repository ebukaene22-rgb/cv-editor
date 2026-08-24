# Exact-MPN acquisition economics gate

## Pre-registered decision

This gate uses only the 16 identities that passed the exact-MPN eBay US
resolver. It does not expand or retune the cohort.

Pass requires at least four identities with conservative net contribution of
GBP 15, at least two with 20% contribution margin, and at least two with
credible transaction velocity. A strong pass requires at least five viable
identities, three above GBP 20 contribution, and a plausible small-basket path
to GBP 500 per month. Fewer than two viable identities is a kill.

## Source evidence

On 2026-08-24, all 16 eReplacementParts product pages were read directly and
their displayed manufacturer part number was checked against the frozen MPN.
Fifteen were in stock and one was special order. Prices are recorded in
`mpn-source-snapshot.csv`.

The source calculates shipping only after a destination ZIP code is entered in
its cart and ships only to eligible US street addresses. No US prep-centre
address or fulfilment contract is part of this experiment, so source shipping
is explicitly `ADDRESS_QUOTE_REQUIRED`; it is not assumed to be free. See the
official shipping policy at `https://www.ereplacementparts.com/faq/#Shipping`.

Exact eBay sold pages require an authenticated session, and the optional
structured sold-data provider has no configured API key. Sold median, sold p25,
count, recency, and velocity therefore remain unavailable. Active asks are not
relabeled as sold evidence.

## Dominance rule

The current exact, coherent active-listing p25 is used only as a conservative
exit-price proxy. For every identity:

```text
net contribution
<= conservative exit proxy - source price
```

Source shipping, eBay fees, outbound shipping, prep, and expected returns are
all non-negative. Therefore, if the pre-cost spread is already below GBP 15,
the identity cannot meet the contribution threshold under any completion of
the missing costs. Such rows can be rejected without estimating those inputs.

The USD-to-GBP rate was 0.73228. This rule is intentionally harsher than using
the active median because the live markets showed material price dispersion.

## Result

| Measure | Result |
| --- | ---: |
| Resolver survivors tested | 16 |
| In stock at source | 15 / 16 |
| Positive pre-cost spread | 2 / 16 |
| Pre-cost spread at least GBP 15 | 0 / 16 |
| Appliance identities with positive spread | 0 / 10 |
| Best pre-cost spread | GBP 4.79 |
| Median pre-cost spread | GBP -9.53 |
| Rows advanced to full economics | 0 / 16 |

The best row, DeWalt `N097361`, has only USD 6.54 / GBP 4.79 between source
price and active p25 before any delivery, marketplace, fulfilment, or return
cost. Fourteen identities are already negative at this stage. Every appliance
identity is negative; the appliance cohort's best spread is GBP -2.17 and its
median is GBP -19.40.

**Decision: KILL eReplacementParts retail acquisition to eBay US for this
cohort.** The source-to-market pairing cannot meet the first GBP 15 condition,
so sold evidence and detailed cost modelling cannot rescue it.

This does not reverse the MPN resolver pass. Exact-MPN market definition still
works materially better than GTIN resolution, but a full-price OEM retailer is
not a viable acquisition source. The next replacement-parts test, if pursued,
must start with a structurally discounted source such as wholesale, dealer
closeout, liquidation, or used-parts supply while retaining this fixed demand
universe.

## Evidence

- `mpn-source-snapshot.csv`: exact source MPN, live price, and stock state.
- `mpn-economics-ledger.csv`: all 16 rows, active p25 proxy, pre-cost spread,
  net-contribution upper bound, unresolved inputs, and deterministic rejection
  state.
- `mpn-resolution-ledger.csv.gz`: exact active-listing evidence from the prior
  resolver gate.
