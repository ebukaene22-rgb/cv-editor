# ecommerce_os — decision engine

The machine-readable core of [`docs/ecommerce-os/strategy.md`](../docs/ecommerce-os/strategy.md).

> Scaffolded in the `cv-editor` repo alongside the football-scout pipeline, for
> the same session-access reason. Intended to migrate to its own repo.

An SKU is never published because it looks profitable. It is published because
every gate independently said yes:

```python
publishable = (
    economic_gate and match_gate and supplier_gate
    and marketplace_gate and product_compliance_gate and inventory_gate
)
```

## What's here

| Module | Responsibility |
|---|---|
| `money.py` | Decimal-only monetary helpers; floats raise rather than silently drift |
| `identity.py` | GTIN check-digit validation, brand/MPN/title normalisation, pack-size parsing |
| `matching.py` | Entity resolution, precision-first, with conflict quarantine |
| `compliance.py` | Supplier authorisation as data; hard gate over channel/territory/fulfilment |
| `fees.py` | Category/country/price-band/date-scoped fee rules that stack — **no default rate** |
| `landed_cost.py` | Contribution margin after VAT, duty, fees, returns, fraud and failures |
| `supply.py` | Supplier reliability scoring and defensive stock buffering |
| `scoring.py` | Pilot gates, risk-adjusted opportunity score, dropship→stock transition rule |
| `killswitch.py` | Fail-closed automatic pause rules for SKUs and suppliers |
| `pipeline.py` | The end-to-end publish decision |
| `schema/` | PostgreSQL migrations for the product graph, compliance, fees and matching |

Every module is pure and deterministic — nothing here opens a socket. That is
deliberate: the gates have to be auditable and unit-testable before a single
listing goes live.

## Design decisions worth knowing

**Sources are not suppliers.** A retail page you may read for price
intelligence confers no right to buy, resell or have goods shipped to your
customers. `intelligence_source` and `supplier_authorisation` are separate
tables and the publish gate only reads the latter.

**Compliance is a gate, not a discount.** It is never a factor in the score. A
90%-likely-compliant listing is not worth 90% of the margin.

**No default fee rate.** An unpriceable combination raises. "About 15%" is how a
portfolio of confidently unprofitable SKUs gets built.

**Unknown pack size scores zero, not one.** Text similarity alone therefore tops
out at 0.70 against a 0.97 auto-match bar, so marketing copy can never publish a
listing by itself. A 3-pack and a 6-pack share nearly every token; the P&L does
not care how similar the copy was.

**Agreeing identifiers plus a contradicting attribute is quarantined**, not
resolved either way — it looks deterministic and is wrong, which makes it the
most dangerous signal in the system.

**Fail closed.** Restrictive defaults, missing data blocks, and all blockers are
collected in one pass so an operator gets the whole remediation list rather than
one blocker per day.

## Running the tests

```bash
pip install pytest
python -m pytest tests/ecommerce_os -q
```

The schema tests are skipped unless a scratch PostgreSQL is pointed at. They
prove the migrations apply *and* that the SQL candidate generator scores pairs
identically to `matching.py` — without that agreement, offline evaluation stops
predicting production behaviour:

```bash
createdb ecomos_test
ECOMMERCE_OS_TEST_DSN=postgresql://user:pw@localhost/ecomos_test \
    python -m pytest tests/ecommerce_os/test_schema.py -q
```

## Schema migrations

Apply `001`–`004` in order. They need stock PostgreSQL plus `pg_trgm`.

`005_semantic_rerank.sql` is **optional** and requires pgvector; it adds the
embedding column and an ANN index used to rerank candidates *after* blocking.
Everything else works without it. It is the one migration not covered by the
test suite here, because pgvector was unavailable in the environment it was
written in — apply it against a pgvector-enabled instance before relying on it.

## Status

This is the decision engine only. Not built, and deliberately out of scope until
the strategy's first eight actions are done: ingestion connectors, marketplace
API clients, the listing/repricing writer, order routing, and the reconciliation
job that feeds realised outcomes back into the models.

The thresholds in `scoring.PilotGates`, `killswitch.SkuThresholds` and
`killswitch.SupplierThresholds` are proposed pilot policy — engineering
judgement, not marketplace rules. Replace them with category-specific posteriors
once enough realised outcomes exist to fit them.
