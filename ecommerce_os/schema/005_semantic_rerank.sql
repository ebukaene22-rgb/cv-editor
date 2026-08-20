-- Optional: semantic reranking with pgvector.
--
-- Everything else in this schema works without it. Embeddings are a *reranker*
-- applied after blocking, never a scan across the whole catalogue: nearest
-- neighbours in embedding space happily return a 6-pack for a 3-pack query,
-- which is exactly the failure the rest of the matcher exists to prevent.
--
-- Keeping relational attributes, identifiers and vectors in one database is
-- worth doing until scale genuinely proves a dedicated search platform is
-- needed. Do not spend six months reinventing infrastructure; the
-- differentiation is in the matching, not the hosting.

CREATE EXTENSION IF NOT EXISTS vector;

-- Dimension must match the embedding model actually in use.
ALTER TABLE canonical_product
    ADD COLUMN IF NOT EXISTS title_embedding vector(384);

-- Approximate nearest neighbour over cosine distance. Build this only once
-- there are enough rows for the lists parameter to mean anything.
CREATE INDEX IF NOT EXISTS canonical_product_embedding_idx
    ON canonical_product USING ivfflat (title_embedding vector_cosine_ops)
    WITH (lists = 100);


-- Reranking query, for reference. Note the WHERE clause: brand and category
-- blocking come first, and the vector search only ever orders the survivors.
--
--   SELECT canonical_product_id,
--          canonical_title,
--          1 - (title_embedding <=> :query_embedding) AS semantic_similarity
--   FROM canonical_product
--   WHERE brand_normalized = :brand
--     AND category_taxonomy = :category
--   ORDER BY title_embedding <=> :query_embedding
--   LIMIT 20;
