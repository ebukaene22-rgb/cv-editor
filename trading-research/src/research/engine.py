"""Event-study backtest engine.

The engine is deliberately data-source-agnostic: callers supply quote
providers as callables, so the same code runs against synthetic quotes in
tests today and real point-in-time NBBO later. Two invariants are enforced
here rather than left to discipline:

* Point-in-time: an event whose entry timestamp precedes the timestamp at
  which its signal became observable is rejected (look-ahead bias is a hard
  error, not a warning).
* Pessimistic fills: entries go through `marketable_limit_fill`; a missed
  fill is recorded as a miss, never silently repriced.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Hashable

from research.execution import (
    CostAssumptions,
    LADDER_RUNGS,
    Quote,
    Side,
    marketable_limit_fill,
    round_trip_ladder,
)
from research.stats import BootstrapResult, cluster_bootstrap_mean


@dataclass(frozen=True)
class Event:
    """One tradeable signal occurrence.

    Timestamps are opaque orderable values (e.g. datetimes or ints); the
    engine only compares them.
    """

    event_id: str
    symbol: str
    observable_ts: object  # when the signal became knowable
    entry_ts: object       # when we intend to trade
    side: Side
    cluster_key: Hashable  # e.g. announcement calendar date
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EventOutcome:
    event: Event
    filled: bool
    ladder: dict[str, float] | None = None
    miss_reason: str = ""


@dataclass(frozen=True)
class StudyResult:
    outcomes: list[EventOutcome]
    summaries: dict[str, BootstrapResult]  # one per ladder rung, filled events only

    @property
    def fill_rate(self) -> float:
        if not self.outcomes:
            return 0.0
        return sum(1 for o in self.outcomes if o.filled) / len(self.outcomes)


QuoteProvider = Callable[[Event], Quote]


def run_event_study(
    events: Iterable[Event],
    *,
    entry_quotes: QuoteProvider,
    exit_quotes: QuoteProvider,
    holding_days: float,
    costs: CostAssumptions,
    limit_offset_bp: float = 5.0,
    n_boot: int = 10_000,
    seed: int = 0,
) -> StudyResult:
    """Run every event through pessimistic execution and summarize by rung.

    Raises ValueError on any event violating the point-in-time invariant.
    """
    outcomes: list[EventOutcome] = []
    for ev in events:
        if ev.entry_ts < ev.observable_ts:  # type: ignore[operator]
            raise ValueError(
                f"look-ahead bias: event {ev.event_id} entry_ts {ev.entry_ts!r} "
                f"precedes observable_ts {ev.observable_ts!r}"
            )
        eq = entry_quotes(ev)
        fill = marketable_limit_fill(
            eq,
            ev.side,
            is_entry=True,
            limit_offset_bp=limit_offset_bp,
            slippage_bp=costs.slippage_bp_per_side,
        )
        if not fill.filled:
            outcomes.append(EventOutcome(ev, filled=False, miss_reason=fill.reason))
            continue
        ladder = round_trip_ladder(eq, exit_quotes(ev), ev.side, holding_days, costs)
        outcomes.append(EventOutcome(ev, filled=True, ladder=ladder))

    filled = [o for o in outcomes if o.filled and o.ladder is not None]
    summaries: dict[str, BootstrapResult] = {}
    if filled:
        for rung in LADDER_RUNGS:
            by_cluster: dict[Hashable, list[float]] = {}
            for o in filled:
                by_cluster.setdefault(o.event.cluster_key, []).append(o.ladder[rung])
            summaries[rung] = cluster_bootstrap_mean(
                by_cluster, n_boot=n_boot, seed=seed
            )
    return StudyResult(outcomes=outcomes, summaries=summaries)
