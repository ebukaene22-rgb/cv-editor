#!/usr/bin/env python3
"""
Availability telemetry.

An `available` 1 -> 0 transition does NOT mean a unit sold. It means the
variant became unavailable, which can be a sellout, a manual inventory edit,
a withdrawn product, a reallocation, a disabled variant, or the store
changing how it exposes stock. Calling that "sell-through" overclaims, so
nothing here is named that. The measured quantity is *availability
depletion*, and demand is only ever inferred from it.

What makes the inference stronger:

  * A single 1 -> 0 flip is weak evidence. It is indistinguishable from a
    withdrawal.
  * A REPLENISHMENT CYCLE -- 0 -> 1 -> 0 -- is much stronger. The store put
    stock back and it went away again. Withdrawals do not do that.
  * Repeated cycles are stronger still, and the rate of cycles is a usable
    proxy for demand intensity.

Confounders explicitly controlled for:

  * Store-wide flips. If half a store's variants go unavailable in the same
    snapshot, that is a feed or platform artefact, not demand. Those
    transitions are discounted via `mass_flip_fraction`.
  * Disappearance. A SKU that vanishes from the feed entirely was withdrawn,
    not bought. Those are marked `delisted` and excluded from cycle counts.

Everything here degrades honestly: with one snapshot there is no signal, and
the code says so rather than returning zero.
"""
from datetime import datetime

# If more than this fraction of a store's SKUs flip in one snapshot, treat
# that snapshot's transitions for that store as an artefact.
MASS_FLIP_THRESHOLD = 0.25


def _snapshots(conn, domain):
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT ts FROM obs WHERE domain=? ORDER BY ts", (domain,))]


def mass_flip_snapshots(conn, domain):
    """
    Snapshots where an implausible share of the store went unavailable at
    once. Returns {ts: fraction} for the offending snapshots only.
    """
    snaps = _snapshots(conn, domain)
    bad = {}
    prev = None
    for ts in snaps:
        cur = dict(conn.execute(
            "SELECT sku, available FROM obs WHERE domain=? AND ts=?",
            (domain, ts)))
        if prev:
            shared = set(prev) & set(cur)
            if shared:
                flips = sum(1 for s in shared if prev[s] == 1 and cur[s] == 0)
                frac = flips / len(shared)
                if frac > MASS_FLIP_THRESHOLD:
                    bad[ts] = frac
        prev = cur
    return bad


