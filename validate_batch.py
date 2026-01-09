"""
Run validation on an existing batch folder with extraction results.

Usage:
    python validate_batch.py outputs/batch_40
    python validate_batch.py outputs/batch_40 --verbose

This will:
1. Read extraction JSONs from <batch>/extractions/
2. Read corresponding split JSONs from <batch>/splits/ (if available)
3. Apply SOI row sanitization
4. Run validation
5. Write results to <batch>/validation_details/
6. Generate summary reports
"""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from validator import validate_extract_response, ValidationResult
from soi_sanitize import normalize_soi_rows, NormalizationResult


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file if it exists."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  Warning: Failed to load {path}: {e}")
        return None


def write_summary_reports(
    validation_results: List[ValidationResult],
    batch_dir: Path,
    validation_details_dir: Path,
) -> None:
    """Write summary reports to batch directory."""
    
    # Aggregate stats
    code_counts: Counter = Counter()
    files_with_errors: List[str] = []
    files_with_warnings: List[str] = []
    files_with_arith_errors: List[str] = []
    files_with_root_mismatch: List[str] = []
    
    for vr in validation_results:
        for issue in vr.issues:
            code_counts[issue.code] += 1
        
        if vr.error_count() > 0:
            files_with_errors.append(vr.source_name)
        elif vr.warning_count() > 0:
            files_with_warnings.append(vr.source_name)
        
        if vr.has_arithmetic_error:
            files_with_arith_errors.append(vr.source_name)
        
        if vr.root_sum_mismatch:
            files_with_root_mismatch.append(vr.source_name)
    
    total_errors = sum(v.error_count() for v in validation_results)
    total_warnings = sum(v.warning_count() for v in validation_results)
    total_rows = sum(v.total_rows for v in validation_results)
    
    # Write validation_summary.json to batch root
    summary = {
        "run_timestamp": datetime.now().strftime("%b %d, %Y at %I:%M %p"),
        "files_validated": len(validation_results),
        "total_rows": total_rows,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "files_with_errors": len(files_with_errors),
        "files_with_warnings": len(files_with_warnings),
        "files_with_arithmetic_errors": len(files_with_arith_errors),
        "files_with_root_mismatch": len(files_with_root_mismatch),
        "issue_counts": dict(code_counts.most_common()),
        "error_files": files_with_errors,
        "arithmetic_error_files": files_with_arith_errors,
    }
    
    summary_path = batch_dir / "validation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"  Written: {summary_path}")
    
    # Write human-readable markdown summary
    md_lines = [
        "# Validation Summary",
        "",
        f"**Run:** {summary['run_timestamp']}",
        f"**Files validated:** {len(validation_results)}",
        f"**Total rows:** {total_rows:,}",
        "",
        "## Results",
        "",
        f"- ✅ Clean files: {len(validation_results) - len(files_with_errors) - len(files_with_warnings)}",
        f"- ⚠️ Files with warnings only: {len(files_with_warnings)}",
        f"- ❌ Files with errors: {len(files_with_errors)}",
        f"- 🔢 Files with arithmetic errors: {len(files_with_arith_errors)}",
        "",
    ]
    
    if files_with_arith_errors:
        md_lines.append("## Files with Arithmetic Errors")
        md_lines.append("")
        for f in files_with_arith_errors:
            md_lines.append(f"- {f}")
        md_lines.append("")
    
    if code_counts:
        md_lines.append("## Issue Breakdown")
        md_lines.append("")
        md_lines.append("| Code | Count |")
        md_lines.append("|------|-------|")
        for code, count in code_counts.most_common(20):
            md_lines.append(f"| {code} | {count} |")
        md_lines.append("")
    
    md_path = batch_dir / "validation_summary.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"  Written: {md_path}")


def validate_batch(batch_dir: Path, verbose: bool = False) -> None:
    """Run validation on all extractions in a batch folder."""
    
    extract_dir = batch_dir / "extractions"
    split_dir = batch_dir / "splits"
    validation_dir = batch_dir / "validation_details"
    
    if not extract_dir.exists():
        print(f"Error: Extractions folder not found: {extract_dir}")
        return
    
    validation_dir.mkdir(exist_ok=True)
    
    # Find all extraction files
    extract_files = list(extract_dir.glob("*_extract_response.json"))
    
    if not extract_files:
        print(f"No extraction files found in {extract_dir}")
        return
    
    print(f"Found {len(extract_files)} extraction file(s) to validate")
    print(f"Output directory: {validation_dir}")
    print("-" * 60)
    
    validation_results: List[ValidationResult] = []
    
    for extract_path in sorted(extract_files):
        # Derive file stem (e.g., "0000935069-03-001603" from "0000935069-03-001603_extract_response.json")
        file_stem = extract_path.stem.replace("_extract_response", "")
        
        if verbose:
            print(f"\nProcessing: {file_stem}")
        else:
            print(f"  {file_stem}...", end=" ", flush=True)
        
        # Load extraction JSON
        extract_json = load_json(extract_path)
        if not extract_json:
            print("SKIP (failed to load)")
            continue
        
        # Load corresponding split JSON (optional)
        split_path = split_dir / f"{file_stem}_split_result.json"
        split_json = load_json(split_path)
        
        # Sanitize SOI rows (same as main.py does)
        norm_result: Optional[NormalizationResult] = None
        soi_rows = extract_json.get("result", {}).get("soi_rows", [])
        if soi_rows:
            sanitized_rows, norm_result = normalize_soi_rows(soi_rows)
            if "result" in extract_json:
                extract_json["result"]["soi_rows"] = sanitized_rows
        
        # Run validation
        val_result = validate_extract_response(
            extract_json,
            split_json=split_json,
            source_name=file_stem,
        )
        
        # Attach normalization metadata if fixes were applied
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
        
        # Write per-file validation result
        val_output = validation_dir / f"{file_stem}_validation.json"
        with open(val_output, "w", encoding="utf-8") as f:
            json.dump(val_result.to_dict(), f, indent=2, default=str)
        
        # Print status
        errors = val_result.error_count()
        warnings = val_result.warning_count()
        if errors > 0:
            status = f"[ERROR] {errors} errors, {warnings} warnings"
        elif warnings > 0:
            status = f"[WARN] {warnings} warnings"
        else:
            status = "[OK]"
        
        if verbose:
            print(f"  → {val_result.total_rows} rows, {status}")
        else:
            print(status)
    
    print("-" * 60)
    print("\nWriting summary reports...")
    write_summary_reports(validation_results, batch_dir, validation_dir)
    
    # Final summary
    total_errors = sum(v.error_count() for v in validation_results)
    total_warnings = sum(v.warning_count() for v in validation_results)
    files_with_errors = sum(1 for v in validation_results if v.error_count() > 0)
    
    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)
    print(f"Files validated: {len(validation_results)}")
    print(f"Total errors: {total_errors} (across {files_with_errors} files)")
    print(f"Total warnings: {total_warnings}")
    print(f"Results in: {validation_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run validation on an existing batch folder with extraction results."
    )
    parser.add_argument(
        "batch_folder",
        help="Path to batch folder (e.g., outputs/batch_40)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress",
    )
    args = parser.parse_args()
    
    batch_path = Path(args.batch_folder)
    if not batch_path.exists():
        print(f"Error: Batch folder not found: {batch_path}")
        exit(1)
    
    validate_batch(batch_path, verbose=args.verbose)
