# Batch #14 - Run Report

**Run:** Jan 01, 2026 at 12:51 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 9 |
| Successful | 9 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 9 |
| Total Rows Extracted | 1308 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 9 |
| Files with Warnings Only | 0 |
| Files with Arithmetic Errors | 9 |
| Files with Grand Total Mismatch | 9 |
| Total Errors | 185 |
| Total Warnings | 55 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 149 |
| `BBOX_PAGE_OUT_OF_RANGE` | 27 |
| `ARITH_MISMATCH_PCT` | 12 |
| `SUBTOTAL_PATH_MISMATCH` | 11 |
| `DATE_MISMATCH` | 9 |
| `ROOT_TOTAL_MISMATCH_FV` | 8 |
| `ROOT_TOTAL_MISMATCH_PCT` | 8 |
| `BBOX_OUT_OF_RANGE` | 6 |
| `ROOT_TOTAL_MISMATCH_COST` | 3 |
| `TOTAL_MISMATCH_PCT` | 2 |
| `TOTAL_MISMATCH_FV` | 2 |
| `TOTAL_MISSING_NUMERIC` | 1 |
| `ORPHANED_TOTAL` | 1 |
| `TOTAL_MISMATCH_COST` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000009521-04-000011`
- `0000009521-04-000022`
- `0000009521-05-000006`
- `0000009521-05-000013`
- `0000009521-06-000013`
- `0000009521-06-000021`
- `0000009521-07-000011`
- `0000009521-07-000020`
- `0000009521-08-000012`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000009521-04-000011`
- `0000009521-04-000022`
- `0000009521-05-000006`
- `0000009521-05-000013`
- `0000009521-06-000013`
- `0000009521-06-000021`
- `0000009521-07-000011`
- `0000009521-07-000020`
- `0000009521-08-000012`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
