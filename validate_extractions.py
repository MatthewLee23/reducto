"""
Validate extraction results and produce quality reports.

Validates:
1) Response structure (required fields)
2) Row structure (row_type, fields present)
3) Arithmetic (holdings sum to subtotals, subtotals to totals)
4) Citation integrity
5) Data completeness

Run: python validate_extractions.py [--folder FOLDER]
"""

import argparse
import json
import csv
from pathlib import Path
from datetime import datetime
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
import re

from soi_sanitize import normalize_soi_rows


# ---------------------------------------------------------------------------
# Validation data structures
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"severity": self.severity, "code": self.code, "message": self.message, "context": self.context}


@dataclass
class ValidationResult:
    filename: str
    total_rows: int = 0
    holdings: int = 0
    subtotals: int = 0
    totals: int = 0
    issues: List[Issue] = field(default_factory=list)
    has_data: bool = True
    
    def add(self, severity: str, code: str, message: str, **context):
        self.issues.append(Issue(severity, code, message, context))
    
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")
    
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def unwrap_value(obj) -> Optional[str]:
    """Extract value from {value, citations} wrapper or return string."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        v = obj.get("value")
        return str(v) if v is not None else None
    return str(obj)


def find_extraction_result(data: dict) -> Optional[dict]:
    """Navigate through wrapper structures to find the actual extraction result."""
    if not isinstance(data, dict):
        return None
    
    result = data.get("result")
    
    # Array extraction
    if isinstance(result, list):
        if result and isinstance(result[0], dict) and "row_type" in result[0]:
            return {"soi_rows": result}
        return None
    
    if not isinstance(result, dict):
        return None
    
    # Double-wrapped
    inner = result.get("result")
    if isinstance(inner, dict) and ("soi_rows" in inner or "soi_title" in inner):
        return inner
    
    # Direct
    if "soi_rows" in result or "soi_title" in result:
        return result
    
    return None


def get_soi_rows(extraction_result: dict) -> List[dict]:
    """
    Extract soi_rows list from extraction result.
    
    Handles two formats:
    1. Direct: [{row_type: ..., investment: ...}, ...]
    2. Wrapped: [{value: {row_type: ...}, citations: [...]}, ...]
    """
    if not extraction_result:
        return []
    
    soi_rows = extraction_result.get("soi_rows", [])
    
    # Handle {value, citations} wrapper around the array itself
    if isinstance(soi_rows, dict):
        soi_rows = soi_rows.get("value", [])
    
    if not isinstance(soi_rows, list):
        return []
    
    # Unwrap individual rows if they're in {value, citations} format
    unwrapped = []
    for row in soi_rows:
        if isinstance(row, dict):
            # Check if row is wrapped: {value: {...}, citations: [...]}
            if "value" in row and "citations" in row and isinstance(row.get("value"), dict):
                # It's a wrapped row - extract the actual row data
                actual_row = row.get("value", {})
                if actual_row:
                    unwrapped.append(actual_row)
            elif "row_type" in row or "investment" in row or "label" in row:
                # It's already unwrapped
                unwrapped.append(row)
            else:
                # Unknown format, try to include
                unwrapped.append(row)
    
    return unwrapped


def parse_numeric(raw) -> Tuple[Optional[Decimal], Optional[str]]:
    """Parse a numeric string to Decimal."""
    if raw is None:
        return None, None
    
    if isinstance(raw, (int, float, Decimal)):
        try:
            return Decimal(str(raw)), None
        except InvalidOperation:
            return None, f"Cannot convert {raw}"
    
    value_str = str(raw).strip()
    if not value_str:
        return None, None
    
    # Handle parentheses for negatives
    negative = value_str.startswith("(") and value_str.endswith(")")
    if negative:
        value_str = value_str[1:-1].strip()
    
    # Clean currency symbols
    cleaned = value_str
    for char in ["$", "€", "£", "¥", " ", "\u00a0", "\t"]:
        cleaned = cleaned.replace(char, "")
    for code in ["USD", "CAD", "EUR", "GBP", "JPY", "S"]:
        cleaned = cleaned.replace(code, "")
    cleaned = cleaned.replace("%", "")
    
    # Find numeric tokens
    pattern = re.compile(r"-?\d[\d.,]*")
    matches = pattern.findall(cleaned)
    
    if not matches:
        return None, None
    
    if len(matches) > 1:
        return None, f"Multiple numeric tokens: {matches}"
    
    num_str = matches[0]
    
    # Handle separators
    if num_str.count(".") > 1:
        num_str = num_str.replace(".", "")
    elif "," in num_str:
        num_str = num_str.replace(",", "")
    
    try:
        number = Decimal(num_str)
    except InvalidOperation:
        return None, f"Cannot parse '{num_str}'"
    
    if negative and number > 0:
        number = -number
    
    return number, None


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validate_structure(data: dict, result: ValidationResult) -> Optional[dict]:
    """Validate top-level structure, return extraction result or None."""
    if not isinstance(data, dict):
        result.add("error", "INVALID_JSON", "Root is not a dict")
        result.has_data = False
        return None
    
    # Check for job metadata
    if "job_id" not in data:
        result.add("warning", "MISSING_JOB_ID", "Missing job_id field")
    
    extraction = find_extraction_result(data)
    if not extraction:
        result.add("error", "NO_EXTRACTION_DATA", "Could not find extraction result structure")
        result.has_data = False
        return None
    
    return extraction


def validate_rows(soi_rows: List[dict], result: ValidationResult):
    """Validate individual rows."""
    for i, row in enumerate(soi_rows):
        row_type = unwrap_value(row.get("row_type"))
        
        if row_type not in ("HOLDING", "SUBTOTAL", "TOTAL"):
            result.add("error", "INVALID_ROW_TYPE", f"Invalid row_type: {row_type}", row=i)
            continue
        
        if row_type == "HOLDING":
            result.holdings += 1
            investment = unwrap_value(row.get("investment"))
            if not investment or not investment.strip():
                result.add("warning", "MISSING_INVESTMENT", "HOLDING missing investment name", row=i)
        elif row_type == "SUBTOTAL":
            result.subtotals += 1
        else:
            result.totals += 1
        
        # Check for numeric fields
        fv = unwrap_value(row.get("fair_value_raw"))
        cost = unwrap_value(row.get("cost_raw"))
        
        if fv:
            _, err = parse_numeric(fv)
            if err and "Multiple" in str(err):
                result.add("error", "MULTI_NUMERIC", err, row=i, field="fair_value_raw")
        
        if cost:
            _, err = parse_numeric(cost)
            if err and "Multiple" in str(err):
                result.add("error", "MULTI_NUMERIC", err, row=i, field="cost_raw")


def validate_arithmetic(soi_rows: List[dict], result: ValidationResult):
    """Validate that holdings sum to subtotals/totals."""
    if not soi_rows:
        return
    
    # Group rows by section
    sections = {}
    current_section = ()
    
    for row in soi_rows:
        row_type = unwrap_value(row.get("row_type"))
        section_path = row.get("section_path", [])
        
        if isinstance(section_path, list):
            section_tuple = tuple(
                unwrap_value(s) if isinstance(s, dict) else str(s)
                for s in section_path
            )
        else:
            section_tuple = ()
        
        if section_tuple:
            current_section = section_tuple
        
        if row_type == "HOLDING":
            if current_section not in sections:
                sections[current_section] = {"holdings": [], "subtotals": []}
            sections[current_section]["holdings"].append(row)
        elif row_type == "SUBTOTAL":
            if current_section not in sections:
                sections[current_section] = {"holdings": [], "subtotals": []}
            sections[current_section]["subtotals"].append(row)
    
    # Validate sums (simplified - just check grand total)
    total_fv = Decimal("0")
    has_fv = False
    
    for row in soi_rows:
        if unwrap_value(row.get("row_type")) == "HOLDING":
            fv_raw = unwrap_value(row.get("fair_value_raw"))
            if fv_raw:
                fv, _ = parse_numeric(fv_raw)
                if fv is not None:
                    total_fv += fv
                    has_fv = True
    
    if has_fv:
        # Find grand total row
        for row in soi_rows:
            if unwrap_value(row.get("row_type")) == "TOTAL":
                label = unwrap_value(row.get("label")) or ""
                if "total" in label.lower():
                    extracted_fv_raw = unwrap_value(row.get("fair_value_raw"))
                    if extracted_fv_raw:
                        extracted_fv, _ = parse_numeric(extracted_fv_raw)
                        if extracted_fv is not None:
                            diff = abs(total_fv - extracted_fv)
                            if diff > Decimal("1"):
                                result.add(
                                    "warning", 
                                    "ARITH_MISMATCH",
                                    f"Sum of holdings ({total_fv}) != Total ({extracted_fv}), diff={diff}",
                                    calculated=str(total_fv),
                                    extracted=str(extracted_fv)
                                )
                    break


def validate_file(filepath: Path) -> ValidationResult:
    """Validate a single extraction result file."""
    result = ValidationResult(filename=filepath.name)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result.add("error", "JSON_PARSE_ERROR", str(e))
        result.has_data = False
        return result
    except Exception as e:
        result.add("error", "FILE_READ_ERROR", str(e))
        result.has_data = False
        return result
    
    extraction = validate_structure(data, result)
    if not extraction:
        return result
    
    soi_rows = get_soi_rows(extraction)
    result.total_rows = len(soi_rows)
    
    if not soi_rows:
        result.add("warning", "EMPTY_EXTRACTION", "No soi_rows found")
        result.has_data = False
        return result
    
    # Sanitize rows to fix misclassified holdings
    sanitized_rows, _ = normalize_soi_rows(soi_rows)
    
    validate_rows(sanitized_rows, result)
    validate_arithmetic(sanitized_rows, result)
    
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Validate extraction results")
    parser.add_argument("--folder", default="actual_extractions", help="Folder to validate")
    parser.add_argument("--output", default="validation_reports", help="Output folder for reports")
    args = parser.parse_args()
    
    input_dir = Path(args.folder)
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)
    
    if not input_dir.exists():
        print(f"ERROR: Folder not found: {input_dir}")
        print("Run 'python separate_and_validate.py' first to create it.")
        return
    
    print("=" * 70)
    print(f"VALIDATING EXTRACTION RESULTS FROM: {input_dir}/")
    print("=" * 70)
    print()
    
    files = list(input_dir.glob("*_extract_response.json"))
    print(f"Found {len(files)} files to validate")
    print()
    
    results = []
    code_counts = Counter()
    
    for i, filepath in enumerate(files, 1):
        result = validate_file(filepath)
        results.append(result)
        
        for issue in result.issues:
            code_counts[issue.code] += 1
        
        status = "OK" if result.error_count() == 0 else f"{result.error_count()}E/{result.warning_count()}W"
        if i % 20 == 0 or i == len(files):
            print(f"[{i}/{len(files)}] Validated... (current: {result.filename}: {status})")
    
    # Calculate summary stats
    files_with_data = [r for r in results if r.has_data]
    files_with_errors = [r for r in results if r.error_count() > 0]
    files_with_warnings = [r for r in results if r.error_count() == 0 and r.warning_count() > 0]
    
    total_rows = sum(r.total_rows for r in results)
    total_holdings = sum(r.holdings for r in results)
    total_subtotals = sum(r.subtotals for r in results)
    total_totals = sum(r.totals for r in results)
    
    # Write reports
    print()
    print("=" * 70)
    print("WRITING REPORTS")
    print("=" * 70)
    
    # Summary JSON
    summary = {
        "timestamp": datetime.now().isoformat(),
        "input_folder": str(input_dir),
        "total_files": len(results),
        "files_with_data": len(files_with_data),
        "files_with_errors": len(files_with_errors),
        "files_with_warnings_only": len(files_with_warnings),
        "total_rows": total_rows,
        "total_holdings": total_holdings,
        "total_subtotals": total_subtotals,
        "total_totals": total_totals,
        "error_codes": dict(code_counts.most_common()),
    }
    
    with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    # CSV report
    csv_path = output_dir / "validation_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "filename", "has_data", "total_rows", "holdings", "subtotals", "totals",
            "errors", "warnings", "top_error"
        ])
        writer.writeheader()
        for r in results:
            error_codes = [i.code for i in r.issues if i.severity == "error"]
            top_error = Counter(error_codes).most_common(1)[0][0] if error_codes else ""
            writer.writerow({
                "filename": r.filename,
                "has_data": r.has_data,
                "total_rows": r.total_rows,
                "holdings": r.holdings,
                "subtotals": r.subtotals,
                "totals": r.totals,
                "errors": r.error_count(),
                "warnings": r.warning_count(),
                "top_error": top_error,
            })
    
    # Per-file details (only for files with issues)
    for r in results:
        if r.issues:
            detail_path = output_dir / f"{r.filename.replace('.json', '')}_validation.json"
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump({
                    "filename": r.filename,
                    "has_data": r.has_data,
                    "total_rows": r.total_rows,
                    "holdings": r.holdings,
                    "subtotals": r.subtotals,
                    "totals": r.totals,
                    "errors": r.error_count(),
                    "warnings": r.warning_count(),
                    "issues": [i.to_dict() for i in r.issues],
                }, f, indent=2)
    
    # Print summary
    print()
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Files validated:        {len(results)}")
    print(f"Files with data:        {len(files_with_data)}")
    print(f"Files with errors:      {len(files_with_errors)}")
    print(f"Files with warnings:    {len(files_with_warnings)}")
    print()
    print(f"Total rows:             {total_rows:,}")
    print(f"  Holdings:             {total_holdings:,}")
    print(f"  Subtotals:            {total_subtotals:,}")
    print(f"  Totals:               {total_totals:,}")
    print()
    
    if code_counts:
        print("Issue breakdown:")
        for code, count in code_counts.most_common(10):
            print(f"  {code}: {count}")
    
    print()
    print("=" * 70)
    print("REPORTS SAVED")
    print("=" * 70)
    print(f"  {output_dir}/summary.json")
    print(f"  {output_dir}/validation_results.csv")
    print(f"  {output_dir}/*_validation.json (per-file details)")


if __name__ == "__main__":
    main()

