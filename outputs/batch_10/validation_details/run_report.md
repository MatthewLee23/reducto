# Batch #10 - Run Report

**Run:** Dec 30, 2025 at 11:37 AM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 1 |
| Successful | 1 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 1 |
| Total Rows Extracted | 131 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 1 |
| Files with Warnings Only | 0 |
| Files with Arithmetic Errors | 1 |
| Files with Grand Total Mismatch | 1 |
| Total Errors | 8 |
| Total Warnings | 17 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `MISSING_SUBTOTAL` | 9 |
| `SUBTOTAL_MISSING_LABEL` | 6 |
| `CITATION_VALUE_MISMATCH` | 6 |
| `BBOX_OUT_OF_RANGE` | 1 |
| `TOTAL_MISMATCH_FV` | 1 |
| `ROOT_TOTAL_MISMATCH_FV` | 1 |
| `DATE_MISMATCH` | 1 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000009521-04-000011`

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

- `0000009521-04-000011`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
