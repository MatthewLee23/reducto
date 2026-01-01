# Batch #5 - Run Report

**Run:** Dec 27, 2025 at 04:32 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 1 |
| Successful | 1 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 1 |
| Total Rows Extracted | 180 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 1 |
| Files with Warnings Only | 0 |
| Files with Arithmetic Errors | 1 |
| Files with Grand Total Mismatch | 1 |
| Total Errors | 26 |
| Total Warnings | 16 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 24 |
| `SUBTOTAL_MISSING_LABEL` | 13 |
| `ARITH_MISMATCH_FV` | 1 |
| `MISSING_SUBTOTAL` | 1 |
| `ROOT_TOTAL_MISMATCH_FV` | 1 |
| `ORPHANED_TOTAL` | 1 |
| `DATE_MISMATCH` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000002230-03-000010`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000002230-03-000010`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
