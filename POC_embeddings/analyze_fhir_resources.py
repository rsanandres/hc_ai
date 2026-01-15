#!/usr/bin/env python3
"""
Analyze FHIR resources from random sample of files.

This script analyzes 10,000 random FHIR bundle files to:
- Count occurrences of each resource type
- Measure content length for each resource type
- Calculate statistics (min, max, avg, median) per resource type
- Help determine which resource categories are worth chunking
"""

import json
import os
import random
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_fhir_bundle(file_path: str) -> Optional[Dict]:
    """Load a FHIR bundle from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {file_path}: {e}")
        return None


def extract_resources_from_bundle(bundle: Dict) -> List[Dict]:
    """Extract all resources from a FHIR bundle."""
    resources = []
    entries = bundle.get("entry", [])
    
    for entry in entries:
        resource = entry.get("resource", {})
        if resource:
            # Add metadata from entry
            resource_with_meta = {
                "resourceType": resource.get("resourceType", "Unknown"),
                "id": resource.get("id", ""),
                "fullUrl": entry.get("fullUrl", ""),
                "resource": resource
            }
            resources.append(resource_with_meta)
    
    return resources


def extract_content_from_resource(resource: Dict) -> str:
    """
    Extract meaningful text content from a FHIR resource.
    Uses the same extraction logic as test_chunking_comparison.py
    """
    import re
    
    resource_obj = resource.get("resource", {})
    if not resource_obj:
        return ""
    
    resource_type = resource_obj.get("resourceType", "")
    parts = []
    
    # Patient resource
    if resource_type == "Patient":
        parts.append("Patient:")
        if "name" in resource_obj and isinstance(resource_obj["name"], list) and len(resource_obj["name"]) > 0:
            name_obj = resource_obj["name"][0]
            if isinstance(name_obj, dict):
                name_parts = []
                if "family" in name_obj and isinstance(name_obj["family"], str):
                    name_parts.append(name_obj["family"])
                if "given" in name_obj and isinstance(name_obj["given"], list):
                    name_parts.extend([g for g in name_obj["given"] if isinstance(g, str)])
                if name_parts:
                    parts.append(" ".join(name_parts))
        if "birthDate" in resource_obj:
            parts.append(f"DOB: {resource_obj['birthDate']}")
        if "gender" in resource_obj:
            parts.append(f"Gender: {resource_obj['gender']}")
    
    # Condition resource
    elif resource_type == "Condition":
        parts.append("Condition:")
        if "code" in resource_obj:
            code_obj = resource_obj["code"]
            if isinstance(code_obj, dict):
                if "text" in code_obj:
                    parts.append(code_obj["text"])
                elif "coding" in code_obj and isinstance(code_obj["coding"], list) and len(code_obj["coding"]) > 0:
                    coding_obj = code_obj["coding"][0]
                    if isinstance(coding_obj, dict) and "display" in coding_obj:
                        parts.append(coding_obj["display"])
        if "onsetDateTime" in resource_obj:
            parts.append(f"Onset: {resource_obj['onsetDateTime']}")
        if "clinicalStatus" in resource_obj:
            status = resource_obj["clinicalStatus"]
            if isinstance(status, dict) and "text" in status:
                parts.append(f"Status: {status['text']}")
    
    # Observation resource
    elif resource_type == "Observation":
        parts.append("Observation:")
        if "code" in resource_obj:
            code_obj = resource_obj["code"]
            if isinstance(code_obj, dict):
                if "text" in code_obj:
                    parts.append(code_obj["text"])
                elif "coding" in code_obj and isinstance(code_obj["coding"], list) and len(code_obj["coding"]) > 0:
                    coding_obj = code_obj["coding"][0]
                    if isinstance(coding_obj, dict) and "display" in coding_obj:
                        parts.append(coding_obj["display"])
        if "valueQuantity" in resource_obj:
            value_qty = resource_obj["valueQuantity"]
            if isinstance(value_qty, dict):
                value = value_qty.get("value")
                unit = value_qty.get("unit", "")
                if value is not None:
                    if unit:
                        parts.append(f"Value: {value:.2f} {unit}")
                    else:
                        parts.append(f"Value: {value:.2f}")
        if "effectiveDateTime" in resource_obj:
            parts.append(f"Date: {resource_obj['effectiveDateTime']}")
    
    # Encounter resource
    elif resource_type == "Encounter":
        parts.append("Healthcare Encounter:")
        if "type" in resource_obj and isinstance(resource_obj["type"], list) and len(resource_obj["type"]) > 0:
            type_obj = resource_obj["type"][0]
            if isinstance(type_obj, dict):
                if "text" in type_obj:
                    parts.append(type_obj["text"])
                elif "coding" in type_obj and isinstance(type_obj["coding"], list) and len(type_obj["coding"]) > 0:
                    coding_obj = type_obj["coding"][0]
                    if isinstance(coding_obj, dict) and "display" in coding_obj:
                        parts.append(coding_obj["display"])
        if "period" in resource_obj:
            period = resource_obj["period"]
            if isinstance(period, dict) and "start" in period:
                parts.append(f"Start: {period['start']}")
        if "reason" in resource_obj:
            reason = resource_obj["reason"]
            if isinstance(reason, dict) and "coding" in reason and isinstance(reason["coding"], list) and len(reason["coding"]) > 0:
                coding_obj = reason["coding"][0]
                if isinstance(coding_obj, dict) and "display" in coding_obj:
                    parts.append(f"Reason: {coding_obj['display']}")
    
    # Other resource types
    elif resource_type in ["MedicationRequest", "Medication", "Immunization", "DiagnosticReport", "Procedure", "Organization"]:
        parts.append(f"{resource_type}:")
        if "code" in resource_obj:
            code_obj = resource_obj["code"]
            if isinstance(code_obj, dict):
                if "text" in code_obj:
                    parts.append(code_obj["text"])
                elif "coding" in code_obj and isinstance(code_obj["coding"], list) and len(code_obj["coding"]) > 0:
                    coding_obj = code_obj["coding"][0]
                    if isinstance(coding_obj, dict) and "display" in coding_obj:
                        parts.append(coding_obj["display"])
        if "name" in resource_obj and isinstance(resource_obj["name"], str):
            parts.append(resource_obj["name"])
        
        # DiagnosticReport specific
        if resource_type == "DiagnosticReport" and "conclusion" in resource_obj:
            parts.append(resource_obj["conclusion"])
        
        # MedicationRequest specific
        if resource_type == "MedicationRequest" and "medicationCodeableConcept" in resource_obj:
            mcc = resource_obj["medicationCodeableConcept"]
            if isinstance(mcc, dict) and "text" in mcc:
                parts.append(mcc["text"])
    
    if len(parts) == 0:
        # Fallback: use JSON string
        return json.dumps(resource_obj, ensure_ascii=False)
    
    content = " ".join(parts)
    
    # Clean HTML tags if present
    content = re.sub(r'<[^>]+>', '', content)
    
    return content


def analyze_file(file_path: str) -> Dict:
    """Analyze a single FHIR bundle file."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    
    file_stats = {
        "file": os.path.basename(file_path),
        "total_resources": len(resources),
        "resource_types": defaultdict(list)  # resource_type -> list of content lengths
    }
    
    for resource in resources:
        resource_type = resource.get("resourceType", "Unknown")
        content = extract_content_from_resource(resource)
        content_length = len(content)
        
        file_stats["resource_types"][resource_type].append(content_length)
    
    # Convert defaultdict to regular dict for JSON serialization
    file_stats["resource_types"] = dict(file_stats["resource_types"])
    
    return file_stats


