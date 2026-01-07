# Batch #27 - Validation Summary

**Run:** Jan 07, 2026 at 10:43 AM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 7 |
| Total Rows Extracted | 480 |
| Total Validation Errors | 56 |
| Total Validation Warnings | 49 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 6 failures |
| Subtotals sum to grand total | 2 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 30 | See detailed report |
| `SUBTOTAL_PATH_MISMATCH` | 27 | See detailed report |
| `ARITH_MISMATCH_PCT` | 14 | Percent sum doesn't match subtotal |
| `TOTAL_MISMATCH_PCT` | 9 | See detailed report |
| `DATE_MISMATCH` | 7 | See detailed report |
| `ORPHANED_TOTAL` | 6 | See detailed report |
| `NORMALIZATION_APPLIED` | 5 | See detailed report |
| `ROOT_TOTAL_MISMATCH_PCT` | 2 | See detailed report |
| `TOTAL_MISMATCH_FV` | 1 | See detailed report |
| `TOTAL_PATH_MISMATCH` | 1 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000009521-06-000021`
- `0000935069-08-002438`
- `0000935069-08-002901`
- `0000935069-08-002908`
- `0000935069-08-002911`
- `0000935069-09-000669`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000935069-08-002901`
- `0000935069-08-002908`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
