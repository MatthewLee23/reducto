# Batch #7 - Validation Summary

**Run:** Dec 27, 2025 at 05:23 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 8 |
| Total Rows Extracted | 1020 |
| Total Validation Errors | 113 |
| Total Validation Warnings | 165 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 5 failures |
| Subtotals sum to grand total | 5 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 104 | See detailed report |
| `SUBTOTAL_MISSING_LABEL` | 79 | See detailed report |
| `MISSING_SUBTOTAL` | 46 | See detailed report |
| `SUBTOTAL_PATH_MISMATCH` | 14 | See detailed report |
| `ORPHANED_TOTAL` | 9 | See detailed report |
| `DATE_MISMATCH` | 8 | See detailed report |
| `BBOX_OUT_OF_RANGE` | 5 | See detailed report |
| `TOTAL_MISSING_NUMERIC` | 4 | See detailed report |
| `ROOT_TOTAL_MISMATCH_FV` | 4 | See detailed report |
| `ROOT_TOTAL_MISMATCH_PCT` | 2 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000002230-08-000027`
- `0000002230-08-000057`
- `0000002230-09-000035`
- `0000009521-04-000011`
- `0000009521-04-000022`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000002230-08-000027`
- `0000002230-08-000057`
- `0000002230-09-000035`
- `0000009521-04-000011`
- `0000009521-04-000022`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
