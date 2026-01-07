# Batch #28 - Run Report

**Run:** Jan 07, 2026 at 11:54 AM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 7 |
| Successful | 7 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 7 |
| Total Rows Extracted | 459 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 6 |
| Files with Warnings Only | 1 |
| Files with Arithmetic Errors | 6 |
| Files with Grand Total Mismatch | 3 |
| Total Errors | 121 |
| Total Warnings | 45 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 102 |
| `ROW_FROM_NON_SOI_PAGE` | 20 |
| `ARITH_MISMATCH_PCT` | 12 |
| `DATE_MISMATCH` | 7 |
| `BBOX_OUT_OF_RANGE` | 5 |
| `ORPHANED_TOTAL` | 5 |
| `NORMALIZATION_APPLIED` | 5 |
| `TOTAL_MISMATCH_PCT` | 4 |
| `ROOT_TOTAL_MISMATCH_PCT` | 3 |
| `TOTAL_PATH_MISMATCH` | 2 |
| `MISSING_SUBTOTAL` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000009521-06-000021`
- `0000935069-08-002438`
- `0000935069-08-002901`
- `0000935069-08-002908`
- `0000935069-08-002911`
- `0000935069-09-000669`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000009521-06-000021`
- `0000935069-08-002901`
- `0000935069-09-000669`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
