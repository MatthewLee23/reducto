# Batch #5 - Validation Summary

**Run:** Dec 27, 2025 at 04:32 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 1 |
| Total Rows Extracted | 180 |
| Total Validation Errors | 26 |
| Total Validation Warnings | 16 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 1 failures |
| Subtotals sum to grand total | 1 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 24 | See detailed report |
| `SUBTOTAL_MISSING_LABEL` | 13 | See detailed report |
| `ARITH_MISMATCH_FV` | 1 | Fair value sum doesn't match subtotal |
| `MISSING_SUBTOTAL` | 1 | See detailed report |
| `ROOT_TOTAL_MISMATCH_FV` | 1 | See detailed report |
| `ORPHANED_TOTAL` | 1 | See detailed report |
| `DATE_MISMATCH` | 1 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000002230-03-000010`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000002230-03-000010`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
