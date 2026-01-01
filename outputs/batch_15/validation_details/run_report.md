# Batch #15 - Run Report

**Run:** Jan 01, 2026 at 02:37 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 1 |
| Successful | 1 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 1 |
| Total Rows Extracted | 169 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 1 |
| Files with Warnings Only | 0 |
| Files with Arithmetic Errors | 1 |
| Files with Grand Total Mismatch | 0 |
| Total Errors | 5 |
| Total Warnings | 18 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `SUBTOTAL_PATH_MISMATCH` | 10 |
| `ORPHANED_TOTAL` | 4 |
| `CITATION_VALUE_MISMATCH` | 3 |
| `TOTAL_MISSING_NUMERIC` | 1 |
| `BBOX_OUT_OF_RANGE` | 1 |
| `ARITH_MISMATCH_FV` | 1 |
| `ARITH_MISMATCH_PCT` | 1 |
| `DATE_MISMATCH` | 1 |
| `NORMALIZATION_APPLIED` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000009521-04-000011`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
