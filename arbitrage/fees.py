#!/usr/bin/env python3
"""
Contribution-margin engine for eBay UK business sellers.

Replaces the earlier flat "13.2% + 2.9% + $0.30" model, which was wrong in
three separate ways:

  1. It charged a Stripe/PayPal-style processing fee on top of the final
     value fee. Under eBay managed payments there is no separate processing
     fee -- it is inside the FVF. That inflated costs.
  2. It used one universal FVF. Business FVF is category-dependent, roughly
     6.9%-14.9% (most categories 9.9%-12.9%).
  3. It ignored VAT on eBay's fees (20%), the 0.35% regulatory operating
     fee, the international fee, and the fact that FVF is charged on the
     total including postage. Those all understated costs.

Net effect: the old model was not simply "pessimistic", it was biased in
both directions at once, which is worse -- you cannot correct for it.

Contribution per order:

    CM = Revenue
       - SupplierCost - InboundShip - Duty
       - OutboundShip
       - FVF(category) - PerOrderFee - RegulatoryFee - IntlFee - AdFee
       - VAT on those eBay fees (if not VAT-registered)
       - ExpectedReturnCost

VAT note: a VAT-registered business reclaims input VAT on eBay's fees, so it
is not a cost. An unregistered seller eats it. That is a ~2pp swing on a
typical order, so it is a flag, not an assumption.

Rates verified Aug 2026 against current eBay UK business-seller guidance.
Category rates below are the published band midpoints, not a full category
tree -- treat FVF_BY_CATEGORY as a lookup to extend, and `default` as the
honest fallback when a product has not been mapped.
"""

# Business-seller final value fee by broad category. eBay's real tree is far
# larger; these are the bands most Shopify-sourced goods land in.
FVF_BY_CATEGORY = {
    "clothing":       0.129,
    "shoes":          0.129,
    "accessories":    0.129,
    "home":           0.129,
    "beauty":         0.129,
    "sports":         0.119,
    "outdoors":       0.119,
    "toys":           0.129,
    "electronics":    0.0899,
    "computers":      0.0699,
    "media":          0.1490,
    "jewellery":      0.129,
    "default":        0.129,
}

# International fee by buyer region (charged on the total sale amount).
INTL_FEE = {"UK": 0.0, "EU": 0.0105, "US": 0.018, "CA": 0.018, "OTHER": 0.020}

PER_ORDER_LOW = 0.30      # orders <= PER_ORDER_THRESHOLD
PER_ORDER_HIGH = 0.40     # orders above it (Feb 2026 increase)
PER_ORDER_THRESHOLD = 10.0
REG_OP_FEE = 0.0035       # regulatory operating fee
VAT_RATE = 0.20           # VAT charged on eBay's fees


