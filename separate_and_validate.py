"""
Separate actual data extraction results from split/classification results.

Split results have a nested structure like:
  {"result": {"result": {"splits": [...]}}}

Actual extraction results have:
  {"result": {"soi_rows": [...], "soi_title": {...}, ...}}

This script:
1. Identifies which files are split results vs extraction results
2. Moves/copies extraction results to a dedicated folder
3. Validates the extraction results

Run: python separate_and_validate.py
"""

import json
import shutil
from pathlib import Path
from collections import Counter
from datetime import datetime


def is_split_result(data: dict) -> bool:
    """
    Check if this is a split/classification result (not actual extraction).
    
    Split results have structure:
      {"result": {"result": {"splits": [...]}, "usage": {...}}}
    
    Or sometimes:
      {"result": {"result": {"section_mapping": ..., "splits": [...]}}}
    """
    if not isinstance(data, dict):
        return False
    
    result = data.get("result")
    if not isinstance(result, dict):
        return False
    
    # Check for nested "result.result.splits" structure (split results)
    inner_result = result.get("result")
    if isinstance(inner_result, dict) and "splits" in inner_result:
        return True
    
    # Check for direct "splits" key in result
    if "splits" in result:
        return True
    
    return False


from typing import Optional

from soi_sanitize import normalize_soi_rows

def get_extraction_result(data: dict) -> Optional[dict]:
    """
    Extract the actual extraction result dict from various wrapper structures.
    
    Returns the dict containing soi_rows/soi_title, or None if not found.
    
    Handles:
    1. Direct: {"result": {"soi_rows": [...], ...}}
    2. Wrapped: {"result": {"result": {"soi_rows": [...], ...}}}
    3. List result: {"result": [...]} - array extraction
    """
    if not isinstance(data, dict):
        return None
    
    result = data.get("result")
    
    # Check if result is a list (array extraction format)
    if isinstance(result, list):
        # Check if it looks like actual soi_rows (list of dicts with row_type)
        # vs error messages (list of strings)
        if result and isinstance(result[0], dict) and "row_type" in result[0]:
            return {"soi_rows": result}
        # Otherwise not a valid extraction (might be error messages)
        return None
    
    if not isinstance(result, dict):
        return None
    
    # Check for nested result.result structure (double-wrapped)
    inner = result.get("result")
    if isinstance(inner, dict) and ("soi_rows" in inner or "soi_title" in inner):
        return inner
    
    # Check for direct soi_rows/soi_title in result
    if "soi_rows" in result or "soi_title" in result:
        return result
    
    return None


def is_actual_extraction(data: dict) -> bool:
    """
    Check if this is an actual data extraction result.
    
    Real extraction results have:
      - result.soi_rows (list of holdings/subtotals/totals)
      - result.soi_title, result.as_of_date, etc.
    
    Note: soi_rows can be either a list directly OR a dict with {value, citations}
    """
    return get_extraction_result(data) is not None


def get_extraction_stats(data: dict) -> dict:
    """Get statistics about an extraction result."""
    extraction_result = get_extraction_result(data)
    if extraction_result is None:
        return {
            "total_rows": 0,
            "holdings": 0,
            "subtotals": 0,
            "totals": 0,
            "num_pages": None,
            "as_of_date": None,
        }
    
    soi_rows_raw = extraction_result.get("soi_rows", [])
    
    # Handle both list and dict with {value: list} structures
    if isinstance(soi_rows_raw, dict):
        soi_rows = soi_rows_raw.get("value", [])
        if not isinstance(soi_rows, list):
            soi_rows = []
    elif isinstance(soi_rows_raw, list):
        soi_rows = soi_rows_raw
    else:
        soi_rows = []
    
    # Sanitize rows to fix misclassified holdings before counting
    if soi_rows:
        soi_rows, _ = normalize_soi_rows(soi_rows)
    
    row_types = Counter()
    for row in soi_rows:
        rt_obj = row.get("row_type")
        if isinstance(rt_obj, dict):
            rt = rt_obj.get("value", "UNKNOWN")
        else:
            rt = rt_obj if rt_obj else "UNKNOWN"
        row_types[rt] += 1
    
    usage = data.get("usage", {}) or data.get("result", {}).get("usage", {})
    
    # Get as_of_date
    as_of_date_obj = extraction_result.get("as_of_date")
    as_of_date = None
    if isinstance(as_of_date_obj, dict):
        as_of_date = as_of_date_obj.get("value")
    elif as_of_date_obj:
        as_of_date = str(as_of_date_obj)
    
    return {
        "total_rows": len(soi_rows),
        "holdings": row_types.get("HOLDING", 0),
        "subtotals": row_types.get("SUBTOTAL", 0),
        "totals": row_types.get("TOTAL", 0),
        "num_pages": usage.get("num_pages"),
        "as_of_date": as_of_date,
    }


