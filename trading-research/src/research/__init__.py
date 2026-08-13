"""Execution-first research toolkit: pessimistic fills, cost ladders,
cluster-bootstrap statistics, and an event-study backtest engine.

Zero third-party dependencies by design so every kill decision is
reproducible anywhere Python 3.11+ runs.
"""

from research.execution import (
    BP,
    CostAssumptions,
    Quote,
    Side,
    marketable_limit_fill,
    round_trip_ladder,
)
from research.stats import annualized_sharpe, cluster_bootstrap_mean

__all__ = [
    "BP",
    "CostAssumptions",
    "Quote",
    "Side",
    "marketable_limit_fill",
    "round_trip_ladder",
    "annualized_sharpe",
    "cluster_bootstrap_mean",
]
