"""
Revalidate existing extraction results in a batch folder.
Usage: python revalidate_batch.py [batch_folder]

Example:
  python revalidate_batch.py outputs/batch_3
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from collections import Counter
from validator import validate_extract_response, ValidationResult
from soi_sanitize import normalize_soi_rows, NormalizationResult
from typing import Dict, List


def main(batch_folder: str):
    batch_dir = Path(batch_folder)
    extractions_dir = batch_dir / "extractions"
    validation_details_dir = batch_dir / "validation_details"
    
    if not extractions_dir.exists():
        print(f"ERROR: Extractions folder not found: {extractions_dir}")
        return
    
    validation_details_dir.mkdir(exist_ok=True)
    
    # Find all extract response files
    extract_files = list(extractions_dir.glob("*_extract_response.json"))
    print(f"Found {len(extract_files)} extract responses to validate")
    print()
    
    validation_results: List[ValidationResult] = []
    
    for i, extract_file in enumerate(extract_files, 1):
        stem = extract_file.stem.replace("_extract_response", "")
        
        try:
            with open(extract_file, "r") as f:
                extract_json = json.load(f)
            
            # Try to load split JSON if available
            split_file = batch_dir / "splits" / f"{stem}_split_result.json"
            split_json = None
            if split_file.exists():
                try:
                    with open(split_file, "r") as f:
                        split_json = json.load(f)
                except Exception:
                    pass
            
            # Sanitize soi_rows before validation to fix misclassified rows
            norm_result: NormalizationResult | None = None
            soi_rows = extract_json.get("result", {}).get("soi_rows", [])
            if soi_rows:
                sanitized_rows, norm_result = normalize_soi_rows(soi_rows)
                if "result" in extract_json:
                    extract_json["result"]["soi_rows"] = sanitized_rows
            
            val_result = validate_extract_response(
                extract_json,
                split_json=split_json,
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
            val_output = validation_details_dir / f"{stem}_validation.json"
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
    code_counts: Counter = Counter()
    files_with_errors: List[str] = []
    files_with_warnings: List[str] = []
    files_with_arith: List[str] = []
    files_with_root_mismatch: List[str] = []
    
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
    
    # Extract batch number from folder name
    batch_num = 0
    parts = batch_dir.name.split("_")
    if len(parts) >= 2 and parts[-1].isdigit():
        batch_num = int(parts[-1])
    
    # Write summary.json
    summary = {
        "batch_number": batch_num,
        "run_timestamp": run_timestamp,
        "total_files": len(validation_results),
        "total_rows": total_rows,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "files_with_errors": len(files_with_errors),
        "files_with_warnings": len(files_with_warnings),
        "files_with_arithmetic_errors": len(files_with_arith),
        "files_with_root_mismatch": len(files_with_root_mismatch),
        "all_passed": total_errors == 0,
        "top_error_codes": dict(code_counts.most_common(10)),
        "files_with_errors_list": files_with_errors,
        "files_with_arithmetic_errors_list": files_with_arith,
        "files_with_root_mismatch_list": files_with_root_mismatch,
    }
    with open(batch_dir / "validation_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    # Write human-readable summary.md
    md_lines = [
        f"# Batch #{batch_num} - Validation Summary",
        "",
        f"**Run:** {run_timestamp}",
        "",
        "## Quick Stats",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Files Validated | {len(validation_results)} |",
        f"| Total Rows Extracted | {total_rows} |",
        f"| Total Validation Errors | {total_errors} |",
        f"| Total Validation Warnings | {total_warnings} |",
        "",
        "## Arithmetic Validation (Deterministic Checks)",
        "",
        "These are **hard logic deterministic checks** that verify all numbers add up correctly:",
        "",
        f"| Check | Files with Issues |",
        f"|-------|-------------------|",
        f"| Holdings sum to subtotals | {len(files_with_arith)} failures |",
        f"| Subtotals sum to grand total | {len(files_with_root_mismatch)} failures |",
        "",
    ]
    
    if total_errors == 0 and total_warnings == 0:
        md_lines.extend([
            "## Result: ALL PASSED",
            "",
            "All files passed deterministic validation. All numbers add up correctly.",
            "",
        ])
    else:
        if code_counts:
            md_lines.extend([
                "## Top Issues",
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
    
    with open(batch_dir / "validation_summary.md", "w") as f:
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
    print(f"  {batch_dir}/validation_summary.json - Quick summary")
    print(f"  {batch_dir}/validation_summary.md   - Human-readable summary")
    print(f"  {validation_details_dir}/<stem>_validation.json - Per-file details")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Revalidate existing batch extractions")
    parser.add_argument(
        "batch_folder",
        nargs="?",
        default="outputs/batch_3",
        help="Path to batch folder (default: outputs/batch_3)"
    )
    args = parser.parse_args()
    main(args.batch_folder)

