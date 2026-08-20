"""Schema tests against a real PostgreSQL.

These prove two things the Python tests cannot:

1. the migrations actually apply, and
2. the SQL candidate generator agrees with :mod:`ecommerce_os.matching` —
   the same pair must get the same score and the same class in both, or an
   offline evaluation stops predicting production behaviour.

Skipped unless ``ECOMMERCE_OS_TEST_DSN`` points at a scratch database that the
test is allowed to drop objects in. To run them::

    createdb ecomos_test
    ECOMMERCE_OS_TEST_DSN=postgresql://user:pw@localhost/ecomos_test \\
        python -m pytest tests/ecommerce_os/test_schema.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

from ecommerce_os.matching import MatchClass, ProductRecord, classify_match

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "ecommerce_os" / "schema"
CORE_MIGRATIONS = (
    "001_canonical_product.sql",
    "002_supplier_compliance.sql",
    "003_fees_and_economics.sql",
    "004_matching.sql",
)

DSN = os.environ.get("ECOMMERCE_OS_TEST_DSN")

pytestmark = [
    pytest.mark.skipif(not DSN, reason="ECOMMERCE_OS_TEST_DSN is not set"),
    pytest.mark.skipif(shutil.which("psql") is None, reason="psql is not installed"),
]

SEED = """
INSERT INTO canonical_product
    (canonical_product_id, brand_normalized, mpn_normalized, gtin14,
     pack_count, condition, category_taxonomy, canonical_title)
VALUES
    (1,'brita','MAXTRAPRO','04006381333931',3,'new','filters','brita maxtra pro 3 pack'),
    (2,'acme',NULL,NULL,NULL,'new','valves','acme hvac solenoid valve');

INSERT INTO source_product (source_product_id, source_id, source_sku, raw_title)
VALUES
    (10,'sup-a','A-1','Brita Maxtra Pro 6 Pack'),
    (11,'sup-a','A-2','Brita Maxtra Pro 3 Pack'),
    (12,'sup-a','A-3','Acme HVAC solenoid valve');

INSERT INTO source_product_clean
    (source_product_id, gtin14, mpn_norm, brand_norm, title_norm,
     pack_count, condition, category_taxonomy)
VALUES
    (10,'04006381333931','MAXTRAPRO','brita','brita maxtra pro 6 pack',6,'new','filters'),
    (11,'04006381333931','MAXTRAPRO','brita','brita maxtra pro 3 pack',3,'new','filters'),
    (12,NULL,NULL,'acme','acme hvac solenoid valve',NULL,'new','valves');

INSERT INTO supplier (supplier_id, legal_entity_name, supplier_type, country, onboarded_on)
VALUES ('s1','Distributor Ltd','authorised_distributor','GB','2026-01-01');

