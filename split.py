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
                    "Statement of Investments. Include pages labeled '(continued)'. "
                    "EXCLUDE pages with 'Top Holdings', 'Largest Investment Holdings', 'Major Holdings', "
                    "'Top Ten Holdings', or similar summary tables that show only a subset of holdings "
                    "(typically 5-15 holdings with a partial Total). "
                    "These pages typically contain long tabular line items of holdings and columns like "
                    "Investments, Shares, Units, Principal/Par Amount, Cost/Amortized Cost, Fair Value/Value, "
                    "% of Net Assets, Interest Rate, Maturity Date, Notional, Level 1/2/3, and subtotal/total lines "
                    "such as 'Total Investments'. Include pages that show headings like 'Schedule of Investments', "
                    "'Portfolio of Investments', 'Consolidated Schedule of Investments', 'Condensed Schedule of Investments'."
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
        "split_rules": "Maximize recall for the SOI. A page can be assigned to multiple categories if it clearly contains both (e.g., SOI and SOI notes). If uncertain, include the page in SOI with conf=low rather than excluding it. Include all '(continued)' SOI pages even when the title is abbreviated.",
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
