# Batch Run Report

**Run Timestamp:** 20251221_212902

## Summary

| Metric | Count |
|--------|-------|
| Total Files | 82 |
| Successful | 75 |
| Skipped | 0 |
| **Failed (Errors)** | **7** |
| Validated | 75 |
| Total Rows Extracted | 13699 |

## Processing Errors (7 files)

These files failed during upload/split/extract:

1. **0000009521-07-000011.txt**: `Error code: 400 - {'detail': "Job failed. Reason: Error in post-processing: 4 validation errors for ExtractResultItem\ncitations.0.CitationBlock\n  In`
2. **0000009521-07-000020.txt**: `Error code: 400 - {'detail': "Job failed. Reason: Error in post-processing: 2 validation errors for ExtractResultItem\ncitations.0.CitationBlock\n  In`
3. **0000078713-11-000003.txt**: `Error code: 400 - {'detail': "Job failed. Reason: Error in post-processing: 6 validation errors for ExtractResultItem\ncitations.0.CitationBlock\n  In`
4. **0000078713-13-000099.txt**: `Error code: 400 - {'detail': "Job failed. Reason: Error in post-processing: 4 validation errors for ExtractResultItem\ncitations.0.CitationBlock\n  In`
5. **0000276300-04-000023.txt**: `Error code: 400 - {'detail': "Job failed. Reason: Error in post-processing: 1 validation error for ExtractResultItem\ncitations\n  Input should be a v`
6. **0000276776-17-000048.txt**: `Error code: 400 - {'detail': "Job failed. Reason: Error in post-processing: 4 validation errors for ExtractResultItem\ncitations.0.CitationBlock\n  In`
7. **0000351786-03-000005.txt**: `Error code: 400 - {'detail': "Job failed. Reason: Error in post-processing: 1 validation error for ExtractResultItem\ncitations\n  Input should be a v`

## Validation Results

| Metric | Count |
|--------|-------|
| Files with Errors | 68 |
| Files with Warnings Only | 7 |
| Files with Arithmetic Errors | 67 |
| Files with Grand Total Mismatch | 62 |
| Total Errors | 717 |
| Total Warnings | 13832 |

### Top Validation Issue Codes

| Code | Count |
|------|-------|
| `BBOX_PAGE_OUT_OF_RANGE` | 11487 |
| `CITATION_VALUE_MISMATCH` | 1058 |
| `MISSING_SUBTOTAL` | 875 |
| `MISSING_ROW_TYPE` | 501 |
| `SUBTOTAL_MISSING_LABEL` | 277 |
| `ARITH_MISMATCH_FV` | 135 |
| `DATE_MISMATCH` | 75 |
| `TOTAL_MISSING_NUMERIC` | 58 |
| `GRAND_TOTAL_MISMATCH_FV` | 57 |
| `GRAND_TOTAL_MISMATCH_COST` | 13 |
| `ARITH_MISMATCH_COST` | 4 |
| `GRAND_TOTAL_MISMATCH_PCT` | 4 |
| `MULTIPLE_NUMERIC_TOKENS` | 3 |
| `HOLDING_MISSING_INVESTMENT` | 2 |

### Files with Arithmetic Errors

These files have math that doesn't add up:

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
- `0000078713-12-000001`
- `0000078713-13-000015`
- `0000088053-05-001116`
- `0000088053-05-001117`
- `0000088053-05-001449`
- `0000088053-17-001401`
- `0000216851-03-000005`
- `0000216851-04-000013`
- `0000216851-04-000018`
- `0000216851-05-000016`
- ... and 37 more

### Files with Grand Total Mismatch

Holdings don't sum to reported total:

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
- `0000088053-05-001116`
- `0000088053-05-001117`
- `0000088053-05-001449`
- `0000088053-17-001401`
- `0000216851-03-000005`
- `0000216851-04-000013`
- `0000216851-04-000018`
- `0000216851-05-000016`
- `0000216851-06-000012`
- `0000216851-06-000041`
- ... and 32 more

## Output Files

- **Full JSON Report**: `validation_details/run_report.json`
- **CSV Report**: `validation_details/batch_report.csv`
- **Per-file Validations**: `validation_details/<stem>_validation.json`
