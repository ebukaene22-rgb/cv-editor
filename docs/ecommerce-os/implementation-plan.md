# Fitment-First: Twelve-Month Implementation Plan (UK)

> Companion to [`strategy.md`](strategy.md) and the `ecommerce_os` decision
> engine. Thresholds and figures here are **proposed operating policy and
> planning estimates** — not marketplace rules, quotations, or legal or tax
> advice. Verify regulatory and marketplace positions against primary sources.

The compliant version of this business cannot win on price — an authorised
distributor sells to every reseller at the same trade price. It wins on
**knowing which part fits what**. This plan sequences the year around proving
that, cheaply, before it costs real money.

## Viability assessment

**6/10 as originally scoped. 7.5/10 narrowed to one market and one vertical.**

| Dimension | Score | Reasoning |
|---|---:|---|
| Strategic reasoning | 9 | Genuinely better than most people bring to this |
| Compliance posture | 9 | Correctly names the thing that kills these businesses |
| Economic rigour | 8 | The landed-cost discipline is real and rare |
| Founder fit | 8 | Data science is the right skill for the version worth building |
| Capital efficiency | 7 | Can be tested cheaply, if the tests are sequenced right |
| Margin durability | 4 | The unresolved problem — see below |
| Supplier access realism | 4 | Badly underestimated |
| Scope discipline | 3 | Two markets in year one |

## Three corrections to the strategy document

| Correction | Original assumption | What this plan does instead |
|---|---|---|
| **Margin source** | Compliance is a pure upgrade to the arbitrage model. | Compliance trades margin for durability. Retail arbitrage has margin *because* it is unauthorised; at trade prices you compete against resellers with an identical cost base. Margin must come from fitment knowledge, catalogue gaps and bundles — so the compatibility graph is built first, not last. |
| **Supply ladder** | Dropship first, graduate winners into stock. | Inverted. Distributors grant dropship to accounts with trading history. Open with a stock order, earn dropship at month 4–6. Working capital is a day-one line, not a month-seven one. |
| **Scope** | UK and UAE cells inside twelve months. | UK only. UAE becomes a decision at month 12, funded by UK contribution — not a parallel build. |

The cheapest thing in this plan is Phase 2: a two-week desk exercise against one
real trade price list, answering "does any margin survive at authorised prices?"
before a single contract, listing or line of ingestion code exists. If it fails
twice, the thesis is wrong and you have spent about £2,000 finding out.

## The funnel that actually matters

A 100–300 order pilot proves the machinery, not the business. Plan against the
number that makes this worth a founder's full time: **£20,000/month contribution
by month 18.**

| Working backwards | Figure | Assumption |
|---|---:|---|
| Monthly contribution target | £20,000 | Founder-viable, before overhead |
| Orders per month | 1,100 | £18 average contribution per order |
| Productive SKUs | 440 | 2.5 orders per SKU per month, long-tail parts |
| Live SKUs | 1,100 | ~40% of listings ever sell |
| Matched candidates needed | 4,400 | ~25% clear every gate |

Two consequences. The catalogue must reach four figures, so manual matching does
not scale past the pilot and the review queue has to be genuinely fast. And a
single vertical must contain 4,000+ addressable SKUs — which rules out niches
that feel comfortable but are simply too small.

## Phase sequence

Phases overlap deliberately. Supplier access is the long pole and starts in
week 2; everything else is arranged around its lead time. No phase proceeds
without clearing its gate.

### P0 · Weeks 1–4 · Choose the vertical and stand up the entity

- Score 6–8 candidate verticals against the rubric below. Commit to one, name the runner-up.
- Incorporate, open a business bank account, register for VAT voluntarily (input VAT recovery matters more than the threshold here).
- **Product liability insurance** — you become seller of record for goods you did not make. Frequently overlooked; get quotes now.
- Brief ecommerce counsel on two things only: the source-rights matrix for your data inputs, and a supplier agreement template covering resale, territory, channel, dropship, packaging, content licence and returns.
- Build a target list of **40–60** distributors and wholesalers, not 10–20. Expect roughly 10% to convert to an account.

