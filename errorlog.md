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

### 4. 0000900092-06-000075 (Deep Analysis - Batch 44)

**Error Summary:**
- `has_arithmetic_error`: true
- `error_count`: 77
- `warning_count`: 185
- `max_dollar_diff`: 12,189,308

**Key Arithmetic Errors (non-citation):**

1. **ARITH_MISMATCH_FV in Insurance section:**
   - Calculated fair_value: $15,394,328
   - Extracted subtotal: $3,205,020
   - Difference: $12,189,308

2. **SHIFTED_SUBTOTAL_DETECTED:**
   - Media subtotal ($13,440,797) appearing in Electric Utilities section
   - Electric Utilities calculated: $6,846,902
   - Difference: $6,593,895

3. **TOTAL_MISMATCH_PCT:**
   - Section percent: 22.0%
   - Total row: 23.2%
   - Difference: 1.2%

**Root Cause Analysis (Deep Investigation):**

**Issue 1: Insurance Section Mismatch ($12.2M diff)**

The Insurance section in "Preferred Securities > Preferred Stocks > Insurance" contains 10 holdings:
- Row 39: ACE Ltd. Series C, 7.80% ($2,088,000)
- Row 40: Aegon NV, 6.375% ($2,022,504)
- Row 41: Axis Capital Holdings Ltd., 7.25% ($190,400)
- Row 42: Endurance Specialty Holdings Ltd., 7.75% ($194,000)
- Row 43: Genworth Financial, Inc. Series A, 5.25% ($1,525,314)
- Row 44: Metlife, Inc. Series B, 6.50% ($1,866,240)
- Row 45: Prudential Plc, 6.75% ($2,061,600)
- Row 46: Zurich RegCaPS Funding Trust, 6.58% ($2,241,250)
- Row 47: Pacific Gas & Electric Co. Series A, 6% ($2,076,000) **<-- UTILITY, NOT INSURANCE**
- Row 48: Public Service Electric & Gas Series E, 5.28% ($1,129,020) **<-- UTILITY, NOT INSURANCE**

**Root Cause:** The Reducto API incorrectly assigned rows 47-48 (Pacific Gas & Electric and Public Service Electric & Gas) to the Insurance section path. These are **utility companies**, not insurance companies. The calculated sum includes these misassigned utilities ($15,394,328), but the extracted subtotal ($3,205,020) only covers actual insurance holdings.

This is an **upstream extraction/section path assignment issue** from the Reducto API, not a sanitization bug.

**Issue 2: Shifted Subtotal (Media -> Electric Utilities)**

- Row 234: "Electric Utilities" SUBTOTAL with fair_value_raw: $13,440,797
- But $13,440,797 is the **Media section total** (calculated from Media holdings)
- Electric Utilities holdings only sum to ~$6.8M

**Root Cause:** Section path misalignment from the Reducto API. The subtotal value is being assigned to the wrong section.

**Issue 3: SUMMARY_TABLE_BLOCK_DETECTED Dropping Legitimate Holdings**

27 rows were dropped with reason "SUMMARY_TABLE_BLOCK_DETECTED", including:
- Dresdner Funding Trust I, 8.151% ($1,229,484)
- Lloyds TSB Bank Plc, 6.90% ($2,032,600)
- Mizuho JGB Investment LLC, 9.87% ($3,317,826)
- SB Treasury Co. LLC, 9.40% ($3,285,372)
- Westpac Capital Trust III, 5.819% ($2,043,360)
- Total Capital Trusts ($11,908,642)
- Alexandria Real Estate Equities, Inc. ($1,332,760)
- ABN AMRO North America Capital Funding ($2,109,520)
- Southwest Gas Capital II, 7.70% ($1,047,544)
- Total Preferred Securities ($76,778,858)
- Municipal Bonds holdings and totals
- Short-Term Securities holdings

**Root Cause:** These rows are being dropped because they're in blocks with TOTAL rows that have low percentage values (< 50%). However, these are legitimate holdings that should not be dropped.

**Split Results Analysis:**

The split identified SOI pages as: 5, 6, 8, 11, 14, 15, 16, 17

**Missing pages:** 7, 9, 10, 12, 13 are NOT included in the SOI split. This is suspicious - if the SOI spans pages 5-17, why are some pages in the middle missing? This could be contributing to extraction issues.

**Conclusions:**

1. **Primary Issue:** Reducto API section path assignment errors (utilities assigned to Insurance, Media subtotal assigned to Electric Utilities)
2. **Secondary Issue:** SUMMARY_TABLE_BLOCK_DETECTED is still too aggressive, dropping legitimate holdings
3. **Tertiary Issue:** Split may be missing some SOI pages (7, 9, 10, 12, 13)

**Potential Fixes:**

1. **Cannot fix:** Section path misalignment is an upstream Reducto API issue
2. **Can investigate:** SUMMARY_TABLE_BLOCK_DETECTED logic may need refinement
3. **Can investigate:** Split gap-filling logic may need improvement

**Status:** Upstream extraction issue - limited fixes possible on our end

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

## Verification Results

Re-ran main.py on problematic PDFs in `pdfs-for-main-extraction/reruns/reruns-5/` (batch_43).

### 0000930413-05-005563.pdf - FIX VERIFIED

**Before (batch_42):**
- `has_arithmetic_error`: true
- `error_count`: 3
- 12 rows dropped by SUMMARY_TABLE_BLOCK_DETECTED
- `calculated_total_fv`: $85,617,420 (only 22% of actual)
- `extracted_total_fv`: $389,013,672

