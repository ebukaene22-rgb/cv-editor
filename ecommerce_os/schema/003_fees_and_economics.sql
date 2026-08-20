-- Marketplace fees, tax treatment and realised economics.
--
-- Fees vary by marketplace, country, category, price band and date, and they
-- stack. There is deliberately no default rate anywhere in this schema: an
-- unpriceable combination must fail to resolve, because "about 15%" is how a
-- portfolio of confidently unprofitable SKUs gets built.

CREATE TABLE marketplace_fee_rule (
    marketplace_fee_rule_id bigserial PRIMARY KEY,
    marketplace             text        NOT NULL,
    country                 text        NOT NULL,   -- ISO code, or '*' for any
    category                text        NOT NULL,   -- taxonomy node, or '*' for any
    fee_kind                text        NOT NULL
                            CHECK (fee_kind IN (
                                'referral', 'final_value', 'regulatory_operating',
                                'international', 'closing', 'fulfilment',
                                'storage', 'advertising'
                            )),
    variable_rate           numeric(8, 6) NOT NULL CHECK (variable_rate BETWEEN 0 AND 1),
    fixed_fee               numeric(12, 2) NOT NULL DEFAULT 0,
    currency                char(3)     NOT NULL,
    -- Half-open band [price_min, price_max) so adjacent bands cannot both match.
    price_min               numeric(12, 2),
    price_max               numeric(12, 2),
    effective_from          date        NOT NULL,
    effective_to            date,
    schedule_version        text        NOT NULL,
    source_ref              text,       -- where this rate was read from
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CHECK (price_max IS NULL OR price_min IS NULL OR price_max > price_min)
);

CREATE INDEX marketplace_fee_rule_lookup_idx
    ON marketplace_fee_rule (marketplace, fee_kind, country, category, effective_from);

-- Fee estimates returned by a marketplace API are observations, not truth: the
-- marketplace itself does not guarantee they equal the fee finally charged.
-- Storing them lets the reconciliation loop measure that gap.
CREATE TABLE fee_estimate_observation (
    fee_estimate_observation_id bigserial PRIMARY KEY,
    marketplace             text        NOT NULL,
    marketplace_listing_ref  text       NOT NULL,
    observed_at             timestamptz NOT NULL DEFAULT now(),
    price                   numeric(12, 2) NOT NULL,
    currency                char(3)     NOT NULL,
    estimated_total_fee     numeric(12, 2) NOT NULL,
    estimate_detail         jsonb       NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE tax_treatment (
    tax_treatment_id        bigserial PRIMARY KEY,
    market                  char(2)     NOT NULL,
    marketplace             text        NOT NULL,
    -- Distinguishes the three different things called "VAT": collected,
    -- recoverable, and genuinely a cost.
    vat_treatment           text        NOT NULL
                            CHECK (vat_treatment IN (
                                'seller_collects', 'marketplace_deemed_supplier',
                                'zero_rated', 'out_of_scope'
                            )),
    sale_vat_rate           numeric(6, 5) NOT NULL CHECK (sale_vat_rate BETWEEN 0 AND 1),
    input_vat_recoverable   boolean     NOT NULL,
    consignment_value_min   numeric(12, 2),
    consignment_value_max   numeric(12, 2),
    goods_located_in        char(2),
    effective_from          date        NOT NULL,
    effective_to            date,
    notes                   text
);

CREATE TABLE duty_rule (
    duty_rule_id            bigserial PRIMARY KEY,
    destination             char(2)     NOT NULL,
    commodity_code          text        NOT NULL,
    -- Charged on the customs value: cost + insurance + freight.
    duty_rate               numeric(6, 5) NOT NULL CHECK (duty_rate BETWEEN 0 AND 1),
    basis                   text        NOT NULL DEFAULT 'cif' CHECK (basis IN ('cif', 'fob')),
    effective_from          date        NOT NULL,
    effective_to            date,
    source_ref              text
);

-- Predicted vs realised, per order. This table is what turns heuristics into
-- posteriors: the residual CM_actual - CM_predicted decomposes into fee error,
-- shipping error, tax error, return error, supplier price error and ad error.
CREATE TABLE order_economics (
    order_economics_id      bigserial PRIMARY KEY,
    order_ref               text        NOT NULL UNIQUE,
    canonical_product_id    bigint      NOT NULL REFERENCES canonical_product (canonical_product_id),
    supplier_id             text        NOT NULL REFERENCES supplier (supplier_id),
    marketplace             text        NOT NULL,
    market                  char(2)     NOT NULL,
    fulfilment_method       text        NOT NULL
                            CHECK (fulfilment_method IN (
                                'supplier_dropship', 'own_stock',
                                'third_party_logistics', 'marketplace_fulfilled'
                            )),
    ordered_at              timestamptz NOT NULL,
    currency                char(3)     NOT NULL,

    predicted_contribution  numeric(12, 2) NOT NULL,
    predicted_lines         jsonb       NOT NULL,

    actual_contribution     numeric(12, 2),
    actual_lines            jsonb,
    settled_at              timestamptz,

    was_cancelled           boolean     NOT NULL DEFAULT false,
    was_returned            boolean     NOT NULL DEFAULT false,
    was_charged_back        boolean     NOT NULL DEFAULT false
);

CREATE INDEX order_economics_reconciliation_idx
    ON order_economics (canonical_product_id, ordered_at)
    WHERE actual_contribution IS NOT NULL;
