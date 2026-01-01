# Batch #4 - Validation Summary

**Run:** Dec 27, 2025 at 03:03 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 14 |
| Total Rows Extracted | 2154 |
| Total Validation Errors | 193 |
| Total Validation Warnings | 218 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 10 failures |
| Subtotals sum to grand total | 10 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 181 | See detailed report |
| `SUBTOTAL_MISSING_LABEL` | 93 | See detailed report |
| `SUBTOTAL_PATH_MISMATCH` | 55 | See detailed report |
| `MISSING_SUBTOTAL` | 30 | See detailed report |
| `DATE_MISMATCH` | 14 | See detailed report |
| `BBOX_OUT_OF_RANGE` | 12 | See detailed report |
| `ROOT_TOTAL_MISMATCH_FV` | 10 | See detailed report |
| `TOTAL_MISSING_NUMERIC` | 7 | See detailed report |
| `ORPHANED_TOTAL` | 7 | See detailed report |
| `ARITH_MISMATCH_FV` | 1 | Fair value sum doesn't match subtotal |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000002230-04-000031`
- `0000002230-04-000040`
- `0000002230-05-000014`
- `0000002230-05-000033`
- `0000002230-06-000011`
- `0000002230-06-000044`
- `0000002230-07-000025`
- `0000002230-07-000062`
- `0000002230-08-000027`
- `0000002230-09-000035`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000002230-04-000031`
- `0000002230-04-000040`
- `0000002230-05-000014`
- `0000002230-05-000033`
- `0000002230-06-000011`
- `0000002230-06-000044`
- `0000002230-07-000025`
- `0000002230-07-000062`
- `0000002230-08-000027`
- `0000002230-09-000035`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
