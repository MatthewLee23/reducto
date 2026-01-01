# Batch #7 - Run Report

**Run:** Dec 27, 2025 at 05:23 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 8 |
| Successful | 8 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 8 |
| Total Rows Extracted | 1020 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 7 |
| Files with Warnings Only | 1 |
| Files with Arithmetic Errors | 5 |
| Files with Grand Total Mismatch | 5 |
| Total Errors | 113 |
| Total Warnings | 165 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 104 |
| `SUBTOTAL_MISSING_LABEL` | 79 |
| `MISSING_SUBTOTAL` | 46 |
| `SUBTOTAL_PATH_MISMATCH` | 14 |
| `ORPHANED_TOTAL` | 9 |
| `DATE_MISMATCH` | 8 |
| `BBOX_OUT_OF_RANGE` | 5 |
| `TOTAL_MISSING_NUMERIC` | 4 |
| `ROOT_TOTAL_MISMATCH_FV` | 4 |
| `ROOT_TOTAL_MISMATCH_PCT` | 2 |
| `ARITH_MISMATCH_FV` | 1 |
| `TOTAL_MISMATCH_FV` | 1 |
| `TOTAL_MISMATCH_PCT` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000002230-08-000027`
- `0000002230-08-000057`
- `0000002230-09-000035`
- `0000009521-04-000011`
- `0000009521-04-000022`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000002230-08-000027`
- `0000002230-08-000057`
- `0000002230-09-000035`
- `0000009521-04-000011`
- `0000009521-04-000022`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