def aggregate_results(all_file_stats: List[Dict]) -> Dict:
    """Aggregate statistics across all files."""
    # Aggregate by resource type
    resource_type_stats = defaultdict(lambda: {
        "occurrences": 0,
        "content_lengths": [],
        "files_with_resource": set()
    })
    
    total_files = len(all_file_stats)
    
    for file_stat in all_file_stats:
        file_name = file_stat["file"]
        for resource_type, lengths in file_stat.get("resource_types", {}).items():
            resource_type_stats[resource_type]["occurrences"] += len(lengths)
            resource_type_stats[resource_type]["content_lengths"].extend(lengths)
            resource_type_stats[resource_type]["files_with_resource"].add(file_name)
    
    # Calculate statistics for each resource type
    aggregated = {
        "total_files_analyzed": total_files,
        "total_resources": sum(stat["occurrences"] for stat in resource_type_stats.values()),
        "resource_types": {}
    }
    
    for resource_type, stats in resource_type_stats.items():
        lengths = stats["content_lengths"]
        files_with = len(stats["files_with_resource"])
        
        if lengths:
            aggregated["resource_types"][resource_type] = {
                "total_occurrences": stats["occurrences"],
                "files_with_this_resource": files_with,
                "percentage_of_files": (files_with / total_files) * 100 if total_files > 0 else 0,
                "content_length_stats": {
                    "min": min(lengths),
                    "max": max(lengths),
                    "mean": statistics.mean(lengths),
                    "median": statistics.median(lengths),
                    "stdev": statistics.stdev(lengths) if len(lengths) > 1 else 0,
                    "total_chars": sum(lengths)
                },
                "chunking_recommendation": get_chunking_recommendation(
                    resource_type, 
                    statistics.median(lengths),
                    statistics.mean(lengths),
                    max(lengths)
                )
            }
    
    return aggregated


