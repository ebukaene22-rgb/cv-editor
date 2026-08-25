#!/usr/bin/env python3
"""Survival analysis over the recorder's data: the go/no-go instrument.

For each gross-edge bucket, reports how many apparently-cheap listings were
still purchasable at each horizon, and the median NET edge (after sell +
withdrawal fees) of listings that survived the gate horizon. Prints the live
verdict against the gate in config.json:
  >= min_candidates AND median net edge on survivors >= 7% at 5min -> PASS
"""
import json, os, sqlite3, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
DB = os.path.join(HERE, "recorder.sqlite")

BUCKETS = [(-1.0, 0.0, "<0%"), (0.0, 0.03, "0-3%"), (0.03, 0.05, "3-5%"),
           (0.05, 0.07, "5-7%"), (0.07, 0.10, "7-10%"), (0.10, 0.15, "10-15%"),
           (0.15, 9.9, ">15%")]


def main():
    if not os.path.exists(DB):
        sys.exit("no recorder.sqlite yet - run recorder.py first")
    db = sqlite3.connect(DB)
    horizons = CFG["recheck_horizons_s"]
    fees = CFG["fees"]["sell_pct"] + CFG["fees"]["withdrawal_pct"]
    gate = CFG["gate"]
    rows = db.execute("SELECT id, edge_gross FROM listings WHERE edge_gross IS NOT NULL").fetchall()
    checks = {}
    for lid, h, state in db.execute("SELECT listing_id, horizon_s, state FROM checks"):
        checks.setdefault(lid, {})[h] = state
    candidates = [(lid, e) for lid, e in rows if e is not None and e > 0]
    print(f"listings with reference price: {len(rows)}; positive-edge candidates: {len(candidates)}\n")
    hdr = "edge bucket | n    " + "".join(f"| alive@{h:>4}s " for h in horizons)
    print(hdr); print("-" * len(hdr))
    for lo, hi, label in BUCKETS:
        grp = [(lid, e) for lid, e in rows if e is not None and lo <= e < hi]
        line = f"{label:11} | {len(grp):<4} "
        for h in horizons:
            got = [lid for lid, _ in grp if checks.get(lid, {}).get(h)]
            alive = [lid for lid in got if checks[lid][h] == "listed"]
            line += f"| {len(alive):>3}/{len(got):<3}   " if got else "|   -      "
        print(line)
    gh = gate["survival_horizon_s"]
    survivors = [e for lid, e in candidates if checks.get(lid, {}).get(gh) == "listed"]
    net = [e - fees for e in survivors]
    med = statistics.median(net) if net else None
    print(f"\nsurvivors at {gh}s: {len(survivors)}; median NET edge (after {fees:.1%} fees): "
          f"{med:.2%}" if med is not None else f"\nsurvivors at {gh}s: 0")
    ok = len(candidates) >= gate["min_candidates"] and med is not None and med >= gate["min_median_net_edge_on_survivors"]
    print(f"GATE ({gate['min_candidates']}+ candidates, median net edge >= "
          f"{gate['min_median_net_edge_on_survivors']:.0%} on {gh}s survivors): {'PASS - $500 diagnostic capital unlocked' if ok else 'not passed - no live capital'}")


if __name__ == "__main__":
    main()
