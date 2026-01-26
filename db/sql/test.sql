CREATE TABLE test_table (
    id serial PRIMARY KEY,
    embedding vector(1024)
);

-- Insert a dummy vector (all zeros for now)
INSERT INTO test_table (embedding) VALUES (array_fill(0, ARRAY[1024])::vector);

-- Check it
SELECT * FROM test_table;
