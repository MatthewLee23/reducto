# Batch #20 - Run Report

**Run:** Jan 06, 2026 at 10:38 AM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 1 |
| Successful | 1 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 1 |
| Total Rows Extracted | 140 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 0 |
| Files with Warnings Only | 1 |
| Files with Arithmetic Errors | 0 |
| Files with Grand Total Mismatch | 0 |
| Total Errors | 0 |
| Total Warnings | 51 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `SUBTOTAL_PATH_MISMATCH` | 36 |
| `MISSING_SUBTOTAL` | 14 |
| `DATE_MISMATCH` | 1 |

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
