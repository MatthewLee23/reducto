# Batch #34 - Run Report

**Run:** Jan 07, 2026 at 04:38 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 5 |
| Successful | 4 |
| Skipped | 0 |
| **Failed (Errors)** | **1** |
| Validated | 4 |
| Total Rows Extracted | 706 |

## Processing Errors (1 files)

These files failed during upload/split/extract:

1. **0000950116-05-002117.pdf**: `Connection error.`

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 4 |
| Files with Warnings Only | 0 |
| Files with Arithmetic Errors | 4 |
| Files with Grand Total Mismatch | 2 |
| Total Errors | 90 |
| Total Warnings | 36 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 55 |
| `MISSING_SUBTOTAL` | 14 |
| `ARITH_MISMATCH_FV` | 10 |
| `TOTAL_MISMATCH_FV` | 10 |
| `TOTAL_PATH_MISMATCH` | 7 |
| `ARITH_MISMATCH_PCT` | 4 |
| `DATE_MISMATCH` | 4 |
| `TOTAL_MISMATCH_PCT` | 4 |
| `BBOX_PAGE_OUT_OF_RANGE` | 4 |
| `NORMALIZATION_APPLIED` | 3 |
| `BBOX_OUT_OF_RANGE` | 2 |
| `TOTAL_MISMATCH_COST` | 2 |
| `ROOT_TOTAL_MISMATCH_FV` | 2 |
| `ROOT_TOTAL_MISMATCH_PCT` | 2 |
| `PRICE_TOO_LOW` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000828803-06-000017`
- `0000930413-04-003491`
- `0000936772-05-000012`
- `0001047469-05-022355`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000930413-04-003491`
- `0001047469-05-022355`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
