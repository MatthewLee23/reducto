"""
Regression test for SOI row sanitizer.

Tests that the phantom holding issue ($8,169,847 misclassified as HOLDING)
is correctly detected and fixed by the sanitizer.

Run: python soi_sanitize_regression_test.py
"""

import json
import sys
from pathlib import Path
from decimal import Decimal

from soi_sanitize import normalize_soi_rows, unwrap_value
from validator import validate_extract_response


def test_phantom_holding_detection():
    """
    Test that 'Principal Amount:' + subtotal value row is detected and fixed.
    
    The $8,169,847 row was extracted as:
        row_type: HOLDING
        investment: "Principal Amount:"
        fair_value_raw: "8,169,847"
    
    This should be converted to SUBTOTAL or dropped, not counted as a holding.
    """
    print("=" * 70)
    print("REGRESSION TEST: Phantom Holding Detection")
    print("=" * 70)
    print()
    
    # Create a minimal test case with the problematic row
    test_rows = [
        # Regular holding
        {
            "row_type": {"value": "HOLDING", "citations": []},
            "section_path": [{"value": "CONVERTIBLE BONDS AND NOTES", "citations": []}],
            "investment": {"value": "Lucent Technologies, Inc. 2.75% 2023 series A cv. sr. deb.", "citations": []},
            "quantity_raw": {"value": "1,000,000", "citations": []},
            "fair_value_raw": {"value": "1,293,340", "citations": []},
        },
        # Regular holding
        {
            "row_type": {"value": "HOLDING", "citations": []},
            "section_path": [{"value": "CONVERTIBLE BONDS AND NOTES", "citations": []}],
            "investment": {"value": "Nortel Networks Corp. 4.25% 2008 cv. sr. notes", "citations": []},
            "quantity_raw": {"value": "1,250,000", "citations": []},
            "fair_value_raw": {"value": "1,176,563", "citations": []},
        },
        # PHANTOM HOLDING - This is the problematic row (subtotal misclassified as holding)
        {
            "row_type": {"value": "HOLDING", "citations": []},
            "section_path": [{"value": "CONVERTIBLE BONDS AND NOTES", "citations": []}],
            "investment": {"value": "Principal Amount:", "citations": []},
            "quantity_raw": {"value": None, "citations": []},
            "fair_value_raw": {"value": "8,169,847", "citations": []},
            "row_text": {"value": "Principal Amount: \nValue (Note 1): 8,169,847", "citations": []},
        },
        # Total row
        {
            "row_type": {"value": "TOTAL", "citations": []},
            "section_path": [{"value": "CONVERTIBLE BONDS AND NOTES", "citations": []}],
            "label": {"value": "TOTAL CONVERTIBLE BONDS AND NOTES", "citations": []},
            "fair_value_raw": {"value": "2,469,903", "citations": []},  # Sum of first two holdings
        },
    ]
    
    print("Input rows:")
    for i, row in enumerate(test_rows):
        row_type = unwrap_value(row.get("row_type"))
        inv = unwrap_value(row.get("investment")) or unwrap_value(row.get("label")) or ""
        fv = unwrap_value(row.get("fair_value_raw")) or ""
        print(f"  [{i}] {row_type}: {inv[:50]}... | fv={fv}")
    print()
    
    # Run sanitizer
    sanitized_rows, norm_result = normalize_soi_rows(test_rows)
    
    print(f"Normalization result:")
    print(f"  Fix count: {norm_result.fix_count}")
    print(f"  Dropped: {norm_result.dropped_count}")
    print(f"  Converted: {norm_result.converted_count}")
    print()
    
    if norm_result.fix_log:
        print("Fix log:")
        for entry in norm_result.fix_log:
            print(f"  - Row {entry.row_idx}: {entry.old_row_type} -> {entry.new_row_type or 'DROPPED'}")
            print(f"    Reason: {entry.reason_code} (confidence: {entry.confidence})")
            print(f"    Signature: {entry.row_signature}")
        print()
    
    print("Sanitized rows:")
    for i, row in enumerate(sanitized_rows):
        row_type = unwrap_value(row.get("row_type"))
        inv = unwrap_value(row.get("investment")) or unwrap_value(row.get("label")) or ""
        fv = unwrap_value(row.get("fair_value_raw")) or ""
        print(f"  [{i}] {row_type}: {inv[:50]}... | fv={fv}")
    print()
    
    # Assertions
    errors = []
    
    # 1. The phantom holding should be fixed
    if norm_result.fix_count == 0:
        errors.append("ERROR: Sanitizer did not detect the phantom holding!")
    
    # 2. Check that no HOLDING row has "Principal Amount:" as investment
    for row in sanitized_rows:
        row_type = unwrap_value(row.get("row_type"))
        investment = unwrap_value(row.get("investment")) or ""
        if row_type == "HOLDING" and "principal amount" in investment.lower():
            errors.append(f"ERROR: Phantom holding still present: {investment}")
    
    # 3. The fix should be logged with correct reason
    has_correct_reason = any(
        e.reason_code == "COLUMN_HEADER_AS_HOLDING" 
        for e in norm_result.fix_log
    )
    if not has_correct_reason:
        errors.append("ERROR: Fix log doesn't have COLUMN_HEADER_AS_HOLDING reason")
    
    # Report results
    if errors:
        print("FAILURES:")
        for e in errors:
            print(f"  {e}")
        return False
    else:
        print("SUCCESS: All assertions passed!")
        return True


