#!/usr/bin/env python3
"""Prospective opportunity log for the Japan corridor pilot.

Discipline instrument, not automation: every candidate gets logged when first
seen, with the information available AT THAT MOMENT. Outcomes are recorded as
they resolve. Stats separate the two denominators the reviews demanded:
  - observability: how often listings can even be underwritten
  - incidence: qualified opportunities per 100 observable listings
and realized economics count losers, returns and dead stock.

States (from research/final-program.md taxonomy):
  unobservable : identity_unknown | condition_unknown | exit_estimate_unavailable
                 | listing_unavailable
  qualified    : spread_negative | spread_positive
  in-flight    : lost_auction | purchased | inspection_downgrade | listed
  terminal     : completed_profit | completed_loss | returned | dead_stock

Usage:
  oplog.py add --model "SEIKO SARB033" --source yahoo --url URL \
               --first-price-jpy 12000 --expected-sale-usd 180 \
               --state spread_positive [--notes "..."]
  oplog.py update <id> --state purchased --final-price-jpy 13500
  oplog.py update <id> --state completed_profit --net-usd 52
  oplog.py list [--state STATE]
  oplog.py stats
"""
import argparse, json, os, sys, time, uuid

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "opportunities.jsonl")

UNOBSERVABLE = {"identity_unknown", "condition_unknown", "exit_estimate_unavailable", "listing_unavailable"}
QUALIFIED = {"spread_negative", "spread_positive"}
INFLIGHT = {"lost_auction", "purchased", "inspection_downgrade", "listed"}
TERMINAL = {"completed_profit", "completed_loss", "returned", "dead_stock"}
ALL_STATES = UNOBSERVABLE | QUALIFIED | INFLIGHT | TERMINAL


def read_all():
    if not os.path.exists(LOG):
        return {}
    recs = {}
    with open(LOG) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                recs[r["id"]] = {**recs.get(r["id"], {}), **r}  # last write wins per field
    return recs


def append(rec):
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def cmd_add(a):
    if a.state not in ALL_STATES:
        sys.exit(f"unknown state {a.state!r}; valid: {sorted(ALL_STATES)}")
    rec = {
        "id": uuid.uuid4().hex[:8],
        "ts_first_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": a.model, "source": a.source, "url": a.url,
        "first_price_jpy": a.first_price_jpy,
        "expected_sale_usd": a.expected_sale_usd,
        "state": a.state, "notes": a.notes,
    }
    append(rec)
    print(rec["id"])


def cmd_update(a):
    recs = read_all()
    if a.id not in recs:
        sys.exit(f"no record {a.id}")
    if a.state and a.state not in ALL_STATES:
        sys.exit(f"unknown state {a.state!r}")
    patch = {"id": a.id, "ts_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for k in ("state", "final_price_jpy", "landed_usd", "sold_usd", "net_usd", "notes"):
        v = getattr(a, k.replace("-", "_"), None)
        if v is not None:
            patch[k] = v
    append(patch)
    print("ok")


def cmd_list(a):
    for r in read_all().values():
        if a.state and r.get("state") != a.state:
            continue
        print(f'{r["id"]}  {r.get("state","?"):24}  {r.get("model","?")[:40]:40}  '
              f'¥{r.get("final_price_jpy") or r.get("first_price_jpy","?")}  '
              f'exp ${r.get("expected_sale_usd","?")}  net ${r.get("net_usd","-")}')


def cmd_stats(a):
    recs = list(read_all().values())
    n = len(recs)
    if not n:
        sys.exit("log is empty")
    unob = [r for r in recs if r.get("state") in UNOBSERVABLE]
    observable = [r for r in recs if r.get("state") not in UNOBSERVABLE]
    qualified_pos = [r for r in observable if r.get("state") == "spread_positive"
                     or r.get("state") in INFLIGHT | TERMINAL]
    purchased = [r for r in recs if r.get("state") in {"purchased", "inspection_downgrade", "listed"} | TERMINAL]
    terminal = [r for r in recs if r.get("state") in TERMINAL]
    completed = [r for r in terminal if r.get("net_usd") is not None and r.get("landed_usd")]
    total_net = sum(r["net_usd"] for r in terminal if r.get("net_usd") is not None)
    total_landed = sum(r["landed_usd"] for r in terminal if r.get("landed_usd"))
    out = {
        "records": n,
        "observability_rate": round(len(observable) / n, 3),
        "qualified_per_100_observable": round(100 * len(qualified_pos) / max(1, len(observable)), 1),
        "purchase_conversion": f"{len(purchased)}/{len(qualified_pos)}",
        "terminal_count": len(terminal),
        "realized_net_usd_incl_losers": round(total_net, 2),
        "realized_roi_on_cost": round(total_net / total_landed, 4) if total_landed else None,
        "scale_gate": "PASS" if (total_landed and total_net / total_landed >= 0.20 and len(completed) >= 10) else
                      f"pending ({len(completed)}/10 terminal w/ economics; gate: realized ROI >= 20%)",
    }
    json.dump(out, sys.stdout, indent=2); print()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("add")
    q.add_argument("--model", required=True); q.add_argument("--source", required=True)
    q.add_argument("--url", default=""); q.add_argument("--first-price-jpy", type=float, required=True)
    q.add_argument("--expected-sale-usd", type=float, required=True)
    q.add_argument("--state", required=True); q.add_argument("--notes", default="")
    q.set_defaults(fn=cmd_add)
    q = sub.add_parser("update")
    q.add_argument("id"); q.add_argument("--state"); q.add_argument("--final-price-jpy", type=float)
    q.add_argument("--landed-usd", type=float); q.add_argument("--sold-usd", type=float)
    q.add_argument("--net-usd", type=float); q.add_argument("--notes")
    q.set_defaults(fn=cmd_update)
    q = sub.add_parser("list"); q.add_argument("--state"); q.set_defaults(fn=cmd_list)
    q = sub.add_parser("stats"); q.set_defaults(fn=cmd_stats)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
