-- Quick check: Are embeddings actually present?
-- Run these queries in your PostgreSQL terminal

-- 1. First, see what columns exist
\d hc_ai_schema.hc_ai_table

-- 2. Count rows with and without embeddings
SELECT 
    COUNT(*) as total_rows,
    COUNT(embedding) as rows_with_embeddings,
    COUNT(*) - COUNT(embedding) as rows_without_embeddings
FROM hc_ai_schema.hc_ai_table;

-- 3. Check embedding dimension (should be 1024) and sample rows
SELECT 
    langchain_id,
    CASE 
        WHEN embedding IS NULL THEN 'NULL - NO EMBEDDING'
        ELSE format('Has embedding: %s dimensions', 
            array_length(embedding::float[], 1)
        )
    END as embedding_info,
    LENGTH(content) as content_length
FROM hc_ai_schema.hc_ai_table
LIMIT 5;

-- 4. Sample embedding values (first 3 dimensions only)
SELECT 
    langchain_id,
    LEFT(content, 40) as content_preview,
    format('[%s, %s, %s, ...]', 
        (embedding::float[])[1],
        (embedding::float[])[2], 
        (embedding::float[])[3]
    ) as embedding_preview
FROM hc_ai_schema.hc_ai_table
LIMIT 3;
