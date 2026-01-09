# Batch #38 - Run Report

**Run:** Jan 08, 2026 at 02:28 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 10 |
| Successful | 10 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 10 |
| Total Rows Extracted | 2412 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 8 |
| Files with Warnings Only | 2 |
| Files with Arithmetic Errors | 8 |
| Files with Grand Total Mismatch | 6 |
| Total Errors | 579 |
| Total Warnings | 905 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `ROW_FROM_NON_SOI_PAGE` | 551 |
| `CITATION_VALUE_MISMATCH` | 547 |
| `BBOX_PAGE_OUT_OF_RANGE` | 270 |
| `BBOX_OUT_OF_RANGE` | 47 |
| `MISSING_SUBTOTAL` | 16 |
| `DATE_MISMATCH` | 9 |
| `NORMALIZATION_APPLIED` | 9 |
| `TOTAL_MISMATCH_FV` | 7 |
| `NEGATIVE_FAIR_VALUE` | 7 |
| `ROOT_TOTAL_MISMATCH_FV` | 5 |
| `ROOT_TOTAL_MISMATCH_PCT` | 4 |
| `TOTAL_MISMATCH_PCT` | 3 |
| `TOTAL_PATH_MISMATCH` | 3 |
| `ARITH_MISMATCH_PCT` | 2 |
| `PARTIAL_EXTRACTION_FV` | 2 |

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
- `0001379491-07-000103`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
