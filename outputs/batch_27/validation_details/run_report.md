# Batch #27 - Run Report

**Run:** Jan 07, 2026 at 10:43 AM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 7 |
| Successful | 7 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 7 |
| Total Rows Extracted | 480 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 6 |
| Files with Warnings Only | 1 |
| Files with Arithmetic Errors | 6 |
| Files with Grand Total Mismatch | 2 |
| Total Errors | 56 |
| Total Warnings | 49 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 30 |
| `SUBTOTAL_PATH_MISMATCH` | 27 |
| `ARITH_MISMATCH_PCT` | 14 |
| `TOTAL_MISMATCH_PCT` | 9 |
| `DATE_MISMATCH` | 7 |
| `ORPHANED_TOTAL` | 6 |
| `NORMALIZATION_APPLIED` | 5 |
| `ROOT_TOTAL_MISMATCH_PCT` | 2 |
| `TOTAL_MISMATCH_FV` | 1 |
| `TOTAL_PATH_MISMATCH` | 1 |
| `TOTAL_MISSING_NUMERIC` | 1 |
| `BBOX_OUT_OF_RANGE` | 1 |
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

- `0000935069-08-002901`
- `0000935069-08-002908`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
