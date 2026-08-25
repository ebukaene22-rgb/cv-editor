#!/usr/bin/env python3
"""Landed-cost / net-proceeds model for the Japan corridor pilot.

Implements the corrected fee stack from research/final-program.md:
eBay FVF includes payment processing (no separate 2%), plus the fixed
per-order fee, the international surcharge, Payoneer USD->AED FX, and a
return/defect reserve. The Dubai route adds the verified 10.25% duty+VAT
stack on CIF; the default route ships direct from Japan and skips it.

Usage:
  model.py evaluate --hammer-jpy 20000 --sale-usd 180 [--weight small]
                    [--category default] [--route direct|dubai]
  model.py max-bid  --sale-usd 180 [--weight small] [--category default]
                    [--route direct|dubai]
"""
import argparse, json, os, sys

CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_cfg(path=CFG_PATH):
    with open(path) as f:
        return json.load(f)


def landed_cost_usd(hammer_jpy, weight, route, cfg):
    """All-in cost of getting one item from auction close to sellable."""
    s = cfg["source_costs_jpy"]
    jpy = (
        hammer_jpy
        + hammer_jpy * s["proxy_card_pct"]
        + s["proxy_fee_per_item"]
        + s["jp_domestic_ship"]
        + s["consolidation_per_item"]
        + s["intl_ship_by_weight"][weight]
    )
    usd = jpy / cfg["fx"]["jpy_per_usd"]
    if route == "dubai":
        usd = usd * (1 + cfg["route"]["dubai_import_pct"]) + cfg["route"]["dubai_clearance_fee_usd"]
    return usd


def net_proceeds_usd(sale_usd, weight, category, cfg):
    """Cash that actually lands after a sale, before purchase cost."""
    c = cfg["sell_costs"]
    fvf = c["ebay_fvf_pct"].get(category, c["ebay_fvf_pct"]["default"])
    gross = sale_usd * (1 - fvf - c["ebay_intl_surcharge_pct"]) - c["ebay_per_order_usd"]
    gross -= c["outbound_ship_usd"][weight]
    gross *= 1 - c["payoneer_fx_pct"]
    gross -= sale_usd * c["return_defect_reserve_pct"]
    return gross


def evaluate(hammer_jpy, sale_usd, weight, category, route, cfg):
    landed = landed_cost_usd(hammer_jpy, weight, route, cfg)
    net = net_proceeds_usd(sale_usd, weight, category, cfg)
    profit = net - landed
    return {
        "landed_usd": round(landed, 2),
        "net_proceeds_usd": round(net, 2),
        "profit_usd": round(profit, 2),
        "roi_on_cost": round(profit / landed, 4) if landed > 0 else None,
        "margin_on_revenue": round(profit / sale_usd, 4) if sale_usd > 0 else None,
        "passes_buy_rule": profit / landed >= cfg["underwriting"]["target_roi_on_cost"] if landed > 0 else False,
    }


def max_bid_jpy(sale_usd, weight, category, route, cfg):
    """Highest hammer price at which the buy rule still passes.

    landed(h) is linear in h: landed = a*h + b, so solve
    net / (a*h + b) = 1 + target  =>  h = (net/(1+target) - b) / a
    """
    net = net_proceeds_usd(sale_usd, weight, category, cfg)
    target = cfg["underwriting"]["target_roi_on_cost"]
    a = (1 + cfg["source_costs_jpy"]["proxy_card_pct"]) / cfg["fx"]["jpy_per_usd"]
    b = landed_cost_usd(0, weight, route, cfg)
    if route == "dubai":
        a *= 1 + cfg["route"]["dubai_import_pct"]
    h = (net / (1 + target) - b) / a
    return max(0, int(h))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("evaluate", "max-bid"):
        q = sub.add_parser(name)
        q.add_argument("--sale-usd", type=float, required=True, help="conservative expected sale price (eBay sold p25, not best comp)")
        q.add_argument("--weight", choices=["small", "medium", "large"], default="small")
        q.add_argument("--category", default="default")
        q.add_argument("--route", choices=["direct", "dubai"], default=None)
        if name == "evaluate":
            q.add_argument("--hammer-jpy", type=float, required=True)
    args = p.parse_args()
    cfg = load_cfg()
    route = args.route or cfg["route"]["mode"]
    if args.cmd == "evaluate":
        out = evaluate(args.hammer_jpy, args.sale_usd, args.weight, args.category, route, cfg)
    else:
        out = {"max_bid_jpy": max_bid_jpy(args.sale_usd, args.weight, args.category, route, cfg),
               "route": route, "note": "highest hammer at which net/landed >= 1.35"}
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
