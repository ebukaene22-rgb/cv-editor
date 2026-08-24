# Exact-MPN public liquidation title-search screen

Audit time: 2026-08-24 11:10 UTC  
Demand universe: the same 16 exact-MPN eBay resolver survivors  
Sources: B-Stock and Direct Liquidation public live-inventory searches

## Scope

This was a discovery screen, not a manifest-content test. Marketplace title
search may not index the models inside an attached lot manifest. Zero search
results therefore cannot close manifested liquidation or establish that a
frozen MPN is absent from available lots.

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

## Corrected decision

**TITLE_SEARCH_INCONCLUSIVE.**

The result only says the frozen identifiers did not appear in public lot
titles. The valid experiment is the line-level audit now recorded in
`MPN-MANIFEST-GATE.md` and `mpn-manifest-ledger.csv`.

## Evidence

- `mpn-liquidation-coverage.csv`: all 32 exact searches, URLs, timestamps, and
  observed result counts.
- B-Stock appliance-parts category:
  <https://bstock.com/auctions/appliances/appliances-parts-and-accessories/>
- Direct Liquidation:
  <https://www.directliquidation.com/>

Recompute the title-search summary from the evidence snapshot:

```bash
python3 scan.py mpn-liquidation-coverage
```
