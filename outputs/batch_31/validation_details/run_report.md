# Batch #31 - Run Report

**Run:** Jan 07, 2026 at 02:20 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 1 |
| Successful | 1 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 1 |
| Total Rows Extracted | 59 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 1 |
| Files with Warnings Only | 0 |
| Files with Arithmetic Errors | 1 |
| Files with Grand Total Mismatch | 0 |
| Total Errors | 33 |
| Total Warnings | 1 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 30 |
| `ARITH_MISMATCH_PCT` | 2 |
| `TOTAL_MISMATCH_PCT` | 1 |
| `DATE_MISMATCH` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000935069-08-002908`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
