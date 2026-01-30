
import argparse
import json
import os
import sys
from glob import glob
from pathlib import Path
from typing import List, Dict

from datasets import Dataset
from ragas import evaluate
# Revert to original imports to match installed version compatibility
from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_precision,
    context_recall,
)

# Import local modules
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG
from langchain_ollama import ChatOllama, OllamaEmbeddings

# Define metrics
METRICS = [
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
]

def load_batch_results(batch_dir: Path) -> List[Dict]:
    """Load all result_*.json files from the directory."""
    results = []
    pattern = str(batch_dir / "result_*.json")
    files = sorted(glob(pattern))
    
    if not files:
        print(f"No result files found in {batch_dir}")
        return []
        
    print(f"Found {len(files)} result files.")
    
    for fpath in files:
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
                
            if data.get("status") != "success":
                continue
                
            response_data = data.get("response", {})
            if isinstance(response_data, str):
                 # Handle case where response might be just a string (though unlikely in recent runs)
                 answer = response_data
                 sources = []
            else:
                answer = response_data.get("response", "")
                sources = response_data.get("sources", [])
            
            # Extract basic fields
            question = data.get("question")
            ground_truths = data.get("ground_truths", [])
            
            # Extract contexts from sources
            contexts = []
            for src in sources:
                if isinstance(src, dict):
                    contexts.append(src.get("content_preview", ""))
                elif isinstance(src, str):
                    contexts.append(src)
            
            # RAGAS expects list of strings for contexts
            results.append({
                "question": question,
                "answer": answer,
                "contexts": contexts if contexts else ["N/A"], # Prevent empty context error
                "ground_truth": ground_truths[0] if ground_truths else ""
            })
            
        except Exception as e:
            print(f"Error loading {fpath}: {e}")
            
    return results

def main():
    parser = argparse.ArgumentParser(description="Score RAGAS batch results.")
    parser.add_argument("--batch-dir", type=Path, required=True, help="Directory containing result_*.json files")
    args = parser.parse_args()
    
    if not args.batch_dir.exists():
        print(f"Directory not found: {args.batch_dir}")
        sys.exit(1)
        
    print(f"Loading results from {args.batch_dir}...")
    raw_results = load_batch_results(args.batch_dir)
    
    if not raw_results:
        print("No valid successful results to score.")
        sys.exit(0)
        
    # Prepare dataset for RAGAS
    ragas_data = {
        "question": [r["question"] for r in raw_results],
        "answer": [r["answer"] for r in raw_results],
        "contexts": [r["contexts"] for r in raw_results],
        "ground_truth": [r["ground_truth"] for r in raw_results]
    }
    
    dataset = Dataset.from_dict(ragas_data)
    
    # Configure Local LLM and Embeddings
    print("Configuring local Ollama models...")
    # Use environment vars or defaults suitable for user's setup
    llm_model = os.getenv("LLM_MODEL", "llama3:latest") 
    emb_model = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large:latest")
    
    llm = ChatOllama(model=llm_model)
    embeddings = OllamaEmbeddings(model=emb_model)
    
    print(f"Running RAGAS evaluation with LLM={llm_model}, Embeddings={emb_model}...")
    results = evaluate(
        dataset=dataset,
        metrics=METRICS,
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False
    )
    
    print("\nEvaluation Complete!")
    print(results)
    
    # Save Report
    output_file = args.batch_dir / "report.md"
    df = results.to_pandas()
    
    with open(output_file, "w") as f:
        f.write(f"# Batch Evaluation Report\n\n")
        f.write(f"**Date:** {os.getenv('RunDate', datetime.now().isoformat())}\n")
        f.write(f"**Total Questions Scored:** {len(df)}\n\n")
        
        f.write("## Aggregate Metrics\n")
        for metric, score in results.items():
            f.write(f"- **{metric}:** {score:.4f}\n")
            
        f.write("\n## Detailed Results\n")
        f.write(df.to_markdown(index=False))
        
    print(f"\nReport saved to: {output_file}")

if __name__ == "__main__":
    from datetime import datetime
    main()
