# Batch #33 - Validation Summary

**Run:** Jan 07, 2026 at 02:59 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 10 |
| Total Rows Extracted | 1775 |
| Total Validation Errors | 499 |
| Total Validation Warnings | 180 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 5 failures |
| Subtotals sum to grand total | 2 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `MISSING_ROW_TYPE` | 303 | Row is missing required type field |
| `CITATION_VALUE_MISMATCH` | 174 | See detailed report |
| `ROW_FROM_NON_SOI_PAGE` | 115 | See detailed report |
| `MISSING_SUBTOTAL` | 17 | See detailed report |
| `DATE_MISMATCH` | 10 | See detailed report |
| `TOTAL_PATH_MISMATCH` | 10 | See detailed report |
| `BBOX_OUT_OF_RANGE` | 9 | See detailed report |
| `ORPHANED_TOTAL` | 7 | See detailed report |
| `BBOX_PAGE_OUT_OF_RANGE` | 7 | See detailed report |
| `TOTAL_MISMATCH_FV` | 6 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000828803-06-000017`
- `0000930413-04-003491`
- `0000936772-05-000012`
- `0000950116-05-002117`
- `0001047469-05-022355`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000930413-04-003491`
- `0001047469-05-022355`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
