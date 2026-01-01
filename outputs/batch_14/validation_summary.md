# Batch #14 - Validation Summary

**Run:** Jan 01, 2026 at 12:51 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 9 |
| Total Rows Extracted | 1308 |
| Total Validation Errors | 185 |
| Total Validation Warnings | 55 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 9 failures |
| Subtotals sum to grand total | 9 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 149 | See detailed report |
| `BBOX_PAGE_OUT_OF_RANGE` | 27 | See detailed report |
| `ARITH_MISMATCH_PCT` | 12 | Percent sum doesn't match subtotal |
| `SUBTOTAL_PATH_MISMATCH` | 11 | See detailed report |
| `DATE_MISMATCH` | 9 | See detailed report |
| `ROOT_TOTAL_MISMATCH_FV` | 8 | See detailed report |
| `ROOT_TOTAL_MISMATCH_PCT` | 8 | See detailed report |
| `BBOX_OUT_OF_RANGE` | 6 | See detailed report |
| `ROOT_TOTAL_MISMATCH_COST` | 3 | See detailed report |
| `TOTAL_MISMATCH_PCT` | 2 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000009521-04-000011`
- `0000009521-04-000022`
- `0000009521-05-000006`
- `0000009521-05-000013`
- `0000009521-06-000013`
- `0000009521-06-000021`
- `0000009521-07-000011`
- `0000009521-07-000020`
- `0000009521-08-000012`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000009521-04-000011`
- `0000009521-04-000022`
- `0000009521-05-000006`
- `0000009521-05-000013`
- `0000009521-06-000013`
- `0000009521-06-000021`
- `0000009521-07-000011`
- `0000009521-07-000020`
- `0000009521-08-000012`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
