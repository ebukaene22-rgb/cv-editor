# Exact-MPN public liquidation coverage gate

Audit time: 2026-08-24 11:10 UTC  
Demand universe: the same 16 exact-MPN eBay resolver survivors  
Sources: B-Stock and Direct Liquidation public live-inventory searches

## Gate

The source class advances to manifest underwriting only if at least three
frozen MPNs appear in currently available lots. Exact search results are only
a coverage signal: any positive lot would still require a downloadable
manifest, exact line-level identity, condition, quantity, landed cost, and
condition-matched exit economics before it could be viable.

## Result

| Source | Exact searches | MPNs with results |
|---|---:|---:|
| B-Stock | 16 | 0 |
| Direct Liquidation | 16 | 0 |
| **Combined** | **32** | **0** |

B-Stock explicitly supports Appliance Parts & Accessories auctions and states
that condition may range from new through salvage, but its category page had no
available lots during the audit. Its public exact searches returned zero for
all 16 MPNs.

Direct Liquidation describes its inventory as customer returns, overstock, and
end-of-life products and exposes public current-inventory search. It also
returned zero for all 16 exact MPNs.

## Decision

**NO_PUBLIC_COVERAGE: do not build manifest economics for this frozen set.**

This result does not prove that manifested liquidation is commercially dead.
It proves that broad public liquidation marketplaces do not currently provide
repeatable acquisition coverage for the already-resolved demand universe. A
future test should run only when a specific dealer, liquidator, or private feed
provides an actual line-level appliance-parts manifest. That manifest should
be checked against the same frozen MPNs before any bidding or account work.

## Evidence

- `mpn-liquidation-coverage.csv`: all 32 exact searches, URLs, timestamps, and
  observed result counts.
- B-Stock appliance-parts category:
  <https://bstock.com/auctions/appliances/appliances-parts-and-accessories/>
- Direct Liquidation:
  <https://www.directliquidation.com/>

Recompute the frozen decision from the evidence snapshot:

```bash
python3 scan.py mpn-liquidation-coverage
```