def get_chunking_recommendation(resource_type: str, median_length: float, mean_length: float, max_length: int) -> str:
    """Provide chunking recommendation based on resource statistics."""
    # Resources that are typically small and atomic
    atomic_resources = ["Patient", "Medication", "Organization", "Practitioner"]
    
    if resource_type in atomic_resources:
        return "direct_chunk"  # No chunking needed, preserve as single unit
    
    # Very small resources (< 200 chars) - direct chunk
    if median_length < 200 and mean_length < 200:
        return "direct_chunk"
    
    # Small resources (200-500 chars) - may benefit from chunking if max is large
    if median_length < 500 and mean_length < 500:
        if max_length > 2000:
            return "conditional_chunk"  # Most are small, but some are large
        return "direct_chunk"
    
    # Medium resources (500-1500 chars) - likely need chunking
    if median_length < 1500 and mean_length < 1500:
        if max_length > 3000:
            return "parent_child_chunk"  # Some are quite large
        return "semantic_chunk"  # Moderate size, semantic chunking
    
    # Large resources (> 1500 chars median) - definitely need chunking
    if max_length > 5000:
        return "parent_child_chunk"  # Very large, use parent-child
    return "semantic_chunk"  # Large but manageable with semantic


def main(data_dir: str = "../data/fhir", num_files: int = 10000, output_file: str = "fhir_resource_analysis.json"):
    """Main analysis function."""
    data_path = Path(data_dir)
    
    if not data_path.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return
    
    # Get all JSON files
    all_json_files = list(data_path.glob("*.json"))
    total_available = len(all_json_files)
    
    if total_available == 0:
        logger.error(f"No JSON files found in {data_dir}")
        return
    
    # Randomly sample files
    num_files = min(num_files, total_available)
    logger.info(f"Found {total_available} files, analyzing {num_files} random files")
    
    sampled_files = random.sample(all_json_files, num_files)
    
    logger.info("="*80)
    logger.info("Starting FHIR Resource Analysis")
    logger.info("="*80)
    
    all_file_stats = []
    start_time = time.time()
    
    for i, file_path in enumerate(sampled_files, 1):
        if i % 1000 == 0:
            logger.info(f"  Processed {i}/{num_files} files...")
        
        file_stat = analyze_file(str(file_path))
        if file_stat:
            all_file_stats.append(file_stat)
    
    total_time = time.time() - start_time
    
    logger.info(f"\nCompleted analysis of {len(all_file_stats)} files in {total_time:.2f} seconds")
    logger.info("Aggregating results...")
    
    # Aggregate results
    aggregated = aggregate_results(all_file_stats)
    
    # Write results to JSON
    output_path = Path(__file__).parent / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\nResults written to: {output_path}")
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("RESOURCE TYPE SUMMARY")
    logger.info("="*80)
    
    # Sort by total occurrences
    sorted_resources = sorted(
        aggregated["resource_types"].items(),
        key=lambda x: x[1]["total_occurrences"],
        reverse=True
    )
    
    logger.info(f"\nTotal Resources Analyzed: {aggregated['total_resources']:,}")
    logger.info(f"Unique Resource Types: {len(sorted_resources)}\n")
    
    logger.info(f"{'Resource Type':<25} {'Occurrences':>12} {'Files':>8} {'% Files':>8} {'Median':>10} {'Mean':>10} {'Max':>10} {'Recommendation':<20}")
    logger.info("-" * 120)
    
    for resource_type, stats in sorted_resources[:30]:  # Top 30
        length_stats = stats["content_length_stats"]
        logger.info(
            f"{resource_type:<25} "
            f"{stats['total_occurrences']:>12,} "
            f"{stats['files_with_this_resource']:>8} "
            f"{stats['percentage_of_files']:>7.1f}% "
            f"{length_stats['median']:>10.0f} "
            f"{length_stats['mean']:>10.0f} "
            f"{length_stats['max']:>10} "
            f"{stats['chunking_recommendation']:<20}"
        )
    
    if len(sorted_resources) > 30:
        logger.info(f"\n... and {len(sorted_resources) - 30} more resource types")
    
    # Summary by chunking recommendation
    logger.info("\n" + "="*80)
    logger.info("CHUNKING RECOMMENDATIONS SUMMARY")
    logger.info("="*80)
    
    by_recommendation = defaultdict(list)
    for resource_type, stats in sorted_resources:
        rec = stats["chunking_recommendation"]
        by_recommendation[rec].append((resource_type, stats))
    
    for recommendation, resources in sorted(by_recommendation.items()):
        total_occurrences = sum(s["total_occurrences"] for _, s in resources)
        logger.info(f"\n{recommendation.upper().replace('_', ' ')}:")
        logger.info(f"  Resource types: {len(resources)}")
        logger.info(f"  Total occurrences: {total_occurrences:,}")
        logger.info(f"  Resources: {', '.join(r[0] for r in resources[:10])}")
        if len(resources) > 10:
            logger.info(f"  ... and {len(resources) - 10} more")
    
    logger.info("\n" + "="*80)
    
    return aggregated


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze FHIR resources from random sample")
    parser.add_argument("--data-dir", type=str, default="../data/fhir", help="Directory containing FHIR JSON files")
    parser.add_argument("--num-files", type=int, default=10000, help="Number of files to analyze")
    parser.add_argument("--output", type=str, default="fhir_resource_analysis.json", help="Output file name")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    
    args = parser.parse_args()
    
    if args.seed is not None:
        random.seed(args.seed)
        logger.info(f"Using random seed: {args.seed}")
    
    main(args.data_dir, args.num_files, args.output)
