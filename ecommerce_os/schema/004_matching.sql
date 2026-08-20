-- Candidate generation and match decisions.
--
-- The weights and thresholds here are the SQL twin of ecommerce_os/matching.py.
-- Keeping them identical is what makes an offline evaluation on labelled pairs
-- predict what the database will actually do; if you change one, change both
-- and re-run tests/test_matching.py.

CREATE TABLE product_match (
    product_match_id      bigserial PRIMARY KEY,
    source_product_id     bigint NOT NULL
                          REFERENCES source_product (source_product_id) ON DELETE CASCADE,
    canonical_product_id  bigint NOT NULL
                          REFERENCES canonical_product (canonical_product_id),
    match_method          text        NOT NULL
                          CHECK (match_method IN (
                              'gtin', 'brand_mpn', 'model', 'semantic', 'human'
                          )),
    match_class           text        NOT NULL
                          CHECK (match_class IN (
                              'deterministic', 'very_high', 'high',
                              'medium', 'low', 'conflict'
                          )),
    match_score           numeric(6, 4) NOT NULL CHECK (match_score BETWEEN 0 AND 1),
    match_model_version   text        NOT NULL,
    review_status         text        NOT NULL DEFAULT 'pending'
                          CHECK (review_status IN (
                              'auto_accepted', 'pending', 'approved',
                              'rejected', 'quarantined'
                          )),
    conflicts             text[]      NOT NULL DEFAULT '{}',
    reviewed_by           text,
    reviewed_at           timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_product_id, canonical_product_id)
);

-- One source row resolves to at most one canonical product at a time.
CREATE UNIQUE INDEX product_match_active_source_uidx
    ON product_match (source_product_id)
    WHERE review_status IN ('auto_accepted', 'approved');

-- A conflict is never silently resolved in either direction.
ALTER TABLE product_match
    ADD CONSTRAINT product_match_conflict_is_quarantined
    CHECK (match_class <> 'conflict' OR review_status = 'quarantined');

CREATE INDEX product_match_review_queue_idx
    ON product_match (review_status, match_score DESC)
    WHERE review_status = 'pending';

-- Manually labelled pairs. This is the evaluation set that auto-match precision
-- is measured against; unattended listing stays off until audited precision is
-- consistently above ~99.5% for the categories being automated.
CREATE TABLE match_label (
    match_label_id        bigserial PRIMARY KEY,
    source_product_id     bigint NOT NULL REFERENCES source_product (source_product_id),
    canonical_product_id  bigint NOT NULL REFERENCES canonical_product (canonical_product_id),
    is_same_product       boolean NOT NULL,
    labelled_by           text    NOT NULL,
    labelled_at           timestamptz NOT NULL DEFAULT now(),
    note                  text,
    UNIQUE (source_product_id, canonical_product_id)
);


-- Candidate generation: exact identifiers first, blocked fuzzy search second.
--
-- Note the pack term. NULL = NULL is NULL in SQL, so an unknown pack count on
-- either side scores zero rather than agreeing by default. That caps a
-- text-only match at 0.45*1 + 0.25*1 = 0.70, safely under the 0.97 auto-match
-- bar: marketing copy alone can never publish a listing.
CREATE OR REPLACE VIEW match_candidate AS
WITH candidates AS (
    SELECT
        s.source_product_id,
        c.canonical_product_id,

        CASE
            WHEN s.gtin14 IS NOT NULL AND s.gtin14 = c.gtin14
                THEN 1.00
            WHEN s.mpn_norm IS NOT NULL
                 AND s.mpn_norm  = c.mpn_normalized
                 AND s.brand_norm = c.brand_normalized
                THEN 0.96
            ELSE 0.00
        END::numeric AS identifier_score,

        similarity(s.title_norm, c.canonical_title)::numeric AS title_score,

        CASE WHEN s.brand_norm = c.brand_normalized THEN 1.0 ELSE 0.0 END::numeric
            AS brand_score,

        CASE WHEN s.pack_count = c.pack_count THEN 1.0 ELSE 0.0 END::numeric
            AS pack_score,

        -- Asserted contradictions only: a value absent on either side is
        -- unknown, not disagreement.
        ARRAY_REMOVE(ARRAY[
            CASE WHEN s.pack_count IS NOT NULL AND c.pack_count IS NOT NULL
                      AND s.pack_count <> c.pack_count      THEN 'pack_count' END,
            CASE WHEN s.condition <> c.condition             THEN 'condition' END,
            CASE WHEN s.category_taxonomy IS NOT NULL AND c.category_taxonomy IS NOT NULL
                      AND s.category_taxonomy <> c.category_taxonomy
                                                             THEN 'category' END,
            CASE WHEN s.attributes ? 'voltage' AND c.attributes_json ? 'voltage'
                      AND s.attributes ->> 'voltage' IS DISTINCT FROM
                          c.attributes_json ->> 'voltage'    THEN 'voltage' END,
            CASE WHEN s.attributes ? 'region' AND c.attributes_json ? 'region'
                      AND s.attributes ->> 'region' IS DISTINCT FROM
                          c.attributes_json ->> 'region'     THEN 'region' END
        ], NULL) AS conflicts

    FROM source_product_clean s
    JOIN canonical_product c
      ON (
           s.gtin14 = c.gtin14
           OR (
               -- Block on brand before paying for trigram comparison.
               s.brand_norm = c.brand_normalized
               AND similarity(s.title_norm, c.canonical_title) > 0.55
           )
      )
),
scored AS (
    SELECT
        *,
        GREATEST(
            identifier_score,
            0.45 * title_score + 0.25 * brand_score + 0.30 * pack_score
        ) AS match_score
    FROM candidates
)
SELECT
    *,
    CASE
        WHEN identifier_score > 0 AND cardinality(conflicts) > 0 THEN 'conflict'
        WHEN identifier_score = 1.00 THEN 'deterministic'
        WHEN identifier_score = 0.96 AND pack_score = 1.0 THEN 'very_high'
        WHEN cardinality(conflicts) > 0 THEN 'low'
        WHEN match_score >= 0.97 THEN 'high'
        WHEN match_score >= 0.85 THEN 'medium'
        ELSE 'low'
    END AS match_class
FROM scored
WHERE match_score >= 0.65;   -- generation floor; the action thresholds are above
