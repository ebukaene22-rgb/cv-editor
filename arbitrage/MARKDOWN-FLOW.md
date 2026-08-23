# Markdown event flow — the alert product's raw material (2026-08-23)

Pivot #1 (B2B inventory-anomaly alerts) sells *events*: "this supplier
just discounted X". So the decisive number is how many NEW deep-markdown
events the system observes per day. Measured on the archive.

## Method
Consecutive snapshots, same store set, SKU-keyed join. An event = a SKU
crossing into >=35% off that was NOT >=35% off in the prior snapshot.
Verified on a clean 26-hour pair (2026-08-21 -> 2026-08-22, 23 stores).
(An earlier verification pass of mine returned zeros because the query
dropped the `Z` from the timestamps and joined nothing; corrected here.)

## Result over 26 hours, 79,803 SKUs tracked in both snapshots

| observation | count |
|---|---|
| any price change | 1,883 |
| compare-at price change | 1,616 |
| availability flips | 619 |
| deeply discounted (>=35%) in first snapshot | 8,166 |
| deeply discounted in second | 7,229 |
| **NEWLY deep-discounted** | **0** |
| **no longer deep-discounted** | **937** |

Across all 11 snapshots spanning four days: **zero new deep-markdown
events observed.**

The market is demonstrably moving -- 1,883 price changes -- but the moves
were **upward**: Allbirds 60->100, 60->145, 112->160; Gymshark
16.20->27.00. Sales ENDING, prices reverting. We observed the tail of
clearance events, never the start of one.

## Implications

1. **Every one of the ~8,000 deep discounts in our data was already in
   progress when we started watching.** The "fresh shock" that both the
   latency thesis and the alert product depend on has never actually been
   observed by this system.
2. Discount events look **episodic** (seasonal sale launches), not a
   continuous stream. A four-day window can contain none. Any alert
   product must be sized against event frequency measured over months,
   not assumed.
3. **The depletion telemetry works** -- 619 availability flips in 26h.
   That component is sound and always was; earlier empty readings were a
   lack of well-spaced paired snapshots, not a defect.

## Caveat

Four days is a very short window and may have landed in a post-summer-sale
lull. This does not prove events are rare year-round. It does mean the
event rate is **unmeasured and currently indistinguishable from zero**,
and that measuring it is a prerequisite to any product that sells events.
