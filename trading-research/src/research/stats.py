"""Statistics with honest error bars.

Trades sharing an announcement date, index-rebalance event, or calendar day are
not independent draws. All programme-level summary statistics therefore
bootstrap by *cluster*, resampling whole event groups with replacement, so the
confidence intervals do not pretend one earnings season is fifty observations.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Hashable


@dataclass(frozen=True)
class BootstrapResult:
    point: float
    ci_low: float
    ci_high: float
    n_clusters: int
    n_obs: int
    n_boot: int
    ci_level: float

    def excludes_zero(self) -> bool:
        return self.ci_low > 0 or self.ci_high < 0


def cluster_bootstrap_mean(
    returns_by_cluster: Mapping[Hashable, Sequence[float]],
    *,
    n_boot: int = 10_000,
    ci_level: float = 0.95,
    seed: int = 0,
) -> BootstrapResult:
    """Bootstrap CI for the mean, resampling clusters with replacement.

    Each bootstrap replicate draws `n_clusters` clusters (with replacement)
    and averages every observation inside the drawn clusters.
    """
    clusters = [list(v) for v in returns_by_cluster.values() if len(v) > 0]
    if not clusters:
        raise ValueError("no non-empty clusters supplied")
    if not 0 < ci_level < 1:
        raise ValueError("ci_level must be in (0, 1)")

    all_obs = [x for c in clusters for x in c]
    point = sum(all_obs) / len(all_obs)

    rng = random.Random(seed)
    k = len(clusters)
    means: list[float] = []
    for _ in range(n_boot):
        total = 0.0
        count = 0
        for _ in range(k):
            c = clusters[rng.randrange(k)]
            total += sum(c)
            count += len(c)
        means.append(total / count)
    means.sort()

    alpha = (1 - ci_level) / 2
    lo_idx = max(0, min(len(means) - 1, int(math.floor(alpha * n_boot))))
    hi_idx = max(0, min(len(means) - 1, int(math.ceil((1 - alpha) * n_boot)) - 1))
    return BootstrapResult(
        point=point,
        ci_low=means[lo_idx],
        ci_high=means[hi_idx],
        n_clusters=k,
        n_obs=len(all_obs),
        n_boot=n_boot,
        ci_level=ci_level,
    )


def annualized_sharpe(
    period_returns: Sequence[float],
    *,
    periods_per_year: int = 252,
    risk_free_per_period: float = 0.0,
) -> float:
    """Annualized Sharpe ratio of per-period returns. Requires >= 2 periods."""
    n = len(period_returns)
    if n < 2:
        raise ValueError("need at least 2 return observations")
    excess = [r - risk_free_per_period for r in period_returns]
    mean = sum(excess) / n
    var = sum((r - mean) ** 2 for r in excess) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        raise ValueError("zero return volatility; Sharpe undefined")
    return mean / sd * math.sqrt(periods_per_year)
