# Fitment-First: Twelve-Month Implementation Plan (UK)

> Companion to [`strategy.md`](strategy.md) and the `ecommerce_os` decision
> engine. Thresholds and figures here are **proposed operating policy and
> planning estimates** — not marketplace rules, quotations, or legal or tax
> advice. Verify regulatory and marketplace positions against primary sources.

This business should not depend on wholesale-under-retail as its enduring edge.
Cost advantages are real, but almost all of them are earned with volume you do
not yet have. What is available in week one is **knowing which part fits what** —
so the year is sequenced around proving that, cheaply, before it costs real
money.

## Viability assessment

**6/10 as originally scoped. 7.5/10 narrowed to one market and one vertical.**

| Dimension | Score | Reasoning |
|---|---:|---|
| Strategic reasoning | 9 | Genuinely better than most people bring to this |
| Compliance posture | 9 | Correctly names the thing that kills these businesses |
| Economic rigour | 8 | The landed-cost discipline is real and rare |
| Founder fit | 8 | Data science is the right skill for the version worth building |
| Capital efficiency | 7 | Can be tested cheaply, if the tests are sequenced right |
| Margin durability | 4 | Not from price gap; must come from information — see below |
| Supplier access realism | 4 | Underestimated, though not in one direction |
| Scope discipline | 3 | Two markets in year one |

## Three divergences from the strategy document

| Divergence | Original assumption | What this plan does instead |
|---|---|---|
| **Where the edge lives** | The enduring edge is wholesale price below marketplace price. | Cost-base advantages are real — volume tiers, rebates, payment terms, buying direct rather than through an intermediary — but nearly all are *earned with volume you do not yet have*. What is available in week one is informational: supplier selection, stale competitor pricing, catalogue quality, bundles, fulfilment route. The graph is the day-one edge; cost tiers are the year-two prize. |
| **Supply access** | Dropship first, graduate winners into stock. | Neither ladder holds. Access mode is a property of each supplier, classified at onboarding: some dropship immediately with no minimum and hourly feeds, some require a £750–£5,000 opening order, some never dropship, some are worth stocking purely on economics. Hold an MOQ reserve so a good supplier is never inaccessible. |
| **Scope** | UK and UAE cells inside twelve months. | UK only. UAE becomes a decision at month 12, funded by UK contribution — not a parallel build. |

The cheapest thing in this plan is Phase 2: a two-week desk exercise against one
real trade price list, answering "does any margin survive at authorised prices?"
before a single contract, listing or line of ingestion code exists.

## Sizing under uncertainty

A 100–300 order pilot proves the machinery, not the business. The number that
makes this worth a founder's full time is **£20,000/month contribution by month
18**. One step backwards from there is solid; the next is not.

### The step that holds

Contribution per order is measurable within the first fifty orders, so dividing
the target by it is a reliable link rather than an assumption.

| Contribution per order | Orders needed per month |
|---|---:|
| £12 — thin margin, commodity-adjacent | 1,670 |
| £18 — central planning case | 1,110 |
| £25 — fitment-led pricing, bundles | 800 |
| £35 — service kits, specialist components | 570 |

### The step that does not hold

Converting orders into a SKU count requires an orders-per-SKU figure, and any
single value for it is arbitrary. Worse, long-tail parts demand is heavily
skewed — most SKUs sell under once a month by definition — so planning on a mean
is the wrong *shape* of model, not merely the wrong number. The honest output is
a range:

| Orders per live SKU per month | Live SKUs at 1,110 orders | What produces it |
|---|---:|---|
| 0.5 | 2,220 | Browse traffic, generic titles, no fitment answer |
| 1.0 | 1,110 | Marketplace search, decent titles |
| 2.0 | 560 | Fitment pages ranking, intent traffic arriving |
| 3.0+ | 370 | Authoritative on a machine; repeat service custom |

**Why this matters more than the number.** The graph moves you down that table.
Someone arriving on "ABC-100 oven door gasket" converts far better than someone
browsing "EPDM gasket 580mm" — so the fitment work raises orders-per-SKU *and*
cuts the catalogue you need to carry. It attacks both sides of the ratio at
once, which is a stronger argument for building it than the margin case.

### A better planning unit: machines covered completely

SKU count is the wrong denominator anyway. A customer with an ABC-100 oven
should find *every* part for it, not sixty per cent of them — partial coverage
kills the trust and the return visit that make this business work. So plan in
machines, not parts.

If a commercial oven model has roughly forty serviceable parts, covering a
hundred models completely is about four thousand SKUs — but only a hundred
authoritative pages, and a hundred defensible search positions. The tail is a
marketing asset that happens to also sell; it does not need to be individually
productive to earn its place.

Demand can then be estimated from the graph rather than guessed: units in
service × service events per unit per year × parts per event × your share. That
is a model you can calibrate against pilot data.

## Phase sequence

Phases overlap deliberately. Supplier access is the long pole and starts in
week 2; everything else is arranged around its lead time. No phase proceeds
without clearing its gate.

