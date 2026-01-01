"""
Analyze all downloaded job results to understand what we have.
Separates extract jobs from split jobs and provides insights.

Run: python analyze_results.py
"""

import json
from pathlib import Path
from collections import Counter
from datetime import datetime


def classify_result(data: dict) -> str:
    """Classify what type of job result this is."""
    result = data.get("result", {})
    
    # Check for nested result (common in job downloads)
    if isinstance(result, dict) and "result" in result:
        inner = result.get("result", {})
        if "splits" in inner:
            return "split"
        if "soi_rows" in inner:
            return "extract"
    
    # Direct result structure
    if "splits" in result:
        return "split"
    if "soi_rows" in result:
        return "extract"
    if "blocks" in result:
        return "parse"
    
    return "unknown"


def count_soi_rows(data: dict) -> int:
    """Count soi_rows in an extract result."""
    result = data.get("result", {})
    
    # Handle nested structure
    if isinstance(result, dict) and "soi_rows" in result:
        soi_rows = result.get("soi_rows")
    elif isinstance(result, dict) and "result" in result:
        soi_rows = result.get("result", {}).get("soi_rows")
    else:
        soi_rows = None
    
    if isinstance(soi_rows, list):
        return len(soi_rows)
    return 0


def main():
    extract_urls_dir = Path("extract_urls")
    
    print("=" * 70)
    print("ANALYZING ALL DOWNLOADED RESULTS")
    print("=" * 70)
    print()
    
    files = list(extract_urls_dir.glob("*.json"))
    print(f"Total files: {len(files)}")
    print()
    
    # Classify each file
    by_type = {
        "extract": [],
        "split": [],
        "parse": [],
        "unknown": [],
    }
    
    extract_stats = {
        "with_rows": [],
        "empty_rows": [],
        "null_rows": [],
    }
    
    for f in files:
        try:
            with open(f, "r") as fp:
                data = json.load(fp)
            
            job_type = classify_result(data)
            by_type[job_type].append(f.stem)
            
            if job_type == "extract":
                row_count = count_soi_rows(data)
                if row_count > 0:
                    extract_stats["with_rows"].append((f.stem, row_count))
                else:
                    # Check if null or empty list
                    result = data.get("result", {})
                    soi_rows = result.get("soi_rows")
                    if soi_rows is None:
                        extract_stats["null_rows"].append(f.stem)
                    else:
                        extract_stats["empty_rows"].append(f.stem)
                        
        except Exception as e:
            by_type["unknown"].append(f.stem)
    
    # Report
    print("JOB TYPES:")
    print(f"  Extract jobs:  {len(by_type['extract'])}")
    print(f"  Split jobs:    {len(by_type['split'])}")
    print(f"  Parse jobs:    {len(by_type['parse'])}")
    print(f"  Unknown:       {len(by_type['unknown'])}")
    print()
    
    print("EXTRACT JOB QUALITY:")
    print(f"  With soi_rows data:  {len(extract_stats['with_rows'])}")
    print(f"  Empty soi_rows:      {len(extract_stats['empty_rows'])}")
    print(f"  Null soi_rows:       {len(extract_stats['null_rows'])}")
    print()
    
    if extract_stats["with_rows"]:
        row_counts = [r[1] for r in extract_stats["with_rows"]]
        total_rows = sum(row_counts)
        avg_rows = total_rows / len(row_counts)
        print(f"  Total rows extracted: {total_rows}")
        print(f"  Average rows/file:    {avg_rows:.1f}")
        print(f"  Min rows:             {min(row_counts)}")
        print(f"  Max rows:             {max(row_counts)}")
    print()
    
    # Move split jobs to split_results
    print("-" * 70)
    print("ORGANIZING FILES...")
    print("-" * 70)
    
    split_dir = Path("split_results")
    split_dir.mkdir(exist_ok=True)
    
    moved = 0
    for stem in by_type["split"]:
        src = extract_urls_dir / f"{stem}_extract_response.json"
        dst = split_dir / f"{stem}_split_result.json"
        
        if src.exists() and not dst.exists():
            # Read, rename, and move
            with open(src, "r") as f:
                data = json.load(f)
            with open(dst, "w") as f:
                json.dump(data, f, indent=2)
            src.unlink()  # Remove from extract_urls
            moved += 1
    
    print(f"  Moved {moved} split results to split_results/")
    
    # Remove unknown/parse from extract_urls (they're not what we need)
    removed = 0
    for stem in by_type["unknown"] + by_type["parse"]:
        src = extract_urls_dir / f"{stem}_extract_response.json"
        if src.exists():
            src.unlink()
            removed += 1
    
    print(f"  Removed {removed} non-extract files from extract_urls/")
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Usable extract results: {len(extract_stats['with_rows'])}")
    print(f"Extract jobs with no data: {len(extract_stats['empty_rows']) + len(extract_stats['null_rows'])}")
    print()
    
    # Top files by row count
    if extract_stats["with_rows"]:
        print("TOP 10 EXTRACTIONS (by row count):")
        sorted_by_rows = sorted(extract_stats["with_rows"], key=lambda x: x[1], reverse=True)
        for stem, count in sorted_by_rows[:10]:
            print(f"  {stem}: {count} rows")
        print()
    
    # Files with null/empty that might need re-running
    bad_files = extract_stats["empty_rows"] + extract_stats["null_rows"]
    if bad_files:
        print(f"FILES WITH NO DATA ({len(bad_files)} files):")
        print("  These extractions returned empty results - might need investigation")
        for stem in bad_files[:20]:
            print(f"  - {stem}")
        if len(bad_files) > 20:
            print(f"  ... and {len(bad_files) - 20} more")
    
    print()
    print("Next: Run 'python validate_existing.py' to validate the clean extract results")


if __name__ == "__main__":
    main()