-- The seed sets explicit ids, which leaves the sequences behind. Without this
-- the next generated id collides on the primary key.
SELECT setval(pg_get_serial_sequence('canonical_product','canonical_product_id'), 100);
SELECT setval(pg_get_serial_sequence('source_product','source_product_id'), 100);
"""


def psql(sql: str, *, expect_failure: bool = False) -> str:
    """Run SQL and return stdout, asserting the exit status we expected."""
    result = subprocess.run(
        ["psql", DSN, "-v", "ON_ERROR_STOP=1", "-qtA", "-F", "|"],
        input=sql,
        capture_output=True,
        text=True,
    )
    if expect_failure:
        assert result.returncode != 0, f"expected SQL to be rejected:\n{sql}"
        return result.stderr
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture(scope="module", autouse=True)
def database():
    """Rebuild the schema from the migration files for every run."""
    psql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    for migration in CORE_MIGRATIONS:
        psql((SCHEMA_DIR / migration).read_text())
    psql(SEED)
    yield


class TestMigrationsApply:
    def test_core_tables_exist(self):
        rows = psql(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1"
        ).splitlines()
        assert {"canonical_product", "source_product", "supplier_authorisation"} <= set(rows)

    def test_core_schema_does_not_require_pgvector(self):
        # 005 is optional; nothing in 001-004 may depend on it.
        assert psql(
            "SELECT count(*) FROM pg_extension WHERE extname='vector'"
        ) == "0"


class TestSqlMatchesPython:
    """The same pair, scored by the view and by the Python classifier."""

    def _view_row(self, source_product_id: int) -> tuple[Decimal, str]:
        row = psql(
            "SELECT match_score, match_class FROM match_candidate "
            f"WHERE source_product_id = {source_product_id}"
        )
        score, match_class = row.split("|")
        return Decimal(score), match_class

    def test_conflicting_pack_size_is_quarantined_by_both(self):
        score, match_class = self._view_row(10)
        result = classify_match(
            ProductRecord.from_raw(
                title="Brita Maxtra Pro 6 Pack", brand="Brita",
                gtin="4006381333931", category="filters", pack_count=6,
            ),
            ProductRecord.from_raw(
                title="Brita Maxtra Pro 3 Pack", brand="Brita",
                gtin="4006381333931", category="filters", pack_count=3,
            ),
        )

        assert match_class == result.match_class.value == MatchClass.CONFLICT.value
        assert score == result.score == Decimal("1.00")

    def test_true_match_is_deterministic_in_both(self):
        score, match_class = self._view_row(11)
        product = dict(
            title="Brita Maxtra Pro 3 Pack", brand="Brita",
            gtin="4006381333931", category="filters", pack_count=3,
        )
        result = classify_match(
            ProductRecord.from_raw(**product), ProductRecord.from_raw(**product)
        )

        assert match_class == result.match_class.value == MatchClass.DETERMINISTIC.value
        assert score == result.score == Decimal("1.00")

    def test_text_only_match_is_capped_at_070_in_both(self):
        score, match_class = self._view_row(12)
        product = dict(title="Acme HVAC solenoid valve", brand="Acme", category="valves")
        result = classify_match(
            ProductRecord.from_raw(**product), ProductRecord.from_raw(**product)
        )

        assert score == result.score == Decimal("0.700")
        assert match_class == result.match_class.value == MatchClass.LOW.value


class TestConstraintsRefuseBadData:
    def test_dropship_without_white_label_packaging_is_refused(self):
        error = psql(
            """
            INSERT INTO supplier_authorisation
                (supplier_id, canonical_product_id, resale_authorised,
                 dropship_authorised, seller_of_record_supported,
                 white_label_packaging, return_address_country, agreement_start)
            VALUES ('s1', 1, true, true, true, false, 'GB', '2026-01-01');
            """,
            expect_failure=True,
        )
        assert "check constraint" in error

    def test_resale_without_a_return_address_is_refused(self):
        error = psql(
            """
            INSERT INTO supplier_authorisation
                (supplier_id, canonical_product_id, resale_authorised, agreement_start)
            VALUES ('s1', 1, true, '2026-01-01');
            """,
            expect_failure=True,
        )
        assert "check constraint" in error

    def test_a_conflict_match_cannot_be_auto_accepted(self):
        error = psql(
            """
            INSERT INTO product_match
                (source_product_id, canonical_product_id, match_method,
                 match_class, match_score, match_model_version, review_status)
            VALUES (10, 1, 'gtin', 'conflict', 1.0, 'v1', 'auto_accepted');
            """,
            expect_failure=True,
        )
        assert "product_match_conflict_is_quarantined" in error

    def test_two_canonical_products_cannot_share_a_gtin(self):
        error = psql(
            """
            INSERT INTO canonical_product
                (brand_normalized, gtin14, category_taxonomy, canonical_title)
            VALUES ('brita', '04006381333931', 'filters', 'duplicate row');
            """,
            expect_failure=True,
        )
        assert "canonical_product_gtin_uidx" in error

    def test_one_source_row_resolves_to_one_canonical_product(self):
        psql(
            """
            INSERT INTO product_match
                (source_product_id, canonical_product_id, match_method,
                 match_class, match_score, match_model_version, review_status)
            VALUES (11, 1, 'gtin', 'deterministic', 1.0, 'v1', 'auto_accepted');
            """
        )
        error = psql(
            """
            INSERT INTO product_match
                (source_product_id, canonical_product_id, match_method,
                 match_class, match_score, match_model_version, review_status)
            VALUES (11, 2, 'model', 'high', 0.98, 'v1', 'approved');
            """,
            expect_failure=True,
        )
        assert "product_match_active_source_uidx" in error