### P0 · Weeks 1–4 · Choose the vertical and stand up the entity

- Score 6–8 candidate verticals against the rubric below. Commit to one, name the runner-up.
- Incorporate, open a business bank account, register for VAT voluntarily (input VAT recovery matters more than the threshold here).
- **Product liability insurance** — you become seller of record for goods you did not make. Frequently overlooked; get quotes now.
- Brief ecommerce counsel on two things only: the source-rights matrix for your data inputs, and a supplier agreement template covering resale, territory, channel, dropship, packaging, content licence and returns.
- Build a target list of **40–60** suppliers, not 10–20, spanning the full range: no-minimum dropship wholesalers, opening-order distributors, and manufacturers. Tag each with its likely access mode. Expect roughly 10% to convert.

**Gate 0 — proceed when:** one vertical scores ≥ 65/90 with a runner-up
identified; entity, bank, VAT and liability cover in place; supplier template
reviewed by counsel; 40+ named targets with a contact route each.

### P1 · Weeks 2–16 · Supplier access (critical path)

**Classify, do not sequence.** There is no universal ladder between dropship and
stock. Access mode is a property of each supplier, established at onboarding —
so the portfolio should be deliberately mixed from day one rather than marched
through a stage.

| Access mode | Signature | How to open it |
|---|---|---|
| **Open dropship** | No minimum, trade pricing, stock feed refreshing hourly | Apply directly. Fastest route to a live pilot; verify feed frequency and packaging neutrality before relying on it |
| **Opening-order** | £750–£5,000 minimum, then trade terms | Draw on the MOQ reserve. Price the order as the cost of access, and pick SKUs the compression test already liked |
| **Stock-only** | Will supply, will never dropship | Worth it where stocked economics clearly beat dropship — often the better margin anyway |
| **Volume-tiered** | Terms improve materially with committed volume | Open at the worst tier knowingly. Record the tier thresholds — this is the year-two cost edge |

Working the list:

- Ask for the price list and stock feed *during* the application. Many share a CSV on request; that feed is the input to Phase 2 and arrives long before any contract does.
- Capture access mode, feed type and frequency, MOQ, packaging neutrality, returns route and warranty owner as structured fields at onboarding — they are exactly what the compliance gate reads.
- Record volume-tier thresholds even when they are far away. They are the roadmap for the cost advantage you cannot access yet.
- Aim for a mix: at least one open-dropship account so the pilot is never blocked, and at least one stocking account so margin is not capped by dropship pricing.

**Gate 1 — proceed when:** 2+ signed trade accounts with machine-readable price
and stock feeds; at least one refreshing hourly or better; written answers on
returns route, warranty owner and packaging neutrality; at least one account
able to fulfil without holding stock; access mode and volume-tier thresholds
recorded for every account.

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
| **Proceed** | ≥ 25% | ≤ 4 | Vertical has room. Move to P3 |
| **Narrow** | 10–25% | 5–8 | Re-cut to the sub-categories that clear; retest one more distributor |
| **Reject** | < 10% | > 8 | Wrong vertical. Return to P0 and take the runner-up |

A low pass rate is **not** a reason to loosen the thresholds. It is the market
telling you that authorised supply in this vertical is already efficiently
priced.

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
- Build the human review queue. Target under 15 seconds per decision: completing even a hundred machines runs to several thousand candidates, and anything slower makes the queue the ceiling on coverage.
- Label 1,000+ match pairs and measure auto-match precision against them.

**Gate 3 — proceed when:** audited auto-match precision ≥ 99.5% on the labelled
set; **25+ machine models covered completely** (every serviceable part mapped,
not most of them — partial coverage is the failure mode); ≥ 5,000 fitment edges
each carrying a source; review queue sustains 200+ decisions per hour.

### P4 · Weeks 16–28 · eBay pilot

Cheapest account risk, best long-tail discovery, most forgiving of a thin catalogue.

- Launch 50–150 SKUs that clear every gate.
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
than marketplace; organic traffic to fitment pages growing month on month; 60+
machine models covered completely across two channels; orders per live SKU
trending up — the signal that the graph is working.

### P6 · Months 10–12 · Scale, hold, or stop

| Month-12 position | Monthly contribution | Decision |
|---|---:|---|
| Working, with a clear supply ladder | ≥ £8k | **Scale** — widen machine coverage, hire ops, push for the next volume tier now that you have order history, then evaluate UAE as cell two |
| Unit economics fine, volume thin | £3k–£8k | **Hold** — catalogue depth is the constraint, not the thesis. Extend six months on the same spend. Do not add a market |
| Margin or reliability not converging | < £3k | **Stop** — wind down listings, keep the graph and the codebase, reassess |

UAE is a month-12 conversation at the earliest, and only from the *scale*
branch. It needs a licensed entity, local fulfilment and a separate supplier
base — a second company, not a second market.

