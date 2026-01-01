"""
Validate existing extract responses without re-running extraction.
Run: python validate_existing.py
"""

import json
from pathlib import Path
from datetime import datetime
from validator import validate_extract_response, ValidationResult
from soi_sanitize import normalize_soi_rows, NormalizationResult
from collections import Counter
import csv


def main():
    extract_urls_dir = Path("extract_urls")
    validation_dir = Path("validation_results")
    validation_dir.mkdir(exist_ok=True)
    
    # Find all extract response files
    extract_files = list(extract_urls_dir.glob("*_extract_response.json"))
    print(f"Found {len(extract_files)} extract responses to validate")
    print()
    
    validation_results = []
    
    for i, extract_file in enumerate(extract_files, 1):
        stem = extract_file.stem.replace("_extract_response", "")
        
        try:
            with open(extract_file, "r") as f:
                extract_json = json.load(f)
            
            # Sanitize soi_rows before validation to fix misclassified rows
            norm_result: NormalizationResult | None = None
            soi_rows = extract_json.get("result", {}).get("soi_rows", [])
            if soi_rows:
                sanitized_rows, norm_result = normalize_soi_rows(soi_rows)
                if "result" in extract_json:
                    extract_json["result"]["soi_rows"] = sanitized_rows
            
            val_result = validate_extract_response(
                extract_json,
                source_name=stem,
            )
            
            # Attach normalization metadata and add warning if fixes were applied
            if norm_result and norm_result.fix_count > 0:
                val_result.normalization = norm_result.to_dict()
                reason_summary = ", ".join(
                    f"{code}={count}" 
                    for code, count in sorted(
                        {e.reason_code: sum(1 for x in norm_result.fix_log if x.reason_code == e.reason_code) 
                         for e in norm_result.fix_log}.items()
                    )
                )
                val_result.add(
                    "warning",
                    "NORMALIZATION_APPLIED",
                    f"Sanitizer fixed {norm_result.fix_count} row(s): {reason_summary}",
                    fix_count=norm_result.fix_count,
                    dropped=norm_result.dropped_count,
                    converted=norm_result.converted_count,
                )
            
            validation_results.append(val_result)
            
            # Write per-file validation
            val_output = validation_dir / f"{stem}_validation.json"
            with open(val_output, "w") as f:
                json.dump(val_result.to_dict(), f, indent=2)
            
            errors = val_result.error_count()
            warnings = val_result.warning_count()
            status = "OK" if errors == 0 and warnings == 0 else f"{errors}E/{warnings}W"
            print(f"[{i}/{len(extract_files)}] {stem}: {status}")
            
        except Exception as e:
            print(f"[{i}/{len(extract_files)}] {stem}: FAILED - {e}")
    
    # Write summary reports
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Aggregate stats
    code_counts = Counter()
    files_with_errors = []
    files_with_warnings = []
    files_with_arith = []
    files_with_root_mismatch = []
    
    for vr in validation_results:
        for issue in vr.issues:
            code_counts[issue.code] += 1
        if vr.error_count() > 0:
            files_with_errors.append(vr.source_name)
        elif vr.warning_count() > 0:
            files_with_warnings.append(vr.source_name)
        if vr.has_arithmetic_error:
            files_with_arith.append(vr.source_name)
        if vr.root_sum_mismatch:
            files_with_root_mismatch.append(vr.source_name)
    
    total_errors = sum(v.error_count() for v in validation_results)
    total_warnings = sum(v.warning_count() for v in validation_results)
    total_rows = sum(v.total_rows for v in validation_results)
    
    # Write summary.json
    summary = {
        "run_timestamp": run_timestamp,
        "total_files": len(validation_results),
        "total_rows": total_rows,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "files_with_errors": files_with_errors,
        "files_with_warnings": files_with_warnings,
        "files_with_arithmetic_errors": files_with_arith,
        "files_with_root_mismatch": files_with_root_mismatch,
        "error_codes": dict(code_counts.most_common()),
    }
    with open(validation_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    # Write CSV report
    csv_path = validation_dir / "batch_report.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["filename", "total_rows", "holdings", "subtotals", "totals",
                      "errors", "warnings", "arithmetic_error", "root_mismatch", 
                      "max_dollar_diff", "top_error"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for vr in validation_results:
            writer.writerow({
                "filename": vr.source_name,
                "total_rows": vr.total_rows,
                "holdings": vr.holding_count,
                "subtotals": vr.subtotal_count,
                "totals": vr.total_count,
                "errors": vr.error_count(),
                "warnings": vr.warning_count(),
                "arithmetic_error": vr.has_arithmetic_error,
                "root_mismatch": vr.root_sum_mismatch,
                "max_dollar_diff": str(vr.max_dollar_diff),
                "top_error": vr.top_error_code() or "",
            })
    
    # Write human-readable summary.md
    md_lines = [
        "# Validation Summary",
        "",
        f"**Run:** {run_timestamp}",
        f"**Files validated:** {len(validation_results)}",
        f"**Total rows:** {total_rows}",
        "",
        "## Results",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total Errors | {total_errors} |",
        f"| Total Warnings | {total_warnings} |",
        f"| Files with Errors | {len(files_with_errors)} |",
        f"| Files with Warnings Only | {len(files_with_warnings)} |",
        f"| Files with Arithmetic Errors | {len(files_with_arith)} |",
        f"| Files with Root Mismatch | {len(files_with_root_mismatch)} |",
        "",
    ]
    
    if code_counts:
        md_lines.extend([
            "## Top Error Codes",
            "",
            "| Code | Count |",
            "|------|-------|",
        ])
        for code, count in code_counts.most_common(15):
            md_lines.append(f"| `{code}` | {count} |")
        md_lines.append("")
    
    if files_with_errors:
        md_lines.extend([
            "## Files with Errors",
            "",
        ])
        for f in files_with_errors[:30]:
            md_lines.append(f"- `{f}`")
        if len(files_with_errors) > 30:
            md_lines.append(f"- ... and {len(files_with_errors) - 30} more")
        md_lines.append("")
    
    if files_with_arith:
        md_lines.extend([
            "## Files with Arithmetic Errors",
            "",
        ])
        for f in files_with_arith[:30]:
            md_lines.append(f"- `{f}`")
        if len(files_with_arith) > 30:
            md_lines.append(f"- ... and {len(files_with_arith) - 30} more")
        md_lines.append("")
    
    with open(validation_dir / "summary.md", "w") as f:
        f.write("\n".join(md_lines))
    
    # Print summary
    print()
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Files validated: {len(validation_results)}")
    print(f"Total rows extracted: {total_rows}")
    print()
    print(f"Total errors: {total_errors}")
    print(f"Total warnings: {total_warnings}")
    print(f"Files with errors: {len(files_with_errors)}")
    print(f"Files with arithmetic errors: {len(files_with_arith)}")
    print(f"Files with root mismatch: {len(files_with_root_mismatch)}")
    print()
    if code_counts:
        print("Top error codes:")
        for code, count in code_counts.most_common(10):
            print(f"  {code}: {count}")
    print()
    print("=" * 60)
    print("REPORTS SAVED TO:")
    print("=" * 60)
    print(f"  validation_results/summary.json    - Machine-readable summary")
    print(f"  validation_results/summary.md      - Human-readable summary")
    print(f"  validation_results/batch_report.csv - Per-file spreadsheet")
    print(f"  validation_results/<stem>_validation.json - Per-file details")
    print("=" * 60)


if __name__ == "__main__":
    main()

