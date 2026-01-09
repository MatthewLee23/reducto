# Batch #37 - Validation Summary

**Run:** 20260108_140514

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 10 |
| Total Rows Extracted | 2455 |
| Total Validation Errors | 614 |
| Total Validation Warnings | 696 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 8 failures |
| Subtotals sum to grand total | 5 failures |

## Top Issues

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 589 |
| `ROW_FROM_NON_SOI_PAGE` | 496 |
| `BBOX_PAGE_OUT_OF_RANGE` | 163 |
| `BBOX_OUT_OF_RANGE` | 14 |
| `DATE_MISMATCH` | 9 |
| `MISSING_SUBTOTAL` | 7 |
| `ARITH_MISMATCH_PCT` | 7 |
| `ROOT_TOTAL_MISMATCH_FV` | 5 |
| `TOTAL_PATH_MISMATCH` | 5 |
| `TOTAL_MISMATCH_FV` | 5 |
| `TOTAL_MISMATCH_PCT` | 3 |
| `ROOT_TOTAL_MISMATCH_COST` | 2 |
| `ROOT_TOTAL_MISMATCH_PCT` | 1 |
| `NORMALIZATION_APPLIED` | 1 |
| `ORPHANED_TOTAL` | 1 |

## Files with Errors

- `0000935069-03-001603`
- `0000935069-05-000617`
- `0000936772-03-000287`
- `0000950156-06-000002`
- `0001233087-05-000018`
- `0001233087-08-000026`
- `0001379491-07-000103`
- `0001445546-15-000766`

## Files with Arithmetic Errors

- `0000935069-03-001603`
- `0000935069-05-000617`
- `0000936772-03-000287`
- `0000950156-06-000002`
- `0001233087-05-000018`
- `0001233087-08-000026`
- `0001379491-07-000103`
- `0001445546-15-000766`
