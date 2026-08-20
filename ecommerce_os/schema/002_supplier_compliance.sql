-- Supplier authorisation and compliance, as data.
--
-- Compliance does not live in a document somebody remembers to check. Every
-- supplier x SKU x marketplace combination carries an explicit record, and the
-- publish gate reads it. Defaults are restrictive: a half-completed onboarding
-- form must fail the gate, never pass it.

CREATE TABLE supplier (
    supplier_id           text PRIMARY KEY,
    legal_entity_name     text        NOT NULL,
    supplier_type         text        NOT NULL
                          CHECK (supplier_type IN (
                              'manufacturer', 'authorised_distributor',
                              'specialist_wholesaler', 'dropship_platform',
                              'b2b_marketplace', 'liquidator'
                          )),
    country               char(2)     NOT NULL,
    onboarded_on          date        NOT NULL,
    notes                 text
);

CREATE TABLE supplier_authorisation (
    supplier_authorisation_id  bigserial PRIMARY KEY,
    supplier_id                text   NOT NULL REFERENCES supplier (supplier_id),
    canonical_product_id       bigint NOT NULL REFERENCES canonical_product (canonical_product_id),

    resale_authorised          boolean NOT NULL DEFAULT false,
    dropship_authorised        boolean NOT NULL DEFAULT false,
    seller_of_record_supported boolean NOT NULL DEFAULT false,
    white_label_packaging      boolean NOT NULL DEFAULT false,
    catalogue_content_rights   boolean NOT NULL DEFAULT false,
    brand_authorisation_status text    NOT NULL DEFAULT 'pending'
                               CHECK (brand_authorisation_status IN (
                                   'authorised', 'not_required', 'pending', 'refused'
                               )),

    -- ISO country codes and marketplace slugs. Empty means nothing is
    -- authorised, which is the correct reading of an agreement that is silent.
    territories                text[]  NOT NULL DEFAULT '{}',
    marketplaces               text[]  NOT NULL DEFAULT '{}',

    return_address_country     char(2),
    warranty_owner             text,
    dispatch_sla_hours         integer CHECK (dispatch_sla_hours IS NULL OR dispatch_sla_hours >= 0),
    tracking_sla_hours         integer CHECK (tracking_sla_hours  IS NULL OR tracking_sla_hours  >= 0),

    inventory_feed_type        text    NOT NULL DEFAULT 'manual'
                               CHECK (inventory_feed_type IN (
                                   'api', 'sftp', 'csv', 'xml', 'json', 'edi', 'manual'
                               )),
    inventory_feed_frequency_minutes integer
                               CHECK (inventory_feed_frequency_minutes IS NULL
                                      OR inventory_feed_frequency_minutes > 0),

    agreement_start            date    NOT NULL,
    agreement_end              date,
    compliance_review_date     date,
    agreement_ref              text,

    CHECK (agreement_end IS NULL OR agreement_end >= agreement_start),
    -- Direct-to-customer fulfilment is meaningless without the ability to be
    -- the only seller the buyer ever sees.
    CHECK (NOT dropship_authorised
           OR (seller_of_record_supported AND white_label_packaging)),
    -- Nothing is authorised for resale without somewhere for returns to go.
    CHECK (NOT resale_authorised OR return_address_country IS NOT NULL),

    UNIQUE (supplier_id, canonical_product_id, agreement_start)
);

CREATE INDEX supplier_authorisation_lookup_idx
    ON supplier_authorisation (canonical_product_id, supplier_id);

-- Rolling observed performance. Suppliers are scored on what they did, not on
-- what they promised.
CREATE TABLE supplier_performance (
    supplier_id               text        NOT NULL REFERENCES supplier (supplier_id),
    window_start              date        NOT NULL,
    window_end                date        NOT NULL,
    orders                    integer     NOT NULL CHECK (orders >= 0),
    fill_rate                 numeric(6, 5) NOT NULL CHECK (fill_rate BETWEEN 0 AND 1),
    on_time_dispatch_rate     numeric(6, 5) NOT NULL CHECK (on_time_dispatch_rate BETWEEN 0 AND 1),
    valid_tracking_rate       numeric(6, 5) NOT NULL CHECK (valid_tracking_rate BETWEEN 0 AND 1),
    feed_accuracy             numeric(6, 5) NOT NULL CHECK (feed_accuracy BETWEEN 0 AND 1),
    return_resolution_quality numeric(6, 5) NOT NULL CHECK (return_resolution_quality BETWEEN 0 AND 1),
    non_defect_rate           numeric(6, 5) NOT NULL CHECK (non_defect_rate BETWEEN 0 AND 1),
    PRIMARY KEY (supplier_id, window_start, window_end),
    CHECK (window_end >= window_start)
);

-- Why a listing is currently not selling. Written by the kill switches.
CREATE TABLE listing_pause (
    listing_pause_id      bigserial PRIMARY KEY,
    scope                 text        NOT NULL CHECK (scope IN ('sku', 'supplier')),
    canonical_product_id  bigint      REFERENCES canonical_product (canonical_product_id),
    supplier_id           text        REFERENCES supplier (supplier_id),
    rule                  text        NOT NULL,
    detail                text        NOT NULL,
    paused_at             timestamptz NOT NULL DEFAULT now(),
    released_at           timestamptz,
    released_by           text,
    CHECK (scope <> 'sku'      OR canonical_product_id IS NOT NULL),
    CHECK (scope <> 'supplier' OR supplier_id IS NOT NULL)
);

CREATE INDEX listing_pause_open_idx
    ON listing_pause (scope, canonical_product_id, supplier_id)
    WHERE released_at IS NULL;
