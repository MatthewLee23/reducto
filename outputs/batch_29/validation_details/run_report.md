# Batch #29 - Run Report

**Run:** Jan 07, 2026 at 12:56 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 6 |
| Successful | 6 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 6 |
| Total Rows Extracted | 375 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 5 |
| Files with Warnings Only | 1 |
| Files with Arithmetic Errors | 1 |
| Files with Grand Total Mismatch | 1 |
| Total Errors | 107 |
| Total Warnings | 23 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 103 |
| `ROW_FROM_NON_SOI_PAGE` | 16 |
| `DATE_MISMATCH` | 6 |
| `TOTAL_MISMATCH_PCT` | 3 |
| `ORPHANED_TOTAL` | 1 |
| `ROOT_TOTAL_MISMATCH_PCT` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000935069-08-002908`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000935069-08-002908`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
