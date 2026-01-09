# Error Log - Batch 42 Arithmetic Error Investigation

This document tracks arithmetic errors found during validation of batch_42 extractions, their root causes, and fixes applied.

## Summary

| File | Error Type | Root Cause | Status |
|------|------------|------------|--------|
| 0000930413-05-005563 | SEVERE_PARTIAL_EXTRACTION | Sanitizer SUMMARY_TABLE_BLOCK_DETECTED bug (12 rows dropped) | **FIX REQUIRED** |
| 0001133228-04-000267 | SEVERE_SECTION_PARTIAL_EXTRACTION | Sanitizer SUMMARY_TABLE_BLOCK_DETECTED bug (28 rows dropped) | **FIX REQUIRED** |
| 0000828803-06-000009 | PARTIAL_EXTRACTION_FV, ZERO_EXTRACTION | Multi-fund document complexity | Lower priority |
| 0000900092-06-000075 | Multiple (80 errors) | Citation alignment issues | Lower priority |
| 0001144204-05-006328 | ROOT_TOTAL_MISMATCH_FV | Net assets includes non-holding items | Lower priority |
| 0001047469-04-036690 | ARITH_MISMATCH_PCT (minor) | Rounding error (0.03% diff) | Low priority |

**Key Finding:** The sanitizer's `drop_summary_tables()` function is the primary cause of arithmetic errors in 2 of 6 files. The `SUMMARY_TABLE_PERCENT_THRESHOLD = 80` is too aggressive and incorrectly flags legitimate SOI sections as summary tables.

---

## Detailed Analysis

### 1. 0000930413-05-005563

**Error Summary:**
- `has_arithmetic_error`: true
- `root_sum_mismatch`: true
- `calculated_total_fv`: 85,617,420
- `extracted_total_fv`: 389,013,672
- `max_dollar_diff`: 303,396,252

**Validation Issues:**
```json
{
  "code": "ROOT_TOTAL_MISMATCH_PCT",
  "message": "Grand total percent (21.5%) != extracted Total (97.9%), diff=76.4%"
},
{
  "code": "SEVERE_PARTIAL_EXTRACTION",
  "message": "CRITICAL: Only 22.0% of holdings extracted. Calculated $85617420 vs TOTAL $389013672. Missing ~$303396252."
}
```

**Root Cause Analysis:**

The sanitizer's `drop_summary_tables()` function incorrectly identified a legitimate SOI section as a "summary table" and dropped 12 rows.

**Document Structure:**
The PDF contains two main sections:
1. "ORDINARY SHARES OF GOLD MINING COMPANIES" - 76.4% of net assets (~$303M)
2. "ORDINARY SHARES OF OTHER COMPANIES" - 21.5% of net assets (~$85M)

**What the sanitizer did:**
The sanitizer dropped the ENTIRE first section because:
1. The TOTAL row for "ORDINARY SHARES OF GOLD MINING COMPANIES" has 76.4% (< 80% threshold)
2. The block has fewer than 20 holdings (about 11 holdings)

**Dropped rows (from normalization fix_log):**
- Row 0: "Newcrest Mining Limited - ADRS" (fv=$30,156,420)
- Row 1: "Newmont Mining Corporation" (fv=19,378,504)
- Row 2: "AngloGold Ashanti Limited" (fv=79,285,527)
- Row 3: "Gold Fields Limited" (fv=105,441,354)
- Row 4: "Harmony Gold Mining Company Limited" (fv=2,133,769)
- Row 5: "Harmony Gold Mining Company Limited - AD" (fv=16,572,960)
- Row 6: SUBTOTAL "Total SOUTH AFRICAN GOLD MINES" (fv=203,433,610)
- Row 7: "Barrick Gold Corporation" (fv=16,782,700)
- Row 8: "Placer Dome Incorporated" (fv=14,403,018)
- Row 9: SUBTOTAL "Total CANADIAN GOLD MINES" (fv=31,185,718)
- Row 10: "Compania de Minas Buenaventura - ADRS" (fv=19,242,000)
- Row 11: TOTAL "Total ORDINARY SHARES OF GOLD MINING COM" (fv=303,396,252)

