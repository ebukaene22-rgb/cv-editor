# Unit-value floor — the constraint underneath every mechanism (2026-08-24)

Written after the small-goods liquidation KILL, because that cohort's failure
is being read as evidence about *liquidation* when it is mostly evidence about
*unit value*.

## What the Wyze cohort actually was

136 of 138 manifest lines are one brand. Exit prices $9.99–$21.49 against
$10/unit outbound shipping — fulfilment is **47–100% of revenue** before a
single fee. The gate imposed a GBP 15 contribution requirement on items
selling for GBP 7–16. No acquisition mechanism clears that: not liquidation,
not dealer closeout, not open-box, not bundle decomposition. The verdict
KILL_ECONOMICS is correct for the cohort and near-uninformative about the
mechanism.

## The floor, computed

Minimum exit price to reach a target contribution, assuming a *generous* 40%
buy-to-exit ratio (i.e. a strong sourcing discount already granted), AE seller,
12.9% FVF, per-order + regulatory fees, 6% returns:

| target CM | ship £3 | ship £5 | ship £8 |
|---|---:|---:|---:|
| £5 | £24 | £29 | £35 |
| £10 | £35 | £40 | £46 |
| £15 | £46 | £51 | £57 |
| £20 | £57 | £61 | £68 |
| £25 | £68 | £72 | £79 |

Below these exit prices the target is unreachable **at any acquisition
discount**, because fees and fulfilment are near-fixed per unit while margin
scales with price.

## Consequences for mechanism selection

1. **A £15 contribution requires roughly a £50+ exit product.** Every cohort
   run to date has been dominated by sub-£40 goods. That is the common factor
   behind clearance, fitment, small-goods liquidation, and multipack
   decomposition failing — not four independent mechanism failures.
2. **Bundle decomposition is structurally worse than it looks**, and this is
   why: splitting a kit into N components multiplies fulfilment by N while
   revenue only redistributes. Adam's Floor Mat Holder prices at 1/2/4-pack
   ($19.99/$34.99/$59.99) give a $19.97 gross spread on decomposition — and
   4x£5 shipping erases it. Decomposition only works where components are
   individually above the floor, which is rare in multipacks by construction.
3. **The screen should be applied before sourcing, not after.** Any future
   cohort should be filtered to candidates whose *exit* price clears the floor
   for the target contribution, before identity or economics work is spent.

## Recommendation

Stop selecting cohorts by acquisition mechanism and start selecting by unit
value. The next test — whatever its mechanism — should draw only from
products with a plausible exit above ~£50, and should treat any cohort whose
median exit is under £30 as pre-failed.