class Economics:
    """
    All monetary inputs and outputs are in one currency (GBP by convention
    here). Callers convert with fx before constructing.
    """

    def __init__(self, category="default", buyer_region="UK",
                 vat_registered=True, ad_rate=0.0, duty_rate=0.0,
                 return_rate=0.06, return_cost_share=0.5,
                 inbound_ship_base=2.50, inbound_ship_per_kg=4.00,
                 outbound_ship_base=2.90, outbound_ship_per_kg=1.60,
                 postage_charged=0.0):
        self.category = category
        self.fvf = FVF_BY_CATEGORY.get(category, FVF_BY_CATEGORY["default"])
        self.intl = INTL_FEE.get(buyer_region, INTL_FEE["OTHER"])
        self.vat_registered = vat_registered
        self.ad_rate = ad_rate                 # Promoted Listings, if used
        self.duty_rate = duty_rate
        self.return_rate = return_rate
        # A return costs the return leg plus handling, not the whole order:
        # most returned goods are resaleable.
        self.return_cost_share = return_cost_share
        self.inbound_ship_base = inbound_ship_base
        self.inbound_ship_per_kg = inbound_ship_per_kg
        self.outbound_ship_base = outbound_ship_base
        self.outbound_ship_per_kg = outbound_ship_per_kg
        self.postage_charged = postage_charged

    # -- cost legs ---------------------------------------------------------
    def inbound(self, supplier_cost, grams):
        kg = (grams or 500) / 1000.0
        ship = self.inbound_ship_base + self.inbound_ship_per_kg * kg
        return supplier_cost * (1 + self.duty_rate) + ship

    def outbound(self, grams):
        kg = (grams or 500) / 1000.0
        return self.outbound_ship_base + self.outbound_ship_per_kg * kg

    def ebay_fees(self, sell_price):
        """
        FVF and the international fee are charged on the total amount of the
        sale -- item price plus postage charged to the buyer.
        """
        gross = sell_price + self.postage_charged
        per_order = (PER_ORDER_HIGH if gross > PER_ORDER_THRESHOLD
                     else PER_ORDER_LOW)
        fees = (gross * self.fvf
                + gross * REG_OP_FEE
                + gross * self.intl
                + gross * self.ad_rate
                + per_order)
        if not self.vat_registered:
            fees *= (1 + VAT_RATE)
        return fees

    # -- headline ----------------------------------------------------------
    def contribution(self, supplier_cost, sell_price, grams):
        """
        -> (contribution, margin_on_cost, breakdown dict).

        margin is expressed on invested cost, which is what decides how fast
        working capital recycles. Margin on revenue is the vanity version.
        """
        if supplier_cost is None or sell_price is None or supplier_cost <= 0:
            return None, None, {}
        inb = self.inbound(supplier_cost, grams)
        out = self.outbound(grams)
        fees = self.ebay_fees(sell_price)
        gross = sell_price + self.postage_charged
        returns = self.return_rate * self.return_cost_share * (out + fees)
        cm = gross - inb - out - fees - returns
        invested = inb
        return cm, (cm / invested if invested else None), {
            "gross": gross, "inbound": inb, "outbound": out,
            "ebay_fees": fees, "returns": returns, "invested": invested,
            "fvf_rate": self.fvf, "category": self.category}


def categorise(title, vendor=""):
    """
    Crude keyword mapping into the FVF bands. Deliberately conservative:
    anything unrecognised returns `default` (the higher 12.9% band) rather
    than optimistically guessing a cheap category.
    """
    t = f"{title} {vendor}".lower()
    rules = [
        ("computers", ("laptop", "macbook", "ssd", "cpu", "gpu", "monitor",
                       "keyboard", "mouse", "router")),
        ("electronics", ("headphone", "earbud", "speaker", "charger", "cable",
                         "camera", "watch", "phone", "battery", "power bank")),
        ("shoes", ("shoe", "sneaker", "trainer", "boot", "slide", "sandal",
                   "runner", "loafer")),
        ("clothing", ("tee", "shirt", "hoodie", "jacket", "sweat", "trouser",
                      "jean", "dress", "sock", "legging", "short", "coat")),
        ("beauty", ("serum", "cream", "shampoo", "lotion", "fragrance",
                    "skincare", "balm")),
        ("sports", ("yoga", "dumbbell", "fitness", "bike", "cycling", "golf",
                    "ski", "climb")),
        ("outdoors", ("tent", "stove", "camping", "hike", "backpack",
                      "sleeping bag", "lantern")),
        ("toys", ("toy", "puzzle", "lego", "game", "doll", "figure")),
        ("media", ("book", "vinyl", "dvd", "blu-ray", "cd ")),
        ("jewellery", ("ring", "necklace", "bracelet", "earring", "pendant")),
        ("home", ("mug", "candle", "cushion", "duvet", "towel", "pan", "pot",
                  "kettle", "chair", "lamp", "rug")),
    ]
    for cat, keys in rules:
        if any(k in t for k in keys):
            return cat
    return "default"
