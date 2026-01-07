# Batch #23 - Validation Summary

**Run:** Jan 06, 2026 at 02:33 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 2 |
| Total Rows Extracted | 237 |
| Total Validation Errors | 25 |
| Total Validation Warnings | 4 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 1 failures |
| Subtotals sum to grand total | 0 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `CITATION_VALUE_MISMATCH` | 21 | See detailed report |
| `TOTAL_MISMATCH_FV` | 2 | See detailed report |
| `TOTAL_MISMATCH_COST` | 2 | See detailed report |
| `ORPHANED_TOTAL` | 2 | See detailed report |
| `DATE_MISMATCH` | 2 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000009521-04-000022`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
