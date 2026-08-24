# Exact-MPN used/open-box source gate

Audit time: 2026-08-24 10:49 UTC  
Demand universe: the same 16 exact-MPN eBay resolver survivors  
Acquisition source: Neu Appliance Parts public Shopify catalogue  
Exit market: eBay US active fixed-price listings

## Pre-registered gate

Advance a source class only when at least three SKUs have all of:

- exact MPN identity;
- condition-matched eBay depth of at least three coherent listings;
- at least GBP 15 spread before still-unresolved costs;
- enough remaining evidence to test repeatability and full economics.

The pre-cost spread is an upper bound. Source shipping, outbound postage,
eBay fees, returns, and sold velocity are deliberately not estimated when a
row already fails identity, market depth, or the GBP 15 dominance test.

## Identity rules

The source MPN must come from the dedicated `Part Number` field. A title-only
match is rejected. Brand must either match exactly or belong to one of two
pre-approved corporate families:

- Frigidaire / Electrolux. Electrolux Group lists both as group brands.
- Whirlpool / Maytag. Whirlpool Corporation lists both in its brand portfolio.

These aliases do not relax the MPN rule. Each accepted row still requires the
same canonical part number in the source's dedicated field.

Condition matching is also exact by family. New, open-box, certified
refurbished, and used variants are valued only against their corresponding
eBay condition ID. The earlier new-item market prices are not reused.

## Result

| Metric | Result |
|---|---:|
| Frozen demand identities | 16 |
| Exact source catalogue matches | 6 |
| Currently available identities | 4 |
| Available condition variants | 5 |
| Variants with >=3 coherent condition-matched listings | 1 |
| Variants clearing GBP 15 before costs | 0 |

The only deep condition-matched market was Frigidaire `154825001`, open box:

- source price: USD 45.00;
- active exact-condition p25: USD 21.95;
- pre-cost spread: USD -23.05 / GBP -16.88.

GE `WR32X10885` had two coherent open-box listings and a zero pre-cost spread.
The other three available variants had no usable exact-condition market.

## Decision

**KILL_SOURCE: Neu Appliance Parts retail used/open-box/refurbished inventory.**

This does not kill exact-MPN demand mapping or distressed supply generally.
It shows that this particular structured secondary retailer does not provide
the required combination of frozen-universe coverage, condition-matched exit
depth, and acquisition discount. The next valid source test needs a manifested
closeout or liquidation feed, or a repeatable dealer-surplus catalogue, using
the same demand universe and the same three-SKU gate.

## Evidence

- `mpn-used-source-ledger.csv`: five available source-condition variants and
  their exact eBay condition-market evidence.
- Electrolux Group brand source:
  <https://www.electroluxgroup.com/en/category/about/>
- Whirlpool Corporation brand source:
  <https://www.whirlpoolcorp.com/our-company.html>
