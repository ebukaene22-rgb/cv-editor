# Valuation and offer (Stage 7)

Anchor on **profit**, not revenue. Revenue multiples are how listings are
written; profit multiples are how they are bought.

## Baseline

- **20–30× monthly profit** for a flat, verified, self-running product.
- **Discount for:** declining revenue, single channel, unverified numbers, high
  maintenance load, owner-dependency.
- **Premium for:** growing, organic channel, low support load, pricing headroom.

## The sanity check

After landing on a number, check that `payback_months` sits under 36 —

```
payback_months = asking_price / monthly_profit
```

If the seller's asking price implies otherwise, that is the negotiating
position, and it should be stated as arithmetic rather than as opinion:

> At £X and £Y/month profit that's a NN-month payback. I'd need to be at £Z for
> this to work as an acquisition rather than a job.

An arithmetic disagreement is one a reasonable seller can check. An opinion
about what their business is worth is one they will defend.

## Structure

**70% at close, 30% at 60 days conditional on revenue holding.**

It protects against churn that isn't visible in twelve months of top-line
revenue, and it is a fair ask — a confident seller accepts it. A seller who
refuses any holdback at all is telling you something about the 60 days.

## What the config does and does not cover

`config.yaml` holds the *screening* thresholds — `max_price_to_revenue`,
`max_payback_months`, the budget band. Those are filters for what is worth
looking at. They are not an offer model, and nothing in this system produces a
valuation. Stage 7 is manual on purpose.
