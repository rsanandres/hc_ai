#!/usr/bin/env python3
"""Standalone script to test faithfulness evaluation."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.evaluators.faithfulness import evaluate_faithfulness

# Example samples - you can modify these
samples = [
    {
        "question": "What is the patient's diagnosis?",
        "answer": "The patient has Type 2 diabetes mellitus.",
        "contexts": [
            "Patient diagnosed with Type 2 diabetes mellitus without complications (ICD-10: E11.9)."
        ],
    },
    {
        "question": "What medications is the patient taking?",
        "answer": "The patient is taking metformin 500mg twice daily.",
        "contexts": [
            "Medication: Metformin 500mg, Frequency: Twice daily"
        ],
    },
]

if __name__ == "__main__":
    print("Running faithfulness evaluation...")
    result = evaluate_faithfulness(samples)
    print(f"\nFaithfulness Score: {result['score']:.3f}")
    print(f"\nRaw result: {result['raw']}")