def depletion_signals(conn, domain):
    """
    Batch per-store computation -> {sku: signal dict}.

    signal keys:
      n_obs        snapshots this sku appeared in
      stockouts    1 -> 0 transitions (artefact snapshots excluded)
      restocks     0 -> 1 transitions
      cycles       complete restock-then-deplete cycles: the strong evidence
      oos_frac     fraction of observations spent unavailable
      delisted     sku stopped appearing in the feed
      intensity    cycles per observed interval, 0..1-ish
      confidence   how much to trust it: 'none'|'weak'|'moderate'|'strong'
    """
    snaps = _snapshots(conn, domain)
    if len(snaps) < 2:
        return {}
    artefacts = mass_flip_snapshots(conn, domain)
    last_ts = snaps[-1]

    frames = {ts: {} for ts in snaps}
    for ts, sku, avail, price in conn.execute(
            "SELECT ts, sku, available, price FROM obs "
            "WHERE domain=? ORDER BY ts", (domain,)):
        frames[ts][sku] = (avail, price)

    def elapsed_days(t0, t1):
        a = datetime.fromisoformat(t0.replace("Z", "+00:00"))
        b = datetime.fromisoformat(t1.replace("Z", "+00:00"))
        return max(0.0, (b - a).total_seconds() / 86400.0)

    out = {}
    all_skus = set().union(*(set(frame) for frame in frames.values()))
    for sku in all_skus:
        seq = [(ts, *frames[ts][sku]) for ts in snaps if sku in frames[ts]]
        stockouts = restocks = cycles = 0
        valid_intervals = price_changes = 0
        sku_days = in_stock_days = out_of_stock_days = 0.0
        armed = False          # saw a restock, waiting for the next depletion
        for t0, t1 in zip(snaps, snaps[1:]):
            before, after = frames[t0].get(sku), frames[t1].get(sku)
            if before is None or after is None:
                # A missing catalogue row is unknown, not a continuous state.
                # Never bridge a transition across that observation gap.
                armed = False
                continue
            if t1 in artefacts:
                armed = False
                continue       # store-wide event: not demand
            a0, p0 = before
            a1, p1 = after
            days = elapsed_days(t0, t1)
            if days <= 0:
                continue
            valid_intervals += 1
            sku_days += days
            if a0:
                in_stock_days += days
            else:
                out_of_stock_days += days
            if p0 is not None and p1 is not None and p0 != p1:
                price_changes += 1
            if a0 == 1 and a1 == 0:
                stockouts += 1
                if armed:
                    cycles += 1
                    armed = False
            elif a0 == 0 and a1 == 1:
                restocks += 1
                armed = True
        n = len(seq)
        intervals = max(1, valid_intervals)
        delisted = seq[-1][0] != last_ts
        oos = (out_of_stock_days / sku_days if sku_days else
               sum(1 for _, a, _ in seq if a == 0) / n)
        observed_prices = [p for _, _, p in seq if p is not None and p > 0]
        price_stability = None
        if observed_prices:
            price_stability = min(observed_prices) / max(observed_prices)

        if delisted or n < 2:
            conf = "none"
        elif cycles >= 2:
            conf = "strong"
        elif cycles == 1:
            conf = "moderate"
        elif stockouts >= 1:
            conf = "weak"
        else:
            conf = "none"

        out[sku] = {"n_obs": n, "stockouts": stockouts, "restocks": restocks,
                    "cycles": cycles, "oos_frac": oos, "delisted": delisted,
                    "intensity": cycles / intervals, "confidence": conf,
                    "first_seen": seq[0][0], "last_seen": seq[-1][0],
                    "sku_days": sku_days, "in_stock_days": in_stock_days,
                    "out_of_stock_days": out_of_stock_days,
                    "valid_intervals": valid_intervals,
                    "coverage": valid_intervals / max(1, len(snaps) - 1),
                    "price_changes": price_changes,
                    "price_stability": price_stability,
                    "cycles_per_30d": (cycles / sku_days * 30.0
                                       if sku_days else None)}
    return out


def expected_monthly_orders(sig, share_of_market=0.15, snapshots_per_day=1.0):
    """
    Convert a depletion signal into an order-rate estimate.

    This is a STRUCTURED ESTIMATOR, not a fitted model. There is no training
    data yet -- fitting demand requires observed outcomes (units we actually
    sold), which do not exist until the thing has been traded. Until then the
    honest move is an explicit formula with visible assumptions rather than a
    model that launders guesses through arithmetic.

    `share_of_market` is the fraction of that product's demand we would
    expect to capture as one seller among many; it is the single most
    load-bearing assumption here and belongs in a sensitivity analysis, not
    buried as a constant.
    """
    if not sig or sig["confidence"] in ("none",):
        return None
    days = sig.get("sku_days")
    if not days:
        days = max(1.0, sig["n_obs"] / max(snapshots_per_day, 1e-6))
    # Each completed cycle = at least one replenished batch depleted.
    cycles_per_day = sig["cycles"] / days
    if cycles_per_day <= 0:
        # Weak evidence: one stockout, never restocked. Floor it low.
        return 0.5 if sig["stockouts"] else None
    return cycles_per_day * 30.0 * share_of_market * 10.0   # ~10 units/batch


def opportunity_score(exp_monthly_orders, contribution_per_order,
                      match_confidence, supply_confidence,
                      capital_cost_per_month=0.0):
    """
    Directly interpretable: expected monthly contribution, risk-adjusted.

        E[monthly contribution] = E[orders] x E[contribution/order]
        score = E[...] x MatchConf x SupplyConf - CapitalCost

    Replaces the earlier `margin x velocity / log(competitors)`, which mixed
    incommensurable quantities multiplicatively and produced rankings that
    could not be sanity-checked against money. Competitor count now feeds the
    demand estimate (as a share-of-market input) instead of being an
    arbitrary divisor.
    """
    if exp_monthly_orders is None or contribution_per_order is None:
        return None
    return (exp_monthly_orders * contribution_per_order
            * match_confidence * supply_confidence) - capital_cost_per_month


def share_from_competition(n_competitors):
    """Crowding enters demand, not the score: more sellers, smaller slice."""
    if not n_competitors:
        return 0.35
    return max(0.02, min(0.35, 1.5 / (n_competitors ** 0.5)))
