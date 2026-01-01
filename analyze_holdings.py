"""
Analyze the actual extracted holdings data from your $930 investment.
This script correctly parses the actual data structure returned by Reducto.

Run: python analyze_holdings.py
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
    """Parse a number from various formats."""
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


def extract_soi_rows(data: dict):
    """Extract soi_rows from the response structure."""
    if not data:
        return []
    
    result = data.get("result", {})
    
    # Handle nested structure
    if isinstance(result, dict):
        inner = result.get("result", result)
        if isinstance(inner, dict):
            soi_rows = inner.get("soi_rows", [])
            if isinstance(soi_rows, list):
                return soi_rows
    
    return []


def get_row_value(row):
    """Get the value dict from a row (handles {value: {...}, citations: []} structure)."""
    if isinstance(row, dict):
        if "value" in row and isinstance(row["value"], dict):
            return row["value"]
        return row
    return {}


def main():
    extract_dir = Path("extract_urls")
    output_dir = Path("analysis_reports")
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("ANALYZING YOUR EXTRACTED INVESTMENT DATA")
    print("=" * 70)
    print()
    
    files = list(extract_dir.glob("*.json"))
    
    # Collect all holdings
    all_holdings = []
    all_subtotals = []
    files_with_data = []
    files_without_data = []
    split_jobs = []
    
    field_usage = Counter()
    row_type_counts = Counter()
    section_paths = Counter()
    
    for f in files:
        data = load_json(f)
        if not data:
            continue
        
        stem = f.stem.replace("_extract_response", "")
        
        # Check for split job
        result = data.get("result", {})
        if isinstance(result, dict):
            inner = result.get("result", result)
            if isinstance(inner, dict) and "splits" in inner:
                split_jobs.append(stem)
                continue
        
        soi_rows = extract_soi_rows(data)
        
        if not soi_rows:
            files_without_data.append(stem)
            continue
        
        files_with_data.append(stem)
        
        for row in soi_rows:
            val = get_row_value(row)
            
            # Track field usage
            for k in val.keys():
                field_usage[k] += 1
            
            row_type = val.get("row_type", "UNKNOWN")
            if isinstance(row_type, dict):
                row_type = row_type.get("value", "UNKNOWN")
            row_type = str(row_type)
            row_type_counts[row_type] += 1
            
            # Track section paths
            section_path = val.get("section_path", [])
            if section_path and isinstance(section_path, list):
                # Handle nested dict structures
                path_strs = []
                for item in section_path[:2]:
                    if isinstance(item, dict):
                        path_strs.append(str(item.get("value", item)))
                    else:
                        path_strs.append(str(item))
                if path_strs:
                    section_paths[" > ".join(path_strs)] += 1
            
            def get_section_str(sp):
                """Convert section_path to string."""
                if not sp or not isinstance(sp, list):
                    return ""
                parts = []
                for item in sp:
                    if isinstance(item, dict):
                        parts.append(str(item.get("value", item)))
                    else:
                        parts.append(str(item))
                return " > ".join(parts)
            
            if row_type == "HOLDING":
                investment = val.get("investment", val.get("label", ""))
                if isinstance(investment, dict):
                    investment = investment.get("value", str(investment))
                
                holding = {
                    "file": stem,
                    "investment": str(investment)[:200] if investment else "",
                    "fair_value": parse_number(val.get("fair_value_raw")),
                    "quantity": parse_number(val.get("quantity_raw")),
                    "quantity_type": val.get("quantity_type", ""),
                    "interest_rate": val.get("interest_rate_raw", ""),
                    "maturity_date": val.get("maturity_date", ""),
                    "section_path": get_section_str(val.get("section_path")),
                    "row_text": str(val.get("row_text", ""))[:100],
                }
                all_holdings.append(holding)
            elif row_type == "SUBTOTAL":
                label = val.get("label", "")
                if isinstance(label, dict):
                    label = label.get("value", str(label))
                
                subtotal = {
                    "file": stem,
                    "label": str(label),
                    "section_path": get_section_str(val.get("section_path")),
                }
                all_subtotals.append(subtotal)
    
    print(f"Files analyzed: {len(files)}")
    print(f"  Extract jobs with holdings: {len(files_with_data)}")
    print(f"  Extract jobs with no data: {len(files_without_data)}")
    print(f"  Split jobs (no holdings): {len(split_jobs)}")
    print()
    
    # =========== HOLDINGS SUMMARY ===========
    print("=" * 70)
    print("HOLDINGS DATA SUMMARY")
    print("=" * 70)
    print()
    
    print(f"Total HOLDING rows: {len(all_holdings):,}")
    print(f"Total SUBTOTAL rows: {len(all_subtotals):,}")
    print()
    
    print("Row Types Found:")
    for row_type, count in row_type_counts.most_common():
        print(f"  {row_type}: {count:,}")
    print()
    
    print("Fields Available in Holdings:")
    for field, count in field_usage.most_common(20):
        print(f"  {field}: {count:,}")
    print()
    
    # =========== VALUE ANALYSIS ===========
    print("=" * 70)
    print("VALUE ANALYSIS")
    print("=" * 70)
    print()
    
    holdings_with_fv = [h for h in all_holdings if h["fair_value"] is not None]
    if holdings_with_fv:
        fair_values = [h["fair_value"] for h in holdings_with_fv]
        total_fv = sum(fair_values)
        avg_fv = total_fv / len(fair_values)
        
        print(f"Holdings with fair value: {len(holdings_with_fv):,}")
        print(f"Total fair value: ${total_fv:,.0f}")
        print(f"Average fair value: ${avg_fv:,.0f}")
        print(f"Min fair value: ${min(fair_values):,.0f}")
        print(f"Max fair value: ${max(fair_values):,.0f}")
    else:
        print("No holdings with parseable fair values found.")
    print()
    
    # =========== SECTION/CATEGORY ANALYSIS ===========
    print("=" * 70)
    print("TOP INVESTMENT CATEGORIES (from section_path)")
    print("=" * 70)
    print()
    
    for section, count in section_paths.most_common(20):
        print(f"  {section}: {count:,} holdings")
    print()
    
    # =========== DATA QUALITY ===========
    print("=" * 70)
    print("DATA QUALITY METRICS")
    print("=" * 70)
    print()
    
    quality = {
        "total_holdings": len(all_holdings),
        "with_fair_value": len([h for h in all_holdings if h["fair_value"]]),
        "with_quantity": len([h for h in all_holdings if h["quantity"]]),
        "with_interest_rate": len([h for h in all_holdings if h["interest_rate"]]),
        "with_maturity_date": len([h for h in all_holdings if h["maturity_date"]]),
        "with_section_path": len([h for h in all_holdings if h["section_path"]]),
    }
    
    print(f"{'Field':<25} {'Count':>10} {'Coverage':>12}")
    print("-" * 50)
    for field, count in quality.items():
        if field == "total_holdings":
            continue
        pct = count / quality["total_holdings"] * 100 if quality["total_holdings"] > 0 else 0
        print(f"{field:<25} {count:>10,} {pct:>11.1f}%")
    print()
    
    # =========== EXPORT TO CSV ===========
    print("=" * 70)
    print("EXPORTING DATA")
    print("=" * 70)
    print()
    
    # Export all holdings to CSV
    csv_path = output_dir / "all_holdings.csv"
    if all_holdings:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_holdings[0].keys())
            writer.writeheader()
            writer.writerows(all_holdings)
        print(f"Exported {len(all_holdings):,} holdings to: {csv_path}")
    
    # Export summary JSON
    summary = {
        "timestamp": datetime.now().isoformat(),
        "files_analyzed": len(files),
        "files_with_data": len(files_with_data),
        "files_without_data": len(files_without_data),
        "split_jobs": len(split_jobs),
        "total_holdings": len(all_holdings),
        "total_subtotals": len(all_subtotals),
        "total_fair_value": sum(h["fair_value"] for h in all_holdings if h["fair_value"]) if all_holdings else 0,
        "row_types": dict(row_type_counts),
        "top_sections": dict(section_paths.most_common(30)),
        "field_usage": dict(field_usage),
        "quality": quality,
        "success_rate": len(files_with_data) / (len(files_with_data) + len(files_without_data)) * 100 if (files_with_data or files_without_data) else 0
    }
    
    summary_path = output_dir / "holdings_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Exported summary to: {summary_path}")
    print()
    
    # =========== SAMPLE DATA ===========
    print("=" * 70)
    print("SAMPLE HOLDINGS (first 5)")
    print("=" * 70)
    print()
    
    for h in all_holdings[:5]:
        print(f"Investment: {h['investment'][:60]}...")
        print(f"  Fair Value: ${h['fair_value']:,.0f}" if h['fair_value'] else "  Fair Value: N/A")
        print(f"  Section: {h['section_path']}")
        print(f"  File: {h['file']}")
        print()
    
    # =========== KEY TAKEAWAYS ===========
    print("=" * 70)
    print("KEY TAKEAWAYS")
    print("=" * 70)
    print()
    
    total_fv = sum(h['fair_value'] for h in all_holdings if h['fair_value'])
    pct_fv = quality['with_fair_value']/quality['total_holdings']*100 if quality['total_holdings'] else 0
    pct_qty = quality['with_quantity']/quality['total_holdings']*100 if quality['total_holdings'] else 0
    pct_sec = quality['with_section_path']/quality['total_holdings']*100 if quality['total_holdings'] else 0
    
    print(f"""
YOUR $930 INVESTMENT RESULTS:
=============================

[+] SUCCESSFULLY EXTRACTED:
  - {len(all_holdings):,} individual investment holdings
  - {len(all_subtotals):,} subtotal/category rows
  - ${total_fv:,.0f} in total fair value tracked
  - From {len(files_with_data)} documents

[+] DATA QUALITY:
  - {pct_fv:.0f}% have fair value
  - {pct_qty:.0f}% have quantity
  - {pct_sec:.0f}% have section categorization

[!] ISSUES TO ADDRESS:
  - {len(files_without_data)} extract jobs returned no holdings
    (Could be documents without SOI tables, or extraction config issues)

[+] ALL DATA EXPORTED TO:
  - {csv_path} (full holdings list)
  - {summary_path} (summary metrics)
""")


if __name__ == "__main__":
    main()

