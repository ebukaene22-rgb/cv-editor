#!/usr/bin/env python3
"""CS2 opportunity-duration recorder (diagnostic instrument, not a trader).

Polls CSFloat's public listings API (read-only, authorized, rate-limited) for
newly listed items in a fixed set of families, prices each against a rolling
same-family reference, and re-checks whether apparently-cheap listings are
still available at fixed horizons (5s/15s/60s/5m/30m). The output answers the
only question that matters before capital: do human-executable underpriced
listings exist, or do they vanish into bots within seconds?

This deliberately performs NO Steam interaction and NO purchases. It uses only
the third-party marketplace's documented API. Review CSFloat's ToS and set a
key from your profile's developer tab: export CSFLOAT_API_KEY=...

Usage:
  recorder.py run [--minutes 60]     poll + recheck loop
  recorder.py once                   single poll cycle (smoke test)
"""
import argparse, json, os, sqlite3, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
DB = os.path.join(HERE, "recorder.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings(
  id TEXT PRIMARY KEY, family TEXT, float_value REAL, price_cents INTEGER,
  ref_cents INTEGER, edge_gross REAL, created_at TEXT, first_seen_ts REAL);
CREATE TABLE IF NOT EXISTS checks(
  listing_id TEXT, horizon_s INTEGER, checked_ts REAL, state TEXT,
  price_cents INTEGER, PRIMARY KEY(listing_id, horizon_s));
"""

_last_req = 0.0


def api_get(path, params=None, auth=True):
    global _last_req
    gap = CFG["min_requests_gap_s"] - (time.time() - _last_req)
    if gap > 0:
        time.sleep(gap)
    url = CFG["api_base"] + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "arb-diagnostic/0.1 (read-only research)"})
    key = os.environ.get(CFG["api_key_env"], "")
    if auth:
        if not key:
            sys.exit(f"set {CFG['api_key_env']} (CSFloat profile -> developer tab)")
        req.add_header("Authorization", key)
    _last_req = time.time()
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"_gone": True}
        print(f"[warn] {e.code} on {path}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[warn] {e} on {path}", file=sys.stderr)
        return None


def listings_from(resp):
    if resp is None:
        return []
    return resp.get("data", resp) if isinstance(resp, dict) else resp


def reference_cents(db, family, exclude_id):
    rows = db.execute(
        "SELECT price_cents FROM listings WHERE family=? AND id<>? ORDER BY first_seen_ts DESC LIMIT ?",
        (family, exclude_id, CFG["reference_window"])).fetchall()
    prices = sorted(r[0] for r in rows)
    return prices[len(prices) // 2] if len(prices) >= 5 else None


def poll_once(db):
    new = 0
    for family in CFG["families"]:
        resp = api_get("/listings", {"sort_by": "most_recent", "limit": 50,
                                     "market_hash_name": family, "type": "buy_now"})
        for l in listings_from(resp) or []:
            lid = str(l.get("id"))
            if not lid or db.execute("SELECT 1 FROM listings WHERE id=?", (lid,)).fetchone():
                continue
            item = l.get("item", {})
            price = l.get("price")
            if price is None:
                continue
            ref = reference_cents(db, family, lid)
            edge = (ref - price) / ref if ref else None
            db.execute("INSERT INTO listings VALUES(?,?,?,?,?,?,?,?)",
                       (lid, family, item.get("float_value"), price, ref, edge,
                        l.get("created_at"), time.time()))
            new += 1
    db.commit()
    return new


def recheck_due(db):
    now = time.time()
    due = db.execute("""
      SELECT l.id, l.first_seen_ts FROM listings l WHERE EXISTS (
        SELECT 1 FROM (SELECT ? AS h UNION SELECT ? UNION SELECT ? UNION SELECT ? UNION SELECT ?) hs
        WHERE l.first_seen_ts + hs.h <= ?
          AND NOT EXISTS (SELECT 1 FROM checks c WHERE c.listing_id=l.id AND c.horizon_s=hs.h))
      ORDER BY l.first_seen_ts LIMIT 20""",
      (*CFG["recheck_horizons_s"], now)).fetchall()
    for lid, first_seen in due:
        resp = api_get(f"/listings/{lid}", auth=False)
        state = "gone" if (resp or {}).get("_gone") else (resp or {}).get("state", "unknown")
        price = (resp or {}).get("price")
        for h in CFG["recheck_horizons_s"]:
            if first_seen + h <= now and not db.execute(
                    "SELECT 1 FROM checks WHERE listing_id=? AND horizon_s=?", (lid, h)).fetchone():
                db.execute("INSERT INTO checks VALUES(?,?,?,?,?)", (lid, h, now, state, price))
    db.commit()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--minutes", type=float, default=60)
    sub.add_parser("once")
    a = p.parse_args()
    db = sqlite3.connect(DB)
    db.executescript(SCHEMA)
    if a.cmd == "once":
        print(f"new listings: {poll_once(db)}")
        recheck_due(db)
        return
    end = time.time() + a.minutes * 60
    while time.time() < end:
        n = poll_once(db)
        recheck_due(db)
        total = db.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        print(f"[{time.strftime('%H:%M:%S')}] +{n} new, {total} tracked")
        time.sleep(CFG["poll_interval_s"])


if __name__ == "__main__":
    main()
