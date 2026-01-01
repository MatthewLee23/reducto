# Batch #15 - Validation Summary

**Run:** Jan 01, 2026 at 02:37 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 1 |
| Total Rows Extracted | 169 |
| Total Validation Errors | 5 |
| Total Validation Warnings | 18 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 1 failures |
| Subtotals sum to grand total | 0 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `SUBTOTAL_PATH_MISMATCH` | 10 | See detailed report |
| `ORPHANED_TOTAL` | 4 | See detailed report |
| `CITATION_VALUE_MISMATCH` | 3 | See detailed report |
| `TOTAL_MISSING_NUMERIC` | 1 | See detailed report |
| `BBOX_OUT_OF_RANGE` | 1 | See detailed report |
| `ARITH_MISMATCH_FV` | 1 | Fair value sum doesn't match subtotal |
| `ARITH_MISMATCH_PCT` | 1 | Percent sum doesn't match subtotal |
| `DATE_MISMATCH` | 1 | See detailed report |
| `NORMALIZATION_APPLIED` | 1 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000009521-04-000011`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
