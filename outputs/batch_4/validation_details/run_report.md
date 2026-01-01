# Batch #4 - Run Report

**Run:** Dec 27, 2025 at 03:03 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 14 |
| Successful | 14 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 14 |
| Total Rows Extracted | 2154 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 13 |
| Files with Warnings Only | 1 |
| Files with Arithmetic Errors | 10 |
| Files with Grand Total Mismatch | 10 |
| Total Errors | 193 |
| Total Warnings | 218 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 181 |
| `SUBTOTAL_MISSING_LABEL` | 93 |
| `SUBTOTAL_PATH_MISMATCH` | 55 |
| `MISSING_SUBTOTAL` | 30 |
| `DATE_MISMATCH` | 14 |
| `BBOX_OUT_OF_RANGE` | 12 |
| `ROOT_TOTAL_MISMATCH_FV` | 10 |
| `TOTAL_MISSING_NUMERIC` | 7 |
| `ORPHANED_TOTAL` | 7 |
| `ARITH_MISMATCH_FV` | 1 |
| `ROOT_TOTAL_MISMATCH_PCT` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000002230-04-000031`
- `0000002230-04-000040`
- `0000002230-05-000014`
- `0000002230-05-000033`
- `0000002230-06-000011`
- `0000002230-06-000044`
- `0000002230-07-000025`
- `0000002230-07-000062`
- `0000002230-08-000027`
- `0000002230-09-000035`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000002230-04-000031`
- `0000002230-04-000040`
- `0000002230-05-000014`
- `0000002230-05-000033`
- `0000002230-06-000011`
- `0000002230-06-000044`
- `0000002230-07-000025`
- `0000002230-07-000062`
- `0000002230-08-000027`
- `0000002230-09-000035`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