**After (batch_43 with fix):**
- `has_arithmetic_error`: **false**
- `error_count`: **0**
- Only 1 row dropped (legitimate "CASH AND OTHER ASSETS LESS LIABILITIES" total)
- `calculated_total_fv`: $389,013,672 (matches extracted)
- All holdings in "ORDINARY SHARES OF GOLD MINING COMPANIES" section (~$303M) are now preserved

### 0001133228-04-000267.pdf - VERIFICATION PENDING

The extraction for this file (19 pages) was still in progress when the batch was interrupted. Re-run required to verify the fix.

### Other Files (not affected by sanitizer fix)

- `0000828803-06-000009.pdf`: 4 errors, 5 warnings (expected - multi-fund complexity)
- `0001144204-05-006328.pdf`: 26 errors, 4 warnings (expected - citation alignment issues)
- `0000900092-06-000075.pdf`: Extraction still in progress when interrupted

## Reruns Completed

PDFs re-processed in `pdfs-for-main-extraction/reruns/reruns-5/`:
- [x] 0000930413-05-005563.pdf - **FIX VERIFIED**
- [x] 0000828803-06-000009.pdf - Completed (errors expected, not sanitizer-related)
- [x] 0001144204-05-006328.pdf - Completed (errors expected, not sanitizer-related)
- [ ] 0001133228-04-000267.pdf - Extraction interrupted, needs re-run
- [ ] 0000900092-06-000075.pdf - Extraction interrupted, needs re-run

---

# Batch 46 Analysis - Gap-Filling Fix

## Summary

Analyzed 7 out of 10 random PDFs from batch_46. Identified a **critical bug** where gap-filling was not being applied before extraction, causing severe partial extraction errors.

| File | Errors | Root Cause | Gap-Fill Applied |
|------|--------|------------|------------------|
| 0000935069-07-002406 | 25E | 12-page gap (4→17), only 22% coverage | Yes - added 12 pages |
| 0000928816-03-000653 | 23E | 11-page gap (9→21), only 6.9% coverage | Yes - added 15 pages |
| 0000930413-05-001717 | 8E | Calculated > extracted (duplicates?) | No gaps |
| 0001047469-04-000524 | 76E | Cost mismatches, missing holdings | No gaps |
| 0001233087-04-000005 | 61E | Calculated > extracted (duplicates?) | No gaps |
| 0000928816-03-000753 | 813E | MISSING_ROW_TYPE (structural) | Multiple gaps |
| 0000950136-08-003015 | 0E | Clean! | Multiple gaps |

## Critical Bug Found: Gap-Filling Not Applied Before Extraction

**Location:** `main.py`, `process_file()` function

**Problem:** The `fill_page_gaps()` and `validate_split_completeness()` functions were defined and called in `_validate_single_file()` (line 492), but NOT in `process_file()` where the actual extraction happens (line 602). This means:
1. The splitter identifies SOI pages with gaps (e.g., [2, 3, 4, 17, 18, 19])
2. The extraction uses these gapped pages directly
3. Gap-filling only happens during validation, which is too late - the extraction has already been done with incomplete pages

**Impact:** Files with large gaps in SOI pages have severe partial extraction errors:
- 0000935069-07-002406: Only 3.5%, 10.4%, 26.8% of holdings extracted (FUND_SEVERE_PARTIAL_EXTRACTION)
- 0000928816-03-000653: Missing $11.7M in holdings (TOTAL_MISMATCH_FV)

**Fix Applied:** Added gap-filling to `process_file()` after extracting SOI pages from split, BEFORE calling the extraction API:

```python
# CRITICAL: Apply gap-filling BEFORE extraction to capture continuation pages
original_page_count = len(soi_pages)

# First, validate split completeness (fills ALL gaps if coverage < 70%)
soi_pages = validate_split_completeness(soi_pages, verbose=True)

# Then apply standard gap-filling for remaining small gaps
soi_pages = fill_page_gaps(soi_pages, max_gap=MAX_PAGE_GAP, verbose=True)

# Log if we added pages
if len(soi_pages) > original_page_count:
    added_pages = len(soi_pages) - original_page_count
    print(f"  [GAP-FILL] {pdf_path.name} - Added {added_pages} pages (now {len(soi_pages)} total)")
```

**Why This Fix Is General (Not Overfitting):**
1. Gap-filling is a general technique that helps any document where the splitter misses continuation pages
2. The split quality warnings already show that gaps are a common problem across many PDFs
3. The fix uses existing functions (`fill_page_gaps`, `validate_split_completeness`) with reasonable defaults
4. The 70% coverage threshold for aggressive gap-filling is based on the observation that legitimate SOI sections are typically contiguous

## Verification (batch_47 - reruns-8)

Re-running main.py on 5 problematic PDFs with the gap-filling fix applied:

**Gap-Fill Results:**
- 0000935069-07-002406: 6 pages → 18 pages (+12 pages)
- 0000928816-03-000653: 7 pages → 22 pages (+15 pages)
- 0000930413-05-001717: 10 pages → 11 pages (+1 page)
- 0001047469-04-000524: 9 pages (no change - contiguous)
- 0001233087-04-000005: 9 pages (no change - contiguous)

**Validation Results:** Pending - Reducto API extraction in progress
