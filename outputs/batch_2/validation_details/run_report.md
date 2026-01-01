# Batch #2 - Run Report

**Run:** Dec 22, 2025 at 10:42 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 15 |
| Successful | 15 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 15 |
| Total Rows Extracted | 363 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 13 |
| Files with Warnings Only | 2 |
| Files with Arithmetic Errors | 3 |
| Files with Grand Total Mismatch | 3 |
| Total Errors | 14 |
| Total Warnings | 26 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 10 |
| `SUBTOTAL_MISSING_LABEL` | 10 |
| `INVALID_SOI_ROWS` | 10 |
| `DATE_MISMATCH` | 5 |
| `GRAND_TOTAL_MISMATCH_FV` | 3 |
| `ARITH_MISMATCH_FV` | 1 |
| `MISSING_GRAND_TOTAL` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000002230-03-000010`
- `0000002230-04-000040`
- `0000002230-06-000044`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000002230-03-000010`
- `0000002230-04-000040`
- `0000002230-06-000044`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
