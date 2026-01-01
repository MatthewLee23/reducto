# Batch #2 - Validation Summary

**Run:** Dec 22, 2025 at 10:42 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 15 |
| Total Rows Extracted | 363 |
| Total Validation Errors | 14 |
| Total Validation Warnings | 26 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 3 failures |
| Subtotals sum to grand total | 3 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 10 | See detailed report |
| `SUBTOTAL_MISSING_LABEL` | 10 | See detailed report |
| `INVALID_SOI_ROWS` | 10 | See detailed report |
| `DATE_MISMATCH` | 5 | See detailed report |
| `GRAND_TOTAL_MISMATCH_FV` | 3 | Holdings don't sum to grand total (fair value) |
| `ARITH_MISMATCH_FV` | 1 | Fair value sum doesn't match subtotal |
| `MISSING_GRAND_TOTAL` | 1 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000002230-03-000010`
- `0000002230-04-000040`
- `0000002230-06-000044`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000002230-03-000010`
- `0000002230-04-000040`
- `0000002230-06-000044`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
