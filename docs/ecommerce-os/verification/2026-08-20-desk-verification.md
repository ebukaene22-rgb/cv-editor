# Desk Verification Log — 2026-08-20

First real-data pass over the plan's assumptions. Method: web search only —
this session's execution environment has an allowlist-restricted egress proxy,
so direct page fetching and scraping were not possible (verified: `CONNECT 403`
for non-allowlisted domains via both curl and WebFetch). Search results quote
live page content and are treated as **search-verified**: real, current,
sourced — but secondary. Every number below needs primary confirmation before
it drives a live listing decision.

Statuses: **CONFIRMED** (multiple independent sources agree) ·
**PARTIAL** (single source or sources disagree on detail) ·
**CORRECTED** (the plan's claim was wrong; log says how) ·
**BLOCKED** (not verifiable without accounts or an open network).

---

## 1. Marketplace fees

| Claim | Status | Evidence |
|---|---|---|
| eBay UK FVF is category-dependent, not a flat rate | **CONFIRMED** | 6.9%–14.9% by category; Business, Office & Industrial **12.5%** since the Feb-2026 rate-card change |
| eBay per-order fixed fee | **CONFIRMED** | £0.30, raised to **£0.40 for orders ≥ £10** in Feb 2026 |
| eBay regulatory operating fee | **PARTIAL** | Most sources say **0.35%**; others quote 0.32%–0.42%. Encoded 0.35%, flagged |
| Amazon UK B/I/S referral | **CONFIRMED** | **12%**, effective **12.24%** with the 2% UK DST pass-through |
| Amazon UK Home & Kitchen referral | **CONFIRMED** | **15%** (15.3% effective); new "Home Products" band at 8% ≤ £20 exists |
| Fees change and stack (the FeeBook's design premise) | **CONFIRMED** | Feb-2026 repricing of both FVF and per-order fee within the plan's own horizon |

Encoded as `ecommerce_os/data/fees_uk_2026.py` (10 tests). Rates ex-VAT; fee
VAT is recoverable input tax for a VAT-registered seller.

Sources: [eBay Seller Centre fees](https://www.ebay.co.uk/sellercentre/selling/start-selling/fees) ·
[eBay rate-card change](https://www.ebay.co.uk/sellercentre/news/2026-january/rate-card-change) ·
[Value Added Resource on the Feb-2026 rise](https://www.valueaddedresource.net/ebay-raises-final-value-fees-in-uk-germany-2026/) ·
[DashVue fee guide](https://dashvue.co.uk/blog/what-are-ebay-selling-fees-uk-guide) ·
[Amazon 2026 EU fee update](https://www.aboutamazon.eu/news/empowering-small-business/update-to-european-referral-and-fulfilment-by-amazon-fees-for-2026) ·
[UK referral table](https://profit-scanner.com/blog/amazon-referral-fees-by-category-eu-uk) ·
[Axivelo UK breakdown](https://axivelo.app/blog/amazon-referral-fees-by-category-uk/)

## 2. Supplier landscape

| Claim (whose) | Status | Evidence |
|---|---|---|
| No-minimum dropship wholesalers with feeds exist in the UK (founder's) | **CONFIRMED** | Named: [Pound Wholesale](https://www.poundwholesale.co.uk/drop-shipping) (dropship service), Aosom (live stock feeds, no minimum), UKSM Trade (no MOQ), [Wholesale2B](https://www.wholesale2b.com/dropship-api-plan.html) (real-time API), [Avasam](https://www.avasam.com/) (CSV export). B2B verification / registered business generally required |
| Typical opening orders are £750–£5,000 (plan's) | **CORRECTED** | Documented opening orders cluster **£100–£500**: Addison Ross £500 opening order, Northern Marketing £250+VAT MOQ, Beads Unlimited £100/order + £500/yr; £500–£750 thresholds are mostly *free-delivery* lines, not MOQs. Capital barrier is lower than planned — MOQ reserve stays useful but the £750–£5k range was overstated as typical |
| Catering spares supply is fragmented with weak incumbents (plan's) | **CORRECTED** | **First Choice Group + Commercial Catering Spares = Parts Town UK since July 2023** — a US consolidator whose model *is* OEM parts + fitment lookup: £13M stockholding, 100k sqft DC, same-day dispatch to 7pm. Consolidating, not fragmenting; strong incumbent, not weak. Also active in coffee parts ([Fracino at Parts Town UK](https://www.partstown.co.uk/manufacturers/fracino)) |
| Several spares sellers retail at "trade prices to the general public" | **NEW FINDING** | CaterSparesUK, CaterSpares both advertise exactly this — the vertical is partially disintermediated, further compressing resale margin |

Sources: [SaleHoo UK supplier survey](https://www.salehoo.com/learn/united-kingdom-dropship-suppliers) ·
[Catering Insight on the Parts Town acquisition](https://www.cateringinsight.com/first-choice-group-acquired-by-pt-holdings/) ·
[Parts Town UK](https://www.firstchoice-cs.co.uk/about/) ·
[Northern Marketing trade-account guide](https://nmarketing.co.uk/blogs/wholesale-trade-hub/how-to-open-a-wholesale-trade-account-step-by-step-guide-uk-retailers) ·
[Addison Ross wholesale terms](https://www.addisonross.com/en-us/pages/wholesale-terms-conditions)

## 3. Information gap (rubric ×3 criterion), live listing probes

Two machine-model searches restricted to ebay.co.uk, reading actual titles.

**Probe A — "Rational combi oven SCC 101 door gasket":** the naive gap does
NOT hold. Titles are part-number-first but **do include the machine model**
("20.02.552P RATIONAL COMBI OVEN STEAMER DOOR GASKET SCC 101…"). Sellers
already do machine-model SEO. The real gap is one level deeper:
**at least three part numbers (20.02.552P, 20.01.802P, 20.00.396P) all claim
SCC 101 fitment** — different variants (WE 101E / 101G / CM Plus, different
dimensions) — and nothing on the results page tells a buyer which one fits
*their* machine. The sellable information product is **disambiguation**
(variant/serial-range → exact part), not discovery. ≥8 competing listings
visible → crowded.

**Probe B — "Fracino group head seal":** gap wide open. Titles carry **no
machine model** ("Fracino Group Head Seal 2X Washer Gasket Genuine…") despite
Fracino's models (Bambino, Cherub, Heavenly) being the natural search terms.
Few competing listings. One probe only — but on this evidence the coffee-parts
end shows a larger information gap and thinner competition than catering.

**Consequence for the rubric:** score the "information gap" criterion on
*disambiguation depth* (parts-per-machine ambiguity), not on whether titles
mention machines. Re-run this probe per candidate vertical before P0 scoring.

## 4. Spot margin test — one real SKU, engine-computed

**SKU:** Rational 20.02.552P door gasket (SCC/CM/iCombi 101).
**Verified UK retail:** £69.99 ([eBay UK](https://www.ebay.co.uk/itm/132194938739)) and £70.19
([Normanton Catering](https://www.normantoncatering.com/product-page/20-02-552p-rational-scc101-door-gasket)) — near-zero
retail dispersion, consistent with an efficiently-priced vertical.
**Trade price: BLOCKED** — behind account walls; requires a real trade account.

So the engine answered the invertible question instead
(`verification/breakeven_20_02_552p.py`, reproducible): *what trade price
clears the pilot gates (≥£5 and ≥15%) at £69.99 on eBay UK, Feb-2026 fees?*

```
eBay UK fees on £69.99 (B&I): FVF 8.75 + regulatory 0.24 + fixed 0.40 = £9.39
Binding gate: 15% of £69.99 = £10.50 contribution

outbound   max supplier cost ex VAT   as % of ex-VAT retail (£58.33)
  £3.50            £34.33                     58.9%
  £4.95            £32.88                     56.4%
  £6.50            £31.33                     53.7%
```

**Reading:** the supplier must give roughly a **41–46% discount off net
retail** for this SKU to clear the gates. OEM parts trade discounts commonly
run 30–50% off list — this sits *at the boundary*: not dead, not comfortable.
Exactly the margin-compression picture, now with a number. The first trade
price list obtained in P1 turns this from boundary into verdict — which is
what the P2 compression test exists to do at n=150 instead of n=1.

## 5. What this environment cannot verify

| Item | Why | Unblock |
|---|---|---|
| Bulk scraping / offer counts per SKU at scale | Egress proxy allowlist blocks all non-allowlisted domains | Run the P2 harness locally, or in a Claude Code environment whose network policy allows the target domains |
| Real trade price lists | Behind supplier account logins — not bypassed, by policy | Open trade accounts (P1); ask for the price list with the application |
| eBay Browse API / Amazon SP-API | Need developer credentials | Register apps when the entity exists |
| Fee rates at primary-source precision | Marketplace fee pages unreachable from here | One manual check of the two fee pages, or the fee-estimate APIs once credentialed |

## Verdict changes driven by this pass

1. **Catering spares demoted** as the default example vertical: strong
   consolidating incumbent (Parts Town), partial disintermediation, crowded
   listings, boundary-line break-even. It can still pass P2 — but it must earn
   it; do not assume it.
2. **Coffee-machine parts promoted to first-probe candidate**: open
   information gap and thin competition on the probe, though Parts Town's
   presence in the supply layer needs watching. Needs the full rubric + P2.
3. **Rubric refinement**: measure the information gap as *disambiguation
   depth*, not model-mention absence.
4. **MOQ reserve stands, sized down**: documented opening orders are
   £100–£500, not £750–£5,000.
5. **Fee engine now runs on real Feb-2026 UK rules** — and the Feb-2026
   mid-year repricing is itself evidence that hard-coding fees would have
   already broken once this year.
