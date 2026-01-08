# Batch #35 - Run Report

**Run:** Jan 08, 2026 at 11:06 AM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 5 |
| Successful | 5 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 5 |
| Total Rows Extracted | 842 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 5 |
| Files with Warnings Only | 0 |
| Files with Arithmetic Errors | 5 |
| Files with Grand Total Mismatch | 1 |
| Total Errors | 168 |
| Total Warnings | 43 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 127 |
| `MISSING_SUBTOTAL` | 22 |
| `ARITH_MISMATCH_FV` | 21 |
| `TOTAL_MISMATCH_FV` | 8 |
| `TOTAL_MISMATCH_PCT` | 7 |
| `TOTAL_PATH_MISMATCH` | 7 |
| `DATE_MISMATCH` | 5 |
| `BBOX_PAGE_OUT_OF_RANGE` | 4 |
| `NORMALIZATION_APPLIED` | 3 |
| `TOTAL_MISMATCH_COST` | 2 |
| `PRICE_TOO_LOW` | 1 |
| `ORPHANED_TOTAL` | 1 |
| `NEGATIVE_FAIR_VALUE` | 1 |
| `ROOT_TOTAL_MISMATCH_FV` | 1 |
| `ROOT_TOTAL_MISMATCH_PCT` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000828803-06-000017`
- `0000930413-04-003491`
- `0000936772-05-000012`
- `0000950116-05-002117`
- `0001047469-05-022355`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0001047469-05-022355`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
