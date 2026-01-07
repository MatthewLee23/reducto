# Batch #28 - Validation Summary

**Run:** Jan 07, 2026 at 11:54 AM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 7 |
| Total Rows Extracted | 459 |
| Total Validation Errors | 121 |
| Total Validation Warnings | 45 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 6 failures |
| Subtotals sum to grand total | 3 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 102 | See detailed report |
| `ROW_FROM_NON_SOI_PAGE` | 20 | See detailed report |
| `ARITH_MISMATCH_PCT` | 12 | Percent sum doesn't match subtotal |
| `DATE_MISMATCH` | 7 | See detailed report |
| `BBOX_OUT_OF_RANGE` | 5 | See detailed report |
| `ORPHANED_TOTAL` | 5 | See detailed report |
| `NORMALIZATION_APPLIED` | 5 | See detailed report |
| `TOTAL_MISMATCH_PCT` | 4 | See detailed report |
| `ROOT_TOTAL_MISMATCH_PCT` | 3 | See detailed report |
| `TOTAL_PATH_MISMATCH` | 2 | See detailed report |

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

- `0000009521-06-000021`
- `0000935069-08-002901`
- `0000935069-09-000669`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
