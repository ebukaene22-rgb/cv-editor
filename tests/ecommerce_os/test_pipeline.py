from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from ecommerce_os.compliance import FulfilmentMethod
from ecommerce_os.fees import ANY, FeeBook, FeeRule
from ecommerce_os.matching import MatchClass, ProductRecord
from ecommerce_os.pipeline import ListingCandidate, evaluate_listing

VALID_EAN13 = "4006381333931"


@pytest.fixture
def candidate(authorisation, costs, performance) -> ListingCandidate:
    """A candidate that clears every gate, so tests can break one at a time."""
    product = dict(
        title="Brita Maxtra Pro 3 Pack",
        brand="Brita",
        gtin=VALID_EAN13,
        category="filters",
        pack_count=3,
    )
    return ListingCandidate(
        canonical_sku_id="cp-1001",
        marketplace="ebay",
        market="GB",
        category="filters",
        fulfilment=FulfilmentMethod.SUPPLIER_DROPSHIP,
        authorisation=authorisation,
        source_product=ProductRecord.from_raw(**product),
        canonical_product=ProductRecord.from_raw(**product),
        costs=costs,
        supplier_performance=performance,
        supplier_qty=100,
        feed_age_minutes=30,
        monthly_demand=Decimal("60"),
        conversion_rate=Decimal("0.5"),
        price_observations=5,
    )


def decide(candidate, fee_book, today, **kwargs):
    return evaluate_listing(candidate, fee_book=fee_book, as_of=today, **kwargs)


class TestHappyPath:
    def test_a_fully_qualified_candidate_publishes(self, candidate, fee_book, today):
        decision = decide(candidate, fee_book, today)

        assert decision.publishable, decision.blockers
        assert decision.blockers == ()

    def test_the_decision_carries_its_own_evidence(self, candidate, fee_book, today):
        decision = decide(candidate, fee_book, today)

        assert decision.match.match_class is MatchClass.DETERMINISTIC
        assert decision.compliance.ok
        assert decision.fee_breakdown == {"referral": Decimal("12.00")}
        # 100.00 net revenue, £12 of that to eBay.
        assert decision.breakdown.expected_contribution == Decimal("21.40")
        assert decision.sellable_qty == 96  # 100 - (2 base + 1 stale + 1 reliability)
        assert decision.score is not None and decision.score.score > 0


class TestEveryGateCanVetoAlone:
    def test_compliance_veto(self, candidate, fee_book, today):
        blocked = replace(
            candidate,
            authorisation=replace(candidate.authorisation, dropship_authorised=False),
        )
        decision = decide(blocked, fee_book, today)

        assert not decision.publishable
        assert any(b.startswith("compliance:") for b in decision.blockers)

    def test_match_veto(self, candidate, fee_book, today):
        # The Brita 3-pack / 6-pack trap, end to end.
        six_pack = ProductRecord.from_raw(
            title="Brita Maxtra Pro 6 Pack",
            brand="Brita",
            gtin=VALID_EAN13,
            category="filters",
            pack_count=6,
        )
        decision = decide(replace(candidate, canonical_product=six_pack), fee_book, today)

        assert not decision.publishable
        assert decision.match.match_class is MatchClass.CONFLICT
        assert any(b.startswith("match:") for b in decision.blockers)

    def test_inventory_veto(self, candidate, fee_book, today):
        decision = decide(replace(candidate, supplier_qty=1), fee_book, today)

        assert not decision.publishable
        assert any(b.startswith("inventory:") for b in decision.blockers)

    def test_missing_fee_rule_blocks_instead_of_defaulting_to_zero(self, candidate, today):
        decision = decide(candidate, FeeBook([]), today)

        assert not decision.publishable
        assert any(b.startswith("fees:") for b in decision.blockers)
        # No economics at all, rather than optimistic economics.
        assert decision.breakdown is None
        assert decision.score is None

    def test_economics_veto(self, candidate, fee_book, today):
        # A 40% referral fee eats the contribution.
        greedy = FeeBook(
            [
                FeeRule(
                    marketplace="ebay",
                    country="GB",
                    category=ANY,
                    fee_kind="referral",
                    variable_rate=Decimal("0.40"),
                    fixed_fee=Decimal("0"),
                    effective_from=date(2026, 1, 1),
                    schedule_version="test",
                )
            ]
        )
        decision = decide(candidate, greedy, today)

        assert not decision.publishable
        assert any(b.startswith("economics:") for b in decision.blockers)


class TestProfitIsNeverEnoughOnItsOwn:
    def test_an_enormously_profitable_but_unauthorised_route_stays_blocked(
        self, candidate, fee_book, today
    ):
        lucrative = replace(
            candidate,
            costs=replace(candidate.costs, supplier_price_ex_vat=Decimal("5.00")),
            authorisation=replace(candidate.authorisation, territories=frozenset({"AE"})),
        )
        decision = decide(lucrative, fee_book, today)

        assert not decision.publishable
        assert decision.breakdown.expected_contribution > Decimal("50")
        assert "compliance: territory GB not authorised" in decision.blockers


class TestReporting:
    def test_all_blockers_are_collected_in_one_pass(self, candidate, fee_book, today):
        # An operator should see the full remediation list, not one blocker a day.
        broken = replace(
            candidate,
            supplier_qty=0,
            price_observations=0,
            authorisation=replace(
                candidate.authorisation,
                dropship_authorised=False,
                territories=frozenset(),
            ),
        )
        decision = decide(broken, fee_book, today)

        prefixes = {blocker.split(":")[0] for blocker in decision.blockers}
        assert {"compliance", "inventory", "economics"} <= prefixes

    def test_compliance_failure_is_not_reported_twice(self, candidate, fee_book, today):
        blocked = replace(
            candidate,
            authorisation=replace(candidate.authorisation, territories=frozenset()),
        )
        decision = decide(blocked, fee_book, today)

        assert "economics: compliance gate not passed" not in decision.blockers

    def test_decision_is_falsy_when_blocked(self, candidate, fee_book, today):
        blocked = replace(candidate, supplier_qty=0)
        assert not decide(blocked, fee_book, today)
        assert decide(candidate, fee_book, today)


class TestPolicyOverrides:
    def test_a_stricter_dispatch_policy_can_block_an_otherwise_fine_route(
        self, candidate, fee_book, today
    ):
        decision = decide(candidate, fee_book, today, max_dispatch_sla_hours=12)

        assert not decision.publishable
        assert any("exceeds 12h policy" in blocker for blocker in decision.blockers)
