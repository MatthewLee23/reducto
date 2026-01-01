# Batch #3 - Validation Summary

**Run:** 20251227_135549

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 14 |
| Total Rows Extracted | 1938 |
| Total Validation Errors | 104 |
| Total Validation Warnings | 194 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 8 failures |
| Subtotals sum to grand total | 6 failures |

## Top Issues

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 93 |
| `SUBTOTAL_MISSING_LABEL` | 80 |
| `SUBTOTAL_PATH_MISMATCH` | 39 |
| `MISSING_SUBTOTAL` | 24 |
| `BBOX_PAGE_OUT_OF_RANGE` | 18 |
| `DATE_MISMATCH` | 14 |
| `ORPHANED_TOTAL` | 7 |
| `BBOX_OUT_OF_RANGE` | 7 |
| `ROOT_TOTAL_MISMATCH_FV` | 6 |
| `TOTAL_PATH_MISMATCH` | 3 |
| `ARITH_MISMATCH_FV` | 2 |
| `TOTAL_MISMATCH_FV` | 2 |
| `TOTAL_MISSING_NUMERIC` | 2 |
| `ROOT_TOTAL_MISMATCH_COST` | 1 |

## Files with Errors

- `0000002230-03-000010`
- `0000002230-04-000031`
- `0000002230-05-000014`
- `0000002230-05-000033`
- `0000002230-06-000011`
- `0000002230-07-000025`
- `0000002230-07-000062`
- `0000002230-08-000027`
- `0000002230-08-000057`
- `0000002230-09-000035`
- `0000009521-03-000025`

## Files with Arithmetic Errors

- `0000002230-03-000010`
- `0000002230-04-000031`
- `0000002230-05-000014`
- `0000002230-05-000033`
- `0000002230-06-000011`
- `0000002230-07-000025`
- `0000002230-09-000035`
- `0000009521-03-000025`