def test_full_file_validation():
    """
    Test that validating the full extraction file no longer produces
    the $8,169,847 ROOT_TOTAL_MISMATCH_FV error after sanitization.
    """
    print()
    print("=" * 70)
    print("REGRESSION TEST: Full File Validation")
    print("=" * 70)
    print()
    
    extract_file = Path("outputs/batch_10/extractions/0000009521-04-000011_extract_response.json")
    
    if not extract_file.exists():
        print(f"SKIP: Test file not found: {extract_file}")
        print("(This test requires the actual extraction file)")
        return None
    
    print(f"Loading: {extract_file}")
    with open(extract_file, "r") as f:
        extract_json = json.load(f)
    
    # Get original soi_rows
    original_rows = extract_json.get("result", {}).get("soi_rows", [])
    print(f"Original row count: {len(original_rows)}")
    
    # Count original HOLDING rows
    original_holdings = sum(
        1 for r in original_rows 
        if unwrap_value(r.get("row_type")) == "HOLDING"
    )
    print(f"Original HOLDING count: {original_holdings}")
    
    # Run sanitizer
    sanitized_rows, norm_result = normalize_soi_rows(original_rows)
    print(f"Sanitized row count: {len(sanitized_rows)}")
    print(f"Fixes applied: {norm_result.fix_count}")
    
    if norm_result.fix_log:
        print()
        print("Fixes:")
        for entry in norm_result.fix_log:
            print(f"  - Row {entry.row_idx}: {entry.reason_code}")
            print(f"    {entry.row_signature}")
    
    # Replace rows and validate
    extract_json["result"]["soi_rows"] = sanitized_rows
    
    val_result = validate_extract_response(
        extract_json,
        source_name="0000009521-04-000011",
    )
    
    print()
    print(f"Validation result:")
    print(f"  Errors: {val_result.error_count()}")
    print(f"  Warnings: {val_result.warning_count()}")
    print(f"  Arithmetic error: {val_result.has_arithmetic_error}")
    print(f"  Root mismatch: {val_result.root_sum_mismatch}")
    print(f"  Max dollar diff: {val_result.max_dollar_diff}")
    print()
    
    # Check for the specific $8,169,847 mismatch
    errors = []
    
    for issue in val_result.issues:
        if issue.code in ("ROOT_TOTAL_MISMATCH_FV", "TOTAL_MISMATCH_FV"):
            diff = issue.context.get("diff", "0")
            if str(diff) == "8169847":
                errors.append(f"ERROR: Still have $8,169,847 mismatch: {issue.message}")
    
    # We expect the sanitizer to have fixed at least one phantom holding
    if norm_result.fix_count == 0:
        errors.append("WARNING: No fixes were applied - phantom holding may not be detected")
    
    if errors:
        print("ISSUES:")
        for e in errors:
            print(f"  {e}")
        return False
    else:
        print("SUCCESS: The $8,169,847 phantom holding issue is resolved!")
        return True


def main():
    """Run all regression tests."""
    print()
    print("SOI SANITIZER REGRESSION TESTS")
    print("=" * 70)
    print()
    
    results = {}
    
    # Test 1: Phantom holding detection
    results["phantom_holding_detection"] = test_phantom_holding_detection()
    
    # Test 2: Full file validation
    results["full_file_validation"] = test_full_file_validation()
    
    # Summary
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, result in results.items():
        if result is True:
            status = "PASS"
            passed += 1
        elif result is False:
            status = "FAIL"
            failed += 1
        else:
            status = "SKIP"
            skipped += 1
        print(f"  {name}: {status}")
    
    print()
    print(f"Total: {passed} passed, {failed} failed, {skipped} skipped")
    print()
    
    if failed > 0:
        print("REGRESSION TEST FAILED!")
        sys.exit(1)
    else:
        print("All regression tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

