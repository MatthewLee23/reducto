"""
Spot-Check Tool: Compare extractions to original source data

This tool helps you manually verify extraction accuracy by:
1. Showing extracted data in a readable format
2. Opening the source PDF on SEC EDGAR
3. Letting you mark accuracy

Run: python spot_check.py [file_stem]
Example: python spot_check.py e9af592f-a06a-4bae-8ce2-ebc2bf918ad6
"""

import json
import sys
import webbrowser
from pathlib import Path


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


def get_soi_rows(data):
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
    if isinstance(row, dict):
        if "value" in row and isinstance(row["value"], dict):
            return row["value"]
        return row
    return {}


def display_extraction(stem):
    """Display extraction data for a file."""
    extract_dir = Path("extract_urls")
    filepath = extract_dir / f"{stem}_extract_response.json"
    
    if not filepath.exists():
        # Try without _extract_response suffix
        filepath = extract_dir / f"{stem}.json"
    
    if not filepath.exists():
        print(f"ERROR: Cannot find {filepath}")
        return None
    
    data = load_json(filepath)
    if not data:
        print(f"ERROR: Cannot parse {filepath}")
        return None
    
    result = data.get("result", {})
    if isinstance(result, dict):
        inner = result.get("result", result)
    else:
        inner = {}
    
    print("=" * 80)
    print(f"EXTRACTION: {stem}")
    print("=" * 80)
    print()
    
    # Header info
    print("DOCUMENT METADATA:")
    print(f"  Title: {inner.get('soi_title', {}).get('value', 'N/A') if isinstance(inner.get('soi_title'), dict) else inner.get('soi_title', 'N/A')}")
    print(f"  As-of Date: {inner.get('as_of_date', {}).get('value', 'N/A') if isinstance(inner.get('as_of_date'), dict) else inner.get('as_of_date', 'N/A')}")
    print(f"  Reporting Basis: {inner.get('reporting_basis', {}).get('value', 'N/A') if isinstance(inner.get('reporting_basis'), dict) else inner.get('reporting_basis', 'N/A')}")
    print()
    
    soi_rows = get_soi_rows(data)
    
    if not soi_rows:
        print("NO SOI_ROWS FOUND")
        return data
    
    # Count by type
    holdings = []
    subtotals = []
    totals = []
    
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
    
    print(f"EXTRACTED ROWS: {len(soi_rows)} total")
    print(f"  Holdings: {len(holdings)}")
    print(f"  Subtotals: {len(subtotals)}")
    print(f"  Totals: {len(totals)}")
    print()
    
    # Show first 10 holdings
    print("-" * 80)
    print("FIRST 10 HOLDINGS (for verification):")
    print("-" * 80)
    
    for i, h in enumerate(holdings[:10], 1):
        inv = h.get("investment", h.get("label", "N/A"))
        if isinstance(inv, dict):
            inv = inv.get("value", str(inv))
        inv = str(inv)[:60]
        
        fv = h.get("fair_value_raw", "N/A")
        qty = h.get("quantity_raw", "N/A")
        section = h.get("section_path", [])
        if isinstance(section, list):
            section = " > ".join(str(s.get("value", s) if isinstance(s, dict) else s) for s in section[:2])
        
        print(f"\n{i}. {inv}")
        print(f"   Fair Value: {fv}")
        print(f"   Quantity: {qty}")
        print(f"   Section: {section}")
    
    if len(holdings) > 10:
        print(f"\n... and {len(holdings) - 10} more holdings")
    
    # Show totals
    if totals:
        print()
        print("-" * 80)
        print("TOTAL ROWS:")
        print("-" * 80)
        for t in totals:
            label = t.get("label", "N/A")
            if isinstance(label, dict):
                label = label.get("value", str(label))
            fv = t.get("fair_value_raw", "N/A")
            print(f"  {label}: {fv}")
    
    print()
    return data


def open_sec_edgar(accession_number):
    """Open the SEC EDGAR page for this filing."""
    # Clean accession number
    acc = accession_number.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{acc[:10]}/{accession_number}/{accession_number}.txt"
    
    # Alternative: search by accession number
    search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&filenum=&State=&SIC=&dateb=&owner=include&count=40&search_text={accession_number}"
    
    print(f"Opening SEC EDGAR search for: {accession_number}")
    print(f"URL: {search_url}")
    webbrowser.open(search_url)


def main():
    if len(sys.argv) < 2:
        # List available files
        print("SPOT-CHECK TOOL")
        print("=" * 80)
        print()
        print("Usage: python spot_check.py <file_stem>")
        print()
        print("Examples:")
        print("  python spot_check.py e9af592f-a06a-4bae-8ce2-ebc2bf918ad6")
        print("  python spot_check.py 0000002230-03-000010")
        print()
        
        # Load quality report to suggest files
        quality_file = Path("quality_reports/quality_summary.json")
        if quality_file.exists():
            with open(quality_file) as f:
                q = json.load(f)
            print("SUGGESTED FILES TO CHECK:")
            print()
            print("Best quality (should be accurate):")
            for f in q.get("best_files", [])[:5]:
                print(f"  python spot_check.py {f}")
            print()
            print("Worst quality (investigate issues):")
            for f in q.get("worst_files", [])[:5]:
                print(f"  python spot_check.py {f}")
        return
    
    stem = sys.argv[1]
    
    # Display extraction
    data = display_extraction(stem)
    if not data:
        return
    
    # Check if this looks like an SEC accession number
    if stem.count("-") == 2 and len(stem) == 20:
        print("-" * 80)
        print("SOURCE DOCUMENT")
        print("-" * 80)
        print()
        print(f"This appears to be SEC filing: {stem}")
        print()
        
        response = input("Open SEC EDGAR to view original? (y/n): ").strip().lower()
        if response == "y":
            open_sec_edgar(stem)
    else:
        print("-" * 80)
        print("NOTE: This file has a UUID name, not an SEC accession number.")
        print("The original PDF may have been uploaded directly to Reducto.")
        print("-" * 80)


if __name__ == "__main__":
    main()

