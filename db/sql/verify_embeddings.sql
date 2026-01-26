-- Verify embeddings are actually present in the database
-- Run this in your PostgreSQL terminal

-- 1. Check table structure to see all columns
SELECT 
    column_name,
    data_type,
    udt_name
FROM information_schema.columns
WHERE table_schema = 'hc_ai_schema'
  AND table_name = 'hc_ai_table'
ORDER BY ordinal_position;

-- 2. Count total rows and rows with embeddings
SELECT 
    COUNT(*) as total_rows,
    COUNT(embedding) as rows_with_embeddings,
    COUNT(*) - COUNT(embedding) as rows_without_embeddings,
    ROUND(100.0 * COUNT(embedding) / COUNT(*), 2) as percent_with_embeddings
FROM hc_ai_schema.hc_ai_table;

-- 3. Check embedding dimensions (should be 1024 for mxbai-embed-large)
SELECT 
    id,
    CASE 
        WHEN embedding IS NULL THEN 'NULL'
        ELSE format('vector(%s dimensions)', array_length(embedding::float[], 1))
    END as embedding_status,
    LENGTH(page_content) as content_length
FROM hc_ai_schema.hc_ai_table
LIMIT 10;

-- 4. Sample actual embedding values (first few dimensions)
SELECT 
    id,
    LEFT(page_content, 50) as content_preview,
    CASE 
        WHEN embedding IS NULL THEN 'NULL'
        ELSE format('First 5 dims: [%s]', 
            array_to_string(
                (embedding::float[])[1:5], 
                ', '
            )
        )
    END as embedding_sample
FROM hc_ai_schema.hc_ai_table
WHERE embedding IS NOT NULL
LIMIT 5;

-- 5. Check if embeddings are all zeros (which would indicate a problem)
SELECT 
    COUNT(*) as total_with_embeddings,
    COUNT(*) FILTER (WHERE embedding = array_fill(0::float, ARRAY[1024])::vector) as zero_embeddings,
    COUNT(*) FILTER (WHERE embedding != array_fill(0::float, ARRAY[1024])::vector) as non_zero_embeddings
FROM hc_ai_schema.hc_ai_table
WHERE embedding IS NOT NULL;
