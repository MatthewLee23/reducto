# Batch #35 - Validation Summary

**Run:** Jan 08, 2026 at 11:06 AM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 5 |
| Total Rows Extracted | 842 |
| Total Validation Errors | 168 |
| Total Validation Warnings | 43 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 5 failures |
| Subtotals sum to grand total | 1 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 127 | See detailed report |
| `MISSING_SUBTOTAL` | 22 | See detailed report |
| `ARITH_MISMATCH_FV` | 21 | Fair value sum doesn't match subtotal |
| `TOTAL_MISMATCH_FV` | 8 | See detailed report |
| `TOTAL_MISMATCH_PCT` | 7 | See detailed report |
| `TOTAL_PATH_MISMATCH` | 7 | See detailed report |
| `DATE_MISMATCH` | 5 | See detailed report |
| `BBOX_PAGE_OUT_OF_RANGE` | 4 | See detailed report |
| `NORMALIZATION_APPLIED` | 3 | See detailed report |
| `TOTAL_MISMATCH_COST` | 2 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000828803-06-000017`
- `0000930413-04-003491`
- `0000936772-05-000012`
- `0000950116-05-002117`
- `0001047469-05-022355`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0001047469-05-022355`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
