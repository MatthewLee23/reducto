# Batch #39 - Validation Summary

**Run:** Jan 08, 2026 at 04:30 PM

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 8 |
| Total Rows Extracted | 2366 |
| Total Validation Errors | 192 |
| Total Validation Warnings | 553 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 6 failures |
| Subtotals sum to grand total | 3 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `BBOX_PAGE_OUT_OF_RANGE` | 243 | See detailed report |
| `ROW_FROM_NON_SOI_PAGE` | 187 | See detailed report |
| `CITATION_VALUE_MISMATCH` | 174 | See detailed report |
| `BBOX_OUT_OF_RANGE` | 56 | See detailed report |
| `MISSING_SUBTOTAL` | 43 | See detailed report |
| `DATE_MISMATCH` | 7 | See detailed report |
| `NORMALIZATION_APPLIED` | 7 | See detailed report |
| `POSSIBLE_DUPLICATE_HOLDINGS` | 6 | See detailed report |
| `TOTAL_MISMATCH_FV` | 6 | See detailed report |
| `ROOT_TOTAL_MISMATCH_FV` | 3 | See detailed report |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000935069-05-000617`
- `0000936772-03-000287`
- `0000950156-06-000002`
- `0001233087-05-000018`
- `0001233087-08-000026`
- `0001379491-07-000103`

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000935069-05-000617`
- `0000936772-03-000287`
- `0000950156-06-000002`

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
