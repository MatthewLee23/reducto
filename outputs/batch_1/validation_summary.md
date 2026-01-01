# Validation Summary

**Run Timestamp:** 20251221_212902

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 75 |
| Total Rows Extracted | 13699 |
| Total Validation Errors | 717 |
| Total Validation Warnings | 13832 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 67 failures |
| Subtotals sum to grand total | 62 failures |

## Top Issues

| Code | Count | Description |
|------|-------|-------------|
| `BBOX_PAGE_OUT_OF_RANGE` | 11487 | See detailed report |
| `CITATION_VALUE_MISMATCH` | 1058 | See detailed report |
| `MISSING_SUBTOTAL` | 875 | See detailed report |
| `MISSING_ROW_TYPE` | 501 | Row is missing required type field |
| `SUBTOTAL_MISSING_LABEL` | 277 | See detailed report |
| `ARITH_MISMATCH_FV` | 135 | Fair value sum doesn't match subtotal |
| `DATE_MISMATCH` | 75 | See detailed report |
| `TOTAL_MISSING_NUMERIC` | 58 | See detailed report |
| `GRAND_TOTAL_MISMATCH_FV` | 57 | Holdings don't sum to grand total (fair value) |
| `GRAND_TOTAL_MISMATCH_COST` | 13 | Holdings don't sum to grand total (cost) |

## Files with Arithmetic Errors

These files have holdings that don't sum to their subtotals:

- `0000002230-04-000031`
- `0000002230-04-000040`
- `0000002230-05-000014`
- `0000002230-05-000033`
- `0000002230-06-000011`
- `0000002230-06-000044`
- `0000002230-07-000062`
- `0000002230-08-000027`
- `0000002230-08-000057`
- `0000002230-09-000035`
- `0000009521-03-000025`
- `0000009521-04-000011`
- `0000009521-04-000022`
- `0000009521-05-000006`
- `0000009521-05-000013`
- `0000009521-06-000021`
- `0000078713-08-000045`
- `0000078713-10-000003`
- `0000078713-10-000076`
- `0000078713-11-000073`
- ... and 47 more

## Files with Grand Total Mismatch

These files have holdings that don't sum to the reported grand total:

- `0000002230-04-000031`
- `0000002230-04-000040`
- `0000002230-05-000014`
- `0000002230-05-000033`
- `0000002230-06-000011`
- `0000002230-06-000044`
- `0000002230-07-000062`
- `0000002230-08-000027`
- `0000002230-08-000057`
- `0000002230-09-000035`
- `0000009521-03-000025`
- `0000009521-04-000011`
- `0000009521-04-000022`
- `0000009521-05-000006`
- `0000009521-05-000013`
- `0000009521-06-000021`
- `0000078713-08-000045`
- `0000078713-10-000003`
- `0000078713-12-000001`
- `0000078713-13-000015`
- ... and 42 more

## Detailed Reports

For full details, see:

- `validation_details/run_report.json` - Complete machine-readable report
- `validation_details/run_report.md` - Full human-readable report
- `validation_details/batch_report.csv` - Per-file analysis spreadsheet
- `validation_details/<filename>_validation.json` - Per-file validation details
