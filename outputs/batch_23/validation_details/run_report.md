# Batch #23 - Run Report

**Run:** Jan 06, 2026 at 02:33 PM

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 2 |
| Successful | 2 |
| Skipped | 0 |
| **Failed (Errors)** | **0** |
| Validated | 2 |
| Total Rows Extracted | 237 |

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 2 |
| Files with Warnings Only | 0 |
| Files with Arithmetic Errors | 1 |
| Files with Grand Total Mismatch | 0 |
| Total Errors | 25 |
| Total Warnings | 4 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 21 |
| `TOTAL_MISMATCH_FV` | 2 |
| `TOTAL_MISMATCH_COST` | 2 |
| `ORPHANED_TOTAL` | 2 |
| `DATE_MISMATCH` | 2 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

- `0000009521-04-000022`

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
