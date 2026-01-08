# Batch #31 - Validation Summary

**Run:** Jan 07, 2026 at 02:20 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 1 |
| Total Rows Extracted | 59 |
| Total Validation Errors | 33 |
| Total Validation Warnings | 1 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 1 failures |
| Subtotals sum to grand total | 0 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 30 | See detailed report |
| `ARITH_MISMATCH_PCT` | 2 | Percent sum doesn't match subtotal |
| `TOTAL_MISMATCH_PCT` | 1 | See detailed report |
| `DATE_MISMATCH` | 1 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000935069-08-002908`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
