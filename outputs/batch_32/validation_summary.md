# Batch #32 - Validation Summary

**Run:** Jan 07, 2026 at 02:46 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 1 |
| Total Rows Extracted | 63 |
| Total Validation Errors | 0 |
| Total Validation Warnings | 2 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 0 failures |
| Subtotals sum to grand total | 0 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `ORPHANED_TOTAL` | 1 | See detailed report |
| `DATE_MISMATCH` | 1 | See detailed report |

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
