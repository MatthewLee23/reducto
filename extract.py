from typing import Any, Dict, List


def _build_parsing_config(pages: List[int]) -> Dict[str, Any]:
    """Construct the parsing config matching the parse.py settings."""
    parsing_config: Dict[str, Any] = {
        "enhance": {
            "agentic": [
                {"scope": "text"},
                {
                    "scope": "table",
                    "prompt": (
                        "CRITICAL OCR RULES FOR PERCENTAGE VALUES:\n"
                        "1. The '%' symbol must NEVER be misread as '8'. Examples:\n"
                        "   - '1.3%' is correct, '1.38' is WRONG (the 8 is a misread %)\n"
                        "   - '1.6%' is correct, '1.68' is WRONG\n"
                        "   - '7.9%' is correct, '7.98' is WRONG\n"
                        "2. Category headers like 'Automotive - 1.38' should be parsed as:\n"
                        "   - Category name: 'Automotive'\n"
                        "   - Percentage: '1.3%' (correcting the misread 8 to %)\n"
                        "3. Dashes between category names and percentages are SEPARATORS, not minus signs.\n\n"
                        "Extract Schedule of Investments tables from SEC N-CSR/N-CSRS. "
                        "Preserve merged headers, multi-line security descriptions, and "
                        "page-spanning tables. Keep numeric columns aligned "
                        "(Principal/Shares, Cost, Fair Value, %Net Assets, Interest Rate, Maturity)."
                    ),
                },
            ],
            "summarize_figures": False,
        },
        "retrieval": {
            "chunking": {"chunk_mode": "disabled"},
            "filter_blocks": ["Footer", "Page Number"],
            "embedding_optimized": False,
        },
        "formatting": {
            "add_page_markers": True,
            "table_output_format": "html",
            "merge_tables": True,
            "include": [],
        },
        "settings": {
            "ocr_system": "standard",
            "force_url_result": True,
            "persist_results": True,
            "return_images": ["table"],
        },
    }

    if pages:
        min_page = min(pages)
        max_page = max(pages)
        parsing_config["settings"]["page_range"] = {"start": min_page, "end": max_page}

    return parsing_config