**Gate 0 — proceed when:** one vertical scores ≥ 55/75 with a runner-up
identified; entity, bank, VAT and liability cover in place; supplier template
reviewed by counsel; 40+ named targets with a contact route each.

### P1 · Weeks 2–16 · Supplier access (critical path)

What distributors actually want: a credit application, a VAT number, Companies
House history, trade references, an indication of volume, and often a minimum
opening order. A new entity has none of the first four. The opening order is
what you have to trade with.

- **Open as a stocking account, not a dropshipper.** Ask for trade terms and place a real opening order (£1,500–4,000). Do not lead with a dropship request — it reads as no-risk-to-you and gets declined.
- Ask for the price list and stock feed *during* the credit application. Many share a CSV on request; that feed is the input to Phase 2.
- Raise dropship at month 4–6, once there is order history to point at. Frame it as extending an existing account, not opening a new model.
- Run a dropship platform in parallel as a cheap fallback so the pilot is not blocked if distributor accounts run late.

**Gate 1 — proceed when:** 2+ signed trade accounts with machine-readable price
and stock feeds; at least one refreshing hourly or better; written answers on
returns route, warranty owner and packaging neutrality; a named path to dropship
rights on at least one account.

**Stop if by week 20** there are zero signed accounts. Either the vertical's
supply is closed to new entrants, or the pitch is wrong.

### P2 · Weeks 4–10 · The margin compression test

Two weeks of desk work that can save six months. Run it the moment the first
price list arrives.

1. Take 150 SKUs at random from a real trade price list.
2. Pull current competitive offers per SKU — eBay Browse API, Amazon SP-API where available, manual sampling otherwise.
3. Run every SKU through the landed-cost engine already built, with real fee rules for the category.
4. Count what share clears **both** £5 contribution and 15% margin.
5. Record the median number of competing offers per SKU.

| Result | SKUs clearing | Median offers | Action |
|---|---:|---:|---|
| **Proceed** | ≥ 25% | ≤ 4 | Vertical has room. Move to P3. |
| **Narrow** | 10–25% | 5–8 | Re-cut to the sub-categories that clear; retest one more distributor. |
| **Reject** | < 10% | > 8 | Wrong vertical. Return to P0 and take the runner-up. |

A low pass rate is **not** a reason to loosen the thresholds. It is the market
telling you that authorised supply in this vertical is already efficiently
priced. Two consecutive rejects across two verticals means the
arbitrage-derived thesis does not hold and the plan should stop.

**Gate 2 — proceed when:** a vertical or sub-category clears at ≥ 25% on real
trade prices, and predicted contribution reconciles against a hand-worked sample
of 10 SKUs.

### P3 · Weeks 8–20 · Build the fitment graph

Price data is replicable; a trustworthy answer to "does this fit my machine?" is
not. In most parts verticals the incumbent answer is a PDF parts diagram, a
phone call, or nothing. That gap is the business.

- Extend the schema with `machine`, `machine_variant` and a `fits` edge carrying a confidence and a source.
- Seed from manufacturer parts lists, distributor cross-reference tables and supersession records — each edge cites where it came from.
- Ingest the first two supplier feeds into the canonical product graph.
- Build the human review queue. Target under 15 seconds per decision; at 4,400 candidates, anything slower becomes the bottleneck.
- Label 1,000+ match pairs and measure auto-match precision against them.

**Gate 3 — proceed when:** audited auto-match precision ≥ 99.5% on the labelled
set; ≥ 2,000 canonical products with ≥ 5,000 sourced fitment edges; review queue
sustains 200+ decisions per hour.

### P4 · Weeks 16–28 · eBay pilot

Cheapest account risk, best long-tail discovery, most forgiving of a thin catalogue.

- Launch 50–150 SKUs that clear every gate. Stocked lines first, since dropship rights may still be pending.
- Reconcile **every order**: predicted versus settled contribution, decomposed into fee, shipping, tax, return, supplier price and ad error.
- Audit 100% of auto-matches for the first 300 listings.
- Turn on kill switches from day one, not after the first incident.

