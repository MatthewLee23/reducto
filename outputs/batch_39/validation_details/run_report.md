# Batch #39 - Run Report

**Run:** Jan 08, 2026 at 04:30 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 8 |
| Successful | 8 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 8 |
| Total Rows Extracted | 2366 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 7 |
| Files with Warnings Only | 1 |
| Files with Arithmetic Errors | 6 |
| Files with Grand Total Mismatch | 3 |
| Total Errors | 192 |
| Total Warnings | 553 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `BBOX_PAGE_OUT_OF_RANGE` | 243 |
| `ROW_FROM_NON_SOI_PAGE` | 187 |
| `CITATION_VALUE_MISMATCH` | 174 |
| `BBOX_OUT_OF_RANGE` | 56 |
| `MISSING_SUBTOTAL` | 43 |
| `DATE_MISMATCH` | 7 |
| `NORMALIZATION_APPLIED` | 7 |
| `POSSIBLE_DUPLICATE_HOLDINGS` | 6 |
| `TOTAL_MISMATCH_FV` | 6 |
| `ROOT_TOTAL_MISMATCH_FV` | 3 |
| `TOTAL_PATH_MISMATCH` | 3 |
| `ROOT_TOTAL_MISMATCH_PCT` | 2 |
| `NEGATIVE_FAIR_VALUE` | 2 |
| `ARITH_MISMATCH_FV` | 2 |
| `ROOT_TOTAL_MISMATCH_COST` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000935069-05-000617`
- `0000936772-03-000287`
- `0000950156-06-000002`
- `0001233087-05-000018`
- `0001233087-08-000026`
- `0001379491-07-000103`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000935069-05-000617`
- `0000936772-03-000287`
- `0000950156-06-000002`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
