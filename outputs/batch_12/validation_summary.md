# Batch #12 - Validation Summary

**Run:** 20251231_132418

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 10 |
| Total Rows Extracted | 322 |
| Total Validation Errors | 19 |
| Total Validation Warnings | 25 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 2 failures |
| Subtotals sum to grand total | 1 failures |

## Top Issues

| Code | Count |
|------|-------|
| `SUBTOTAL_PATH_MISMATCH` | 10 |
| `DATE_MISMATCH` | 8 |
| `CITATION_VALUE_MISMATCH` | 7 |
| `ARITH_MISMATCH_PCT` | 4 |
| `ORPHANED_TOTAL` | 4 |
| `TOTAL_MISMATCH_PCT` | 2 |
| `TOTAL_MISMATCH_FV` | 2 |
| `TOTAL_MISSING_NUMERIC` | 1 |
| `SUSPICIOUS_NEGATIVE_PERCENT` | 1 |
| `NORMALIZATION_APPLIED` | 1 |
| `TOTAL_MISMATCH_COST` | 1 |
| `ROOT_TOTAL_MISMATCH_FV` | 1 |
| `ROOT_TOTAL_MISMATCH_COST` | 1 |
| `ROOT_TOTAL_MISMATCH_PCT` | 1 |

## Files with Errors

- `0000009521-04-000011`
- `0000009521-04-000022`

## Files with Arithmetic Errors

- `0000009521-04-000011`
- `0000009521-04-000022`
