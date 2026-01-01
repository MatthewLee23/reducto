# Batch #8 - Validation Summary

**Run:** Dec 30, 2025 at 09:18 AM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 1 |
| Total Rows Extracted | 98 |
| Total Validation Errors | 5 |
| Total Validation Warnings | 8 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 0 failures |
| Subtotals sum to grand total | 0 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `MISSING_SUBTOTAL` | 7 | See detailed report |
| `CITATION_VALUE_MISMATCH` | 5 | See detailed report |
| `DATE_MISMATCH` | 1 | See detailed report |

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
