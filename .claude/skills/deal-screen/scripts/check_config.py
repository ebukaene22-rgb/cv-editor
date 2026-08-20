#!/usr/bin/env python3
"""Sanity-check acquisition/config.yaml before a run.

Every threshold in the system lives in one file, which is the right design and
also the single point where a typo silently changes what the pipeline rejects.
A band inverted by a slipped digit does not raise an error anywhere — it just
quietly returns nothing, or everything, and looks like a quiet week.

    python .claude/skills/deal-screen/scripts/check_config.py [path/to/config.yaml]

Exit 0 = safe to run. Exit 1 = fix it first.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "acquisition" / "src"))

from acq.config import Config  # noqa: E402

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

REQUIRED = [
    "budget.min_price_gbp", "budget.max_price_gbp",
    "targets.min_mrr_gbp", "targets.min_arpu_gbp", "targets.min_age_months",
    "thresholds.max_price_to_revenue", "thresholds.max_payback_months",
    "thresholds.min_trend_ratio", "thresholds.ltv_tolerance",
    "thresholds.customer_inflation_ratio", "thresholds.min_customer_price_gbp",
    "exclusions.categories", "exclusions.revenue_models",
    "scoring.flag_penalty", "scoring.verification_bonus",
    "neglect.min_active_installs", "neglect.min_months_since_update",
    "neglect.min_rating", "neglect.max_pages",
    "run.currency", "run.request_delay_seconds", "run.user_agent",
    "paths.store", "paths.neglect_store", "paths.out_dir",
]

errors: list[str] = []
warnings: list[str] = []


def check(cfg: Config) -> None:
    missing = set()
    for key in REQUIRED:
        try:
            cfg[key]
        except KeyError:
            errors.append(f"missing required key: {key}")
            missing.add(key)

    def have(*keys: str) -> bool:
        """Skip a check whose inputs are absent — the missing key is already an
        error, and one broken value should not hide the other three."""
        return not any(k in missing for k in keys)

    if not have("budget.min_price_gbp", "budget.max_price_gbp"):
        lo = hi = None
    else:
        lo, hi = cfg["budget.min_price_gbp"], cfg["budget.max_price_gbp"]
        if lo >= hi:
            errors.append(f"budget band is inverted or empty: min {lo} >= max {hi}")
        if lo < 0:
            errors.append(f"budget.min_price_gbp is negative: {lo}")

    if have("thresholds.min_trend_ratio"):
        lo_t = cfg["thresholds.min_trend_ratio"]
        hi_t = cfg.get("thresholds.max_trend_ratio", None)
        if hi_t is not None and lo_t >= hi_t:
            errors.append(f"trend band is inverted: min {lo_t} >= max {hi_t}")
        if lo_t > 1.0:
            warnings.append(f"min_trend_ratio {lo_t} > 1.0 — every flat business will "
                            f"be flagged DECLINING")

    for key in ("thresholds.max_price_to_revenue", "thresholds.max_payback_months",
                "targets.min_arpu_gbp", "thresholds.min_customer_price_gbp",
                "neglect.min_active_installs", "neglect.max_pages"):
        if have(key) and cfg[key] <= 0:
            errors.append(f"{key} must be positive, got {cfg[key]}")

    if have("thresholds.ltv_tolerance"):
        tol = cfg["thresholds.ltv_tolerance"]
        if not 0 < tol <= 5:
            errors.append(f"thresholds.ltv_tolerance should be a fraction like 0.5, "
                          f"got {tol}")

    if have("thresholds.customer_inflation_ratio"):
        ratio = cfg["thresholds.customer_inflation_ratio"]
        if not 0 < ratio < 1:
            errors.append(f"customer_inflation_ratio should sit between 0 and 1, got {ratio}")

    if have("neglect.min_rating"):
        rating = cfg["neglect.min_rating"]
        if not 0 <= rating <= 5:
            errors.append(f"neglect.min_rating is on a 0-5 scale, got {rating} "
                          f"(the API's 0-100 value is converted on ingestion)")

    if have("run.request_delay_seconds") and cfg["run.request_delay_seconds"] < 0.5:
        warnings.append(f"run.request_delay_seconds {cfg['run.request_delay_seconds']} is "
                        f"aggressive for a weekly-cadence system — back off politely")

    if have("run.currency") and cfg["run.currency"].upper() != "GBP":
        warnings.append(f"run.currency is {cfg['run.currency']} — every absolute "
                        f"threshold in this file is written in GBP")

    if not (cfg.get("audience.vertical", "") or "").strip():
        warnings.append("audience.vertical is unset. Stage 0 says pick one vertical and "
                        "fix it — a great one-off in the wrong vertical costs more than "
                        "it earns")

    if have("exclusions.categories") and not cfg.excluded_categories():
        warnings.append("exclusions.categories is empty — content sites and AI wrappers "
                        "will pass screening")
    if have("exclusions.revenue_models") and not cfg.excluded_revenue_models():
        warnings.append("exclusions.revenue_models is empty — pay-once listings will pass")

    mrr_floor = cfg["targets.min_mrr_gbp"] if have("targets.min_mrr_gbp") else None
    if mrr_floor and hi and mrr_floor * 12 > hi:
        warnings.append(f"min MRR £{mrr_floor}/mo implies £{mrr_floor * 12:,}/yr revenue, "
                        f"above the £{hi:,} budget ceiling — nothing will fit both")


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = Config.load(path)
    print(f"checking {cfg.source}")
    check(cfg)

    for w in warnings:
        print(f"  {YELLOW}WARN{RESET}  {w}")
    for e in errors:
        print(f"  {RED}ERROR{RESET} {e}")

    if errors:
        print(f"\n{RED}INVALID{RESET} — {len(errors)} error(s). Fix before running.")
        return 1
    band = f"£{cfg['budget.min_price_gbp']:,}–£{cfg['budget.max_price_gbp']:,}"
    print(f"\n{GREEN}VALID{RESET} — budget {band}, "
          f"max {cfg['thresholds.max_price_to_revenue']}x revenue, "
          f"payback under {cfg['thresholds.max_payback_months']} months, "
          f"ARPU floor £{cfg['targets.min_arpu_gbp']}"
          + (f", {len(warnings)} warning(s)" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
