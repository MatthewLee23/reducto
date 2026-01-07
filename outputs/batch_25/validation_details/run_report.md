# Batch #25 - Run Report

**Run:** Jan 06, 2026 at 04:44 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 5 |
| Successful | 5 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 5 |
| Total Rows Extracted | 599 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 2 |
| Files with Warnings Only | 3 |
| Files with Arithmetic Errors | 1 |
| Files with Grand Total Mismatch | 0 |
| Total Errors | 53 |
| Total Warnings | 12 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 24 |
| `ARITH_MISMATCH_FV` | 14 |
| `ARITH_MISMATCH_COST` | 14 |
| `ORPHANED_TOTAL` | 7 |
| `DATE_MISMATCH` | 5 |
| `ARITH_MISMATCH_PCT` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000009521-06-000021`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
