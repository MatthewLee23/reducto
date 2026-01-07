# Batch #21 - Validation Summary

**Run:** Jan 06, 2026 at 10:50 AM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 8 |
| Total Rows Extracted | 1144 |
| Total Validation Errors | 67 |
| Total Validation Warnings | 535 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 7 failures |
| Subtotals sum to grand total | 6 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `SUBTOTAL_PATH_MISMATCH` | 325 | See detailed report |
| `MISSING_SUBTOTAL` | 190 | See detailed report |
| `CITATION_VALUE_MISMATCH` | 44 | See detailed report |
| `DATE_MISMATCH` | 8 | See detailed report |
| `ARITH_MISMATCH_FV` | 7 | Fair value sum doesn't match subtotal |
| `ROOT_TOTAL_MISMATCH_PCT` | 6 | See detailed report |
| `ORPHANED_TOTAL` | 4 | See detailed report |
| `PERCENTAGE_HIERARCHY_DETECTED` | 4 | See detailed report |
| `BBOX_OUT_OF_RANGE` | 3 | See detailed report |
| `ARITH_MISMATCH_COST` | 3 | Cost sum doesn't match subtotal |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000009521-04-000022`
- `0000009521-05-000006`
- `0000009521-06-000013`
- `0000009521-06-000021`
- `0000009521-07-000011`
- `0000009521-07-000020`
- `0000009521-08-000012`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000009521-04-000022`
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
