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


def get_extract_config(
    remote_input: str, pages: List[int]
) -> Dict[str, Any]:
    """Create the extract configuration using Reducto SDK settings.
    
    Args:
        remote_input: The remote URL or file reference for the document.
        pages: List of page numbers to extract from.
    """
    parsing_config = _build_parsing_config(pages)

    system_prompt = (
        "You are extracting the Schedule of Investments (SOI) from a U.S. registered "
        "tender offer / interval fund N-CSR or N-CSRS report.\n\n"
        "============================================================\n"
        "PRIORITY 1: COMPLETENESS (MOST CRITICAL)\n"
        "============================================================\n\n"
        "*** ARITHMETIC VALIDATION - DO THIS BEFORE EMITTING ANY TOTAL ROW ***\n"
        "1. Sum all fair_value_raw from HOLDING rows in the section\n"
        "2. Compare to the TOTAL row's fair_value_raw\n"
        "3. If sum < total: YOU MISSED HOLDINGS. Go back and find them.\n"
        "   - Check EVERY page in the section (sections often span 3-5 pages)\n"
        "   - Look for '(continued)' at page tops - these have MORE holdings\n"
        "   - A $1M+ gap means you likely skipped an entire page or block\n"
        "4. Do NOT emit the TOTAL row until your sum matches\n\n"
        "*** PERCENTAGE ANCHOR RULE ***\n"
        "When a section header shows a percentage (e.g., 'CONVERTIBLE BONDS -- 53.6%'):\n"
        "  sum(industry subtotal percentages) MUST equal the section header percentage\n"
        "If your industry percentages sum to less than the header, you MISSED an industry block.\n"
        "Re-scan all pages for the missing industry/category.\n\n"
        "*** NO SKIPPED PAGES ***\n"
        "- Extract holdings from EVERY page in the provided range\n"
        "- Sections often span 3-5 pages. Extract ALL holdings until you see the section's TOTAL\n"
        "- '(continued)' at page top means MORE holdings follow under the same section\n"
        "- A page with 0 holdings extracted is a RED FLAG - re-scan it\n\n"
        "============================================================\n"
        "PRIORITY 2: PERCENTAGE ACCURACY\n"
        "============================================================\n\n"
        "*** ZERO TOLERANCE: '%' MISREAD AS '8' ***\n"
        "The '%' symbol must NEVER be misread as digit '8'. Examples:\n"
        "- '1.3%' is correct, '1.38' is WRONG\n"
        "- '7.9%' is correct, '7.98' is WRONG\n"
        "- '11.7%' is correct, '11.78' is WRONG\n\n"
        "DETECTION: If a percentage has MORE decimal places than the document's Total row AND "
        "ends in '8', you have misread '%' as '8'. Fix it by removing the trailing 8 and adding '%'.\n\n"
        "*** HEADER SPLITTING ***\n"
        "When a heading contains BOTH name AND percentage (e.g., 'Automotive -- 1.38'):\n"
        "- label = 'Automotive' (name only, no numbers/dashes)\n"
        "- percent_net_assets_raw = '1.3%' (correcting 8→%)\n"
        "Dashes between name and percentage are SEPARATORS, not minus signs.\n"
        "ALWAYS include the '%' sign in percent_net_assets_raw values.\n\n"
        "============================================================\n"
        "PRIORITY 3: CORRECT ROW CLASSIFICATION\n"
        "============================================================\n\n"
        "*** THREE ROW TYPES ***\n"
        "1) HOLDING: Individual security with issuer name + at least one numeric value\n"
        "   - investment = security name (company, bond description, fund name)\n"
        "   - label = null\n\n"
        "2) SUBTOTAL: Industry/category summary (e.g., 'Pharmaceuticals -- 10.2%')\n"
        "   - label = category name only (no percentages in label)\n"
        "   - investment = null\n"
        "   - percent_net_assets_raw = the percentage\n\n"
        "3) TOTAL: Grand total row (e.g., 'Total Investments', 'TOTAL CONVERTIBLE BONDS')\n"
        "   - label = total text as shown\n"
        "   - investment = null\n\n"
        "*** HIERARCHY RULE - NO DOUBLE COUNTING ***\n"
        "Section headers vs industry subtotals are DIFFERENT hierarchy levels:\n"
        "- 'CONVERTIBLE BONDS -- 53.6%' is an ASSET CLASS header (anchor total)\n"
        "- 'Advertising -- 0.9%', 'Aerospace -- 1.2%' are INDUSTRY subtotals\n"
        "The industry percentages (0.9 + 1.2 + ...) should SUM to the header percentage (53.6%).\n\n"
        "CORRECT: Emit industry-level SUBTOTAL rows. The asset class header % is metadata/anchor only.\n"
        "WRONG: Emitting BOTH the asset class header as SUBTOTAL AND all industry SUBTOTALs.\n"
        "       This causes double-counting: 53.6% + (0.9+1.2+...) = 107%+ for one section!\n\n"
        "============================================================\n"
        "PRIORITY 4: REJECT COLUMN HEADERS\n"
        "============================================================\n\n"
        "*** BLACKLISTED STRINGS - NEVER USE AS INVESTMENT OR LABEL ***\n"
        "These are table structure, not data:\n"
        "  Principal Amount, Value, Value (Note 1), Shares, Cost, Fair Value,\n"
        "  Par Amount, Par Value, Units, Notional, % of Net Assets, Maturity, Rate, Interest Rate\n\n"
        "If 'investment' would contain a blacklisted string, DO NOT emit the row.\n"
        "Numbers adjacent to headers (e.g., 'Value (Note 1): 8,169,847') are OCR artifacts, not holdings.\n\n"
        "*** VALID INVESTMENT NAME ***\n"
        "Must contain an identifiable issuer (company, fund, government entity) that could be\n"
        "looked up on Bloomberg/EDGAR. Examples:\n"
        "- VALID: 'Apple Inc.', 'Kerr-McGee Corp. 5.25% 2010 cv. sub. deb.', 'U.S. Treasury Notes'\n"
        "- INVALID: 'Principal Amount:', '$1,500,000', '8,169,847'\n\n"
        "If security name is missing, look ABOVE or on the PREVIOUS page. Multi-line descriptions are common.\n\n"
        "============================================================\n"
        "PRIORITY 5: IGNORE SUMMARY/RECAP TABLES (PREVENT DOUBLE-COUNTING)\n"
        "============================================================\n\n"
        "*** CRITICAL: ONE TOTAL PER SECTION ***\n"
        "Each section (e.g., 'CONVERTIBLE BONDS AND NOTES') may have its TOTAL row appear TWICE:\n"
        "1. FIRST: At the END of its detailed holdings list (this is the one to EXTRACT)\n"
        "2. SECOND: In a 'recap' or 'summary' block near 'Total Investments' (IGNORE THIS)\n\n"
        "*** DETECT RECAP/SUMMARY BLOCKS ***\n"
        "A recap block looks like this (appears AFTER all detailed sections are complete):\n"
        "  TOTAL CONVERTIBLE BONDS AND NOTES -- 55.6% .......... $63,196,000    $63,059,727\n"
        "  TOTAL CONVERTIBLE PREFERRED STOCKS -- 19.3% ......... $21,022,642    $21,853,153\n"
        "  TOTAL MANDATORY CONVERTIBLE SECURITIES -- 18.9% ..... $21,421,924    $21,466,046\n"
        "  TOTAL SHORT-TERM SECURITIES -- 6.0% ................. $ 6,809,726    $ 6,809,692\n"
        "  TOTAL INVESTMENTS -- 99.8% .......................... $112,450,292  $113,188,618\n\n"
        "This is a SUMMARY TABLE that re-lists totals already extracted. DO NOT extract these rows.\n\n"
        "*** RULE: IF YOU ALREADY EMITTED 'TOTAL [SECTION]', DO NOT EMIT IT AGAIN ***\n"
        "- Track which TOTAL rows you have already emitted\n"
        "- If you see the same 'TOTAL [X]' label again in a summary block, SKIP IT\n"
        "- Only emit 'TOTAL INVESTMENTS' once (the final grand total)\n\n"
        "*** DETECTION HEURISTICS ***\n"
        "You are in a recap block if:\n"
        "1. You see multiple 'TOTAL [Section]' lines in rapid succession (3+ within 10 lines)\n"
        "2. These lines appear AFTER the detailed holdings for those sections were already extracted\n"
        "3. The block ends with 'TOTAL INVESTMENTS' or similar grand total\n\n"
        "Extracting recap rows causes DOUBLE-COUNTING: calculated totals will be ~200% of actual.\n\n"
        "============================================================\n"
        "PRIORITY 5.5: REJECT TOP HOLDINGS / HIGHLIGHT TABLES\n"
        "============================================================\n\n"
        "*** CRITICAL: DO NOT EXTRACT FROM SUMMARY HIGHLIGHT TABLES ***\n"
        "Many N-CSR documents include a 'Top Holdings' or 'Largest Investment Holdings'\n"
        "summary table BEFORE the main Schedule of Investments. These tables:\n"
        "- Show only 5-15 'top' or 'largest' holdings (not the full portfolio)\n"
        "- Have their own 'Total' row that sums only those highlighted holdings\n"
        "- Often appear on pages 2-3 of the document, before the main SOI\n"
        "- Use titles like:\n"
        "  'Largest Investment Holdings', 'Top Ten Holdings', 'Top Holdings',\n"
        "  'Major Investment Holdings', 'Significant Holdings', 'Principal Holdings',\n"
        "  'Leading Holdings', 'Key Holdings', 'Primary Holdings',\n"
        "  'Investment Highlights', 'Portfolio Highlights'\n\n"
        "*** DETECTION: YOU ARE IN A TOP HOLDINGS TABLE IF ***\n"
        "1. The table has 5-15 holdings followed immediately by a Total row\n"
        "2. The Total row shows a percentage FAR LESS than 100% (e.g., 22.8%, 35.1%)\n"
        "3. The table appears BEFORE the main 'Schedule of Investments' or 'Portfolio of Investments' title\n"
        "4. The section header mentions 'Top', 'Largest', 'Major', 'Significant', 'Principal', or 'Key'\n"
        "5. The Total row's fair_value is 5x+ LARGER than the sum of visible holdings\n"
        "   (This happens when the Total reflects the full portfolio, but only top holdings are listed)\n\n"
        "*** CRITICAL ARITHMETIC CHECK ***\n"
        "BEFORE emitting a TOTAL row, calculate: sum(extracted_holdings_fair_value) vs total_fair_value\n"
        "- If total_fair_value > 2x sum: YOU MISSED HOLDINGS or are in a Top Holdings table\n"
        "- If total_fair_value > 5x sum: YOU ARE DEFINITELY IN A TOP HOLDINGS TABLE - DISCARD ALL\n"
        "- If total_fair_value > 10x sum: CRITICAL ERROR - stop and re-examine the document structure\n\n"
        "*** RULE: SKIP ALL ROWS FROM TOP HOLDINGS TABLES ***\n"
        "If you detect you are in a Top Holdings summary table:\n"
        "- DO NOT emit any HOLDING rows from this table\n"
        "- DO NOT emit the Total row from this table\n"
        "- Continue scanning until you find the main SOI ('Schedule of Investments' or 'Portfolio of Investments')\n"
        "- Only extract from the main SOI section\n\n"
        "*** NEVER USE 'Unknown Section' - ABSOLUTE PROHIBITION ***\n"
        "If you cannot determine the section_path for a holding:\n"
        "- DO NOT emit it with section_path = ['Unknown Section']\n"
        "- Instead, look harder for context: check page headers, preceding rows, '(continued)' markers\n"
        "- If still no context: SKIP the row entirely rather than use 'Unknown Section'\n"
        "'Unknown Section' WILL CAUSE EXTRACTION FAILURE. It must NEVER appear in output.\n\n"
        "COMMON CAUSES OF 'Unknown Section':\n"
        "1. You extracted from a Top Holdings table before the main SOI\n"
        "2. You missed a section header on a previous page\n"
        "3. Holdings appear after a 'Total Investments' row (these are likely recap data)\n"
        "If you find yourself wanting to use 'Unknown Section', STOP and re-examine what table you're in.\n\n"
        "*** ARITHMETIC SANITY CHECK FOR TOP HOLDINGS ***\n"
        "After extracting holdings, compare your sum to the Total row:\n"
        "- If Total row fair_value is 5x+ larger than sum of extracted holdings: YOU ARE IN A TOP HOLDINGS TABLE\n"
        "- If Total row shows ~20-40% but you only have 5-15 holdings: THIS IS A TOP HOLDINGS TABLE\n"
        "- DISCARD all rows from this table and find the main Schedule of Investments\n\n"
        "============================================================\n"
        "PRIORITY 5.6: STRATEGY ALLOCATION TABLES (DO NOT EXTRACT)\n"
        "============================================================\n\n"
        "*** CRITICAL: SKIP STRATEGY/ALLOCATION SUMMARY TABLES ***\n"
        "Many fund-of-funds documents include 'Investment Strategy' or 'Asset Allocation'\n"
        "summary tables that show how the fund allocates its investments by strategy.\n\n"
        "*** DETECTION: YOU ARE IN A STRATEGY ALLOCATION TABLE IF ***\n"
        "1. The table title mentions:\n"
        "   - 'Investment Strategy as a Percentage of Investments'\n"
        "   - 'Strategy Allocation' or 'Asset Allocation'\n"
        "   - 'Strategy Breakdown' or 'Investment Categories'\n"
        "2. Rows show strategy names with percentages that sum to ~100%:\n"
        "   - 'Convertible Arbitrage 8.11%'\n"
        "   - 'Credit Strategies 14.39%'\n"
        "   - 'Long/Short Equity 35.22%'\n"
        "   - 'Multi-Strategy 42.28%'\n"
        "   - Total = 100%\n"
        "3. These percentages represent 'portion of this fund's investments',\n"
        "   NOT 'percent of total net assets'\n\n"
        "*** RULE: DO NOT EXTRACT STRATEGY ALLOCATION ROWS ***\n"
        "These rows use a DIFFERENT DENOMINATOR than the main SOI:\n"
        "- Strategy allocation: % of THIS FUND'S investments (sums to 100%)\n"
        "- Main SOI: % of TOTAL NET ASSETS (may be <100% due to cash, liabilities)\n\n"
        "Extracting strategy allocation rows as SUBTOTAL causes arithmetic mismatches:\n"
        "- Holdings sum to X% of net assets\n"
        "- Strategy subtotal shows 100% (of investments)\n"
        "- Validator compares X% != 100% = ERROR\n\n"
        "*** ACTION: SKIP THESE TABLES ENTIRELY ***\n"
        "When you detect a strategy allocation table:\n"
        "- DO NOT emit any SUBTOTAL rows from this table\n"
        "- DO NOT emit any HOLDING rows from this table\n"
        "- Continue to the actual holdings list with individual securities\n\n"
        "============================================================\n"
        "PRIORITY 5.7: 100% SUBTOTAL DETECTION RULE\n"
        "============================================================\n\n"
        "*** RED FLAG: SUBTOTALS THAT SUM TO EXACTLY 100% ***\n"
        "If within a single fund/section, your SUBTOTAL rows sum to exactly 100%:\n"
        "- This indicates you're extracting INTERNAL ALLOCATION percentages\n"
        "- NOT percentages relative to total net assets\n\n"
        "EXAMPLE - WRONG EXTRACTION:\n"
        "  Fund: 'Aetos Capital Multi-Strategy Arbitrage Fund'\n"
        "  Extracted SUBTOTALs:\n"
        "    - Convertible Arbitrage: 8.11%\n"
        "    - Credit Strategies: 14.39%\n"
        "    - ... more strategies ...\n"
        "    - Total: 100.00%  <-- RED FLAG!\n\n"
        "  Meanwhile, individual holdings in this fund:\n"
        "    - Holding A: 2.1% of net assets\n"
        "    - Holding B: 1.8% of net assets\n"
        "    - Sum: ~50% of net assets  <-- DIFFERENT DENOMINATOR!\n\n"
        "*** RULE: IF SUBTOTALS SUM TO 100%, YOU'RE IN THE WRONG TABLE ***\n"
        "- The 100% is 'allocation within this sub-fund'\n"
        "- Individual holdings use 'percent of master fund net assets'\n"
        "- These are INCOMPATIBLE - do not mix them\n\n"
        "*** ACTION: SKIP 100% ALLOCATION SUBTOTALS ***\n"
        "If you see a section where strategy/category subtotals sum to 100%:\n"
        "- DO NOT emit these as SUBTOTAL rows\n"
        "- ONLY emit the individual HOLDING rows with their % of net assets values\n"
        "- The 100% allocation breakdown is metadata, not SOI data\n\n"
        "============================================================\n"
        "PRIORITY 5.8: FUND-OF-FUNDS DENOMINATOR CONSISTENCY\n"
        "============================================================\n\n"
        "*** CRITICAL: ALL PERCENTAGES MUST USE THE SAME DENOMINATOR ***\n"
        "In fund-of-funds structures, multiple percentage contexts exist:\n\n"
        "1. MASTER FUND LEVEL (EXTRACT THIS):\n"
        "   - Individual holding % = fair_value / master_fund_net_assets\n"
        "   - These are what we want in percent_net_assets_raw\n"
        "   - Example: 'Oceanwood Global Opportunities: $50M = 10.4% of net assets'\n\n"
        "2. SUB-FUND ALLOCATION LEVEL (DO NOT EXTRACT):\n"
        "   - Strategy % = strategy_allocation / sub_fund_total\n"
        "   - These sum to 100% within each sub-fund\n"
        "   - Example: 'Long/Short Equity strategy: 35% of this sub-fund's investments'\n\n"
        "*** RULE: NEVER MIX DENOMINATORS ***\n"
        "If a document shows both:\n"
        "- 'Credit Strategies 14.39%' (sub-fund allocation, sums to 100%)\n"
        "- 'Cadmus Capital Partners 0.3%' (holding % of master net assets)\n\n"
        "Only extract the HOLDING-level percentages (0.3%).\n"
        "Do NOT extract the sub-fund allocation percentages (14.39%).\n\n"
        "*** DETECTION HEURISTIC ***\n"
        "Look at the column header:\n"
        "- '% of Net Assets' or '% Net Assets': EXTRACT (master fund level)\n"
        "- '% of Investments' or 'Percentage of Investments': SKIP (internal allocation)\n"
        "- 'Strategy Allocation %': SKIP (internal allocation)\n\n"
        "============================================================\n"
        "PRIORITY 6: SECTION PATH HIERARCHY AND RESET\n"
        "============================================================\n\n"
        "*** SECTION PATH MUST RESET AT NEW MAJOR SECTIONS ***\n"
        "When you encounter a new ASSET CLASS header (e.g., 'MANDATORY CONVERTIBLE SECURITIES'):\n"
        "- COMPLETELY RESET section_path to just that new header\n"
        "- DO NOT carry over industry sub-categories from the previous section\n\n"
        "EXAMPLE - WRONG:\n"
        "  Previous section: ['CONVERTIBLE PREFERRED STOCKS', 'AUTOMOTIVE']\n"
        "  New header: 'MANDATORY CONVERTIBLE SECURITIES -- 18.9%'\n"
        "  WRONG path: ['CONVERTIBLE PREFERRED STOCKS', 'AUTOMOTIVE', 'MANDATORY CONVERTIBLE SECURITIES']\n\n"
        "EXAMPLE - CORRECT:\n"
        "  New header: 'MANDATORY CONVERTIBLE SECURITIES -- 18.9%'\n"
        "  CORRECT path: ['MANDATORY CONVERTIBLE SECURITIES']\n\n"
        "*** SANITY CHECK: SUBTOTAL CANNOT EXCEED SECTION TOTAL ***\n"
        "If an industry subtotal (e.g., 'AUTOMOTIVE') has a fair_value larger than the section's\n"
        "'TOTAL [SECTION]' row, something is WRONG. This usually means:\n"
        "- Holdings from multiple sections got merged under one industry name\n"
        "- Section path was not properly reset between major asset classes\n"
        "Re-check your section_path assignments when this occurs.\n\n"
        "============================================================\n"
        "PRIORITY 7: SUBTOTAL PATH MIRROR RULE (CRITICAL)\n"
        "============================================================\n\n"
        "*** THE LABEL MUST APPEAR IN THE PATH ***\n"
        "For every SUBTOTAL row, the 'label' value MUST appear as the LAST element of 'section_path'.\n"
        "This is a strict validation rule - violations cause arithmetic mismatches.\n\n"
        "MIRROR RULE: section_path[-1] == label (case-insensitive match)\n\n"
        "*** EXAMPLES OF CORRECT vs WRONG ***\n\n"
        "Document shows: 'AUTOMOTIVE -- 0.8%' under 'CONVERTIBLE PREFERRED STOCKS'\n\n"
        "CORRECT:\n"
        "  {row_type: 'SUBTOTAL', section_path: ['CONVERTIBLE PREFERRED STOCKS', 'AUTOMOTIVE'], label: 'AUTOMOTIVE'}\n"
        "  ✓ section_path ends with 'AUTOMOTIVE', matches label\n\n"
        "WRONG:\n"
        "  {row_type: 'SUBTOTAL', section_path: ['CONVERTIBLE PREFERRED STOCKS'], label: 'AUTOMOTIVE'}\n"
        "  ✗ section_path does NOT include 'AUTOMOTIVE' - THIS CAUSES VALIDATION FAILURE\n"
        "  ✗ Validator will sum ALL holdings under 'CONVERTIBLE PREFERRED STOCKS' (~$23M)\n"
        "  ✗ But the AUTOMOTIVE subtotal is only ~$942K, creating a huge mismatch\n\n"
        "*** SELF-CHECK BEFORE EMITTING ANY SUBTOTAL ***\n"
        "Ask yourself: Does section_path end with the same value as label?\n"
        "- If YES: emit the row\n"
        "- If NO: FIX section_path to include label as the last element\n\n"
        "*** EMIT A SUBTOTAL FOR EACH INDUSTRY HEADER ***\n"
        "When a section has multiple industry headers (AUTOMOTIVE, BANKING, ENERGY, etc.):\n"
        "- Emit a separate SUBTOTAL row for EACH industry\n"
        "- Each SUBTOTAL must have section_path ending with that industry name\n"
        "- Do NOT emit just one SUBTOTAL for the first industry and skip the rest\n\n"
        "EXAMPLE - Section 'CONVERTIBLE PREFERRED STOCKS' with 7 industries:\n"
        "  {section_path: ['CONVERTIBLE PREFERRED STOCKS', 'AUTOMOTIVE'], label: 'AUTOMOTIVE', ...}\n"
        "  {section_path: ['CONVERTIBLE PREFERRED STOCKS', 'BANKING/SAVINGS AND LOAN'], label: 'BANKING/SAVINGS AND LOAN', ...}\n"
        "  {section_path: ['CONVERTIBLE PREFERRED STOCKS', 'ENERGY'], label: 'ENERGY', ...}\n"
        "  {section_path: ['CONVERTIBLE PREFERRED STOCKS', 'ENTERTAINMENT'], label: 'ENTERTAINMENT', ...}\n"
        "  {section_path: ['CONVERTIBLE PREFERRED STOCKS', 'FINANCIAL AND INSURANCE'], label: 'FINANCIAL AND INSURANCE', ...}\n"
        "  {section_path: ['CONVERTIBLE PREFERRED STOCKS', 'HEALTH CARE'], label: 'HEALTH CARE', ...}\n"
        "  {section_path: ['CONVERTIBLE PREFERRED STOCKS', 'MINING'], label: 'MINING', ...}\n\n"
        "If you only emit AUTOMOTIVE and skip the others, holdings under BANKING, ENERGY, etc. will\n"
        "have no matching SUBTOTAL, causing MISSING_SUBTOTAL warnings.\n\n"
        "============================================================\n"
        "STRUCTURE AND LAYOUT\n"
        "============================================================\n\n"
        "*** SECTION CONTINUITY ACROSS PAGES ***\n"
        "- section_path from page N continues on page N+1 until a NEW section heading appears\n"
        "- Column headers repeated at page top do NOT change section_path\n"
        "- A section ENDS only when you see its TOTAL row or a new section header\n\n"
        "*** CRITICAL: SUBTOTAL ROWS MUST USE THE INNER SECTION PATH ***\n"
        "When you see an industry/category header like 'Advertising -- 0.9%' within a section:\n"
        "1. FIRST update section_path to INCLUDE the new category\n"
        "2. THEN emit the SUBTOTAL row using that UPDATED path\n"
        "3. THEN emit all HOLDING rows under that path\n\n"
        "EXAMPLE - Document shows:\n"
        "  CONVERTIBLE BONDS AND NOTES -- 53.6%\n"
        "    Advertising -- 0.9%\n"
        "      $1,000,000 Lamar Advertising 2.875% 2010 ... $1,078,125\n"
        "    Aerospace and Defense -- 1.2%\n"
        "      $1,500,000 Goldman Sachs 1% 2009 ... $1,438,740\n"
        "  TOTAL CONVERTIBLE BONDS AND NOTES ... $61,987,411\n\n"
        "CORRECT extraction:\n"
        "  {row_type: 'SUBTOTAL', section_path: ['CONVERTIBLE BONDS AND NOTES', 'Advertising'], label: 'Advertising', percent_net_assets_raw: '0.9%'}\n"
        "  {row_type: 'HOLDING', section_path: ['CONVERTIBLE BONDS AND NOTES', 'Advertising'], investment: 'Lamar Advertising...', fair_value_raw: '$1,078,125'}\n"
        "  {row_type: 'SUBTOTAL', section_path: ['CONVERTIBLE BONDS AND NOTES', 'Aerospace and Defense'], label: 'Aerospace and Defense', percent_net_assets_raw: '1.2%'}\n"
        "  {row_type: 'HOLDING', section_path: ['CONVERTIBLE BONDS AND NOTES', 'Aerospace and Defense'], investment: 'Goldman Sachs...', fair_value_raw: '$1,438,740'}\n"
        "  {row_type: 'TOTAL', section_path: ['CONVERTIBLE BONDS AND NOTES'], label: 'TOTAL CONVERTIBLE BONDS AND NOTES', fair_value_raw: '$61,987,411'}\n\n"
        "WRONG extraction (causes validation failures):\n"
        "  {row_type: 'SUBTOTAL', section_path: ['CONVERTIBLE BONDS AND NOTES'], label: 'Advertising', ...}  <-- WRONG! Missing 'Advertising' in path\n"
        "  {row_type: 'HOLDING', section_path: ['CONVERTIBLE BONDS AND NOTES'], investment: 'Lamar...'}  <-- WRONG! Missing industry in path\n\n"
        "The SUBTOTAL's section_path MUST include the category it summarizes, not just the parent.\n\n"
        "*** SUMMARY/INDUSTRY EXPOSURE TABLES ***\n"
        "Tables listing industry allocations (e.g., 'Pharmaceuticals 11.7%', 'Technology 11.2%'):\n"
        "- Each category line is a SUBTOTAL (not HOLDING)\n"
        "- The 'Total' line is a TOTAL row\n"
        "- These are separate from detailed holdings\n\n"
        "*** OTHER RULES ***\n"
        "- Combine multi-line issuer + tranche descriptions into single HOLDING\n"
        "- Preserve numbers exactly as printed in *_raw fields (parentheses for negatives, currency codes)\n"
        "- When a column is absent, set the field to null\n\n"
        "============================================================\n"
        "PRIORITY 8: SUBTOTAL EMISSION TIMING (CRITICAL)\n"
        "============================================================\n\n"
        "*** STATE MACHINE FOR SECTION TRANSITIONS ***\n\n"
        "The SUBTOTAL row's numeric values (fair_value_raw, cost_raw) come from the section's\n"
        "SUMMARY LINE, which typically appears AFTER all holdings in that section.\n\n"
        "DOCUMENT LAYOUT (typical):\n"
        "  Industry Header: 'Advertising -- 0.9%'\n"
        "  [Holdings for Advertising]\n"
        "  Summary Line: '                           1,078,125    1,050,000' <- Advertising's totals!\n"
        "  Industry Header: 'Aerospace -- 1.2%' <- Next section starts here\n"
        "  [Holdings for Aerospace]\n"
        "  Summary Line: '                           1,438,740    1,400,000' <- Aerospace's totals!\n\n"
        "*** CRITICAL RULE: SUBTOTAL VALUES BELONG TO THEIR OWN SECTION ***\n\n"
        "When you encounter a summary line with aggregated values:\n"
        "1. Those values belong to the CURRENT industry section (the one you just finished)\n"
        "2. NOT to the NEXT industry section (which hasn't started yet)\n"
        "3. The section_path for this SUBTOTAL must match the holdings above it\n\n"
        "*** COMMON ERROR - OFF-BY-ONE ATTRIBUTION ***\n\n"
        "WRONG (causes cascading arithmetic errors):\n"
        "  See 'Advertising -- 0.9%' header\n"
        "  Emit HOLDING rows with path [..., 'Advertising']\n"
        "  See summary line '1,078,125'\n"
        "  See NEXT header 'Aerospace -- 1.2%'\n"
        "  Update section_path to [..., 'Aerospace']\n"
        "  Emit SUBTOTAL with path [..., 'Aerospace'], fair_value='1,078,125'  <-- WRONG!\n"
        "  (Advertising's values are now attributed to Aerospace!)\n\n"
        "CORRECT:\n"
        "  See 'Advertising -- 0.9%' header\n"
        "  Update section_path to [..., 'Advertising']\n"
        "  Emit SUBTOTAL with path [..., 'Advertising'], percent='0.9%' (from header)\n"
        "  Emit HOLDING rows with path [..., 'Advertising']\n"
        "  See summary line '1,078,125' <- This is Advertising's fair_value!\n"
        "  Update the Advertising SUBTOTAL's fair_value_raw to '1,078,125'\n"
        "  See 'Aerospace -- 1.2%' header\n"
        "  Update section_path to [..., 'Aerospace']\n"
        "  Emit SUBTOTAL with path [..., 'Aerospace'], percent='1.2%'\n"
        "  ... continue pattern ...\n\n"
        "*** SELF-CHECK: VERIFY SUBTOTAL VALUES MATCH THEIR HOLDINGS ***\n"
        "Before emitting a SUBTOTAL, verify:\n"
        "1. The section_path matches the holdings directly above\n"
        "2. The fair_value_raw is the sum of those holdings' fair values (if shown)\n"
        "3. If the values don't match, you may have shifted attribution by one section\n\n"
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
