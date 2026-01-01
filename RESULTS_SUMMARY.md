# Reducto Extraction Results Summary

## Investment Overview: $930 Spent

You ran **526 completed jobs** on Reducto. Here's what you got:

### Job Breakdown

| Job Type | Count | Description |
|----------|-------|-------------|
| **Split Jobs** | 327 | Identified which pages contain SOI tables |
| **Extract Jobs** | 374 | Attempted to extract data from SOI pages |
| **Successful Extractions** | 106 | Returned actual investment holdings |
| **Empty Extractions** | 268 | Returned no holdings data |

### Extraction Results

From the 106 successful extractions:

- **8,634 individual investment holdings** extracted
- **2,519 subtotal/category rows** extracted  
- **$1.83 billion** in tracked fair value
- **Average 45 rows per file**

### Data Quality

| Field | Coverage |
|-------|----------|
| Section/Category | 99.8% |
| Fair Value | 33.7% |
| Quantity | 33.7% |
| Interest Rate | 27.1% |
| Maturity Date | 25.2% |

### Top Investment Categories

1. Municipal Bonds > Health Care: 646 holdings
2. Stocks & Convertible Securities > Energy: 292 holdings
3. New York (municipal): 243 holdings
4. Secondary Investment Funds > North America: 184 holdings
5. Long-Term Investments > Common Stocks: 183 holdings

---

## Why 268 Extractions Returned Empty?

After investigating, the empty extractions have `soi_rows: []` but did successfully identify the document metadata (title, date). Causes:

### 1. Table Structure Mismatch
The extraction schema expects specific field names, but SEC filings use many different formats:
- Some use "Par Value" vs "Face Amount"
- Some use "Market Value" vs "Fair Value"
- Column orders vary widely

### 2. Page Range Issues
The split job may have identified pages that contain SOI *mentions* but not the actual table data.

### 3. Schema Strictness
The extraction schema may require fields that aren't present in all documents.

---

## Files & Exports

All your data is now organized:

| Location | Contents |
|----------|----------|
| `extract_urls/` | All extract responses (703 files) |
| `split_results/` | Split job results (if organized) |
| `analysis_reports/all_holdings.csv` | **8,634 holdings as CSV** |
| `analysis_reports/holdings_summary.json` | Summary statistics |
| `validation_results/` | Validation reports |

---

## Recommendations for Future Runs

### 1. Use a More Flexible Schema

Instead of requiring specific fields, use a description-based approach:

```python
extract_config = {
    "description": """
    Extract all rows from the Schedule of Investments table.
    For each investment, extract:
    - Investment name/description
    - Quantity (shares, par value, or principal)
    - Fair value / market value
    - Any interest rate or coupon
    - Maturity date if applicable
    - Cost basis if available
    """,
    "table_format": "auto"
}
```

### 2. Make Fields Optional

All fields should be nullable since not all documents have all data:

```python
schema = {
    "investment": {"type": "string"},
    "fair_value": {"type": "number", "nullable": True},
    "cost": {"type": "number", "nullable": True},
    "quantity": {"type": "number", "nullable": True},
    "rate": {"type": "string", "nullable": True},
    "maturity": {"type": "string", "nullable": True}
}
```

### 3. Verify Split Results First

Before running extract on all files, verify that split correctly identifies SOI pages:
- Run split on 10 sample PDFs
- Manually check if the right pages are identified
- Adjust split config if needed

### 4. Use Tolerance for Validation

For arithmetic checks, accept 0.5-1% tolerance due to:
- Rounding differences
- Footnote adjustments
- Presentation differences

---

## Using Your Extracted Data

The `analysis_reports/all_holdings.csv` file contains all 8,634 holdings with:

- `file`: Source document ID
- `investment`: Investment name
- `fair_value`: Numeric fair value (when parseable)
- `quantity`: Shares/par value
- `section_path`: Category hierarchy
- `interest_rate`: Rate if available
- `maturity_date`: Maturity if available

### Example Python Usage

```python
import pandas as pd

# Load all holdings
df = pd.read_csv('analysis_reports/all_holdings.csv')

# Filter by category
munis = df[df['section_path'].str.contains('Municipal', case=False)]

# Get total fair value by section
by_section = df.groupby('section_path')['fair_value'].sum().sort_values(ascending=False)
```

---

## Cost Analysis

- **Total Spent**: $930
- **Successful Extractions**: 106 files
- **Total Holdings**: 8,634
- **Cost per File**: $8.77
- **Cost per Holding**: $0.11

If you re-run with an optimized schema on the 268 empty files, you could potentially extract another ~12,000 holdings.

---

## Your Extraction Config Analysis

Your `extract.py` config is **well designed**:
- All fields are nullable
- Uses flexible `_raw` fields for exact text capture
- Good system prompt with clear instructions
- Tracks section hierarchy

### Why Some Files Still Returned Empty

The 268 empty files likely have:

1. **Different PDF structure**: Some SEC filings embed SOI as images or complex layouts
2. **Split page mismatch**: The split job may have identified pages with "Schedule of Investments" text but not the actual tables
3. **Multi-document filings**: Some N-CSR files contain multiple fund reports; split may have found one but extraction targeted another

### Next Steps to Improve

1. **Review split results** for failed files - check if the right pages were identified
2. **Manual spot-check** - open a few failed PDFs to see their structure
3. **Consider table_only mode** - if tables are the primary target

---

## Scripts You Now Have

| Script | Purpose |
|--------|---------|
| `download_all_jobs.py` | Download results from all Reducto jobs |
| `analyze_holdings.py` | Analyze extracted holdings and export CSV |
| `validate_existing.py` | Run validation on existing extractions |
| `learning_report.py` | Generate learning insights |
| `check_jobs.py` | Check/cancel running Reducto jobs |
| `main.py` | Main batch processor |

Run `python analyze_holdings.py` anytime to regenerate the CSV export.

