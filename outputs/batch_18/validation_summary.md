# Batch #18 - Validation Summary

**Run:** Jan 05, 2026 at 04:53 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 1 |
| Total Rows Extracted | 142 |
| Total Validation Errors | 5 |
| Total Validation Warnings | 84 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 1 failures |
| Subtotals sum to grand total | 1 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `SUBTOTAL_PATH_MISMATCH` | 44 | See detailed report |
| `MISSING_SUBTOTAL` | 34 | See detailed report |
| `CITATION_VALUE_MISMATCH` | 2 | See detailed report |
| `ORPHANED_TOTAL` | 2 | See detailed report |
| `TOTAL_MISSING_NUMERIC` | 1 | See detailed report |
| `BBOX_OUT_OF_RANGE` | 1 | See detailed report |
| `TOTAL_MISMATCH_FV` | 1 | See detailed report |
| `ROOT_TOTAL_MISMATCH_FV` | 1 | See detailed report |
| `ROOT_TOTAL_MISMATCH_PCT` | 1 | See detailed report |
| `TOTAL_PATH_MISMATCH` | 1 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000009521-04-000011`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000009521-04-000011`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
