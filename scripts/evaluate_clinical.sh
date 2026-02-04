#!/bin/bash

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Add project root to PYTHONPATH
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# Check if .env file exists and export variables (filtering out comments)
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source <(grep -v '^#' "$PROJECT_ROOT/.env" | sed 's/#.*//')
    set +a
fi

# Handle --fresh flag to always start from 0
ARGS="$@"
if [[ "$*" == *"--fresh"* ]]; then
    echo "Starting fresh evaluation (clearing checkpoint)..."
    ARGS="${ARGS/--fresh/} --start-from 0"
fi

echo "Starting RAGAS Clinical Evaluation..."
echo "Testset: POC_RAGAS/data/testsets/generated_clinical_testset.json"
echo "Mode: API (running against http://localhost:8000/agent/query)"

# Run the evaluation
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON_CMD="python3"
fi

# Generate timestamp for output
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
echo "Output ID: $TIMESTAMP"

$PYTHON_CMD "$PROJECT_ROOT/POC_RAGAS/scripts/run_evaluation.py" \
    --testset "$PROJECT_ROOT/POC_RAGAS/data/testsets/generated_clinical_testset.json" \
    --mode api \
    --patient-mode both \
    --output-id "$TIMESTAMP" \
    --cooldown 45 \
    $ARGS
