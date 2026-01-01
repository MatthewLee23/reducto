# Batch #3 - Run Report

**Run:** Dec 26, 2025 at 04:36 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 14 |
| Successful | 14 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 14 |
| Total Rows Extracted | 1938 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 4 |
| Files with Warnings Only | 10 |
| Files with Arithmetic Errors | 4 |
| Files with Grand Total Mismatch | 0 |
| Total Errors | 7 |
| Total Warnings | 238 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 93 |
| `SUBTOTAL_MISSING_LABEL` | 80 |
| `MISSING_SUBTOTAL` | 24 |
| `BBOX_PAGE_OUT_OF_RANGE` | 18 |
| `DATE_MISMATCH` | 14 |
| `BBOX_OUT_OF_RANGE` | 7 |
| `TOTAL_MISMATCH_FV` | 4 |
| `ARITH_MISMATCH_FV` | 3 |
| `TOTAL_MISSING_NUMERIC` | 2 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000002230-04-000031`
- `0000002230-05-000014`
- `0000002230-05-000033`
- `0000002230-08-000027`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
