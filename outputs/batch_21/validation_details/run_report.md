# Batch #21 - Run Report

**Run:** Jan 06, 2026 at 10:50 AM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 8 |
| Successful | 8 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 8 |
| Total Rows Extracted | 1144 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 7 |
| Files with Warnings Only | 1 |
| Files with Arithmetic Errors | 7 |
| Files with Grand Total Mismatch | 6 |
| Total Errors | 67 |
| Total Warnings | 535 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `SUBTOTAL_PATH_MISMATCH` | 325 |
| `MISSING_SUBTOTAL` | 190 |
| `CITATION_VALUE_MISMATCH` | 44 |
| `DATE_MISMATCH` | 8 |
| `ARITH_MISMATCH_FV` | 7 |
| `ROOT_TOTAL_MISMATCH_PCT` | 6 |
| `ORPHANED_TOTAL` | 4 |
| `PERCENTAGE_HIERARCHY_DETECTED` | 4 |
| `BBOX_OUT_OF_RANGE` | 3 |
| `ARITH_MISMATCH_COST` | 3 |
| `TOTAL_MISMATCH_FV` | 2 |
| `TOTAL_MISMATCH_COST` | 2 |
| `ROOT_TOTAL_MISMATCH_FV` | 2 |
| `TOTAL_PATH_MISMATCH` | 1 |
| `ROOT_TOTAL_MISMATCH_COST` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000009521-04-000022`
- `0000009521-05-000006`
- `0000009521-06-000013`
- `0000009521-06-000021`
- `0000009521-07-000011`
- `0000009521-07-000020`
- `0000009521-08-000012`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000009521-04-000022`
- `0000009521-06-000013`
- `0000009521-06-000021`
- `0000009521-07-000011`
- `0000009521-07-000020`
- `0000009521-08-000012`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
