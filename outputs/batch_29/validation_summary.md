# Batch #29 - Validation Summary

**Run:** Jan 07, 2026 at 12:56 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 6 |
| Total Rows Extracted | 375 |
| Total Validation Errors | 107 |
| Total Validation Warnings | 23 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 1 failures |
| Subtotals sum to grand total | 1 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 103 | See detailed report |
| `ROW_FROM_NON_SOI_PAGE` | 16 | See detailed report |
| `DATE_MISMATCH` | 6 | See detailed report |
| `TOTAL_MISMATCH_PCT` | 3 | See detailed report |
| `ORPHANED_TOTAL` | 1 | See detailed report |
| `ROOT_TOTAL_MISMATCH_PCT` | 1 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000935069-08-002908`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000935069-08-002908`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