def main():
    extract_urls_dir = Path("extract_urls")
    
    # Output directories
    extraction_results_dir = Path("actual_extractions")
    split_results_archive_dir = Path("split_results_archive")
    
    extraction_results_dir.mkdir(exist_ok=True)
    split_results_archive_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("SEPARATING EXTRACTION RESULTS FROM SPLIT RESULTS")
    print("=" * 70)
    print()
    
    # Find all JSON files
    all_files = list(extract_urls_dir.glob("*_extract_response.json"))
    print(f"Found {len(all_files)} files in {extract_urls_dir}/")
    print()
    
    # Categorize files
    extraction_files = []          # Has actual soi_rows with data
    empty_extraction_files = []    # Has soi_rows structure but empty/null
    split_files = []
    error_files = []
    unknown_files = []
    
    for filepath in all_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if is_split_result(data):
                split_files.append(filepath)
            elif is_actual_extraction(data):
                stats = get_extraction_stats(data)
                # Check if it has any actual rows
                if stats["total_rows"] > 0:
                    extraction_files.append((filepath, stats))
                else:
                    empty_extraction_files.append(filepath)
            else:
                unknown_files.append(filepath)
                
        except json.JSONDecodeError as e:
            error_files.append((filepath, f"JSON error: {e}"))
        except Exception as e:
            error_files.append((filepath, str(e)))
    
    print("=" * 70)
    print("CATEGORIZATION RESULTS")
    print("=" * 70)
    print(f"  Actual extraction results (with data): {len(extraction_files)}")
    print(f"  Empty extractions (no rows):           {len(empty_extraction_files)}")
    print(f"  Split/classification results:          {len(split_files)}")
    print(f"  Unknown structure:                     {len(unknown_files)}")
    print(f"  Errors reading:                        {len(error_files)}")
    print()
    
    # Show extraction statistics summary
    if extraction_files:
        total_holdings = sum(stats["holdings"] for _, stats in extraction_files)
        total_subtotals = sum(stats["subtotals"] for _, stats in extraction_files)
        total_totals = sum(stats["totals"] for _, stats in extraction_files)
        total_rows = sum(stats["total_rows"] for _, stats in extraction_files)
        
        print("=" * 70)
        print("EXTRACTION DATA SUMMARY")
        print("=" * 70)
        print(f"  Total files with real extraction data: {len(extraction_files)}")
        print(f"  Total rows extracted: {total_rows:,}")
        print(f"    - Holdings: {total_holdings:,}")
        print(f"    - Subtotals: {total_subtotals:,}")
        print(f"    - Totals: {total_totals:,}")
        print()
    
    # Copy extraction results to dedicated folder
    print("=" * 70)
    print(f"COPYING EXTRACTION RESULTS TO: {extraction_results_dir}/")
    print("=" * 70)
    
    copied_count = 0
    for filepath, stats in extraction_files:
        dest = extraction_results_dir / filepath.name
        if not dest.exists():
            shutil.copy2(filepath, dest)
            copied_count += 1
    
    print(f"  Copied {copied_count} new files (skipped {len(extraction_files) - copied_count} existing)")
    print()
    
    # Archive split results (optional - just log for now)
    print("=" * 70)
    print(f"SPLIT RESULTS (can be archived to: {split_results_archive_dir}/)")
    print("=" * 70)
    print(f"  Found {len(split_files)} split result files")
    
    # Show sample split files
    if split_files[:5]:
        print("  Sample files:")
        for f in split_files[:5]:
            print(f"    - {f.name}")
        if len(split_files) > 5:
            print(f"    ... and {len(split_files) - 5} more")
    print()
    
    # Prompt to archive
    print("To archive split results, run:")
    print(f'  Move-Item -Path "extract_urls\\*-*-*-*-*_extract_response.json" -Destination "split_results_archive\\"')
    print("  (This moves UUID-named files which are typically split results)")
    print()
    
    # Write summary report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_files_scanned": len(all_files),
        "extraction_results_with_data": len(extraction_files),
        "empty_extraction_results": len(empty_extraction_files),
        "split_results": len(split_files),
        "unknown_files": len(unknown_files),
        "error_files": len(error_files),
        "extraction_stats": {
            "total_rows": sum(s["total_rows"] for _, s in extraction_files),
            "total_holdings": sum(s["holdings"] for _, s in extraction_files),
            "total_subtotals": sum(s["subtotals"] for _, s in extraction_files),
            "total_totals": sum(s["totals"] for _, s in extraction_files),
        },
        "extraction_files": [
            {"filename": f.name, **stats}
            for f, stats in extraction_files
        ],
        "empty_extraction_files": [f.name for f in empty_extraction_files],
        "split_files": [f.name for f in split_files],
        "unknown_files": [f.name for f in unknown_files],
        "error_files": [{"filename": f.name, "error": e} for f, e in error_files],
    }
    
    report_path = Path("separation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    
    print("=" * 70)
    print("REPORTS SAVED")
    print("=" * 70)
    print(f"  {report_path} - Full categorization report")
    print(f"  {extraction_results_dir}/ - Actual extraction results")
    print()
    print("Next steps:")
    print("  1. Run: python validate_existing.py")
    print("     (to validate the extraction results)")
    print("  2. Or run with the new folder:")
    print("     (modify validate_existing.py to use 'actual_extractions' folder)")
    print()


if __name__ == "__main__":
    main()

