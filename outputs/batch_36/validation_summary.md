# Batch #36 - Validation Summary

**Run:** Jan 08, 2026 at 12:45 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 5 |
| Total Rows Extracted | 979 |
| Total Validation Errors | 271 |
| Total Validation Warnings | 84 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 4 failures |
| Subtotals sum to grand total | 1 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `MISSING_ROW_TYPE` | 188 | Row is missing required type field |
| `CITATION_VALUE_MISMATCH` | 70 | See detailed report |
| `ROW_FROM_NON_SOI_PAGE` | 51 | See detailed report |
| `BBOX_OUT_OF_RANGE` | 10 | See detailed report |
| `BBOX_PAGE_OUT_OF_RANGE` | 6 | See detailed report |
| `DATE_MISMATCH` | 5 | See detailed report |
| `MISSING_SUBTOTAL` | 4 | See detailed report |
| `TOTAL_MISMATCH_COST` | 4 | See detailed report |
| `TOTAL_PATH_MISMATCH` | 4 | See detailed report |
| `TOTAL_MISMATCH_FV` | 3 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000828803-06-000017`
- `0000930413-04-003491`
- `0000936772-05-000012`
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
