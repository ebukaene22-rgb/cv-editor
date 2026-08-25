# Final Program (post-adversarial-review)

Status: supersedes the allocation and KPIs in the earlier plans where they conflict.
Incorporates the external adversarial review (Aug 2026) after independent verification
of its decision-critical claims.

## Verified corrections adopted

- **Kalshi lane: DEAD, formally.** UAE is explicitly listed as a Restricted
  Jurisdiction for Event Contract trading in Kalshi's Member Agreement (Section VI).
  Not "likely blocked" — contractually excluded. Polymarket-side legality under UAE
  GCGRA rules would separately require counsel. Lane removed.
- **Roblox rejection reason corrected.** Reseller share is 50% (not 40%), but Robux
  from trading/reselling items you did not create are NOT Earned Robux and are
  ineligible for DevEx cash-out. The kill verdict stands on stronger grounds than
  originally stated.
- **eBay fee model rebuilt.** The old "13.25% + 2% payment" double-counted
  processing. Correct model: category final-value fee (processing included, ~13.6%
  typical non-store; ~9.35% Cameras & Photo with Store subscription) + $0.40
  per-order + international surcharge (published ~1.65% for US-registered sellers;
  region-tiered for others — verify the UAE/APAC rate at account setup, the
  reviewer's 1.30% figure was not confirmed).
- **UAE import cost corrected: ~10.25%, not 5%** (5% duty on CIF, then 5% VAT on
  duty-inclusive base), plus courier clearance fees.
- **Definitions fixed.** The 1.35 buy rule is 35% ROI on landed cost ≈ 25.9% margin
  on revenue. All gates below are stated as ROI-on-cost.
- **Conceded analytical pattern:** several report figures promoted a true
  observation into a stronger harvestability claim (float→arbitrage, price
  difference→typical 30–80% margin, dubbing watch-time composition→causal lift,
  trough market size→current size). Delete-not-haircut applied to: "Japan 30–80%
  typical", "~25% of StockX below retail", "+45% views from dubbing",
  "$3.8–4.5B CS2 market" (current tracker estimates ~$6.2–6.9B).

## Contested / nuanced

- **Six-condition framework**: retained as a *screening* heuristic only. Capital
  decisions use the review's execution model:
  qualified opportunities × fill probability × executable size × realised net edge
  × capital velocity − tail losses.
- **Podcast lane ($0 vs $4k)**: the reviewer's kill reason ("recreates the sales
  problem you wanted to escape") imports a no-outbound-sales constraint from a
  different conversation. This is an operator preference call, not a market fact.
  Lane is PARKED, not killed: revisit only if willing to do direct sales.
- **Language/dubbing lane**: the +25%/+45% stats are corrected (composition, not
  causal), but the lane's economics never depended on them — marginal cost of an
  additional language track on an existing pipeline is ~an API call. Unchanged as
  a $0-capital production task on the football channel.

## Plan A — Japan corridor: MODIFY and pilot

Allocation: **$1,250** (was $3,000).

1. Category: model-number-exact, small/light, higher ASP bias ($150–400 favored
   over $80). Lenses first. **ジャンク excluded from the first 20–30 trades** —
   model numbers resolve identity, not condition; buy explicitly tested/working
   inventory until the return/failure distribution is measured.
2. **Prospective 30-day opportunity log, not a retrospective comp sheet.** For each
   candidate: price at first detection, final hammer/sale price (or lost-to-other-
   bidder), full fee stack, matched eBay sold *distribution* (not best comp),
   would-I-have-bought at information-available-then. Count only candidates that
   survive at the FINAL price. Require qualified supply ≥ 2× the volume $500/mo
   needs before scaling.
3. **Architecture question to resolve during the pilot:** Japan→Dubai→buyer incurs
   ~10.25% import cost + an extra freight leg on goods that never needed to enter
   the UAE. Test ship-direct-from-Japan (proxy/3PL holding + truthful eBay item
   location = Japan) against the Dubai-routed baseline. Also test Chrono24 (6.5%
   private-seller commission) as the watch exit vs eBay.
4. Scale gates (all three): realised ROI on cost ≥ 20% · median cash-to-cash cycle
   ≤ 45 days · qualified opportunity capacity ≥ 2× required volume.
   Pass on ~10 units → $3,000. Hold at 30 units → capital is no longer the binding
   constraint.

## Plan B — CS2: KILL as written; run the diagnostic

Allocation: **$0** live (was $5,000); **$500 max** after gate.

Conceded: on a float-forward marketplace (CSFloat), a seller's float-ignorance does
not imply harvestable spread — the marginal buyer is API-equipped. The cached-float
"moat" is stale (inspect links self-encode item data since March 2026). 10–15%/flip
is unestablished; underwriting assumption is now 3–5%, at which the $500/mo target
fails at any acceptable inventory cap.

Replacement: an **opportunity-duration recorder** (fits the ev_pipeline pattern):
capture new listings; compute attribute-adjusted fair value; record survival at
5s / 15s / 60s / 5m / 30m, competing equivalent listings, and eventual sale price.
Impose realistic human latency on any paper fill; no hindsight valuations.

Live gate: ≥100 prospective candidates AND projected **≥7% median net edge after
all fees on opportunities surviving long enough for manual execution**. Then $500,
20 completed cycles, P&L including losers and capital-days. ≥7% realised → $2,000.
3–5% realised → valid market, fails the side-project $500/mo objective; stop.

Constraint notes: Steam 7-day Trade Protection + ~8-day CSFloat proceeds hold means
"2 turns/month" is a portfolio-staggering claim, not a cash-cycle fact. Automation
against Steam itself is prohibited by the Subscriber Agreement — the recorder may
only use the third-party marketplace's permitted interfaces. Rails gate is now an
executed loop: deposit → buy → sell → payout landed in the actual UAE account.

## Capital position

| Destination | Now |
|---|---:|
| Japan pilot | $1,250 |
| CS2 recorder | $0 (software time only) |
| CS2 diagnostic (post-gate) | ≤$500 |
| Podcast lane | $0 (parked — preference call) |
| Language/dubbing | $0 (production time on existing pipeline) |
| Uncommitted | ~$13,250 |

Principle adopted verbatim from the review: capital accelerates a proven strategy;
it must not compensate for an unproven one. First KPI for both lanes:
completed net profit (including losers, returns, dead stock) ÷ capital-days deployed.
