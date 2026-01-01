# Batch #12 - Run Report

**Run:** Dec 30, 2025 at 01:55 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 10 |
| Successful | 10 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 10 |
| Total Rows Extracted | 322 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 2 |
| Files with Warnings Only | 6 |
| Files with Arithmetic Errors | 2 |
| Files with Grand Total Mismatch | 1 |
| Total Errors | 19 |
| Total Warnings | 24 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `SUBTOTAL_PATH_MISMATCH` | 10 |
| `DATE_MISMATCH` | 8 |
| `CITATION_VALUE_MISMATCH` | 7 |
| `ARITH_MISMATCH_PCT` | 4 |
| `ORPHANED_TOTAL` | 4 |
| `TOTAL_MISMATCH_PCT` | 2 |
| `TOTAL_MISMATCH_FV` | 2 |
| `TOTAL_MISSING_NUMERIC` | 1 |
| `NORMALIZATION_APPLIED` | 1 |
| `TOTAL_MISMATCH_COST` | 1 |
| `ROOT_TOTAL_MISMATCH_FV` | 1 |
| `ROOT_TOTAL_MISMATCH_COST` | 1 |
| `ROOT_TOTAL_MISMATCH_PCT` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000009521-04-000011`
- `0000009521-04-000022`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000009521-04-000022`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
