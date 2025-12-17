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
                        "Extract Schedule of Investments tables from SEC N-CSR/N-CSRS. "
                        "Preserve merged headers, multi-line security descriptions, and "
                        "page-spanning tables. Prefer table structure that keeps numeric "
                        "columns aligned (Principal/Shares, Cost, Fair Value, %Net Assets, "
                        "Interest Rate, Maturity)."
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
        "Rules:\n"
        "1) Exhaustively capture every investment line item (holding) and every "
        "subtotal/total line that represents summed values (e.g., per asset class, per "
        "sector, and overall Total Investments). Do not stop early.\n"
        "2) Distinguish holdings vs subtotal/total vs headers/footnotes:\n"
        "   - HOLDING rows have an identifiable investment/security and at least one "
        "numeric measure (value/fair value/cost/% net assets/quantity).\n"
        "   - SUBTOTAL rows summarize a group (e.g., sector, asset class) and may have "
        "value/% but no quantity.\n"
        "   - TOTAL rows represent overall totals (e.g., Total Investments, Total "
        "Portfolio Investments).\n"
        "   - Do NOT emit pure headers, page numbers, or narrative paragraphs as rows.\n"
        "3) Multi-line rows: if an investment name/description is split across lines "
        "(issuer line then tranche/series line), combine into a single HOLDING row.\n"
        "4) Preserve numbers exactly as printed in *_raw fields (including parentheses "
        "for negatives, currency codes like CAD, footnote markers like † ‡ # (a)). Do "
        "not infer or compute missing values.\n"
        "5) Track hierarchy: keep a running section_path from nearby headings (e.g., "
        "['Common Stocks', 'Airlines'] or ['Other']). Apply it to each emitted row.\n"
        "6) When a column is absent, set the corresponding field to null and store any "
        "unrecognized columns in additional_fields.\n\n"
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
                    "Each object is one line item from the schedule."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "row_type": {
                            "type": "string",
                            "enum": ["HOLDING", "SUBTOTAL", "TOTAL"],
                            "description": "Classification of the line item.",
                        },
                        "section_path": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                            "description": (
                                "Hierarchy of headings applying to this row (asset class "
                                "/ sector / strategy / geography)."
                            ),
                        },
                        "label": {
                            "type": ["string", "null"],
                            "description": (
                                "For SUBTOTAL/TOTAL rows, the subtotal/total label "
                                "exactly as shown (e.g., 'Total', 'Total Investments', "
                                "'Common Stocks', 'Other (continued)')."
                            ),
                        },
                        "investment": {
                            "type": ["string", "null"],
                            "description": (
                                "For HOLDING rows, the full investment/security name and "
                                "description as shown, including tranche/series/class if "
                                "applicable."
                            ),
                        },
                        "instrument_type": {
                            "type": ["string", "null"],
                            "description": (
                                "If explicitly stated: e.g., common stock, preferred, CLO "
                                "tranche, senior loan, bank debt, private fund interest, "
                                "derivative."
                            ),
                        },
                        "quantity_raw": {
                            "type": ["string", "null"],
                            "description": (
                                "Shares/units/principal/notional exactly as printed (e.g., "
                                "'$5,370,000', 'CAD 11,070,000', '58,413')."
                            ),
                        },
                        "quantity_type": {
                            "type": ["string", "null"],
                            "enum": [
                                "shares",
                                "principal",
                                "par",
                                "units",
                                "notional",
                                "contracts",
                                "other",
                                "unknown",
                                None,
                            ],
                            "description": "Best-effort type of quantity column.",
                        },
                        "cost_raw": {
                            "type": ["string", "null"],
                            "description": "Cost column text exactly as printed, if present.",
                        },
                        "amortized_cost_raw": {
                            "type": ["string", "null"],
                            "description": (
                                "Amortized cost column text exactly as printed, if present."
                            ),
                        },
                        "fair_value_raw": {
                            "type": ["string", "null"],
                            "description": (
                                "Fair value / Value at period end exactly as printed."
                            ),
                        },
                        "percent_net_assets_raw": {
                            "type": ["string", "null"],
                            "description": (
                                "% of net assets (or equivalent) exactly as printed, if "
                                "present."
                            ),
                        },
                        "interest_rate_raw": {
                            "type": ["string", "null"],
                            "description": (
                                "Interest/coupon rate text exactly as printed, including "
                                "reference rates/spreads (e.g., '10.254% (3 mo. USD Term "
                                "SOFR + 5.90%)#', 'Zero Coupon')."
                            ),
                        },
                        "maturity_date": {
                            "type": ["string", "null"],
                            "description": "Maturity date if present.",
                        },
                        "currency_raw": {
                            "type": ["string", "null"],
                            "description": (
                                "Currency code/symbol if explicitly shown (e.g., 'USD', "
                                "'CAD', '$')."
                            ),
                        },
                        "fair_value_level_raw": {
                            "type": ["string", "null"],
                            "description": (
                                "Fair value level / Level 1/2/3 classification text if present."
                            ),
                        },
                        "footnote_markers": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                            "description": (
                                "Footnote markers attached to the row (e.g., '†', '‡', "
                                "'#', '(a)', '1,2,3')."
                            ),
                        },
                        "additional_fields": {
                            "type": ["array", "null"],
                            "description": "Any extra columns not captured above.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "column_header": {"type": "string"},
                                    "value_raw": {"type": "string"},
                                },
                                "required": ["column_header", "value_raw"],
                            },
                        },
                        "row_text": {
                            "type": ["string", "null"],
                            "description": (
                                "Verbatim line item text (helpful for downstream debugging "
                                "when columns are ambiguous)."
                            ),
                        },
                    },
                    "required": ["row_type"],
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
