from reducto import AsyncReducto


def get_split_config(remote_input: str) -> dict:
    """Get split configuration for a given remote input reference."""
    return {
        "input": remote_input,  # Use the server-side uploaded file reference
        "split_description": [
            {
                "name": "SOI",
                "description": (
                    "Pages that contain the fund's Schedule of Investments / Portfolio of Investments / "
                    "Statement of Investments. "
                    "\n\n"
                    "*** CONTINUATION PAGES (CRITICAL - HIGH PRIORITY) ***\n"
                    "ALWAYS include continuation pages, which may appear as:\n"
                    "- 'Schedule of Investments (Continued)'\n"
                    "- 'Schedule of Investments (continued)'\n"
                    "- 'Schedule of Investments - Continued'\n"
                    "- 'Portfolio of Investments (Continued)'\n"
                    "- '(Continued)' alone at the top of the page\n"
                    "- Pages with NO header but continuing tabular data from the previous SOI page\n"
                    "- Pages starting with subtotals or state names (e.g., 'CALIFORNIA--2.5%') that continue from prior pages\n"
                    "If a page has holdings data in the same tabular format as the main SOI, include it even without a header.\n"
                    "\n"
                    "*** WHAT TO INCLUDE ***\n"
                    "- Pages with titles: 'Schedule of Investments', 'Portfolio of Investments', "
                    "'Consolidated Schedule of Investments', 'Condensed Schedule of Investments'\n"
                    "- Pages with detailed holdings data: columns like Investment Name, Shares/Units/Principal, "
                    "Cost, Fair Value, % of Net Assets, Interest Rate, Maturity Date\n"
                    "- Pages with section headers like 'MUNICIPAL BONDS', 'CORPORATE BONDS', 'COMMON STOCKS'\n"
                    "- Pages with state-by-state bond listings (e.g., 'ALABAMA--3.8%', 'CALIFORNIA--5.2%')\n"
                    "- Pages with subtotal/total lines like 'Total Investments', 'Total Municipal Bonds'\n"
                    "\n"
                    "*** WHAT TO EXCLUDE (Summary Tables ONLY) ***\n"
                    "EXCLUDE pages that are CLEARLY summary/highlights tables:\n"
                    "- 'Top Holdings', 'Top Ten Holdings', 'Largest Investment Holdings', 'Major Holdings'\n"
                    "- 'DIVERSIFICATION OF ASSETS', 'Major Industry Exposure'\n"
                    "These summary tables have FEW holdings (5-15) and a Total row showing <80% of net assets.\n"
                    "\n"
                    "*** CRITICAL: DO NOT EXCLUDE MAIN SOI PAGES ***\n"
                    "If a page has DETAILED bond information (maturity dates, interest rates, principal amounts) "
                    "or MANY holdings (20+), it is the MAIN SOI, NOT a summary table. Include it.\n"
                    "Content (columns with dates/rates) takes priority over titles.\n"
                    "\n"
                    "############################################################\n"
                    "*** MULTI-FUND DOCUMENT DETECTION (HIGHEST PRIORITY) ***\n"
                    "############################################################\n"
                    "Many N-CSR filings contain MULTIPLE DISTINCT FUNDS in a single PDF.\n"
                    "Each fund has its own COMPLETE Schedule of Investments section.\n"
                    "\n"
                    "*** FUND NAME PATTERNS TO RECOGNIZE ***\n"
                    "- Series designations: 'Series A', 'Series B', 'Series M', 'Multi-Strategy Series M'\n"
                    "- Fund numbering: 'Fund II', 'Fund III', 'Fund 2', 'Fund 3'\n"
                    "- Geographic funds: 'PIMCO NEW YORK MUNICIPAL INCOME FUND II'\n"
                    "- Strategy funds: 'ALLIANCEBERNSTEIN GLOBAL HIGH INCOME FUND'\n"
                    "- Duration funds: 'LIMITED DURATION INCOME TRUST', 'Franklin Templeton Limited Duration'\n"
                    "- Arbitrage funds: 'FIXED INCOME ARBITRAGE', 'EQUITY ARBITRAGE', 'EVENT DRIVEN'\n"
                    "- Trust structures: 'THE GABELLI DIVIDEND & INCOME TRUST'\n"
                    "- Fund-of-funds: 'FCT Fund Capital Trust', 'Aetos Capital Multi-Strategy'\n"
                    "\n"
                    "*** CRITICAL RULE: INCLUDE ALL PAGES BETWEEN SOI TITLES ***\n"
                    "If you see 'Fund A Schedule of Investments' on page 6 and 'Fund B Schedule of Investments'\n"
                    "on page 25, you MUST include ALL pages 6-24. These are Fund A's holdings.\n"
                    "- A single fund's SOI can span 10-30+ pages\n"
                    "- Municipal bond funds often have 15-25 pages of state-by-state listings\n"
                    "- Do NOT assume a fund's SOI ends just because you see a 'TOTAL INVESTMENTS' row\n"
                    "- Multiple 'TOTAL INVESTMENTS' rows in different locations = multiple funds\n"
                    "\n"
                    "*** PAGE INCLUSION RULE FOR MULTI-FUND DOCUMENTS ***\n"
                    "Once you identify this is a multi-fund document:\n"
                    "1. Find the FIRST 'Schedule of Investments' title (e.g., page 6)\n"
                    "2. Find the LAST 'Schedule of Investments' or 'TOTAL INVESTMENTS' row\n"
                    "3. Include ALL pages from first SOI to the last Total row\n"
                    "4. When in doubt, INCLUDE the page - false positives are better than missed holdings\n"
                    "\n"
                    "*** GAP DETECTION RULE (CRITICAL) ***\n"
                    "If you identify pages 2 and 10-11 as SOI but NOT pages 3-9:\n"
                    "- Pages 3-9 are ALMOST CERTAINLY continuation pages\n"
                    "- SOI sections do NOT have 7-page gaps in the middle\n"
                    "- INCLUDE pages 3-9 automatically\n"
                    "- The gap likely contains holdings that continue from page 2\n"
                    "\n"
                    "*** MULTIPLE 'TOTAL INVESTMENTS' HEURISTIC ***\n"
                    "If you see 'TOTAL INVESTMENTS' on page 8 AND page 11:\n"
                    "- This indicates TWO SEPARATE FUNDS in the document\n"
                    "- Pages 2-8 belong to Fund 1\n"
                    "- Pages 9-11 belong to Fund 2 (or continuation)\n"
                    "- INCLUDE ALL pages 2-11 in the SOI split"
                ),
            },
            {
                "name": "OTHER_FS",
                "description": "Financial statements other than the SOI (statement of assets and liabilities, operations, changes in net assets, financial highlights), management discussion and other narrative sections."
            }
        ],
        "parsing": {
            "enhance": {
                "agentic": [
                    { "scope": "text" },
                    {
                        "scope": "table",
                        "prompt": "These are SEC N-CSR/N-CSRS filings. Prioritize finding 'Schedule of Investments' style tables; preserve column headers across page breaks; do not drop rows that continue across pages; keep multi-line security descriptions attached to their numeric columns."
                    }
                ],
                "summarize_figures": False
            },
            "retrieval": {
                "chunking": { "chunk_mode": "disabled" },
                "filter_blocks": ["Footer", "Page Number"],
                "embedding_optimized": False
            },
            "formatting": {
                "add_page_markers": True,
                "table_output_format": "html",
                "merge_tables": True,
                "include": []
            },
            "settings": {
                "ocr_system": "standard",
                "force_url_result": True,
                "persist_results": False
            }
        },
        "split_rules": (
            "Maximize recall for the SOI. Err on the side of INCLUSION.\n"
            "1. A page can be assigned to multiple categories if it clearly contains both.\n"
            "2. If uncertain, include the page in SOI with conf=low rather than excluding it.\n"
            "3. Include ALL continuation pages ('(continued)', '(Continued)', '-Continued', etc.).\n"
            "4. Include pages with holdings data even if they have no header (continuation pattern).\n"
            "5. Pages between two confirmed SOI pages are likely SOI - include them.\n"
            "6. Only EXCLUDE pages that are clearly 'Top Holdings' summary tables with <20 holdings and <80% total.\n"
            "7. If a page has detailed columns (Interest Rate, Maturity Date), it is the main SOI - INCLUDE it.\n"
            "\n"
            "*** CRITICAL: DETECT CONTINUATION PAGES THAT LACK HEADERS ***\n"
            "8. If page N is SOI and page N+1 has tabular data in the same format (columns of numbers, "
            "security names, dollar values), include N+1 even if it has NO title or header.\n"
            "9. Pages with ONLY numbers and no text headers are CONTINUATIONS - include them.\n"
            "10. Look for state names (e.g., 'CALIFORNIA--5.2%'), country names (e.g., 'Brazil', 'Turkey'), "
            "or industry names (e.g., 'Aerospace', 'Banking') as section markers - these indicate SOI content.\n"
            "\n"
            "############################################################\n"
            "*** CRITICAL: MULTI-FUND DOCUMENTS (HIGHEST PRIORITY) ***\n"
            "############################################################\n"
            "11. Multi-fund PDFs contain MULTIPLE 'Schedule of Investments' sections - one per fund.\n"
            "12. If you see 'Fund A Schedule of Investments' on page 6 and 'Fund B Schedule of Investments' "
            "on page 25, pages 7-24 are Fund A's SOI continuation pages. INCLUDE ALL 18 pages.\n"
            "13. Each fund's SOI may span 10-30 pages. Do NOT assume a fund's SOI ends after 3-5 pages.\n"
            "14. Watch for fund name changes in headers/footers - this indicates a new fund's section started.\n"
            "\n"
            "*** MULTI-FUND BOUNDARY DETECTION (CRITICAL) ***\n"
            "15. When you see MULTIPLE 'Schedule of Investments' or 'Portfolio of Investments' titles:\n"
            "    - Each represents a SEPARATE FUND's SOI section\n"
            "    - ALL pages between two SOI titles belong to the FIRST fund (continuation)\n"
            "    - Example: 'Fund A SOI' on page 6, 'Fund B SOI' on page 25 means pages 6-24 are Fund A\n"
            "16. Fund name patterns to recognize (CRITICAL - look for these in headers/footers):\n"
            "    - 'PIMCO NEW YORK MUNICIPAL INCOME FUND II'\n"
            "    - 'PIMCO CALIFORNIA MUNICIPAL INCOME FUND II'\n"
            "    - 'ALLIANCEBERNSTEIN GLOBAL HIGH INCOME FUND'\n"
            "    - 'LIMITED DURATION INCOME TRUST'\n"
            "    - 'THE GABELLI DIVIDEND & INCOME TRUST'\n"
            "    - 'Franklin Templeton Limited Duration Income Trust'\n"
            "    - Series designations: 'Series M', 'Series A', 'Multi-Strategy Series M'\n"
            "    - Fund numbering: 'Fund II', 'Fund III', 'Fund 2'\n"
            "    - Strategy names: 'FIXED INCOME ARBITRAGE', 'EQUITY ARBITRAGE', 'EVENT DRIVEN'\n"
            "17. Multiple 'TOTAL INVESTMENTS' rows indicate multiple funds - include ALL pages for ALL funds.\n"
            "18. If the document has 100+ pages, expect 3-10 fund sections, each spanning 10-30 pages.\n"
            "\n"
            "*** PAGE SPAN HEURISTICS ***\n"
            "19. If first SOI title is on page 6 and document has 100 pages, expect SOI content through page 90+.\n"
            "20. A single fund's municipal bond section alone can span 15-25 pages (state-by-state listings).\n"
            "21. When in doubt about a page, INCLUDE it. False positives are better than missed holdings.\n"
            "\n"
            "*** SEVERE EXTRACTION FAILURE PREVENTION ***\n"
            "22. If you only identify 5-10 SOI pages for a 100+ page document, YOU ARE MISSING PAGES.\n"
            "23. Each 'TOTAL INVESTMENTS' row you see should have 10-50+ pages of holdings before it.\n"
            "24. If calculated holdings would be <50% of a TOTAL row, you missed continuation pages.\n"
            "25. Include ALL pages from first SOI title to the very last 'TOTAL INVESTMENTS' row in the document.\n"
            "\n"
            "*** GAP FILLING RULE (CRITICAL FOR MULTI-FUND) ***\n"
            "26. If you identify pages [2, 10, 11] as SOI, pages 3-9 are MISSING.\n"
            "27. SOI sections are CONTIGUOUS - there are no 7-page gaps in the middle of holdings.\n"
            "28. When you see a gap of 3+ pages between identified SOI pages, FILL THE GAP.\n"
            "29. Example: [2, 10, 11] should become [2, 3, 4, 5, 6, 7, 8, 9, 10, 11].\n"
            "30. The pages in the gap contain continuation holdings that the model must extract.\n"
            "\n"
            "*** FUND-OF-FUNDS PATTERN (CRITICAL) ***\n"
            "31. Fund-of-funds documents have STRATEGY CATEGORIES as subsections:\n"
            "    - 'EVENT DRIVEN', 'FIXED INCOME ARBITRAGE', 'EQUITY ARBITRAGE'\n"
            "    - These are NOT fund names - they are investment strategies\n"
            "32. Each strategy section may span multiple pages with many holdings.\n"
            "33. If you see 'EVENT DRIVEN' on page 2 and 'EQUITY ARBITRAGE' on page 5:\n"
            "    - Pages 3-4 contain EVENT DRIVEN holdings (continuation)\n"
            "    - INCLUDE pages 3-4 in the SOI split\n"
            "34. Fund-of-funds often have 2+ distinct funds, each with the same strategy categories.\n"
            "35. Look for fund names in headers/footers: 'FCT', 'Multi-Strategy Series M', etc."
        ),
        "settings": {
            "table_cutoff": "preserve"
        }
    }


async def run_split(client: AsyncReducto, remote_input: str):
    """
    Run a split job on an uploaded PDF file.

    Args:
        client: AsyncReducto client instance
        remote_input: Remote input reference from upload

    Returns:
        Split job response
    """
    # Configure split job - reference the uploaded file on Reducto's server
    split_config = get_split_config(remote_input)

    # Run the split job
    response = await client.split.run(**split_config)

    return response
