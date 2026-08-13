#!/usr/bin/env python3
"""EXP-000 scorer: grade a completed vendor point-in-time audit CSV.

This script does NOT fetch vendor data. The audit protocol (sample design,
ground-truth collection) is specified in
docs/preregistration/EXP-000-vendor-pit-audit.md. Once the CSV below is filled
in by hand/tooling, this script computes the verdict so the pass/fail decision
is mechanical, not judgment applied after seeing the numbers.

CSV schema (header required):
    symbol,event_date,vendor_eps_asof,ground_truth_eps,post_announce_revised_eps,verifiable

    symbol                    ticker
    event_date                YYYY-MM-DD earnings announcement date
    vendor_eps_asof           vendor consensus EPS "as of" announcement-1d
    ground_truth_eps          archived pre-announcement consensus (blank if unverifiable)
    post_announce_revised_eps consensus AFTER the announcement (blank if unknown)
    verifiable                1 if ground truth was recoverable, else 0

Verdict rules (frozen in EXP-000 §6):
    PASS  iff match_rate >= 0.90 AND backfill_count == 0 AND verifiable >= 40
    where match  = |vendor - truth| <= $0.01
          backfill = vendor equals post-announcement revision while truth differs

Usage:
    python3 scripts/audit_vendor_pit.py data/exp000/audit_results.csv
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass

EPS_TOLERANCE = 0.01
FLOAT_EPS = 1e-9  # |2.23 - 2.24| must count as 0.01 despite float representation
MIN_VERIFIABLE = 40
MIN_MATCH_RATE = 0.90


def _within(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol + FLOAT_EPS


@dataclass
class Row:
    symbol: str
    event_date: str
    vendor: float | None
    truth: float | None
    revised: float | None
    verifiable: bool


def _parse_float(s: str) -> float | None:
    s = s.strip()
    return float(s) if s else None


def load(path: str) -> list[Row]:
    rows: list[Row] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        required = {
            "symbol",
            "event_date",
            "vendor_eps_asof",
            "ground_truth_eps",
            "post_announce_revised_eps",
            "verifiable",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV missing columns: {sorted(missing)}")
        for r in reader:
            rows.append(
                Row(
                    symbol=r["symbol"].strip(),
                    event_date=r["event_date"].strip(),
                    vendor=_parse_float(r["vendor_eps_asof"]),
                    truth=_parse_float(r["ground_truth_eps"]),
                    revised=_parse_float(r["post_announce_revised_eps"]),
                    verifiable=r["verifiable"].strip() == "1",
                )
            )
    return rows


def score(rows: list[Row]) -> int:
    verifiable = [r for r in rows if r.verifiable and r.vendor is not None and r.truth is not None]
    matches, backfills = [], []
    for r in verifiable:
        matched = _within(r.vendor, r.truth, EPS_TOLERANCE)
        matches.append((r, matched))
        if (
            not matched
            and r.revised is not None
            and _within(r.vendor, r.revised, EPS_TOLERANCE)
        ):
            backfills.append(r)

    n_ver = len(verifiable)
    n_match = sum(1 for _, m in matches if m)
    match_rate = n_match / n_ver if n_ver else 0.0

    print(f"events total:        {len(rows)}")
    print(f"events verifiable:   {n_ver} (minimum {MIN_VERIFIABLE})")
    print(f"EPS matches:         {n_match}/{n_ver}  rate={match_rate:.1%} (minimum {MIN_MATCH_RATE:.0%})")
    print(f"backfill flags:      {len(backfills)} (maximum 0)")
    for r in backfills:
        print(f"  BACKFILL: {r.symbol} {r.event_date} vendor={r.vendor} "
              f"truth={r.truth} post-announce={r.revised}")
    for r, m in matches:
        if not m and r not in backfills:
            print(f"  MISMATCH: {r.symbol} {r.event_date} vendor={r.vendor} truth={r.truth}")

    if n_ver < MIN_VERIFIABLE:
        print("\nVERDICT: INCONCLUSIVE — enlarge sample per EXP-000 §6 before judging.")
        return 2
    if match_rate >= MIN_MATCH_RATE and not backfills:
        print("\nVERDICT: PASS — vendor acceptable as point-in-time source; EXP-001 unblocked.")
        return 0
    print("\nVERDICT: FAIL — vendor rejected. Proceed to next vendor or re-rank per EXP-000 §8.")
    return 1


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    return score(load(sys.argv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
