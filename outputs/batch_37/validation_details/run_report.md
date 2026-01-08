# Batch #37 - Run Report

**Run:** Jan 08, 2026 at 01:20 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 10 |
| Successful | 10 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 10 |
| Total Rows Extracted | 2416 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 8 |
| Files with Warnings Only | 2 |
| Files with Arithmetic Errors | 8 |
| Files with Grand Total Mismatch | 5 |
| Total Errors | 615 |
| Total Warnings | 647 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 585 |
| `ROW_FROM_NON_SOI_PAGE` | 465 |
| `BBOX_PAGE_OUT_OF_RANGE` | 127 |
| `MISSING_SUBTOTAL` | 19 |
| `BBOX_OUT_OF_RANGE` | 13 |
| `DATE_MISMATCH` | 9 |
| `NORMALIZATION_APPLIED` | 8 |
| `ARITH_MISMATCH_PCT` | 7 |
| `TOTAL_MISMATCH_FV` | 6 |
| `ROOT_TOTAL_MISMATCH_FV` | 5 |
| `TOTAL_PATH_MISMATCH` | 5 |
| `TOTAL_MISMATCH_PCT` | 4 |
| `ROOT_TOTAL_MISMATCH_COST` | 3 |
| `ROOT_TOTAL_MISMATCH_PCT` | 2 |
| `TOTAL_MISMATCH_COST` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000935069-03-001603`
- `0000935069-05-000617`
- `0000936772-03-000287`
- `0000950156-06-000002`
- `0001233087-05-000018`
- `0001233087-08-000026`
- `0001379491-07-000103`
- `0001445546-15-000766`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000935069-03-001603`
- `0000935069-05-000617`
- `0000950156-06-000002`
- `0001233087-05-000018`
- `0001233087-08-000026`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