**Gate 4 — proceed when:** 150+ fulfilled orders; portfolio contribution margin
after returns ≥ 12%; prediction error within ±15% and shrinking; supplier fill
rate ≥ 98% and stock-mismatch cancellations < 1%; manual handling under 5
minutes per order.

### P5 · Weeks 24–40 · The fitment site

Marketplaces validate demand. The direct site is the business, because it is the
only channel where the graph is visible to the customer.

- Ship a compatibility finder: pick your machine, see every part that fits. This is the product, not a feature.
- Generate `/compatible-with/{machine}` and `/mpn/{part}` pages from the graph, with genuinely original attribute content — never cloned supplier copy.
- Add bundles and service kits. Bundles are the cleanest escape from price comparison: nobody else lists your exact combination.
- Open Amazon second, once catalogue and operations are clean and FBA is viable for proven lines.
- Move validated winners into stock or 3PL on the transition rule already implemented.

**Gate 5 — proceed when:** direct channel is ≥ 20% of orders at a higher margin
than marketplace; organic traffic to fitment pages growing month on month; 600+
live SKUs across at least two channels.

### P6 · Months 10–12 · Scale, hold, or stop

| Month-12 position | Monthly contribution | Decision |
|---|---:|---|
| Working, with a clear supply ladder | ≥ £8k | **Scale** — raise catalogue toward 1,100 SKUs, hire ops, negotiate volume terms, then evaluate UAE as cell two. |
| Unit economics fine, volume thin | £3k–£8k | **Hold** — catalogue depth is the constraint, not the thesis. Extend six months on the same spend. Do not add a market. |
| Margin or reliability not converging | < £3k | **Stop** — wind down listings, keep the graph and the codebase, reassess. |

UAE is a month-12 conversation at the earliest, and only from the *scale*
branch. It needs a licensed entity, local fulfilment and a separate supplier
base — a second company, not a second market. Funding it from UK contribution
rather than from the same starting capital is the difference between a
considered expansion and running two underfunded businesses.

## Vertical selection rubric (P0 tool)

Score each candidate 1–5 per criterion, multiply by the weight, total out of 75.
Weights are set so fitment complexity and repeat purchase dominate — those are
what make the graph valuable and the customer come back.

| Criterion | Weight | Scores 5 when… |
|---|---:|---|
| Fitment complexity | ×3 | "Will it fit?" is the buyer's main question and getting it wrong means a return |
| Repeat purchase | ×2 | Consumable, with a predictable replacement interval |
| Supply fragmentation | ×2 | Many regional distributors; no brand selling direct at scale |
| Weak incumbents | ×2 | Best existing answer is a PDF diagram or a phone call |
| Return & damage risk | ×2 | Robust, non-fragile, resellable if returned unopened |
| Listing friction | ×2 | Not gated, not a counterfeit magnet, no hazmat or certification burden |
| Catalogue depth | ×2 | 4,000+ addressable SKUs, so the funnel above is reachable |
| Order value £25–150 | ×1 | Enough absolute margin per order to cover handling |
| Shippable | ×1 | Small and light enough for standard tracked parcels |
| **Proceed threshold** | **55 / 75** | Below this, keep looking. Score the runner-up too — P2 may send you back to it. |

Candidates worth scoring: commercial catering spares, coffee-machine parts, HVAC
and refrigeration components, industrial filtration, groundcare and mower parts,
floorcare spares, pool and spa equipment, laboratory consumables. Each has
fragmented supply, real fitment complexity and incumbents who answer
compatibility questions badly.

## What to build, and when

The decision engine is done — gates, landed cost, matching, scoring, kill
switches and schema. Everything below surrounds it, sequenced so nothing is
built before the phase that needs it. Roughly four months of focused founder
time across the year.

