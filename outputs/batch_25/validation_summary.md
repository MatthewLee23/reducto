# Batch #25 - Validation Summary

**Run:** 20260107_094845

## Quick Stats

| Metric | Value |
|--------|-------|
| Files Validated | 5 |
| Total Rows Extracted | 599 |
| Total Validation Errors | 24 |
| Total Validation Warnings | 22 |

## Arithmetic Validation (Deterministic Checks)

These are **hard logic deterministic checks** that verify all numbers add up correctly:

| Check | Files with Issues |
|-------|-------------------|
| Holdings sum to subtotals | 0 failures |
| Subtotals sum to grand total | 0 failures |

## Top Issues

| Code | Count |
|------|-------|
| `CITATION_VALUE_MISMATCH` | 24 |
| `MISSING_SUBTOTAL` | 9 |
| `ORPHANED_TOTAL` | 7 |
| `DATE_MISMATCH` | 5 |
| `NORMALIZATION_APPLIED` | 1 |

## Files with Errors

- `0000009521-06-000021`
- `0000009521-08-000012`
