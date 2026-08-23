#!/usr/bin/env python3
"""
Dislocation gates -- FROZEN 2026-08-23, pre-cohort-5.

These thresholds were derived from the cohort 1-4 label post-mortem
(POSTMORTEM.md) and are frozen for the cohort-5 out-of-sample test.
DO NOT modify them until cohort 5 is fully labelled. The test is only
valid if the rules cannot move after seeing the data.

R1  premium:       filtered clean-comp ask median > 1.2x source reference
                   price (Shopify compare_at; an imperfect anchor, named
                   accordingly)
R2  support:       >= 3 clean identity-filtered comps
R3  executability: not purchasable at target-market retail. Automated
                   where a GB-region feed carries the SKU; otherwise a
                   REQUIRED manual check before any sold-price work.
"""
R1_PREMIUM_MIN = 1.2
R2_MIN_CLEAN_COMPS = 3
R3_RETAIL_MAX_RATIO = 1.3      # existing guard: comp >1.3x in-stock UK retail = not executable


def r1_premium(filtered_median_gbp, source_ref_gbp):
    if not filtered_median_gbp or not source_ref_gbp:
        return False
    return filtered_median_gbp > R1_PREMIUM_MIN * source_ref_gbp


def r2_support(n_clean_comps):
    return (n_clean_comps or 0) >= R2_MIN_CLEAN_COMPS


def passes(filtered_median_gbp, source_ref_gbp, n_clean_comps):
    """R1+R2. R3 is enforced by the retail guard + mandatory manual check."""
    return r1_premium(filtered_median_gbp, source_ref_gbp) and \
        r2_support(n_clean_comps)
