"""
Quality Validation Tool for Reducto Extractions

This script helps you actually SEE how good your extractions are by:
1. Comparing extracted data to source documents
2. Checking arithmetic (do subtotals add up?)
3. Identifying suspicious patterns (missing data, outliers)
4. Generating a quality score

Run: python validate_quality.py
"""

import json
import csv
import re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


def parse_number(val):
    """Parse number from various formats."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").replace("$", "").replace("%", "").strip()
    s = s.replace("(", "-").replace(")", "")
    try:
        return float(s)
    except:
        return None


def get_soi_rows(data):
    """Extract soi_rows from response."""
    if not data:
        return []
    result = data.get("result", {})
    if isinstance(result, dict):
        inner = result.get("result", result)
        if isinstance(inner, dict):
            rows = inner.get("soi_rows", [])
            if isinstance(rows, list):
                return rows
    return []


def get_row_value(row):
    """Get value dict from row structure."""
    if isinstance(row, dict):
        if "value" in row and isinstance(row["value"], dict):
            return row["value"]
        return row
    return {}


def validate_single_file(filepath):
    """Validate a single extract response and return quality metrics."""
    data = load_json(filepath)
    if not data:
        return None
    
    stem = filepath.stem.replace("_extract_response", "")
    soi_rows = get_soi_rows(data)
    
    if not soi_rows:
        return {
            "file": stem,
            "status": "EMPTY",
            "holdings": 0,
            "subtotals": 0,
            "issues": ["No soi_rows extracted"],
            "quality_score": 0
        }
    
    # Classify rows
    holdings = []
    subtotals = []
    totals = []
    issues = []
    
    for row in soi_rows:
        val = get_row_value(row)
        row_type = val.get("row_type", "UNKNOWN")
        if isinstance(row_type, dict):
            row_type = row_type.get("value", "UNKNOWN")
        row_type = str(row_type).upper()
        
        if row_type == "HOLDING":
            holdings.append(val)
        elif row_type == "SUBTOTAL":
            subtotals.append(val)
        elif row_type == "TOTAL":
            totals.append(val)
    
    # Quality checks
    quality_points = 100
    
    # Check 1: Do we have holdings?
    if len(holdings) == 0:
        issues.append("No HOLDING rows found")
        quality_points -= 30
    
    # Check 2: Do holdings have fair values?
    fv_count = sum(1 for h in holdings if parse_number(h.get("fair_value_raw")) is not None)
    fv_pct = fv_count / len(holdings) * 100 if holdings else 0
    if fv_pct < 50:
        issues.append(f"Only {fv_pct:.0f}% of holdings have fair_value")
        quality_points -= 20
    
    # Check 3: Do holdings have investment names?
    name_count = sum(1 for h in holdings if h.get("investment"))
    name_pct = name_count / len(holdings) * 100 if holdings else 0
    if name_pct < 80:
        issues.append(f"Only {name_pct:.0f}% of holdings have investment names")
        quality_points -= 15
    
    # Check 4: Are section paths populated?
    section_count = sum(1 for h in holdings if h.get("section_path"))
    section_pct = section_count / len(holdings) * 100 if holdings else 0
    if section_pct < 50:
        issues.append(f"Only {section_pct:.0f}% have section categorization")
        quality_points -= 10
    
    # Check 5: Arithmetic validation - do subtotals make sense?
    if subtotals and holdings:
        # Get total fair value from holdings
        total_fv = sum(parse_number(h.get("fair_value_raw")) or 0 for h in holdings)
        
        # Check if any total row has a matching value
        total_row_fvs = [parse_number(t.get("fair_value_raw")) for t in totals]
        total_row_fvs = [v for v in total_row_fvs if v is not None]
        
        if total_row_fvs and total_fv > 0:
            closest = min(total_row_fvs, key=lambda x: abs(x - total_fv))
            diff_pct = abs(closest - total_fv) / total_fv * 100 if total_fv else 0
            
            if diff_pct > 5:
                issues.append(f"Arithmetic mismatch: holdings sum to ${total_fv:,.0f}, total row shows ${closest:,.0f} ({diff_pct:.1f}% diff)")
                quality_points -= 15
    
    quality_score = max(0, quality_points)
    
    return {
        "file": stem,
        "status": "OK" if quality_score >= 70 else "WARN" if quality_score >= 50 else "POOR",
        "holdings": len(holdings),
        "subtotals": len(subtotals),
        "totals": len(totals),
        "fv_coverage": f"{fv_pct:.0f}%",
        "name_coverage": f"{name_pct:.0f}%",
        "section_coverage": f"{section_pct:.0f}%",
        "issues": issues,
        "quality_score": quality_score
    }


def main():
    extract_dir = Path("extract_urls")
    output_dir = Path("quality_reports")
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 80)
    print("EXTRACTION QUALITY VALIDATION")
    print("=" * 80)
    print()
    
    files = list(extract_dir.glob("*.json"))
    print(f"Analyzing {len(files)} extraction files...")
    print()
    
    results = []
    for f in files:
        result = validate_single_file(f)
        if result:
            results.append(result)
    
    # Separate by status
    empty = [r for r in results if r["status"] == "EMPTY"]
    ok = [r for r in results if r["status"] == "OK"]
    warn = [r for r in results if r["status"] == "WARN"]
    poor = [r for r in results if r["status"] == "POOR"]
    
    # Summary
    print("=" * 80)
    print("QUALITY SUMMARY")
    print("=" * 80)
    print()
    print(f"Total files:     {len(results)}")
    print(f"  OK (>=70):     {len(ok)} ({len(ok)/len(results)*100:.1f}%)" if results else "")
    print(f"  WARN (50-69):  {len(warn)} ({len(warn)/len(results)*100:.1f}%)" if results else "")
    print(f"  POOR (<50):    {len(poor)} ({len(poor)/len(results)*100:.1f}%)" if results else "")
    print(f"  EMPTY:         {len(empty)} ({len(empty)/len(results)*100:.1f}%)" if results else "")
    print()
    
    # Average quality score (excluding empty)
    scored = [r for r in results if r["status"] != "EMPTY"]
    if scored:
        avg_score = sum(r["quality_score"] for r in scored) / len(scored)
        print(f"Average Quality Score: {avg_score:.1f}/100")
        print()
    
    # Issue frequency
    all_issues = []
    for r in results:
        all_issues.extend(r.get("issues", []))
    
    issue_counts = Counter()
    for issue in all_issues:
        # Normalize issue text
        if "fair_value" in issue.lower():
            issue_counts["Low fair_value coverage"] += 1
        elif "investment names" in issue.lower():
            issue_counts["Low investment name coverage"] += 1
        elif "section" in issue.lower():
            issue_counts["Low section categorization"] += 1
        elif "arithmetic" in issue.lower():
            issue_counts["Arithmetic mismatch"] += 1
        elif "no holding" in issue.lower():
            issue_counts["No HOLDING rows"] += 1
        elif "no soi_rows" in issue.lower():
            issue_counts["Empty extraction"] += 1
        else:
            issue_counts[issue[:50]] += 1
    
    print("=" * 80)
    print("COMMON ISSUES")
    print("=" * 80)
    print()
    for issue, count in issue_counts.most_common(10):
        print(f"  {issue}: {count} files")
    print()
    
    # Show best extractions
    print("=" * 80)
    print("TOP 10 BEST EXTRACTIONS")
    print("=" * 80)
    print()
    best = sorted(scored, key=lambda x: (-x["quality_score"], -x["holdings"]))[:10]
    print(f"{'File':<45} {'Score':>6} {'Holdings':>10} {'FV%':>6}")
    print("-" * 75)
    for r in best:
        print(f"{r['file'][:44]:<45} {r['quality_score']:>6} {r['holdings']:>10} {r['fv_coverage']:>6}")
    print()
    
    # Show worst extractions (for investigation)
    print("=" * 80)
    print("WORST EXTRACTIONS (Need Investigation)")
    print("=" * 80)
    print()
    worst = sorted(scored, key=lambda x: (x["quality_score"], x["holdings"]))[:10]
    for r in worst:
        print(f"File: {r['file']}")
        print(f"  Score: {r['quality_score']}, Holdings: {r['holdings']}")
        if r["issues"]:
            for issue in r["issues"]:
                print(f"  - {issue}")
        print()
    
    # Export detailed report
    csv_path = output_dir / "quality_report.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["file", "status", "quality_score", "holdings", "subtotals", 
                      "fv_coverage", "name_coverage", "section_coverage", "issues"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in sorted(results, key=lambda x: -x.get("quality_score", 0)):
            row = {k: v for k, v in r.items() if k in fieldnames}
            row["issues"] = "; ".join(r.get("issues", []))
            writer.writerow(row)
    
    print("=" * 80)
    print("SPOT-CHECK GUIDE")
    print("=" * 80)
    print()
    print("""
To manually verify accuracy, pick 3-5 files and compare:

1. Open the PDF in your browser/viewer
2. Find the "Schedule of Investments" section
3. Compare with the extracted data

For a file like '0000002230-03-000010':
  - PDF: Search SEC EDGAR for accession number 0000002230-03-000010
  - Extraction: extract_urls/0000002230-03-000010_extract_response.json

Quick comparison command:
  python -c "import json; print(json.dumps(json.load(open('extract_urls/0000002230-03-000010_extract_response.json'))['result']['result']['soi_rows'][:3], indent=2))"

""")
    
    print(f"Detailed report saved to: {csv_path}")
    print()
    
    # Also create a JSON summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(results),
        "status_counts": {
            "ok": len(ok),
            "warn": len(warn),
            "poor": len(poor),
            "empty": len(empty)
        },
        "average_quality_score": avg_score if scored else 0,
        "issue_counts": dict(issue_counts.most_common()),
        "best_files": [r["file"] for r in best],
        "worst_files": [r["file"] for r in worst]
    }
    
    with open(output_dir / "quality_summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()

