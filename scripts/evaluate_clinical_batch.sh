#!/bin/bash

# Batch RAGAS Evaluation Wrapper
# Runs evaluation one question at a time, restarting the API service in between to clear memory.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTSET="$PROJECT_ROOT/POC_RAGAS/data/testsets/generated_clinical_testset.json"
# Allow overriding output dir to resume a run
if [ -z "$BATCH_OUTPUT_DIR" ]; then
    OUTPUT_DIR="$PROJECT_ROOT/POC_RAGAS/data/testsets/batch_runs/batch_run_$(date -u +%Y%m%dT%H%M%SZ)"
else
    OUTPUT_DIR="$BATCH_OUTPUT_DIR"
fi

# Range configuration (defaults to full set 0-30)
START_INDEX=${START_INDEX:-0}
END_INDEX=${END_INDEX:-30}

echo "Starting Batch Evaluation..."
echo "Output Directory: $OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python"
    echo "Using venv python: $PYTHON_CMD"
else
    PYTHON_CMD="python3"
    echo "Using system python: $PYTHON_CMD"
fi

for ((i=START_INDEX; i<END_INDEX; i++)); do
    # Resume check: Skip if result already exists
    RESULT_FILE="$OUTPUT_DIR/result_$(printf "%03d" $i).json"
    if [ -f "$RESULT_FILE" ]; then
        echo "Skipping Q[$i] (Already completed: $RESULT_FILE)"
        continue
    fi

    echo "=================================================="
    echo "PROCESSING QUESTION $i / $((MAX_QUESTIONS-1))"
    echo "=================================================="
    
    # Retry Loop for this question
    while true; do
        # 1. Start API Service in background
        echo "Starting API service..."
        $PYTHON_CMD api/main.py > "$OUTPUT_DIR/api_log_$i.txt" 2>&1 &
        API_PID=$!
        
        # Wait for API to be ready
        echo "Waiting for API to initialize (30s)..."
        sleep 30
        
        # 2. Run Single Evaluation Question
        echo "Running evaluation for Q[$i]..."
        $PYTHON_CMD "$PROJECT_ROOT/POC_RAGAS/scripts/run_evaluation_batch.py" \
            --testset "$TESTSET" \
            --question-index "$i" \
            --output-dir "$OUTPUT_DIR" \
            --mode api \
            --patient-mode both
            
        EXIT_CODE=$?
            
        # 3. Kill API Service (always kill after run)
        echo "Stopping API service (PID: $API_PID)..."
        kill $API_PID
        wait $API_PID 2>/dev/null
        
        # Extra cleanup
        pkill -f "api/main.py" 
        
        # Check exit code
        if [ $EXIT_CODE -eq 2 ]; then
            echo "⚠️  Detected 500 Internal Server Error (Code 2). Sleeping 60s and RETRYING Q[$i]..."
            sleep 60
            # Continue while loop to retry same question
            continue
        else
            # Success (0) or other error (1) - move to next question
            if [ $EXIT_CODE -ne 0 ]; then
                echo "❌ Failed Q[$i] with code $EXIT_CODE (non-retryable)."
            fi
            echo "Finished Q[$i]. Sleeping 5s before next..."
            sleep 5
            break # Break retry loop, move to next question (i++)
        fi
    done
done

echo "Batch Evaluation Complete!"
echo "Results saved in: $OUTPUT_DIR"
