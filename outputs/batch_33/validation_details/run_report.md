# Batch #33 - Run Report

**Run:** Jan 07, 2026 at 02:59 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 10 |
| Successful | 10 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 10 |
| Total Rows Extracted | 1775 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 8 |
| Files with Warnings Only | 2 |
| Files with Arithmetic Errors | 5 |
| Files with Grand Total Mismatch | 2 |
| Total Errors | 499 |
| Total Warnings | 180 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `MISSING_ROW_TYPE` | 303 |
| `CITATION_VALUE_MISMATCH` | 174 |
| `ROW_FROM_NON_SOI_PAGE` | 115 |
| `MISSING_SUBTOTAL` | 17 |
| `DATE_MISMATCH` | 10 |
| `TOTAL_PATH_MISMATCH` | 10 |
| `BBOX_OUT_OF_RANGE` | 9 |
| `ORPHANED_TOTAL` | 7 |
| `BBOX_PAGE_OUT_OF_RANGE` | 7 |
| `TOTAL_MISMATCH_FV` | 6 |
| `ARITH_MISMATCH_PCT` | 3 |
| `ARITH_MISMATCH_FV` | 3 |
| `TOTAL_MISMATCH_COST` | 3 |
| `TOTAL_MISMATCH_PCT` | 3 |
| `ROOT_TOTAL_MISMATCH_COST` | 2 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000828803-06-000017`
- `0000930413-04-003491`
- `0000936772-05-000012`
- `0000950116-05-002117`
- `0001047469-05-022355`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000930413-04-003491`
- `0001047469-05-022355`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
