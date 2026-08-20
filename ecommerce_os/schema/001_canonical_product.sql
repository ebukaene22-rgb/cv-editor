-- Canonical product graph.
--
-- Design rule: raw source facts are preserved separately from interpreted
-- product identity. What a source said is evidence and is immutable; what the
-- matcher decided it means is an interpretation and is revisable. Never
-- overwrite the former with the latter -- when a match is later found to be
-- wrong, the only way to re-derive the truth is from the untouched original.

-- Core schema depends only on stock PostgreSQL plus pg_trgm. Semantic reranking
-- needs pgvector and lives in 005, which is optional: candidate generation and
-- every gate work without it.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Interpretation layer: one row per real-world product.
CREATE TABLE canonical_product (
    canonical_product_id  bigserial PRIMARY KEY,
    brand_normalized      text        NOT NULL,
    manufacturer          text,
    mpn_normalized        text,
    gtin14                char(14),
    product_family        text,
    model                 text,
    variant               text,
    pack_count            integer     CHECK (pack_count IS NULL OR pack_count > 0),
    size_value            numeric(12, 4),
    size_unit             text,
    colour                text,
    country_variant       text,
    voltage               text,
    condition             text        NOT NULL DEFAULT 'new',
    category_taxonomy     text        NOT NULL,
    attributes_json       jsonb       NOT NULL DEFAULT '{}'::jsonb,
    canonical_title       text        NOT NULL,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now()
);

-- A GTIN identifies one product. Two canonical rows sharing one is a data
-- defect that would let the matcher "confirm" identity against the wrong row.
CREATE UNIQUE INDEX canonical_product_gtin_uidx
    ON canonical_product (gtin14)
    WHERE gtin14 IS NOT NULL;

CREATE UNIQUE INDEX canonical_product_brand_mpn_uidx
    ON canonical_product (brand_normalized, mpn_normalized, COALESCE(pack_count, 0))
    WHERE mpn_normalized IS NOT NULL;

CREATE INDEX canonical_product_title_trgm_idx
    ON canonical_product USING gin (canonical_title gin_trgm_ops);

CREATE INDEX canonical_product_blocking_idx
    ON canonical_product (brand_normalized, category_taxonomy);

-- Evidence layer: one row per product per source, never mutated by matching.
CREATE TABLE source_product (
    source_product_id     bigserial PRIMARY KEY,
    source_id             text        NOT NULL,
    source_sku            text        NOT NULL,
    source_ref            text,          -- URL or API key, for audit
    raw_gtin              text,
    raw_mpn               text,
    raw_brand             text,
    raw_title             text        NOT NULL,
    raw_attributes        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    ingested_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id, source_sku)
);

-- Normalised projection of the evidence, safe to rebuild from source_product.
CREATE TABLE source_product_clean (
    source_product_id     bigint PRIMARY KEY
                          REFERENCES source_product (source_product_id) ON DELETE CASCADE,
    gtin14                char(14),
    mpn_norm              text,
    brand_norm            text,
    title_norm            text        NOT NULL,
    pack_count            integer,
    condition             text        NOT NULL DEFAULT 'new',
    category_taxonomy     text,
    attributes            jsonb       NOT NULL DEFAULT '{}'::jsonb,
    normalized_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX source_product_clean_title_trgm_idx
    ON source_product_clean USING gin (title_norm gin_trgm_ops);

CREATE INDEX source_product_clean_blocking_idx
    ON source_product_clean (brand_norm, category_taxonomy);

-- Sources are not suppliers. A retail page we may read for price intelligence
-- confers no right to buy, resell or have goods shipped to our customers; that
-- right comes only from a supply agreement (see 002).
CREATE TABLE intelligence_source (
    source_id             text PRIMARY KEY,
    display_name          text        NOT NULL,
    ingestion_method      text        NOT NULL
                          CHECK (ingestion_method IN (
                              'manufacturer_api', 'edi', 'contracted_feed',
                              'marketplace_api', 'affiliate_feed',
                              'supplier_portal_export', 'permitted_public_pages'
                          )),
    -- Cleared by counsel against that source's terms, not assumed from the
    -- fact that a page loads without logging in.
    automated_collection_cleared  boolean NOT NULL DEFAULT false,
    content_reuse_licensed        boolean NOT NULL DEFAULT false,
    is_approved_supplier          boolean NOT NULL DEFAULT false,
    rights_reviewed_on            date,
    rights_review_notes           text
);