**Why the current logic is wrong:**
The `SUMMARY_TABLE_PERCENT_THRESHOLD = 80` is too high. A legitimate SOI section can have 76.4% of net assets and still be valid. The sanitizer is designed to catch "Top 10 Holdings" summary tables (which typically show 30-50% of holdings), but it's catching legitimate sections.

**Proposed Fix:**
1. Lower `SUMMARY_TABLE_PERCENT_THRESHOLD` from 80 to 50 (or 40)
2. Add keyword detection for summary table labels (e.g., "Top", "Largest", "Holdings Summary")
3. Only drop blocks that BOTH have low percent AND have summary-like labels

**Status:** Fix pending

---

### 2. 0000828803-06-000009

**Error Summary:**
- `has_arithmetic_error`: true
- `error_count`: 28
- `warning_count`: 18
- `max_dollar_diff`: 33,970,077

**Key Issues:**
- PARTIAL_EXTRACTION_FV: Missing holdings in "SHORT TERM INVESTMENTS" section (49.3% extraction ratio)
- TOTAL_MISMATCH_PCT: Section percent mismatch (0.2% calculated vs 98.0% extracted)
- ZERO_EXTRACTION: "NET UNREALIZED GAIN ON FORWARD EXCHANGE CONTRACTS" has subtotal ($1,846,794) but NO holdings extracted

**Root Cause Analysis:**
This is a multi-fund document ("Templeton Global Income Fund"). The errors appear to be related to:
1. Multi-fund document structure causing section path confusion
2. Forward exchange contracts section may not be extractable as traditional holdings
3. Citation value mismatches suggest extraction alignment issues

**Status:** Lower priority - multi-fund document complexity, not sanitizer bug

---

### 3. 0001133228-04-000267

**Error Summary:**
- `has_arithmetic_error`: true
- `root_sum_mismatch`: true
- `calculated_total_fv`: 522,333,836
- `extracted_total_fv`: 531,674,434
- `max_dollar_diff`: 484,604,270

**Key Issues:**
- ROOT_TOTAL_MISMATCH_COST: Grand total cost mismatch ($484,604,270 diff)
- ROOT_TOTAL_MISMATCH_FV: Grand total FV mismatch ($9,340,598 diff)
- SEVERE_SECTION_PARTIAL_EXTRACTION: Only 18.1% of holdings extracted for "High Income Opportunity Fund Inc. > CORPORATE BONDS & NOTES"
- **28 rows dropped by SUMMARY_TABLE_BLOCK_DETECTED**

**Root Cause Analysis:**
Same bug as file #1 - the sanitizer's `drop_summary_tables()` function is incorrectly dropping legitimate holdings. The fix_log shows 28 rows dropped with reason "SUMMARY_TABLE_BLOCK_DETECTED", including legitimate holdings like:
- "Parker Drilling Co., Sub. Notes 5.500%" (fv=$412,050)
- "Amkor Technology, Inc., Sub. Notes 5.000" (fv=$1,913,175)
- "Sanmina-SCI Corp., Sub. Debentures 10.66" (fv=$2,318,131)
- "Northrop Grumman Corp., 7.250%" (fv=$175,746)
- "Alamosa Holdings, Inc., Series B 7.500%" (fv=$2,196,272)

**Status:** Will be fixed by lowering SUMMARY_TABLE_PERCENT_THRESHOLD

---

### 4. 0000900092-06-000075

**Error Summary:**
- `has_arithmetic_error`: true
- `error_count`: 80
- `warning_count`: 57
- `max_dollar_diff`: 586,479,155

