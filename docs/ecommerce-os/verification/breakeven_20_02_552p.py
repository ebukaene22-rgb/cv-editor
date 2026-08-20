"""Break-even trade price for a real, verified SKU.

SKU: Rational 20.02.552P door gasket (SCC/CM/iCombi 101).
Verified UK retail 2026-08-20: £69.99 (eBay UK, Nottingham seller),
£70.19 (Normanton Catering). eBay UK, Business & Industrial category,
Feb-2026 rate card via ecommerce_os.data.fees_uk_2026.

Question answered: what is the MAXIMUM supplier price (ex VAT) at which this
SKU clears the pilot gates (>= GBP 5 contribution AND >= 15% margin) sold at
GBP 69.99 on eBay UK?  Everything else is the engine's standard treatment.
"""
from datetime import date
from decimal import Decimal

from ecommerce_os.data import uk_fee_book_2026
from ecommerce_os.data.fees_uk_2026 import EBAY_UK_FEE_KINDS
from ecommerce_os.landed_cost import (
    LandedCostInputs, ReturnProfile, VatTreatment, contribution_margin,
)

PRICE = Decimal("69.99")
AS_OF = date(2026, 8, 20)

book = uk_fee_book_2026()
total_fees, breakdown = book.total_fees(
    marketplace="ebay", country="GB", category="business_industrial",
    price=PRICE, on_date=AS_OF, fee_kinds=EBAY_UK_FEE_KINDS,
)
print(f"eBay UK fees on GBP {PRICE} (B&I, Feb-2026 card, ex VAT):")
for kind, amount in breakdown.items():
    print(f"  {kind:<22} {amount:>7}")
print(f"  {'TOTAL':<22} {total_fees:>7}")

# Robust rubber part: modest return profile. Flagged assumptions.
returns = ReturnProfile(
    return_rate=Decimal("0.04"),
    reverse_logistics_cost=Decimal("4.00"),
    resell_probability=Decimal("0.80"),
    writeoff_cost=Decimal("30.00"),
    handling_cost=Decimal("1.00"),
    nonrefundable_fees=Decimal("0.64"),  # fixed fee + regulatory not refunded
)

def contribution(cost: Decimal, outbound: Decimal):
    inputs = LandedCostInputs(
        selling_price=PRICE,
        supplier_price_ex_vat=cost,
        vat_treatment=VatTreatment.SELLER_COLLECTS,
        sale_vat_rate=Decimal("0.20"),
        supplier_vat_rate=Decimal("0.20"),
        input_vat_recoverable=True,        # VAT-registered from day one
        outbound_shipping=outbound,
        marketplace_fees=total_fees,       # payment processing inside eBay FVF
        return_profile=returns,
        fulfilment_failure_rate=Decimal("0.01"),
        fulfilment_failure_cost=Decimal("3.00"),
    )
    return contribution_margin(inputs)

GATE_ABS = Decimal("5.00")
GATE_PCT = Decimal("0.15")

print(f"\nGates: contribution >= GBP {GATE_ABS} AND margin >= {GATE_PCT:.0%}"
      f"  (binding: 15% of {PRICE} = GBP {(GATE_PCT*PRICE).quantize(Decimal('0.01'))})")
print(f"{'outbound':>9} | {'max cost ex VAT':>15} | {'as % of ex-VAT retail':>21}")
for outbound in (Decimal("3.50"), Decimal("4.95"), Decimal("6.50")):
    # sweep in pennies for the exact break-even
    lo, hi = Decimal("0"), Decimal("60.00")
    best = None
    cost = lo
    while cost <= hi:
        b = contribution(cost, outbound)
        if b.expected_contribution >= GATE_ABS and b.margin_pct >= GATE_PCT:
            best = (cost, b)
        cost += Decimal("0.01")
    if best:
        cost, b = best
        ex_vat_retail = PRICE / Decimal("1.2")
        pct = (cost / ex_vat_retail * 100).quantize(Decimal("0.1"))
        print(f"{outbound:>9} | {cost:>15} | {pct:>20}%")
        last = b
    else:
        print(f"{outbound:>9} | {'never clears':>15} |")

b = contribution(Decimal("32.00"), Decimal("4.95"))
print(f"\nWorked example at cost GBP 32.00, outbound GBP 4.95:")
print(f"  net revenue          {b.net_revenue}")
for k, v in b.lines.items():
    if v:
        print(f"  {k:<20} {v:>7}")
print(f"  expected contribution {b.expected_contribution}  margin {b.margin_pct:.1%}")
