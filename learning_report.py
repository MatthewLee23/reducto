"""
Comprehensive analysis of extraction results to learn what worked and what didn't.
This script will help identify patterns and improvements for future runs.

Run: python learning_report.py
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


def get_soi_rows(data: dict):
    """Extract soi_rows from various response structures."""
    if not data:
        return None
    
    result = data.get("result", {})
    
    # Direct structure
    if isinstance(result, dict):
        if "soi_rows" in result:
            return result.get("soi_rows")
        if "result" in result and isinstance(result["result"], dict):
            return result["result"].get("soi_rows")
    
    return None


def analyze_extractions():
    extract_dir = Path("extract_urls")
    output_dir = Path("analysis_reports")
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("LEARNING FROM YOUR $930 INVESTMENT")
    print("=" * 70)
    print()
    
    files = list(extract_dir.glob("*.json"))
    
    # Categorize files
    with_data = []
    empty_data = []
    split_jobs = []
    
    # Error pattern analysis
    all_errors = []
    files_by_error = defaultdict(list)
    
    # Row quality analysis
    row_issues = Counter()
    field_missing = Counter()
    
    for f in files:
        data = load_json(f)
        if not data:
            continue
        
        stem = f.stem.replace("_extract_response", "")
        result = data.get("result", {})
        
        # Check for split job
        if isinstance(result, dict):
            if "splits" in result:
                split_jobs.append(stem)
                continue
            inner = result.get("result", {})
            if isinstance(inner, dict) and "splits" in inner:
                split_jobs.append(stem)
                continue
        
        soi_rows = get_soi_rows(data)
        
        if soi_rows and len(soi_rows) > 0:
            with_data.append({
                "stem": stem,
                "row_count": len(soi_rows),
                "rows": soi_rows
            })
        else:
            empty_data.append({
                "stem": stem,
                "data": data
            })
    
    print(f"Files analyzed: {len(files)}")
    print(f"  Extract jobs with data: {len(with_data)}")
    print(f"  Extract jobs with no data: {len(empty_data)}")
    print(f"  Split jobs: {len(split_jobs)}")
    print()
    
    # =========== ANALYZE SUCCESSFUL EXTRACTIONS ===========
    print("=" * 70)
    print("WHAT'S WORKING (Files with data)")
    print("=" * 70)
    print()
    
    if with_data:
        total_rows = sum(d["row_count"] for d in with_data)
        avg_rows = total_rows / len(with_data)
        
        print(f"Total rows extracted: {total_rows:,}")
        print(f"Average rows per file: {avg_rows:.1f}")
        print()
        
        # Field completeness analysis
        field_present = Counter()
        field_missing = Counter()
        field_with_citations = Counter()
        
        expected_fields = [
            "investment_name", "fair_value", "cost", "shares_principal",
            "industry", "asset_category", "geography", "interest_rate",
            "maturity_date", "investment_description", "percent_of_net_assets"
        ]
        
        for item in with_data:
            for row in item["rows"]:
                for field in expected_fields:
                    if field in row:
                        val = row[field]
                        if val is not None and val != "":
                            field_present[field] += 1
                            # Check if it has citations
                            citation_field = f"{field}_citations"
                            if citation_field in row and row[citation_field]:
                                field_with_citations[field] += 1
                        else:
                            field_missing[field] += 1
                    else:
                        field_missing[field] += 1
        
        print("Field Extraction Quality:")
        print("-" * 70)
        print(f"{'Field':<30} {'Present':>10} {'Missing':>10} {'% Complete':>12}")
        print("-" * 70)
        
        for field in expected_fields:
            present = field_present.get(field, 0)
            missing = field_missing.get(field, 0)
            total = present + missing
            pct = (present / total * 100) if total > 0 else 0
            print(f"{field:<30} {present:>10,} {missing:>10,} {pct:>11.1f}%")
        print()
        
        # Citation analysis
        print("\nCitation Coverage:")
        print("-" * 70)
        for field in expected_fields:
            present = field_present.get(field, 0)
            with_cit = field_with_citations.get(field, 0)
            if present > 0:
                pct = with_cit / present * 100
                print(f"  {field}: {with_cit:,}/{present:,} have citations ({pct:.1f}%)")
    
    # =========== ANALYZE VALIDATION RESULTS ===========
    print()
    print("=" * 70)
    print("VALIDATION ERROR PATTERNS")
    print("=" * 70)
    print()
    
    val_dir = Path("validation_results")
    if val_dir.exists():
        summary = load_json(val_dir / "summary.json")
        if summary:
            error_codes = summary.get("error_codes", {})
            
            # Categorize errors
            structural_errors = {}
            data_quality_errors = {}
            citation_errors = {}
            arithmetic_errors = {}
            
            for code, count in error_codes.items():
                if "MISSING_TOP" in code or "MISSING_SOI" in code or "INVALID" in code:
                    structural_errors[code] = count
                elif "CITATION" in code or "BBOX" in code:
                    citation_errors[code] = count
                elif "ARITH" in code or "MISMATCH" in code or "TOTAL" in code:
                    arithmetic_errors[code] = count
                else:
                    data_quality_errors[code] = count
            
            if structural_errors:
                print("STRUCTURAL ERRORS (Response format issues):")
                for code, count in sorted(structural_errors.items(), key=lambda x: -x[1]):
                    print(f"  {code}: {count}")
                print()
            
            if citation_errors:
                print("CITATION ERRORS (Source reference issues):")
                for code, count in sorted(citation_errors.items(), key=lambda x: -x[1]):
                    print(f"  {code}: {count}")
                print()
            
            if arithmetic_errors:
                print("ARITHMETIC ERRORS (Number verification issues):")
                for code, count in sorted(arithmetic_errors.items(), key=lambda x: -x[1]):
                    print(f"  {code}: {count}")
                print()
            
            if data_quality_errors:
                print("DATA QUALITY ERRORS:")
                for code, count in sorted(data_quality_errors.items(), key=lambda x: -x[1]):
                    print(f"  {code}: {count}")
                print()
    
    # =========== KEY INSIGHTS ===========
    print()
    print("=" * 70)
    print("KEY INSIGHTS & RECOMMENDATIONS")
    print("=" * 70)
    print()
    
    insights = []
    
    # Insight 1: Empty extractions
    if len(empty_data) > len(with_data):
        insights.append({
            "issue": "Most extract jobs returned no data",
            "count": len(empty_data),
            "cause": "The extraction config may not match the document structure",
            "recommendation": "Review the extraction schema - make fields optional, use simpler prompts"
        })
    
    # Insight 2: Citation mismatches
    if "CITATION_VALUE_MISMATCH" in error_codes:
        insights.append({
            "issue": "Citation values don't match extracted data",
            "count": error_codes["CITATION_VALUE_MISMATCH"],
            "cause": "OCR/parsing differences or incorrect bounding boxes",
            "recommendation": "Use fuzzy matching for citation verification, or simplify citation requirements"
        })
    
    # Insight 3: Arithmetic issues
    arith_count = sum(1 for c in error_codes if "ARITH" in c or "MISMATCH" in c)
    if arith_count > 0:
        insights.append({
            "issue": "Arithmetic totals don't match row sums",
            "count": arith_count,
            "cause": "Rounding errors, missing rows, or different number parsing",
            "recommendation": "Accept tolerance (e.g., ±1%) for financial totals"
        })
    
    # Insight 4: Missing subtotals
    if "MISSING_SUBTOTAL" in error_codes:
        insights.append({
            "issue": "Subtotal rows not properly identified",
            "count": error_codes["MISSING_SUBTOTAL"],
            "cause": "Schema doesn't specify how to identify subtotal rows",
            "recommendation": "Add is_subtotal or is_total field to extraction schema"
        })
    
    for i, insight in enumerate(insights, 1):
        print(f"{i}. {insight['issue']}")
        print(f"   Affected: {insight['count']}")
        print(f"   Likely cause: {insight['cause']}")
        print(f"   FIX: {insight['recommendation']}")
        print()
    
    # =========== RECOMMENDED CONFIG CHANGES ===========
    print()
    print("=" * 70)
    print("RECOMMENDED EXTRACTION CONFIG CHANGES")
    print("=" * 70)
    print()
    
    print("""
