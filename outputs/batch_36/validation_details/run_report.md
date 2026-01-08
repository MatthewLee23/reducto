# Batch #36 - Run Report

**Run:** Jan 08, 2026 at 12:45 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 5 |
| Successful | 5 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 5 |
| Total Rows Extracted | 979 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 5 |
| Files with Warnings Only | 0 |
| Files with Arithmetic Errors | 4 |
| Files with Grand Total Mismatch | 1 |
| Total Errors | 271 |
| Total Warnings | 84 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `MISSING_ROW_TYPE` | 188 |
| `CITATION_VALUE_MISMATCH` | 70 |
| `ROW_FROM_NON_SOI_PAGE` | 51 |
| `BBOX_OUT_OF_RANGE` | 10 |
| `BBOX_PAGE_OUT_OF_RANGE` | 6 |
| `DATE_MISMATCH` | 5 |
| `MISSING_SUBTOTAL` | 4 |
| `TOTAL_MISMATCH_COST` | 4 |
| `TOTAL_PATH_MISMATCH` | 4 |
| `TOTAL_MISMATCH_FV` | 3 |
| `NORMALIZATION_APPLIED` | 3 |
| `ARITH_MISMATCH_PCT` | 2 |
| `TOTAL_MISMATCH_PCT` | 2 |
| `PRICE_TOO_LOW` | 1 |
| `NEGATIVE_FAIR_VALUE` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000828803-06-000017`
- `0000930413-04-003491`
- `0000936772-05-000012`
- `0001047469-05-022355`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0001047469-05-022355`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
