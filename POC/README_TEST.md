# Chunking Comparison Test

This test compares semantic chunking vs parent-child chunking on FHIR patient data.

## Usage

```bash
# Activate virtual environment
source ../.venv/bin/activate

# Run test on 1000 files (default)
python test_chunking_comparison.py

# Run test on custom number of files
python test_chunking_comparison.py --num-files 500

# Specify custom data directory
python test_chunking_comparison.py --data-dir ../data/fhir --num-files 1000

# Custom output file
python test_chunking_comparison.py --output my_results.json
```

## Output

The test generates a JSON file (`chunking_comparison_results.json` by default) containing:

- **Test configuration**: Parameters used for both chunking methods
- **Semantic chunking results**: Aggregate stats and individual file results
- **Parent-child chunking results**: Aggregate stats and individual file results
- **Comparison**: Side-by-side differences and percentage changes

## Metrics Compared

- Total chunks created
- Average chunk size
- Min/max chunk sizes
- Processing time
- Chunks per resource type
- Parent-to-child ratios (for parent-child method)