Based on your results, here are concrete changes to make:

1. MAKE FIELDS OPTIONAL
   Many documents may not have all fields. Instead of required fields,
   make them optional with nullable types.

2. ADD ROW TYPE CLASSIFICATION
   Add a field like:
   "row_type": "holding | subtotal | total | header | other"
   This helps identify which rows are actual investments vs summaries.

3. SIMPLIFY CITATION REQUIREMENTS  
   If you don't need exact bounding boxes, disable citations or use
   page-level citations instead of bbox-level.

4. USE DESCRIPTION-BASED EXTRACTION
   Instead of strict field names, give the model examples:
   "Extract all rows from the Schedule of Investments table"

5. HANDLE MULTI-PAGE TABLES
   Ensure your split config correctly identifies all SOI pages.
   Review split results to verify the right pages are being extracted.

6. ADD TOLERANCE FOR NUMBERS
   Accept that financial documents have rounding differences.
   Use percentage tolerance (e.g., 0.1%) for verification.
""")
    
    # =========== SAMPLE COMPARISON ===========
    print()
    print("=" * 70)
    print("SAMPLE DATA: SUCCESS vs FAILURE")
    print("=" * 70)
    print()
    
    if with_data:
        best = max(with_data, key=lambda x: x["row_count"])
        print(f"BEST EXTRACTION: {best['stem']}")
        print(f"  Rows extracted: {best['row_count']}")
        print(f"  Sample row fields: {list(best['rows'][0].keys())[:10]}...")
        print()
    
    if empty_data:
        sample_empty = empty_data[0]
        print(f"FAILED EXTRACTION: {sample_empty['stem']}")
        print(f"  Response structure: {list(sample_empty['data'].keys())}")
        result = sample_empty['data'].get('result', {})
        if isinstance(result, dict):
            print(f"  Result keys: {list(result.keys())[:10]}")
        print()
    
    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "files_analyzed": len(files),
        "with_data": len(with_data),
        "empty_data": len(empty_data),
        "split_jobs": len(split_jobs),
        "total_rows": sum(d["row_count"] for d in with_data) if with_data else 0,
        "insights": insights,
        "success_rate": len(with_data) / (len(with_data) + len(empty_data)) * 100 if (with_data or empty_data) else 0
    }
    
    with open(output_dir / "learning_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print()
    print(f"Report saved to: {output_dir / 'learning_report.json'}")
    print()
    print(f"SUCCESS RATE: {report['success_rate']:.1f}% of extract jobs returned data")


if __name__ == "__main__":
    analyze_extractions()