**Key Issues:**
- 80 errors, mostly CITATION_VALUE_MISMATCH errors
- Many BBOX_PAGE_OUT_OF_RANGE warnings (bbox.page=11 outside [1, 10])
- Citation alignment issues throughout the document

**Root Cause Analysis:**
This file has extensive citation/extraction alignment issues. The BBOX_PAGE_OUT_OF_RANGE warnings suggest the extraction may have pulled data from pages outside the expected SOI range. The citation mismatches indicate the extracted values don't match the source text locations.

This is likely a Reducto API extraction issue rather than a sanitizer bug. The system correctly identified the data but the citations are misaligned.

**Status:** Lower priority - citation alignment issue, not sanitizer bug

---

### 5. 0001144204-05-006328

**Error Summary:**
- `has_arithmetic_error`: true
- `root_sum_mismatch`: true
- `calculated_total_fv`: 11,182,989
- `extracted_total_fv`: 11,721,829
- `max_dollar_diff`: 538,840

**Key Issues:**
- ROOT_TOTAL_MISMATCH_FV: Grand total mismatch ($538,840 diff)
- ROOT_TOTAL_MISMATCH_PCT: 95.40% calculated vs 100% extracted (4.6% diff)
- Multiple CITATION_VALUE_MISMATCH errors (33 citation errors)

**Root Cause Analysis:**
The extracted "Net assets" total ($11,721,829) is higher than the calculated sum of holdings ($11,182,989). This suggests:
1. The "Net assets" row may include items beyond just investment holdings (e.g., cash, receivables)
2. The 4.6% difference ($538,840) could be cash or other assets not captured as holdings
3. Citation mismatches indicate extraction alignment issues

**Status:** Lower priority - likely correct behavior (Net assets includes more than just holdings)

---

### 6. 0001047469-04-036690

**Error Summary:**
- `has_arithmetic_error`: true (minor)
- `error_count`: 1
- `max_dollar_diff`: 0

**Key Issue:**
- ARITH_MISMATCH_PCT: Calculated percent (0.13%) != extracted subtotal (0.1%), diff=0.03%

**Root Cause Analysis:**
This is a minor rounding error in percentage calculation. The extracted value "0.1%" is likely rounded from 0.13%. This is not a significant issue.

**Status:** Low priority - rounding error

---

## Fixes Applied

### Fix 1: Lower SUMMARY_TABLE_PERCENT_THRESHOLD and Add Keyword Detection

**File:** `soi_sanitize.py`
**Changes:**
1. Lowered `SUMMARY_TABLE_PERCENT_THRESHOLD` from 80% to 50%
2. Added `SUMMARY_TABLE_KEYWORDS` list for detecting summary table labels
3. Added `_has_summary_table_keyword()` function to check for keywords like "Top", "Largest", "Summary"
4. Updated `drop_summary_tables()` to use both percentage AND keyword detection

**Rationale:** 
- The 80% threshold was too aggressive and caught legitimate SOI sections
- A section with 76.4% of net assets ("ORDINARY SHARES OF GOLD MINING COMPANIES") was incorrectly flagged
- Lowering to 50% prevents false positives while still catching true summary tables (typically 30-50%)
- Keyword detection adds an additional signal for identifying summary tables

**Code Changes:**
```python
# Before
SUMMARY_TABLE_PERCENT_THRESHOLD = Decimal("80")

# After
SUMMARY_TABLE_PERCENT_THRESHOLD = Decimal("50")

# Added keyword detection
SUMMARY_TABLE_KEYWORDS = [
    "top ", "top-", "largest", "biggest", "holdings summary",
    "summary of", "highlights", "principal holdings", "major holdings",
]
```

---

## Reruns Required

After fixes are applied, the following PDFs need to be re-processed:
- [ ] 0000930413-05-005563.pdf
- [ ] 0000828803-06-000009.pdf
- [ ] 0001133228-04-000267.pdf
- [ ] 0000900092-06-000075.pdf
- [ ] 0001144204-05-006328.pdf