def get_extract_config(remote_input: str, pages: List[int]) -> Dict[str, Any]:
    """Create the extract configuration using Reducto SDK settings."""
    parsing_config = _build_parsing_config(pages)

    system_prompt = (
        "You are extracting the Schedule of Investments (SOI) from a U.S. registered "
        "tender offer / interval fund N-CSR or N-CSRS report.\n\n"
        "============================================================\n"
        "PERCENTAGE ACCURACY RULES (HIGHEST PRIORITY - READ FIRST)\n"
        "============================================================\n\n"
        "*** RULE 1: ZERO TOLERANCE FOR '%' MISREAD AS '8' ***\n"
        "The '%' symbol must NEVER be misread as the digit '8'. This is the #1 source of errors.\n"
        "SPECIFIC EXAMPLES OF MISREADS TO AVOID:\n"
        "- '1.3%' is '1.3%', NOT '1.38'\n"
        "- '1.6%' is '1.6%', NOT '1.68'\n"
        "- '2.7%' is '2.7%', NOT '2.78'\n"
        "- '7.9%' is '7.9%', NOT '7.98'\n"
        "- '11.7%' is '11.7%', NOT '11.78'\n"
        "- '20.2%' is '20.2%', NOT '20.28'\n\n"
        "*** RULE 2: DECIMAL PRECISION CONSISTENCY ***\n"
        "All percentage values in a document should have CONSISTENT decimal precision.\n"
        "If the TOTAL row shows '20.2%' (1 decimal place), then ALL percentages should have 1 decimal.\n"
        "DETECTION: If you extract a percentage with MORE decimal places than the Total, AND it ends in '8',\n"
        "you have misread the '%' as '8'. Correct it immediately.\n"
        "EXAMPLES:\n"
        "- Total is '20.2%' (1 decimal) and you extracted '1.38' (2 decimals ending in 8) → FIX to '1.3%'\n"
        "- Total is '81.9%' (1 decimal) and you extracted '11.78' (2 decimals ending in 8) → FIX to '11.7%'\n"
        "- Total is '100.0%' (1 decimal) and you extracted '2.28' (2 decimals ending in 8) → FIX to '2.2%'\n"
        "ALWAYS include the '%' sign in percent_net_assets_raw values.\n\n"
        "*** RULE 3: CATEGORY HEADER SPLITTING (CRITICAL) ***\n"
        "When a section/category heading contains BOTH a name AND a percentage, you MUST:\n"
        "1. Put ONLY the category name in 'label' (no numbers, no dashes, no '%' signs)\n"
        "2. Put the percentage (with '%' sign) in 'percent_net_assets_raw'\n"
        "3. Apply the OCR correction from Rules 1-2 to the percentage\n\n"
        "EXAMPLES OF MANGLED HEADERS AND CORRECT EXTRACTION:\n"
        "- 'Automotive - 1.38' → label='Automotive', percent_net_assets_raw='1.3%' (8 is misread %)\n"
        "- 'Health Care -- 1.68' → label='Health Care', percent_net_assets_raw='1.6%' (8 is misread %)\n"
        "- 'Consumer Goods 2.28' → label='Consumer Goods', percent_net_assets_raw='2.2%'\n"
        "- 'Retail 7.98' → label='Retail', percent_net_assets_raw='7.9%'\n"
        "- 'Entertainment -- 1.08' → label='Entertainment', percent_net_assets_raw='1.0%'\n"
        "- 'Financial and Insurance - 1.98' → label='Financial and Insurance', percent_net_assets_raw='1.9%'\n"
        "- 'Technology -- 11.2%' → label='Technology', percent_net_assets_raw='11.2%'\n"
        "- 'Banking/Savings and Loan -- 8.2%' → label='Banking/Savings and Loan', percent_net_assets_raw='8.2%'\n\n"
        "WATCH FOR: Numbers at the END of a category name are almost always percentages.\n"
        "The percentage should NEVER be part of the label text.\n\n"
        "*** RULE 4: HYPHEN/DASH SEPARATOR DISAMBIGUATION ***\n"
        "Dashes/hyphens between a category name and percentage are SEPARATORS, not minus signs.\n"
        "STRIP THEM from both the label and the percentage value.\n"
        "- 'Automotive - 1.38' → The dash is a separator. label='Automotive' (no trailing dash)\n"
        "- 'Banking/Savings and Loan -- 1.8%' → label='Banking/Savings and Loan', pct='1.8%' (NOT '-1.8%')\n"
        "- 'Category - 5.2%' → label='Category', pct='5.2%' (NOT '-5.2%')\n"
        "A NEGATIVE value is indicated ONLY by parentheses or a minus directly attached: '(1.8%)' or '-1.8%'\n"
        "If there is WHITESPACE between the dash and the number, it is a separator.\n\n"
        "============================================================\n"
        "STRICT HEADER REJECTION (CRITICAL - ZERO TOLERANCE)\n"
        "============================================================\n\n"
        "*** BLACKLISTED STRINGS - NEVER USE AS INVESTMENT OR LABEL ***\n"
        "The following strings are COLUMN HEADERS, not investments or securities.\n"
        "If you see these strings, they are TABLE STRUCTURE, not data to extract:\n\n"
        "BLACKLIST (case-insensitive):\n"
        "  - 'Principal Amount'\n"
        "  - 'Principal Amount:'\n"
        "  - 'Value'\n"
        "  - 'Value (Note 1)'\n"
        "  - 'Value (Note 1):'\n"
        "  - 'Shares'\n"
        "  - 'Cost'\n"
        "  - 'Fair Value'\n"
        "  - 'Par Amount'\n"
        "  - 'Par Value'\n"
        "  - 'Units'\n"
        "  - 'Notional'\n"
        "  - '% of Net Assets'\n"
        "  - 'Maturity'\n"
        "  - 'Rate'\n"
        "  - 'Interest Rate'\n\n"
        "ENFORCEMENT RULES:\n"
        "1. If the 'investment' field would contain ANY of these blacklisted strings,\n"
        "   DO NOT emit the row. It is a header, not a holding.\n"
        "2. If the 'label' field would contain ANY of these blacklisted strings,\n"
        "   DO NOT emit the row. It is a header, not a subtotal.\n"
        "3. A number appearing NEXT TO a blacklisted header string is NOT a fair_value.\n"
        "   Example: 'Value (Note 1): 8,169,847' is a HEADER with a stray number, not a holding.\n\n"
        "*** SECURITY NAME SANITY CHECK (CRITICAL) ***\n"
        "An 'investment' name can NEVER be just a column header or numeric quantity.\n"
        "BEFORE emitting any HOLDING row, verify the investment field passes these checks:\n\n"
        "1. NOT A HEADER: The investment name must NOT be 'Principal Amount', 'Principal Amount:',\n"
        "   'Value', 'Shares', 'Cost', 'Fair Value', or any column header text.\n"
        "2. NOT A NUMERIC QUANTITY: The investment name must NOT be primarily numeric.\n"
        "   - INVALID: '$1,500,000', '8,169,847', '500,000 shares'\n"
        "   - VALID: 'Company X $1,500,000 5% 2025' (numeric is part of bond description)\n"
        "3. CONTAINS ISSUER NAME: The investment MUST contain an identifiable company, fund,\n"
        "   or entity name that could be looked up on Bloomberg/EDGAR.\n"
        "   - VALID: 'Lucent Technologies 2.75% 2023 cv. sr. deb.'\n"
        "   - INVALID: 'Principal Amount: 8,169,847' (no issuer name)\n\n"
        "IF THE SECURITY NAME IS MISSING OR LOOKS LIKE A HEADER:\n"
        "- Look ABOVE the current row for the actual security name\n"
        "- Look on the PREVIOUS page for continued holdings\n"
        "- The security name may be on a separate line from the numeric values\n"
        "- NEVER emit a holding where you cannot identify the issuer/company name\n\n"
        "*** PAGE-TOP HEADER REPETITION (CRITICAL) ***\n"
        "When tables span multiple pages, column headers are often REPEATED at the top of each page.\n"
        "These repeated headers look like:\n"
        "  - 'Principal Amount' | [blank] | 'Value (Note 1)'\n"
        "  - 'Shares' | 'Cost' | 'Fair Value'\n"
        "If you see these patterns at the TOP of a page (first 1-3 rows), they are HEADERS.\n"
        "DO NOT extract them as HOLDING or SUBTOTAL rows.\n\n"
        "VISUAL CONTEXT RULE:\n"
        "If a numeric value appears directly adjacent to or below column header text\n"
        "(like 'Principal Amount: 8,169,847'), this is OCR noise from the header row.\n"
        "It is NOT a valid fair_value for a holding. IGNORE IT.\n\n"
        "SPECIFIC FAILURE MODE TO AVOID:\n"
        "  WRONG: row_type='HOLDING', investment='Principal Amount:', fair_value_raw='8,169,847'\n"
        "  WRONG: row_type='HOLDING', investment='Principal Amount: ', fair_value_raw='8,169,847'\n"
        "  WRONG: row_type='SUBTOTAL', label='Value (Note 1)', fair_value_raw='8,169,847'\n"
        "  These are ALL incorrect. The model extracted a HEADER as if it were data.\n"
        "  The value 8,169,847 in this context is NOT a real subtotal - it's OCR artifact.\n\n"
        "============================================================\n"
        "ARITHMETIC CONSISTENCY & COMPLETENESS\n"
        "============================================================\n\n"
        "*** INDUSTRY/SECTOR CHECKLIST RULE (CRITICAL) ***\n"
        "1. At the START of extraction, identify any 'Major Industry Exposure' or 'Sector Breakdown'\n"
        "   summary table at the beginning of the report. This table lists all industries/categories\n"
        "   with their percentage allocations.\n"
        "2. For EVERY industry/category listed there with a percentage > 0.1%, you MUST find\n"
        "   corresponding holdings in the detailed Schedule of Investments.\n"
        "3. If you reach the end of an asset class (e.g., 'CONVERTIBLE BONDS AND NOTES') and the sum\n"
        "   of your extracted sub-categories does not match the asset class total, you are likely\n"
        "   MISSING a category that appears in the summary table.\n"
        "4. CROSS-REFERENCE: After extracting each asset class, compare your sub-category list against\n"
        "   the summary table. If 'Telecommunications -- 7.1%' appears in the summary but you have\n"
        "   no 'Telecommunications' holdings under 'CONVERTIBLE BONDS AND NOTES', re-scan for it.\n\n"
        "*** ASSET CLASS TOTAL ANCHORING (CRITICAL) ***\n"
        "When you encounter a top-level asset class heading with a percentage:\n"
        "  e.g., 'CONVERTIBLE BONDS AND NOTES -- 53.6%'\n"
        "This is your 'Anchor Total' for that section.\n"
        "1. As you extract sub-categories (Advertising, Aerospace, Telecommunications, etc.),\n"
        "   their percentages MUST sum up to this Anchor Total (within rounding tolerance of ~0.5%).\n"
        "2. If they do not sum correctly, you have MISSED a sub-category or MISREAD a percentage.\n"
        "3. RE-SCAN immediately: Look for industry headings you may have skipped, especially:\n"
        "   - Headings that appear at the top of a new page (often missed due to page breaks)\n"
        "   - Headings with unusual formatting or that span multiple lines\n"
        "   - Industries listed in the summary table that you haven't encountered yet\n\n"
        "1. TOTAL MATCHING RULE: The sum of 'fair_value_raw' for all HOLDING rows in a section\n"
        "   MUST equal the section's TOTAL row. Before emitting a TOTAL row, mentally verify:\n"
        "   - Sum all fair_value_raw from HOLDING rows under that section\n"
        "   - Compare with the TOTAL row's fair_value_raw\n"
        "   - If they don't match, you have MISSED HOLDINGS or MISREAD VALUES. Go back and find them.\n"
        "   EXAMPLE: If 'TOTAL CONVERTIBLE BONDS AND NOTES' shows $61,987,411 but you only extracted\n"
        "   holdings summing to $53,307,084, you are MISSING $8,680,327 worth of holdings.\n"
        "   This is a CRITICAL ERROR. Re-scan ALL pages for missing rows.\n\n"
        "2. NO SKIPPED PAGES: You MUST scan EVERY page in the provided page range thoroughly.\n"
        "   - Do NOT assume a page is empty just because the previous page had a section total.\n"
        "   - Do NOT skip pages that appear to only have continuation data.\n"
        "   - Sections like 'CONVERTIBLE BONDS AND NOTES' often span 3-5 pages. Extract ALL holdings.\n"
        "   - If you see 'CONVERTIBLE BONDS AND NOTES -- (continued)' at the top of a page, that page\n"
        "     contains MORE holdings that belong to the same section. Extract them ALL.\n\n"
        "3. PAGE-BY-PAGE VERIFICATION: After processing the document, verify for EACH section:\n"
        "   - You found holdings on ALL pages where that section appears\n"
        "   - The holdings you extracted span the full page range for that section\n"
        "   - No 'orphan' pages exist where you skipped extraction\n\n"
        "============================================================\n"
        "LAYOUT AND STRUCTURE INSTRUCTIONS\n"
        "============================================================\n\n"
        "CRITICAL LAYOUT INSTRUCTIONS:\n"
        "- Documents may have LARGE VERTICAL GAPS between the 'Schedule of Investments' title "
        "and the actual table start. You must scan down or to the next page to find the table.\n"
        "- Column headers (Shares, Value) may be far above the data rows. Associate them visually.\n"
        "- Tables often span many pages. Treat them as one continuous dataset.\n"
        "- Ignore blank spaces or 'Page Intentionally Left Blank' markers.\n\n"
        "*** SECTION CONTINUITY ACROSS PAGE BREAKS (CRITICAL) ***\n"
        "Tables frequently span multiple pages. When you see:\n"
        "- '(continued)' or 'CONTINUED' markers\n"
        "- A page break in the middle of a category's holdings\n"
        "- Column headers repeated at the top of a new page\n"
        "...the SECTION PATH from the previous page MUST continue to apply.\n"
        "DO NOT reset section_path at page boundaries unless you see a NEW section heading.\n"
        "EXAMPLE: If page 5 shows 'CONVERTIBLE BONDS AND NOTES' with holdings under 'Telecommunications',\n"
        "and page 6 starts with more holdings (no new heading), those holdings are STILL under\n"
        "'CONVERTIBLE BONDS AND NOTES > Telecommunications'.\n\n"
        "*** MULTI-PAGE SECTION TRACKING (CRITICAL FOR LARGE SECTIONS) ***\n"
        "Large asset classes like 'CONVERTIBLE BONDS AND NOTES' often span 3-6 pages:\n"
        "1. PAGE TRACKING: Mentally note which pages each section spans. Example:\n"
        "   - Page 5: CONVERTIBLE BONDS AND NOTES begins (Advertising, Aerospace, Automotive...)\n"
        "   - Page 6: CONVERTIBLE BONDS AND NOTES continues (Consumer Goods, Energy...)\n"
        "   - Page 7: CONVERTIBLE BONDS AND NOTES ends, TOTAL appears\n"
        "   ALL holdings from pages 5, 6, AND 7 must be extracted under this section.\n\n"
        "2. CONTINUATION MARKERS: Watch for these patterns that indicate MORE data follows:\n"
        "   - 'CONVERTIBLE BONDS AND NOTES -- (continued)'\n"
        "   - Column headers repeated at page top (Principal Amount | Value)\n"
        "   - No TOTAL row yet appearing for the current section\n"
        "   - Sub-section headers continuing (e.g., 'Pharmaceuticals' split across pages)\n\n"
        "3. SECTION BOUNDARY DETECTION: A section ENDS only when you see:\n"
        "   - A TOTAL row for that section (e.g., 'TOTAL CONVERTIBLE BONDS AND NOTES')\n"
        "   - A NEW top-level section header (e.g., 'CONVERTIBLE PREFERRED STOCKS')\n"
        "   Until you see one of these, KEEP EXTRACTING under the current section_path.\n\n"
        "4. COMMON FAILURE MODE: Stopping extraction after page 5 when holdings continue on\n"
        "   pages 6-7. The TOTAL row is your signal that extraction is complete for a section,\n"
        "   NOT a page break or visual gap.\n\n"
        "ROW TYPE CLASSIFICATION (CRITICAL):\n"
        "1) HOLDING rows:\n"
        "   - Must have an identifiable security/investment NAME (e.g., 'Apple Inc.', "
        "'Lucent Technologies 2.75% 2023 series A cv. sr. deb.').\n"
        "   - Must have at least one numeric value (quantity, cost, fair value, or %).\n"
        "   - The 'investment' field MUST contain the security name, NOT column headers.\n"
        "   - Set 'label' to null for HOLDING rows.\n\n"
        "   *** WHAT MAKES A VALID 'investment' FIELD (STRICT REQUIREMENTS) ***\n"
        "   A valid investment name MUST contain at least ONE of the following:\n"
        "   a) A company/issuer name (e.g., 'Apple Inc.', 'General Motors Corp.', 'Bank of America')\n"
        "   b) A fund or trust name (e.g., 'Vanguard Total Stock Market ETF', 'SPDR S&P 500')\n"
        "   c) A government entity (e.g., 'U.S. Treasury', 'Federal National Mortgage Association')\n"
        "   d) A bond/note description with issuer + terms (e.g., 'Lucent 2.75% 2023 cv. sr. deb.')\n\n"
        "   A valid investment name MUST NOT be:\n"
        "   - A column header (Principal Amount, Value, Shares, Cost, etc.)\n"
        "   - A generic descriptor (Total, Subtotal, Amount, etc.)\n"
        "   - Just a number or dollar amount\n"
        "   - Just punctuation or whitespace\n\n"
        "   VALIDATION TEST: Before emitting a HOLDING row, ask:\n"
        "   'Could I look up this investment name on Bloomberg/Reuters/SEC EDGAR?'\n"
        "   - 'Apple Inc.' → YES, valid issuer name\n"
        "   - 'Kerr-McGee Corp. 5.25% 2010 cv. sub. deb.' → YES, valid bond description\n"
        "   - 'Principal Amount:' → NO, this is a column header → DO NOT EMIT\n"
        "   - 'Principal Amount: 8,169,847' → NO, header + number → DO NOT EMIT\n"
        "   - 'Value (Note 1): 8,169,847' → NO, header text with a number → DO NOT EMIT\n"
        "   - '500,000' → NO, just a quantity → DO NOT EMIT\n"
        "   - '$8,169,847' → NO, just a dollar amount → DO NOT EMIT\n\n"
        "   *** RECOVERY WHEN SECURITY NAME IS MISSING ***\n"
        "   If you find a row with fair_value but the 'investment' name is missing or invalid:\n"
        "   1. Look ABOVE: The security name may be on the preceding line(s)\n"
        "   2. Look on PREVIOUS PAGE: Holdings often span page breaks; name may be on prior page\n"
        "   3. Check for multi-line descriptions: Bond descriptions often span 2-3 lines\n"
        "   4. If you cannot find a valid security name, DO NOT emit the row as a HOLDING\n"
        "   NEVER emit a holding where the 'investment' field contains numeric quantities\n"
        "   (like '$1,500,000' or '8,169,847') unless they are part of a valid bond description\n"
        "   (e.g., 'Company X $1,500,000 5% 2025 convertible note').\n\n"
        "2) SUBTOTAL rows:\n"
        "   - Summarize a group (e.g., sector subtotal, asset class subtotal).\n"
        "   - Usually appear after a group of holdings with a line/separator.\n"
        "   - May have value/% but typically NO quantity.\n"
        "   - The 'label' field should contain the subtotal text.\n"
        "   - Set 'investment' to null for SUBTOTAL rows.\n"
        "   - IMPORTANT: Category headers like 'Major Industry Exposure' that list percentages\n"
        "     (e.g., 'Pharmaceuticals 11.7%', 'Technology 11.2%') are SUMMARY/SUBTOTAL rows,\n"
        "     NOT individual holdings. Each line should be a SUBTOTAL with the category name\n"
        "     as label and the percentage in percent_net_assets_raw.\n\n"
        "   *** SUBTOTAL vs HEADER DISTINCTION (CRITICAL) ***\n"
        "   A SUBTOTAL row is DIFFERENT from a repeated column header. Here is how to tell them apart:\n\n"
        "   SUBTOTAL (valid - emit this):\n"
        "   - Appears AFTER a group of holdings (at the bottom of a section)\n"
        "   - Has a descriptive label like 'Total Telecommunications', 'Subtotal', or a category name\n"
        "   - The label describes WHAT is being summed (e.g., 'TOTAL CONVERTIBLE BONDS AND NOTES')\n"
        "   - The numeric value is the SUM of the holdings above it\n\n"
        "   HEADER (invalid - do NOT emit):\n"
        "   - Appears at the TOP of a page or table\n"
        "   - Contains generic column names like 'Principal Amount', 'Value', 'Shares', 'Cost'\n"
        "   - The label would be a column descriptor, not a category or section name\n"
        "   - Any adjacent number is likely OCR noise, not a meaningful subtotal\n\n"
        "   DECISION RULE: Ask yourself: 'Does this row describe a column or summarize holdings?'\n"
        "   - If it describes a column (what TYPE of data is in this column) → HEADER → SKIP IT\n"
        "   - If it summarizes holdings (total for Automotive, etc.) → SUBTOTAL → EMIT IT\n\n"
        "*** SUMMARY/INDUSTRY EXPOSURE TABLES (CRITICAL) ***\n"
        "Some documents contain summary tables that list industry allocations, e.g.:\n"
        "   | Major Industry Exposure | % of Total Net Assets |\n"
        "   | Pharmaceuticals         | 11.7%                 |\n"
        "   | Technology              | 11.2%                 |\n"
        "   | Banking/Savings & Loan  | 11.0%                 |\n"
        "   | Total                   | 81.9%                 |\n\n"
        "EXTRACTION RULES FOR SUMMARY TABLES:\n"
        "1. Each category line is a SUBTOTAL row, NOT a HOLDING:\n"
        "   - row_type='SUBTOTAL'\n"
        "   - label='Pharmaceuticals' (NOT 'Pharmaceuticals 11.7%')\n"
        "   - percent_net_assets_raw='11.7%'\n"
        "   - section_path=['Major Industry Exposure']\n\n"
        "2. The 'Total' line at the bottom is a TOTAL row:\n"
        "   - row_type='TOTAL'\n"
        "   - label='Total'\n"
        "   - percent_net_assets_raw='81.9%'\n"
        "   - section_path=['Major Industry Exposure']\n\n"
        "3. Extract ALL rows in the summary table, not just a subset.\n"
        "4. These summary tables are SEPARATE from the detailed holdings. They provide\n"
        "   a high-level breakdown. The detailed holdings appear elsewhere in the document.\n"
        "5. Do NOT confuse summary table categories with actual holdings.\n\n"
        "3) TOTAL rows:\n"
        "   - Represent grand totals (e.g., 'Total Investments', 'Total Portfolio').\n"
        "   - The 'label' field should contain the total text.\n"
        "   - Set 'investment' to null for TOTAL rows.\n\n"
        "WHAT IS NOT A HOLDING (NEVER emit these as HOLDING rows):\n"
        "- Column headers like 'Principal Amount', 'Value', 'Cost', 'Shares', 'Par Amount'\n"
        "- Section headings like 'Telecommunications -- 7.1%' (emit as SUBTOTAL if it has data)\n"
        "- Summary tables showing industry exposure percentages (emit each as SUBTOTAL)\n"
        "- Subtotal lines that show only aggregated values without a security name\n"
        "- Page numbers, footnotes, or narrative text\n\n"
        "EXAMPLE OF INCORRECT EXTRACTION (DO NOT DO THIS):\n"
        "  WRONG: row_type='HOLDING', investment='Principal Amount:', fair_value='8,169,847'\n"
        "  This is a SUBTOTAL row, not a holding! Column headers are not investments.\n\n"
        "  WRONG: row_type='SUBTOTAL', label='Pharmaceuticals 11.78'\n"
        "  The '8' is a misread '%'! Should be: label='Pharmaceuticals', percent_net_assets_raw='11.7%'\n\n"
        "SECTION PATH HANDLING (CRITICAL FOR ACCURACY):\n"
        "- When you see a section heading like 'Telecommunications -- 7.1%':\n"
        "  1) Add 'Telecommunications' (without the percentage) to section_path for subsequent rows.\n"
        "  2) IF the heading contains a percentage or dollar value, ALSO emit a SUBTOTAL row for it.\n"
        "     Set label to the category name only (e.g., 'Telecommunications') and \n"
        "     populate percent_net_assets_raw with '7.1%'.\n"
        "  3) Set section_path on that SUBTOTAL row to include the section name.\n"
        "- This ensures section-level percentages are captured even if individual holdings lack them.\n"
        "- Apply the current section_path to each emitted row.\n"
        "- SECTION CONTINUITY RULE: You MUST NOT lose track of the hierarchy when page breaks, \n"
        "  large vertical gaps, or column breaks occur. The section_path you established on page N \n"
        "  continues to apply to rows on page N+1 until a new section heading changes it.\n"
        "- COMPLETENESS RULE: After processing all pages, verify that every section heading you \n"
        "  encountered has at least one HOLDING or child SUBTOTAL row assigned to it. If you see \n"
        "  a section like 'Telecommunications -- 7.1%' but no holdings are emitted under it, \n"
        "  you have likely skipped rows. Go back and extract them.\n\n"
        "OTHER RULES:\n"
        "- Multi-line rows: combine issuer + tranche/series lines into a single HOLDING.\n"
        "- Preserve numbers exactly as printed in *_raw fields (parentheses for negatives, "
        "currency codes like CAD, footnote markers like † ‡ # (a)).\n"
        "- When a column is absent, set the corresponding field to null.\n\n"
        "Output must reflect only what appears in the document. Be precise and thorough."
    )

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "soi_title": {
                "type": ["string", "null"],
                "description": (
                    "Exact schedule title if present (e.g., 'Schedule of Investments', "
                    "'Portfolio of Investments', including 'Consolidated'/'Condensed')."
                ),
            },
            "as_of_date": {
                "type": ["string", "null"],
                "description": (
                    "As-of date for the schedule if present (e.g., 'December 31, 2024')."
                ),
            },
            "reporting_basis": {
                "type": ["string", "null"],
                "description": "If present, e.g., 'Unaudited' or 'Audited'.",
            },
            "soi_rows": {
                "type": "array",
                "description": (
                    "All SOI line items across all pages: holdings + subtotals + totals. "
                    "Each object is one line item from the schedule. "
                    "IMPORTANT: Use the correct row_type and ensure HOLDING rows have "
                    "a real security name in 'investment', not column headers."
                ),
                "items": {
                    "oneOf": [
                        # HOLDING row schema
                        {
                            "type": "object",
                            "description": (
                                "A HOLDING row represents an individual investment/security. "
                                "MUST have a real security name (not column headers like "
                                "'Principal Amount' or 'Value')."
                            ),
                            "properties": {
                                "row_type": {
                                    "type": "string",
                                    "const": "HOLDING",
                                    "description": "Must be 'HOLDING' for investment rows.",
                                },
                                "section_path": {
                                    "type": ["array", "null"],
                                    "items": {"type": "string"},
                                    "description": "Hierarchy of headings (asset class/sector).",
                                },
                                "investment": {
                                    "type": "string",
                                    "minLength": 1,
                                    "description": (
                                        "REQUIRED: The security/investment name. MUST be an identifiable "
                                        "issuer, company, fund, or bond description (e.g., 'Apple Inc.', "
                                        "'Kerr-McGee Corp. 5.25% 2010 cv. sub. deb.', 'U.S. Treasury Notes'). "
                                        "BLACKLISTED VALUES (never use): 'Principal Amount', 'Principal Amount:', "
                                        "'Value', 'Value (Note 1)', 'Value (Note 1):', 'Shares', 'Cost', 'Fair Value', "
                                        "'Par Amount', 'Par Value', 'Units', 'Notional', 'Rate', 'Maturity'. "
                                        "NUMERIC REJECTION: If the value is primarily numeric (e.g., '$1,500,000', "
                                        "'8,169,847'), it is NOT a valid investment name - look above or on the "
                                        "previous page for the actual security name. "
                                        "If the investment name matches any blacklisted value or is numeric-only, "
                                        "DO NOT emit the row."
                                    ),
                                },
                                "label": {
                                    "type": "null",
                                    "description": "Must be null for HOLDING rows.",
                                },
                                "instrument_type": {
                                    "type": ["string", "null"],
                                    "description": "e.g., common stock, preferred, CLO tranche.",
                                },
                                "quantity_raw": {
                                    "type": ["string", "null"],
                                    "description": "Shares/units/principal as printed.",
                                },
                                "quantity_type": {
                                    "type": ["string", "null"],
                                    "enum": ["shares", "principal", "par", "units", "notional", "contracts", "other", "unknown", None],
                                },
                                "cost_raw": {"type": ["string", "null"]},
                                "amortized_cost_raw": {"type": ["string", "null"]},
                                "fair_value_raw": {"type": ["string", "null"]},
                                "percent_net_assets_raw": {
                                    "type": ["string", "null"],
                                    "description": (
                                        "Percentage of net assets. MUST include '%' sign. "
                                        "CRITICAL: Do NOT misread '%' as '8'. "
                                        "If value ends in '8' without '%', it is likely wrong (e.g., '2.78' should be '2.7%')."
                                    ),
                                },
                                "interest_rate_raw": {"type": ["string", "null"]},
                                "maturity_date": {"type": ["string", "null"]},
                                "currency_raw": {"type": ["string", "null"]},
                                "fair_value_level_raw": {"type": ["string", "null"]},
                                "footnote_markers": {"type": ["array", "null"], "items": {"type": "string"}},
                                "additional_fields": {
                                    "type": ["array", "null"],
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "column_header": {"type": "string"},
                                            "value_raw": {"type": "string"},
                                        },
                                        "required": ["column_header", "value_raw"],
                                    },
                                },
                                "row_text": {"type": ["string", "null"]},
                            },
                            "required": ["row_type", "investment"],
                        },
                        # SUBTOTAL row schema
                        {
                            "type": "object",
                            "description": (
                                "A SUBTOTAL row summarizes a group of holdings (e.g., sector subtotal). "
                                "Has aggregated values but no individual security name."
                            ),
                            "properties": {
                                "row_type": {
                                    "type": "string",
                                    "const": "SUBTOTAL",
                                    "description": "Must be 'SUBTOTAL' for subtotal rows.",
                                },
                                "section_path": {
                                    "type": ["array", "null"],
                                    "items": {"type": "string"},
                                },
                                "label": {
                                    "type": "string",
                                    "minLength": 1,
                                    "description": "REQUIRED: The subtotal label as shown.",
                                },
                                "investment": {
                                    "type": "null",
                                    "description": "Must be null for SUBTOTAL rows.",
                                },
                                "quantity_raw": {"type": ["string", "null"]},
                                "cost_raw": {"type": ["string", "null"]},
                                "amortized_cost_raw": {"type": ["string", "null"]},
                                "fair_value_raw": {"type": ["string", "null"]},
                                "percent_net_assets_raw": {
                                    "type": ["string", "null"],
                                    "description": (
                                        "Percentage of net assets. MUST include '%' sign. "
                                        "CRITICAL: Do NOT misread '%' as '8'."
                                    ),
                                },
                                "footnote_markers": {"type": ["array", "null"], "items": {"type": "string"}},
                                "row_text": {"type": ["string", "null"]},
                            },
                            "required": ["row_type", "label"],
                        },
                        # TOTAL row schema
                        {
                            "type": "object",
                            "description": (
                                "A TOTAL row represents grand totals (e.g., 'Total Investments'). "
                                "Has aggregated values for the entire schedule or major section."
                            ),
                            "properties": {
                                "row_type": {
                                    "type": "string",
                                    "const": "TOTAL",
                                    "description": "Must be 'TOTAL' for grand total rows.",
                                },
                                "section_path": {
                                    "type": ["array", "null"],
                                    "items": {"type": "string"},
                                },
                                "label": {
                                    "type": "string",
                                    "minLength": 1,
                                    "description": "REQUIRED: The total label (e.g., 'Total Investments').",
                                },
                                "investment": {
                                    "type": "null",
                                    "description": "Must be null for TOTAL rows.",
                                },
                                "quantity_raw": {"type": ["string", "null"]},
                                "cost_raw": {"type": ["string", "null"]},
                                "amortized_cost_raw": {"type": ["string", "null"]},
                                "fair_value_raw": {"type": ["string", "null"]},
                                "percent_net_assets_raw": {
                                    "type": ["string", "null"],
                                    "description": (
                                        "Percentage of net assets. MUST include '%' sign. "
                                        "CRITICAL: Do NOT misread '%' as '8'."
                                    ),
                                },
                                "footnote_markers": {"type": ["array", "null"], "items": {"type": "string"}},
                                "row_text": {"type": ["string", "null"]},
                            },
                            "required": ["row_type", "label"],
                        },
                    ],
                },
            },
        },
        "required": ["soi_rows"],
    }

    return {
        "input": remote_input,
        "parsing": parsing_config,
        "instructions": {
            "system_prompt": system_prompt,
            "schema": schema,
        },
        "settings": {
            "force_url_result": True,
            "array_extract": True,
            "citations": {"enabled": True, "numerical_confidence": True},
            "include_images": False,
            "optimize_for_latency": False,
        },
    }