| For | Component | Effort | Note |
|---|---|---:|---|
| P2 | Supplier feed parser (CSV/XML/SFTP) | 1 wk | One format per supplier; resist a generic framework |
| P2 | Marketplace price puller + batch scorer | 1 wk | Enough to run the compression test. Throwaway is fine |
| P3 | Fitment graph schema + edge ingestion | 2 wks | Every edge carries a source and a confidence |
| P3 | Canonical loader + human review queue | 3 wks | Keyboard-driven. Speed here decides catalogue ceiling |
| P4 | eBay listing writer + order router | 3 wks | Trading/Inventory API; idempotent writes |
| P4 | Reconciliation job | 2 wks | Highest-value component in the system. Do not defer it |
| P5 | Storefront sync + compatibility finder | 4 wks | The customer-facing product |
| P5 | Bounded repricer | 2 wks | Floor at the contribution gate; never below |
| P5 | Amazon SP-API integration | 3 wks | Only after eBay economics are proven |

**Sequencing rule:** do not build ingestion for a supplier you have not signed,
or a listing writer for a channel you have not validated. The failure mode for a
technical founder is a beautiful pipeline with no supply at one end and no
demand at the other.

## Twelve-month budget (UK only)

Planning estimates, not quotations, excluding founder salary. The material
difference from the original budget is that opening stock orders appear in month
one — that is the price of a distributor account, and it buys the trading
history that dropship rights depend on.

| Line | Low | Expected | Timing |
|---|---:|---:|---|
| Legal — source rights, supplier template, T&Cs | £4,000 | £8,000 | P0, front-loaded |
| Accountancy — setup, VAT, monthly | £2,000 | £4,000 | Throughout |
| Entity, banking, product liability cover | £1,000 | £2,500 | P0 |
| **Opening stock orders** — 2–4 accounts | £8,000 | £15,000 | P1, month 1–4 |
| Replenishment working capital | £5,000 | £12,000 | P4 onward |
| Cloud, data, tooling | £2,000 | £4,000 | Throughout |
| Marketplace fees and pilot advertising | £3,000 | £6,000 | P4–P5 |
| 3PL onboarding | £1,000 | £3,000 | P5 |
| Storefront build and SEO content | £3,000 | £6,000 | P5 |
| Part-time ops, months 5–12 | £8,000 | £12,000 | P4 onward |
| Contingency, 20% | £7,000 | £15,000 | — |
| **Twelve-month total** | **£44,000** | **£87,500** | Release in tranches |

Release capital against gates, not against calendar. Roughly £18k should carry
you through Gate 2 — and Gate 2 is where you find out whether the remaining £70k
is worth committing.

## Stop-loss criteria

Written now, while it is cheap to be objective. The characteristic failure of
this kind of venture is not a bad decision — it is eighteen months of not
deciding.

| Trigger point | Condition | Action |
|---|---|---|
| Week 10 | Margin compression test rejects two verticals | Stop. The thesis does not survive authorised pricing |
| Week 20 | No signed distributor account | Stop, or fall back to a dropship platform for a cheaper test only |
| Month 7 | Auto-match precision below 99% after two model revisions | Cap the catalogue at manually reviewed SKUs; the automated version is off the table |
| Month 9 | Contribution below £3k/month | Stop adding SKUs; diagnose demand or margin before further spend |
| Month 12 | Contribution below £3k/month, or portfolio margin under 10% | Wind down. Retain the graph and codebase |
| Any time | Cumulative spend exceeds £75k without £10k/month contribution | Hard stop regardless of trajectory |
| Any time | Marketplace suspension unresolved after 30 days | Channel concentration is the risk — accelerate the direct site or stop |

**The risk not on that table:** account suspension is correlated, not
diversifiable, at this scale. One marketplace decision can halt the whole
operation with stock committed and no route to market. That is the strongest
argument for treating the direct fitment site as the destination rather than a
later channel — and for never letting one marketplace exceed roughly 60% of
orders.

## The next ten working days

1. Score six candidate verticals on the rubric. Commit to one, name the runner-up.
2. Draft the distributor approach as a stocking account with an opening order — not a dropship request.
3. Build the 40–60 target list with a named contact and route for each.
4. Start incorporation, VAT registration and product liability quotes in parallel.
5. Send the first twelve approaches. Ask for the price list with the credit application.
6. Brief counsel on the source-rights matrix and the supplier template.
7. Write the feed parser and batch scorer so the compression test can run the day a price list lands.

Nothing on that list is a modelling problem. The binding constraint for the next
four months is supplier access, and it is worked by email and phone.
