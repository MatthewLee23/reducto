# Batch #41 - Run Report

**Run:** Jan 09, 2026 at 09:57 AM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 8 |
| Successful | 8 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 8 |
| Total Rows Extracted | 2388 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 8 |
| Files with Warnings Only | 0 |
| Files with Arithmetic Errors | 7 |
| Files with Grand Total Mismatch | 4 |
| Total Errors | 526 |
| Total Warnings | 817 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `ROW_FROM_NON_SOI_PAGE` | 606 |
| `CITATION_VALUE_MISMATCH` | 498 |
| `BBOX_PAGE_OUT_OF_RANGE` | 104 |
| `BBOX_OUT_OF_RANGE` | 59 |
| `POSSIBLE_DUPLICATE_HOLDINGS` | 10 |
| `FUND_MISSING_TOTAL` | 7 |
| `DATE_MISMATCH` | 7 |
| `TOTAL_PATH_MISMATCH` | 6 |
| `NORMALIZATION_APPLIED` | 6 |
| `ARITH_MISMATCH_PCT` | 6 |
| `MULTI_FUND_DOCUMENT_DETECTED` | 5 |
| `ARITH_MISMATCH_FV` | 5 |
| `ROOT_TOTAL_MISMATCH_FV` | 4 |
| `MISSING_SUBTOTAL` | 4 |
| `ROOT_TOTAL_MISMATCH_PCT` | 2 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000935069-03-001603`
- `0000935069-05-000617`
- `0000936772-03-000287`
- `0000950156-06-000002`
- `0001233087-05-000018`
- `0001233087-08-000026`
- `0001379491-07-000103`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000935069-03-001603`
- `0000935069-05-000617`
- `0000950156-06-000002`
- `0001379491-07-000103`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
