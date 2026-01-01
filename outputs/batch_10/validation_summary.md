# Batch #10 - Validation Summary

**Run:** 20251230_124529

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 1 |
| Total Rows Extracted | 131 |
| Total Validation Errors | 7 |
| Total Validation Warnings | 18 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 1 failures |
| Subtotals sum to grand total | 0 failures |

## Top Issues

| Code | Count |
|------|-------|
| `MISSING_SUBTOTAL` | 9 |
| `SUBTOTAL_MISSING_LABEL` | 6 |
| `CITATION_VALUE_MISMATCH` | 6 |
| `BBOX_OUT_OF_RANGE` | 1 |
| `ARITH_MISMATCH_FV` | 1 |
| `DATE_MISMATCH` | 1 |
| `NORMALIZATION_APPLIED` | 1 |

## Files with Errors

- `0000009521-04-000011`

## Files with Arithmetic Errors

- `0000009521-04-000011`