## Vertical selection rubric (P0 tool)

Score each candidate 1–5 per criterion, multiply by the weight, total out of 90.
The two heaviest criteria are both about information: how hard the fitment
question is, and how badly the market currently answers it. Those are the only
two things on this list a new entrant can be better at in week one.

Note the inversion this implies. **Ugly is good.** Thousands of MPNs, terrible
descriptions, no compatibility data and fragmented suppliers are the conditions
that make the graph valuable — a clean, well-described, easily-understood
consumer catalogue is one where the information work has already been done by
someone else.

| Criterion | Weight | Scores 5 when… |
|---|---:|---|
| Fitment complexity | ×3 | "Will it fit?" is the buyer's main question, and getting it wrong means a return |
| Information gap | ×3 | Listings are titled by part number, not by machine. Best existing answer is a PDF diagram or a phone call |
| Repeat purchase | ×2 | Consumable, with a predictable replacement interval |
| Supply fragmentation | ×2 | Many regional distributors; no brand selling direct at scale |
| MPN density | ×2 | Thousands of part numbers, heavy supersession, many-to-many model compatibility |
| Return & damage risk | ×2 | Robust, non-fragile, resellable if returned unopened |
| Listing friction | ×2 | Not gated, not a counterfeit magnet, no hazmat or certification burden |
| Order value £25–150 | ×1 | Enough absolute margin per order to cover handling |
| Shippable | ×1 | Small and light enough for standard tracked parcels |
| **Proceed threshold** | **65 / 90** | Below this, keep looking. Score the runner-up too — P2 may send you back to it |

Candidates worth scoring: commercial catering spares, coffee-machine parts, HVAC
and refrigeration components, industrial filtration, groundcare and mower parts,
floorcare spares, pool and spa equipment, laboratory consumables.

A useful field test before scoring: search the vertical the way a customer
would — by machine model, not by part number. If the first page returns part
numbers, dimensions and materials rather than "fits your machine", the
information gap is real and scores high.

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
| P3 | Canonical loader + human review queue | 3 wks | Keyboard-driven. Speed here decides coverage ceiling |
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
difference from the original budget is the **MOQ access reserve**: money held
from month one so that a supplier worth having is never inaccessible because its
minimum order is £750 or £5,000. It is reserved, not pre-committed — drawn per
supplier as accounts open, and spent on SKUs the compression test has already
approved.

| Line | Low | Expected | Timing |
|---|---:|---:|---|
| Legal — source rights, supplier template, T&Cs | £4,000 | £8,000 | P0, front-loaded |
| Accountancy — setup, VAT, monthly | £2,000 | £4,000 | Throughout |
| Entity, banking, product liability cover | £1,000 | £2,500 | P0 |
| **MOQ access reserve** — drawn per supplier | £5,000 | £9,000 | P1, held from month 1 |
| Replenishment working capital | £5,000 | £12,000 | Released after Gate 4 |
| Cloud, data, tooling | £2,000 | £4,000 | Throughout |
| Marketplace fees and pilot advertising | £3,000 | £6,000 | P4–P5 |
| 3PL onboarding | £1,000 | £3,000 | P5 |
| Storefront build and SEO content | £3,000 | £6,000 | P5 |
| Part-time ops, months 5–12 | £8,000 | £12,000 | P4 onward |
| Contingency, 20% | £7,000 | £13,500 | — |
| **Twelve-month total** | **£41,000** | **£80,000** | Release in tranches |

Release capital against gates, not against calendar. Around **£10,000–£16,000**
carries you through Gate 2 — legal, entity, insurance, one MOQ draw and tooling.
Gate 2 is where you find out whether the remaining £30k–£65k is worth
committing, and it is the cheapest decision point in the year by a wide margin.

## Stop-loss criteria

Written now, while it is cheap to be objective. The characteristic failure of
this kind of venture is not a bad decision — it is eighteen months of not
deciding.

| Trigger point | Condition | Action |
|---|---|---|
| Week 10 | Margin compression test rejects two verticals | Stop. The thesis does not survive authorised pricing |
| Week 20 | No signed account of any access mode — including no-minimum dropship | Stop. If even the open-dropship end of the market will not take you, the entity or the pitch is the problem, not the vertical |
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

1. Score six candidate verticals on the rubric — searching each by machine model rather than part number, to test the information gap directly.
2. Build the 40–60 target list with a named contact, and tag each with its likely access mode: open dropship, opening-order, stock-only, tiered.
3. Write two approach templates — one for no-minimum dropship accounts, one for opening-order distributors. They are different pitches.
4. Start incorporation, VAT registration and product liability quotes in parallel.
5. Send the first twelve approaches. Ask for the price list with the application.
6. Brief counsel on the source-rights matrix and the supplier template.
7. Write the feed parser and batch scorer so the compression test can run the day a price list lands.

Nothing on that list is a modelling problem. The binding constraint for the next
four months is supplier access, and it is worked by email and phone.
