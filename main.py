"""
High-performance batch processor for Reducto PDF extraction.

Features:
- Concurrent processing with asyncio.Semaphore(200)
- Fault-tolerant: errors are collected, not raised
- Comprehensive JSON/MD reporting at the end
"""

import os
import json
import re
import asyncio
import argparse
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import urlopen
from dotenv import load_dotenv
from reducto import AsyncReducto
from upload import upload_pdf
from split import run_split
from extract import get_extract_config
from validator import validate_extract_response, ValidationResult
from soi_sanitize import normalize_soi_rows, NormalizationResult

load_dotenv()

# Maximum concurrent Reducto API requests
MAX_CONCURRENCY = 200

# Maximum gap size to fill between SOI pages (inclusive)
# If splitter returns pages [2, 5], and MAX_PAGE_GAP=15, we fill to [2, 3, 4, 5]
# Increased from 10 to 15 to capture multi-fund documents where Fund A's SOI
# may span many pages before Fund B's SOI starts
MAX_PAGE_GAP = 15

# Larger gap for multi-fund documents (each fund's SOI can span 10-20+ pages)
# Increased from 20 to 30 for more aggressive page inclusion
MAX_PAGE_GAP_MULTI_FUND = 30


def fill_page_gaps(pages: List[int], max_gap: int = MAX_PAGE_GAP, verbose: bool = False) -> List[int]:
    """
    Fill small gaps in page sequences to prevent missing SOI continuation pages.
    
    The splitter may miss intermediate pages of the SOI (e.g., a page with just
    a few holdings and no clear header). If the gap is small, it's safer to
    include those pages than to risk missing holdings.
    
    Args:
        pages: List of page numbers identified by the splitter
        max_gap: Maximum gap size to fill (default 10)
        verbose: If True, print when gaps are filled
    
    Returns:
        List of page numbers with small gaps filled
    
    Example:
        fill_page_gaps([2, 5, 6, 15]) with max_gap=10
        -> [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]  # All gaps filled
    """
    if not pages:
        return []
    
    sorted_pages = sorted(set(pages))
    if len(sorted_pages) <= 1:
        return sorted_pages
    
    filled = [sorted_pages[0]]
    for i in range(1, len(sorted_pages)):
        prev_page = sorted_pages[i - 1]
        curr_page = sorted_pages[i]
        gap = curr_page - prev_page - 1
        
        # If gap is small, fill it
        if 0 < gap <= max_gap:
            for p in range(prev_page + 1, curr_page):
                filled.append(p)
        
        filled.append(curr_page)
    
    result = sorted(filled)
    
    # Log if we filled any gaps
    if verbose and set(result) != set(sorted_pages):
        filled_pages = sorted(set(result) - set(sorted_pages))
        print(f"  [GAP-FILL] Added pages {filled_pages} to SOI range")
    
    return result


def validate_split_completeness(split_pages: List[int], verbose: bool = False) -> List[int]:
    """
    Validate and potentially expand split pages if they appear incomplete.
    
    If the detected pages are sparse (gaps > 30% of total span), this indicates
    the splitter may have missed continuation pages. In this case, we fill
    ALL gaps to ensure completeness.
    
    Args:
        split_pages: List of page numbers identified by the splitter
        verbose: If True, print when aggressive filling is applied
    
    Returns:
        List of page numbers, potentially expanded to fill all gaps
    """
    if not split_pages or len(split_pages) < 2:
        return split_pages
    
    sorted_pages = sorted(set(split_pages))
    page_span = max(sorted_pages) - min(sorted_pages) + 1
    
    # If detected pages cover less than 70% of the span, splitter likely missed pages
    coverage_ratio = len(sorted_pages) / page_span
    
    if coverage_ratio < 0.7:
        # Fill ALL gaps - the splitter is unreliable for this document
        if verbose:
            print(f"  [SPLIT-VALIDATE] Low coverage ({coverage_ratio:.1%}), filling all gaps in range {min(sorted_pages)}-{max(sorted_pages)}")
        return list(range(min(sorted_pages), max(sorted_pages) + 1))
    
    return sorted_pages


def validate_split_for_multi_fund(
    split_pages: List[int],
    extract_json: Optional[Dict[str, Any]] = None,
    total_document_pages: Optional[int] = None,
    verbose: bool = False,
) -> List[int]:
    """
    Aggressively expand split pages for multi-fund documents.
    
    Multi-fund documents have multiple 'TOTAL INVESTMENTS' rows and often span
    many more pages than the splitter identifies. This function detects multi-fund
    patterns and expands the page range to capture all holdings.
    
    Detection heuristics:
    1. Multiple TOTAL rows in extraction (each fund has its own TOTAL)
    2. Holdings with different fund names in section_path[0]
    3. Strategy categories at root level (indicates missing fund attribution)
    
    Expansion strategy:
    - If multi-fund detected and split covers <50% of document, expand to full range
    - If split has large gaps (>10 pages), fill them all
    - Always include all pages from first SOI page to last SOI page
    
    Args:
        split_pages: List of page numbers identified by the splitter
        extract_json: Optional extraction result (for detecting multi-fund patterns)
        total_document_pages: Optional total page count of the document
        verbose: If True, print when expansion is applied
    
    Returns:
        List of page numbers, potentially expanded for multi-fund documents
    """
    if not split_pages:
        return split_pages
    
    sorted_pages = sorted(set(split_pages))
    if len(sorted_pages) < 2:
        return sorted_pages
    
    is_multi_fund = False
    total_rows_count = 0
    fund_names = set()
    has_strategy_at_root = False
    
    # Known strategy categories that shouldn't be at root level
    strategy_categories = {
        "event driven", "fixed income arbitrage", "equity arbitrage",
        "credit strategies", "long/short equity", "multi-strategy",
        "convertible arbitrage", "distressed/restructuring", "merger arbitrage",
        "global macro", "statistical arbitrage", "relative value",
    }
    
    # Analyze extraction for multi-fund patterns
    if extract_json:
        soi_rows = extract_json.get("result", {}).get("soi_rows", [])
        
        for row in soi_rows:
            # Count TOTAL rows
            row_type = row.get("row_type")
            if isinstance(row_type, dict):
                row_type = row_type.get("value")
            if row_type == "TOTAL":
                total_rows_count += 1
            
            # Collect fund names and detect strategy-at-root
            section_path = row.get("section_path")
            if isinstance(section_path, dict):
                section_path = section_path.get("value")
            if isinstance(section_path, list) and section_path:
                first_elem = section_path[0]
                if isinstance(first_elem, dict):
                    first_elem = first_elem.get("value")
                if first_elem and isinstance(first_elem, str):
                    # Check if first element is a strategy category (bad)
                    if first_elem.lower().strip() in strategy_categories:
                        has_strategy_at_root = True
                    else:
                        fund_names.add(first_elem)
        
        # Multi-fund detection
        if total_rows_count >= 2:
            is_multi_fund = True
        if len(fund_names) >= 2:
            is_multi_fund = True
        if has_strategy_at_root and fund_names:
            # Strategy at root + other fund names = multi-fund with mislabeling
            is_multi_fund = True
    
    if not is_multi_fund:
        return sorted_pages
    
    # Multi-fund document detected - apply aggressive expansion
    min_page = min(sorted_pages)
    max_page = max(sorted_pages)
    page_span = max_page - min_page + 1
    current_coverage = len(sorted_pages) / page_span
    
    if verbose:
        print(f"  [MULTI-FUND] Detected: {total_rows_count} TOTAL rows, {len(fund_names)} fund names, strategy_at_root={has_strategy_at_root}")
    
    # Strategy 1: If coverage is low (<70%), fill ALL gaps
    if current_coverage < 0.7:
        if verbose:
            print(f"  [MULTI-FUND] Low coverage ({current_coverage:.1%}), filling all gaps from page {min_page} to {max_page}")
        return list(range(min_page, max_page + 1))
    
    # Strategy 2: If we have total document pages and split is <50% of document, expand
    if total_document_pages and len(sorted_pages) < total_document_pages * 0.5:
        # Expand to include more pages after the last identified page
        # Multi-fund docs often have Fund B's SOI after Fund A's
        expansion_factor = 1.5  # Expand by 50%
        new_max = min(int(max_page * expansion_factor), total_document_pages)
        if new_max > max_page:
            if verbose:
                print(f"  [MULTI-FUND] Expanding page range from {max_page} to {new_max}")
            return list(range(min_page, new_max + 1))
    
    # Strategy 3: Fill all gaps regardless of size for multi-fund
    if verbose:
        print(f"  [MULTI-FUND] Filling all gaps in range {min_page}-{max_page}")
    return list(range(min_page, max_page + 1))


def validate_split_quality(split_json: Dict[str, Any], verbose: bool = False) -> List[str]:
    """
    Validate the quality of a split result and return warnings if suspect.
    
    Quality checks:
    1. At least 5 SOI pages for most documents (very short SOIs are rare)
    2. No large gaps (>10 pages) in SOI page list
    3. Page numbers are sequential or near-sequential
    4. Multiple "Schedule of Investments" titles detected = multi-fund
    
    Args:
        split_json: The split result JSON
        verbose: If True, print warnings
    
    Returns:
        List of warning messages if quality is suspect
    """
    warnings = []
    
    if not split_json:
        return warnings
    
    splits = split_json.get("result", {}).get("splits", [])
    soi_pages = []
    
    for split in splits:
        if str(split.get("name", "")).lower() == "soi":
            pages = split.get("pages", []) or []
            soi_pages = sorted([int(p) for p in pages if isinstance(p, int) or str(p).isdigit()])
            break
    
    if not soi_pages:
        warnings.append("No SOI pages identified by splitter")
        return warnings
    
    # Check 1: Minimum page count
    if len(soi_pages) < 5:
        warnings.append(f"Only {len(soi_pages)} SOI pages identified - may be missing pages")
    
    # Check 2: Large gaps in page sequence
    if len(soi_pages) >= 2:
        max_gap = 0
        gap_location = None
        for i in range(1, len(soi_pages)):
            gap = soi_pages[i] - soi_pages[i-1] - 1
            if gap > max_gap:
                max_gap = gap
                gap_location = (soi_pages[i-1], soi_pages[i])
        
        if max_gap > 10:
            warnings.append(f"Large gap of {max_gap} pages between pages {gap_location[0]} and {gap_location[1]}")
    
    # Check 3: Page span vs page count ratio
    if len(soi_pages) >= 2:
        page_span = max(soi_pages) - min(soi_pages) + 1
        coverage = len(soi_pages) / page_span
        if coverage < 0.5:
            warnings.append(f"Low page coverage ({coverage:.1%}) - splitter may have missed continuation pages")
    
    # Check 4: Very few pages for large documents
    # (This would require knowing total document pages, which we may not have here)
    
    if verbose and warnings:
        for w in warnings:
            print(f"  [SPLIT-QUALITY] {w}")
    
    return warnings


def _to_jsonable(obj: Any) -> Dict[str, Any]:
    """Convert SDK response objects to JSON-ready dictionaries."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return obj
    # Fallback: best-effort serialization
    return json.loads(json.dumps(obj, default=str))


def extract_soi_pages_from_split(split_response: Any) -> List[int]:
    """Extract SOI pages from a split response (object, dict, or string)."""
    # Prefer structured data
    data = None
    if hasattr(split_response, "model_dump"):
        data = split_response.model_dump()
    elif isinstance(split_response, dict):
        data = split_response

    if data:
        splits = data.get("result", {}).get("splits", [])
        for split in splits:
            if str(split.get("name")).lower() == "soi":
                pages = split.get("pages", []) or []
                return sorted(int(p) for p in pages if isinstance(p, int) or str(p).isdigit())

    # Fallback: parse from stringified response
    split_str = str(split_response)
    match = re.search(r"name='SOI',\\s*pages=\\[([^\\]]+)\\]", split_str)
    if not match:
        return []
    pages_str = match.group(1)
    pages = [p.strip() for p in pages_str.split(",") if p.strip()]
    return sorted(int(p) for p in pages if p.isdigit())


def detect_multi_fund_document(extract_json: Optional[Dict[str, Any]], split_json: Optional[Dict[str, Any]]) -> bool:
    """
    Detect if this appears to be a multi-fund document.
    
    Multi-fund documents contain multiple distinct funds, each with their own
    Schedule of Investments. These require larger page gap filling to capture
    all holdings.
    
    Detection heuristics:
    1. Multiple TOTAL rows in the extraction
    2. Large page span (100+ pages)
    3. Multiple distinct fund names in section paths
    
    Returns True if the document appears to be multi-fund.
    """
    # Check extraction for multiple TOTAL rows
    if extract_json:
        soi_rows = extract_json.get("result", {}).get("soi_rows", [])
        total_count = 0
        fund_names = set()
        
        for row in soi_rows:
            # Count TOTAL rows
            row_type = row.get("row_type")
            if isinstance(row_type, dict):
                row_type = row_type.get("value")
            if row_type == "TOTAL":
                total_count += 1
            
            # Collect unique fund names from section paths
            section_path = row.get("section_path")
            if isinstance(section_path, dict):
                section_path = section_path.get("value")
            if isinstance(section_path, list) and section_path:
                # First element is often the fund name
                fund_name = section_path[0]
                if isinstance(fund_name, dict):
                    fund_name = fund_name.get("value")
                if fund_name and isinstance(fund_name, str):
                    fund_names.add(fund_name)
        
        # Multiple TOTAL rows or multiple fund names suggests multi-fund
        if total_count >= 2:
            return True
        if len(fund_names) >= 2:
            return True
    
    # Check split for large page span
    if split_json:
        splits = split_json.get("result", {}).get("splits", [])
        for split in splits:
            if str(split.get("name", "")).lower() == "soi":
                pages = split.get("pages", []) or []
                if len(pages) >= 20:  # 20+ SOI pages suggests multi-fund
                    return True
                # Check page span (difference between first and last page)
                if pages:
                    page_nums = [int(p) for p in pages if isinstance(p, int) or str(p).isdigit()]
                    if page_nums:
                        span = max(page_nums) - min(page_nums)
                        if span >= 50:  # 50+ page span suggests multi-fund
                            return True
    
    return False


def get_dynamic_page_gap(extract_json: Optional[Dict[str, Any]], split_json: Optional[Dict[str, Any]], verbose: bool = False) -> int:
    """
    Determine the appropriate MAX_PAGE_GAP based on document characteristics.
    
    Multi-fund documents need larger gaps because each fund's SOI can span
    10-20+ pages, and the splitter may miss continuation pages.
    
    Returns:
        MAX_PAGE_GAP_MULTI_FUND (20) for multi-fund documents
        MAX_PAGE_GAP (10) for single-fund documents
    """
    is_multi_fund = detect_multi_fund_document(extract_json, split_json)
    
    if is_multi_fund:
        if verbose:
            print("  [MULTI-FUND] Detected multi-fund document, using larger page gap")
        return MAX_PAGE_GAP_MULTI_FUND
    
    return MAX_PAGE_GAP


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file into a dictionary if it exists."""
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


async def process_file(
    client: AsyncReducto,
    pdf_path: Path,
    split_dir: Path,
    extract_urls_dir: Path,
    extract_dir: Path,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Upload -> split -> extract SOI pages for a single file (PDF or TXT)."""
    async with semaphore:
        try:
            print(f"[START] {pdf_path.name}")

            split_output = split_dir / f"{pdf_path.stem}_split_result.json"
            extract_urls_output = extract_urls_dir / f"{pdf_path.stem}_extract_response.json"
            extract_output = extract_dir / f"{pdf_path.stem}_extract_result.json"

            # Short-circuit if raw extract already exists
            if extract_output.exists():
                print(f"  [SKIP] {pdf_path.name} - extract already exists")
                # Load existing JSONs for validation
                existing_split_json = _load_json(split_output)
                existing_extract_json = _load_json(extract_urls_output)
                return {
                    "file": pdf_path.name,
                    "status": "skipped",
                    "reason": "extract already present",
                    "split_output": str(split_output),
                    "extract_response_output": str(extract_urls_output),
                    "extract_output": str(extract_output),
                    "soi_pages": [],
                    "split_json": existing_split_json,
                    "extract_json": existing_extract_json,
                }

            # Ensure split exists (reuse if present)
            split_json = _load_json(split_output)
            if split_json is None:
                print(f"  [SPLIT] {pdf_path.name}")
                remote_input_for_split = await upload_pdf(client, pdf_path)
                split_response = await run_split(client, remote_input_for_split)
                split_json = _to_jsonable(split_response)
                with open(split_output, "w") as f:
                    json.dump(split_json, f, indent=2, default=str)

            soi_pages = extract_soi_pages_from_split(split_json)
            if not soi_pages:
                print(f"  [SKIP] {pdf_path.name} - no SOI pages found")
                return {
                    "file": pdf_path.name,
                    "status": "skipped",
                    "reason": "No SOI pages found",
                    "split_output": str(split_output),
                    "split_json": split_json,
                    "extract_json": None,
                }
            
            # Validate split quality and log any warnings
            split_warnings = validate_split_quality(split_json, verbose=True)
            if split_warnings:
                print(f"  [SPLIT-QUALITY] {pdf_path.name} - {len(split_warnings)} quality warning(s)")

            print(f"  [EXTRACT] {pdf_path.name} - {len(soi_pages)} SOI pages")

            # Try to use existing extract response to download raw result
            extract_json = _load_json(extract_urls_output)
            downloaded = False
            if extract_json:
                result_url = extract_json.get("result", {}).get("url")
                if result_url:
                    try:
                        with urlopen(result_url) as resp:
                            extract_output.write_bytes(resp.read())
                        downloaded = True
                    except Exception:
                        pass

            # If no existing extract or download failed, run extraction
            if not downloaded:
                remote_input = await upload_pdf(client, pdf_path)
                
                extract_config = get_extract_config(remote_input, soi_pages)
                extract_response = await client.extract.run(**extract_config)
                extract_json = _to_jsonable(extract_response)

                with open(extract_urls_output, "w") as f:
                    json.dump(extract_json, f, indent=2, default=str)

                result_url = extract_json.get("result", {}).get("url")
                if result_url:
                    try:
                        with urlopen(result_url) as resp:
                            extract_output.write_bytes(resp.read())
                    except Exception:
                        extract_output = None
                else:
                    extract_output = None

            print(f"  [DONE] {pdf_path.name}")

            return {
                "file": pdf_path.name,
                "status": "success",
                "split_output": str(split_output),
                "extract_response_output": str(extract_urls_output),
                "extract_output": str(extract_output) if extract_output else None,
                "soi_pages": soi_pages,
                "split_json": split_json,
                "extract_json": extract_json,
            }

        except Exception as e:
            error_msg = str(e)
            tb = traceback.format_exc()
            print(f"  [ERROR] {pdf_path.name}: {error_msg}")
            return {
                "file": pdf_path.name,
                "status": "error",
                "error": error_msg,
                "traceback": tb,
                "split_json": None,
                "extract_json": None,
            }


def _write_comprehensive_report(
    all_results: List[dict],
    validation_results: List[ValidationResult],
    batch_dir: Path,
    validation_details_dir: Path,
    run_timestamp: str,
    batch_num: int,
) -> None:
    """
    Write comprehensive batch run report with errors, validation, and statistics.
    
    Creates in batch_dir (root):
      - validation_summary.json: Quick summary for batch overview
      - validation_summary.md: Human-readable summary at top level
    
    Creates in validation_details_dir:
      - run_report.json: Full detailed report
      - batch_report.csv: CSV for per-file analysis
      - {filename}_validation.json: Per-file validation results (written separately)
    """
    import csv
    from collections import Counter
    
    # Categorize results
    successes = [r for r in all_results if r.get("status") == "success"]
    skipped = [r for r in all_results if r.get("status") == "skipped"]
    errors = [r for r in all_results if r.get("status") == "error"]
    
    # Validation aggregation
    code_counts: Counter = Counter()
    files_with_errors: List[str] = []
    files_with_warnings: List[str] = []
    files_with_arith_errors: List[str] = []
    files_with_root_mismatch: List[str] = []
    
    val_by_file: Dict[str, ValidationResult] = {}
    for vr in validation_results:
        val_by_file[vr.source_name] = vr
        for issue in vr.issues:
            code_counts[issue.code] += 1
        
        if vr.error_count() > 0:
            files_with_errors.append(vr.source_name)
        elif vr.warning_count() > 0:
            files_with_warnings.append(vr.source_name)
        
        if vr.has_arithmetic_error:
            files_with_arith_errors.append(vr.source_name)
        
        if vr.root_sum_mismatch:
            files_with_root_mismatch.append(vr.source_name)

    total_files = len(all_results)
    total_val_errors = sum(v.error_count() for v in validation_results)
    total_val_warnings = sum(v.warning_count() for v in validation_results)
    total_rows = sum(v.total_rows for v in validation_results)
    
    # Build comprehensive JSON report
    report_json = {
        "batch_number": batch_num,
        "run_timestamp": run_timestamp,
        "summary": {
            "total_files": total_files,
            "successful": len(successes),
            "skipped": len(skipped),
            "failed": len(errors),
            "validated": len(validation_results),
            "total_rows_extracted": total_rows,
            "validation_errors": total_val_errors,
            "validation_warnings": total_val_warnings,
            "files_with_arithmetic_errors": len(files_with_arith_errors),
            "files_with_root_mismatch": len(files_with_root_mismatch),
        },
        "errors": [
            {
                "file": e["file"],
                "error": e.get("error", "Unknown"),
                "traceback": e.get("traceback", ""),
            }
            for e in errors
        ],
        "skipped": [
            {
                "file": s["file"],
                "reason": s.get("reason", "Unknown"),
            }
            for s in skipped
        ],
        "validation_issues_by_code": dict(code_counts.most_common()),
        "files_with_validation_errors": files_with_errors,
        "files_with_validation_warnings": files_with_warnings,
        "files_with_arithmetic_errors": files_with_arith_errors,
        "files_with_root_mismatch": files_with_root_mismatch,
    }
    
    # Write detailed JSON report to validation_details/
    json_report_path = validation_details_dir / "run_report.json"
    with open(json_report_path, "w") as f:
        json.dump(report_json, f, indent=2)
    
    # Write CSV report for per-file analysis to validation_details/
    csv_path = validation_details_dir / "batch_report.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "filename",
            "status",
            "error_message",
            "total_rows",
            "holding_count",
            "subtotal_count",
            "total_count",
            "validation_errors",
            "validation_warnings",
            "has_arithmetic_error",
            "max_dollar_diff",
            "root_sum_mismatch",
            "calculated_total_fv",
            "extracted_total_fv",
            "top_error_code",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in all_results:
            stem = Path(result["file"]).stem
            vr = val_by_file.get(stem)
            
            row = {
                "filename": result["file"],
                "status": result.get("status", "unknown"),
                "error_message": result.get("error", "")[:200] if result.get("error") else "",
            }
            
            if vr:
                row.update({
                    "total_rows": vr.total_rows,
                    "holding_count": vr.holding_count,
                    "subtotal_count": vr.subtotal_count,
                    "total_count": vr.total_count,
                    "validation_errors": vr.error_count(),
                    "validation_warnings": vr.warning_count(),
                    "has_arithmetic_error": vr.has_arithmetic_error,
                    "max_dollar_diff": str(vr.max_dollar_diff),
                    "root_sum_mismatch": vr.root_sum_mismatch,
                    "calculated_total_fv": str(vr.calculated_total_fv) if vr.calculated_total_fv is not None else "",
                    "extracted_total_fv": str(vr.extracted_total_fv) if vr.extracted_total_fv is not None else "",
                    "top_error_code": vr.top_error_code() or "",
                })
            else:
                row.update({
                    "total_rows": "",
                    "holding_count": "",
                    "subtotal_count": "",
                    "total_count": "",
                    "validation_errors": "",
                    "validation_warnings": "",
                    "has_arithmetic_error": "",
                    "max_dollar_diff": "",
                    "root_sum_mismatch": "",
                    "calculated_total_fv": "",
                    "extracted_total_fv": "",
                    "top_error_code": "",
                })
            
            writer.writerow(row)
    
    # Write human-readable MD report
    md_lines = [
        f"# Batch #{batch_num} - Run Report",
        f"",
        f"**Run:** {run_timestamp}",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total Files | {total_files} |",
        f"| Successful | {len(successes)} |",
        f"| Skipped | {len(skipped)} |",
        f"| **Failed (Errors)** | **{len(errors)}** |",
        f"| Validated | {len(validation_results)} |",
        f"| Total Rows Extracted | {total_rows} |",
        f"",
    ]
    
    # Processing Errors Section
    if errors:
        md_lines.extend([
            f"## Processing Errors ({len(errors)} files)",
            f"",
            f"These files failed during upload/split/extract:",
            f"",
        ])
        for i, e in enumerate(errors[:50], 1):  # Limit to first 50
            error_msg = e.get("error", "Unknown error")[:150]
            md_lines.append(f"{i}. **{e['file']}**: `{error_msg}`")
        if len(errors) > 50:
            md_lines.append(f"")
            md_lines.append(f"... and {len(errors) - 50} more errors. See JSON report for full list.")
        md_lines.append(f"")
    
    # Validation Errors Section
    if total_val_errors > 0 or total_val_warnings > 0:
        md_lines.extend([
            f"## Validation Results",
            f"",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Files with Errors | {len(files_with_errors)} |",
            f"| Files with Warnings Only | {len(files_with_warnings)} |",
            f"| Files with Arithmetic Errors | {len(files_with_arith_errors)} |",
            f"| Files with Grand Total Mismatch | {len(files_with_root_mismatch)} |",
            f"| Total Errors | {total_val_errors} |",
            f"| Total Warnings | {total_val_warnings} |",
            f"",
        ])
        
        # Top error codes
        if code_counts:
            md_lines.extend([
                f"### Top Validation Issue Codes",
                f"",
                f"| Code | Count |",
                f"|------|-------|",
            ])
            for code, count in code_counts.most_common(15):
                md_lines.append(f"| `{code}` | {count} |")
            md_lines.append(f"")
        
        # Files with arithmetic errors
        if files_with_arith_errors:
            md_lines.extend([
                f"### Files with Arithmetic Errors",
                f"",
                f"These files have math that doesn't add up:",
                f"",
            ])
            for fname in files_with_arith_errors[:30]:
                md_lines.append(f"- `{fname}`")
            if len(files_with_arith_errors) > 30:
                md_lines.append(f"- ... and {len(files_with_arith_errors) - 30} more")
            md_lines.append(f"")
        
        # Files with root mismatch
        if files_with_root_mismatch:
            md_lines.extend([
                f"### Files with Grand Total Mismatch",
                f"",
                f"Holdings don't sum to reported total:",
                f"",
            ])
            for fname in files_with_root_mismatch[:30]:
                md_lines.append(f"- `{fname}`")
            if len(files_with_root_mismatch) > 30:
                md_lines.append(f"- ... and {len(files_with_root_mismatch) - 30} more")
            md_lines.append(f"")
    
    # Skipped files section
    if skipped:
        md_lines.extend([
            f"## Skipped Files ({len(skipped)} files)",
            f"",
        ])
        # Group by reason
        by_reason: Dict[str, List[str]] = {}
        for s in skipped:
            reason = s.get("reason", "Unknown")
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(s["file"])
        
        for reason, files in by_reason.items():
            md_lines.append(f"### {reason} ({len(files)} files)")
            md_lines.append(f"")
            for f in files[:20]:
                md_lines.append(f"- {f}")
            if len(files) > 20:
                md_lines.append(f"- ... and {len(files) - 20} more")
            md_lines.append(f"")
    
    md_lines.extend([
        f"## Output Files",
        f"",
        f"- **Full JSON Report**: `validation_details/run_report.json`",
        f"- **CSV Report**: `validation_details/batch_report.csv`",
        f"- **Per-file Validations**: `validation_details/<stem>_validation.json`",
        f"",
    ])
    
    # Write detailed markdown report to validation_details/
    md_report_path = validation_details_dir / "run_report.md"
    with open(md_report_path, "w") as f:
        f.write("\n".join(md_lines))
    
    # Write summary JSON to batch root for quick access
    summary_json = {
        "batch_number": batch_num,
        "run_timestamp": run_timestamp,
        "total_files": len(validation_results),
        "total_rows": total_rows,
        "total_errors": total_val_errors,
        "total_warnings": total_val_warnings,
        "files_with_errors": len(files_with_errors),
        "files_with_warnings": len(files_with_warnings),
        "files_with_arithmetic_errors": len(files_with_arith_errors),
        "files_with_root_mismatch": len(files_with_root_mismatch),
        "all_passed": total_val_errors == 0,
        "top_error_codes": dict(code_counts.most_common(10)),
        "files_with_errors_list": files_with_errors,
        "files_with_arithmetic_errors_list": files_with_arith_errors,
        "files_with_root_mismatch_list": files_with_root_mismatch,
    }
    with open(batch_dir / "validation_summary.json", "w") as f:
        json.dump(summary_json, f, indent=2)
    
    # Write summary markdown to batch root for quick human-readable overview
    summary_md_lines = [
        f"# Batch #{batch_num} - Validation Summary",
        "",
        f"**Run:** {run_timestamp}",
        "",
        "## Quick Stats",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Files Validated | {len(validation_results)} |",
        f"| Total Rows Extracted | {total_rows} |",
        f"| Total Validation Errors | {total_val_errors} |",
        f"| Total Validation Warnings | {total_val_warnings} |",
        "",
        "## Arithmetic Validation (Deterministic Checks)",
        "",
        "These are **hard logic deterministic checks** that verify all numbers add up correctly:",
        "",
        f"| Check | Files with Issues |",
        f"|-------|-------------------|",
        f"| Holdings sum to subtotals | {len(files_with_arith_errors)} failures |",
        f"| Subtotals sum to grand total | {len(files_with_root_mismatch)} failures |",
        "",
    ]
    
    if total_val_errors == 0 and total_val_warnings == 0:
        summary_md_lines.extend([
            "## Result: ALL PASSED",
            "",
            "All files passed deterministic validation. All numbers add up correctly.",
            "",
        ])
    else:
        summary_md_lines.extend([
            "## Top Issues",
            "",
            "| Code | Count | Description |",
            "|------|-------|-------------|",
        ])
        code_descriptions = {
            "ARITH_MISMATCH_FV": "Fair value sum doesn't match subtotal",
            "ARITH_MISMATCH_COST": "Cost sum doesn't match subtotal",
            "ARITH_MISMATCH_PCT": "Percent sum doesn't match subtotal",
            "GRAND_TOTAL_MISMATCH_FV": "Holdings don't sum to grand total (fair value)",
            "GRAND_TOTAL_MISMATCH_COST": "Holdings don't sum to grand total (cost)",
            "GRAND_TOTAL_MISMATCH_PCT": "Holdings don't sum to grand total (percent)",
            "MULTIPLE_NUMERIC_TOKENS": "Field contains multiple conflicting numbers",
            "MISSING_ROW_TYPE": "Row is missing required type field",
            "INVALID_ROW_TYPE": "Row has invalid type",
        }
        for code, count in code_counts.most_common(10):
            desc = code_descriptions.get(code, "See detailed report")
            summary_md_lines.append(f"| `{code}` | {count} | {desc} |")
        summary_md_lines.append("")
        
        # List files with arithmetic errors
        if files_with_arith_errors:
            summary_md_lines.extend([
                "## Files with Arithmetic Errors",
                "",
                "These files have holdings that don't sum to their subtotals:",
                "",
            ])
            for fname in files_with_arith_errors[:20]:
                summary_md_lines.append(f"- `{fname}`")
            if len(files_with_arith_errors) > 20:
                summary_md_lines.append(f"- ... and {len(files_with_arith_errors) - 20} more")
            summary_md_lines.append("")
        
        # List files with root mismatch
        if files_with_root_mismatch:
            summary_md_lines.extend([
                "## Files with Grand Total Mismatch",
                "",
                "These files have holdings that don't sum to the reported grand total:",
                "",
            ])
            for fname in files_with_root_mismatch[:20]:
                summary_md_lines.append(f"- `{fname}`")
            if len(files_with_root_mismatch) > 20:
                summary_md_lines.append(f"- ... and {len(files_with_root_mismatch) - 20} more")
            summary_md_lines.append("")
    
    summary_md_lines.extend([
        "## Detailed Reports",
        "",
        "For full details, see:",
        "",
        "- `validation_details/run_report.json` - Complete machine-readable report",
        "- `validation_details/run_report.md` - Full human-readable report",
        "- `validation_details/batch_report.csv` - Per-file analysis spreadsheet",
        "- `validation_details/<filename>_validation.json` - Per-file validation details",
        "",
    ])
    
    with open(batch_dir / "validation_summary.md", "w") as f:
        f.write("\n".join(summary_md_lines))


async def main(input_folder: str = "txt"):
    client = AsyncReducto(
        api_key=os.environ.get("REDUCTO_API_KEY"),
        environment="production",
    )

    input_dir = Path(input_folder)
    
    # Look for both PDF and TXT files
    pdf_files = list(input_dir.glob("*.pdf"))
    txt_files = list(input_dir.glob("*.txt"))
    all_files = pdf_files + txt_files

    if not all_files:
        print(f"No PDF or TXT files found in {input_dir}")
        return

    run_timestamp = datetime.now().strftime("%b %d, %Y at %I:%M %p")  # e.g., "Dec 22, 2025 at 02:30 PM"
    
    # Create outputs directory and numbered batch subdirectory
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    
    # Find the next batch number
    existing_batches = list(outputs_dir.glob("batch_*"))
    batch_numbers = []
    for b in existing_batches:
        # Extract number from folder name like "batch_3"
        parts = b.name.split("_")
        if len(parts) >= 2 and parts[-1].isdigit():
            batch_numbers.append(int(parts[-1]))
    next_batch_num = max(batch_numbers, default=0) + 1
    
    batch_dir = outputs_dir / f"batch_{next_batch_num}"
    split_dir = batch_dir / "splits"
    extract_dir = batch_dir / "extractions"
    validation_details_dir = batch_dir / "validation_details"
    
    batch_dir.mkdir(exist_ok=True)
    split_dir.mkdir(exist_ok=True)
    extract_dir.mkdir(exist_ok=True)
    validation_details_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("REDUCTO BATCH PROCESSOR")
    print("=" * 70)
    print(f"Batch #{next_batch_num} - {run_timestamp}")
    print(f"Files to process: {len(all_files)} ({len(pdf_files)} PDF, {len(txt_files)} TXT)")
    print(f"Max concurrency: {MAX_CONCURRENCY}")
    print(f"Output directory: {batch_dir}/")
    print(f"  - splits/          (intermediate split results)")
    print(f"  - extractions/     (Reducto JSON responses)")
    print(f"  - validation_details/ (per-file validations)")
    print("=" * 70)
    print()

    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    # Create all tasks (extract_dir now holds both extract response and raw result)
    tasks = [
        process_file(client, file_path, split_dir, extract_dir, extract_dir, semaphore)
        for file_path in all_files
    ]

    # Run all tasks concurrently and collect results
    print(f"Starting concurrent processing of {len(all_files)} files...")
    print()
    
    all_results = await asyncio.gather(*tasks)

    # Run validation on all successful/skipped files with extract_json
    print()
    print("Running validation on extracted files...")
    
    validation_results: List[ValidationResult] = []
    
    for result in all_results:
        extract_json = result.get("extract_json")
        split_json = result.get("split_json")
        
        if extract_json is not None:
            file_stem = Path(result["file"]).stem
            
            # Extract SOI pages from split result for page-based filtering
            soi_pages_set: set = set()
            if split_json:
                splits = split_json.get("result", {}).get("splits", [])
                for split in splits:
                    if str(split.get("name", "")).lower() == "soi":
                        pages = split.get("pages", []) or []
                        soi_pages_list = [int(p) for p in pages if isinstance(p, int) or str(p).isdigit()]
                        
                        # First: validate split completeness and expand if sparse
                        soi_pages_list = validate_split_completeness(soi_pages_list, verbose=True)
                        
                        # CRITICAL: Check for multi-fund patterns and expand aggressively
                        # This catches documents where Fund A and Fund B have separate SOI sections
                        # and the splitter only identified some pages from each
                        soi_pages_list = validate_split_for_multi_fund(
                            soi_pages_list,
                            extract_json=extract_json,
                            verbose=True,
                        )
                        
                        # Determine dynamic page gap based on document type
                        dynamic_gap = get_dynamic_page_gap(extract_json, split_json, verbose=True)
                        # Fill gaps to capture continuation pages the splitter may have missed
                        soi_pages_list = fill_page_gaps(soi_pages_list, max_gap=dynamic_gap, verbose=True)
                        soi_pages_set = set(soi_pages_list)
                        break
            
            # Sanitize soi_rows before validation to fix misclassified rows
            # Pass soi_pages to enable page-based filtering. The gap-filling above ensures
            # we don't drop valid continuation pages. Content-based filtering in the sanitizer
            # will catch "Top Holdings" tables that slip through.
            norm_result: NormalizationResult | None = None
            soi_rows = extract_json.get("result", {}).get("soi_rows", [])
            if soi_rows:
                sanitized_rows, norm_result = normalize_soi_rows(
                    soi_rows,
                    soi_pages=soi_pages_set if soi_pages_set else None,
                )
                # Replace with sanitized rows for validation
                if "result" in extract_json:
                    extract_json["result"]["soi_rows"] = sanitized_rows
            
            val_result = validate_extract_response(
                extract_json,
                split_json=split_json,
                source_name=file_stem,
            )
            
            # Attach normalization metadata and add warning if fixes were applied
            if norm_result and norm_result.fix_count > 0:
                val_result.normalization = norm_result.to_dict()
                # Add a warning issue to highlight normalization was applied
                reason_summary = ", ".join(
                    f"{code}={count}" 
                    for code, count in sorted(
                        {e.reason_code: sum(1 for x in norm_result.fix_log if x.reason_code == e.reason_code) 
                         for e in norm_result.fix_log}.items()
                    )
                )
                val_result.add(
                    "warning",
                    "NORMALIZATION_APPLIED",
                    f"Sanitizer fixed {norm_result.fix_count} row(s): {reason_summary}",
                    fix_count=norm_result.fix_count,
                    dropped=norm_result.dropped_count,
                    converted=norm_result.converted_count,
                )
            
            validation_results.append(val_result)
            
            # Write per-file validation report to validation_details/
            val_output = validation_details_dir / f"{file_stem}_validation.json"
            with open(val_output, "w") as f:
                json.dump(val_result.to_dict(), f, indent=2)

    # Write comprehensive reports (summary at batch root, details in validation_details/)
    print("Writing reports...")
    _write_comprehensive_report(
        all_results, 
        validation_results, 
        batch_dir,  # Root for summary files
        validation_details_dir,  # Subdir for detailed reports
        run_timestamp,
        next_batch_num,
    )

    # Print final summary
    successes = [r for r in all_results if r.get("status") == "success"]
    skipped = [r for r in all_results if r.get("status") == "skipped"]
    errors = [r for r in all_results if r.get("status") == "error"]

    print()
    print("=" * 70)
    print(f"BATCH #{next_batch_num} COMPLETE")
    print("=" * 70)
    print(f"Total files: {len(all_results)}")
    print(f"  Successful: {len(successes)}")
    print(f"  Skipped: {len(skipped)}")
    print(f"  Errors: {len(errors)}")
    print()
    
    if validation_results:
        total_val_errors = sum(v.error_count() for v in validation_results)
        total_val_warnings = sum(v.warning_count() for v in validation_results)
        files_with_arith = sum(1 for v in validation_results if v.has_arithmetic_error)
        files_with_root = sum(1 for v in validation_results if v.root_sum_mismatch)
        
        print(f"Validation ({len(validation_results)} files):")
        print(f"  Errors: {total_val_errors}")
        print(f"  Warnings: {total_val_warnings}")
        print(f"  Arithmetic errors: {files_with_arith} files")
        print(f"  Grand total mismatch: {files_with_root} files")
        print()
    
    print(f"Output: {batch_dir}/")
    print(f"  - validation_summary.json  (quick summary)")
    print(f"  - validation_summary.md    (human-readable summary)")
    print(f"  - validation_details/      (detailed reports)")
    print(f"      - run_report.json      (full details)")
    print(f"      - batch_report.csv     (per-file analysis)")
    print("=" * 70)

    # List errors if any
    if errors:
        print()
        print("FILES WITH ERRORS:")
        for e in errors[:20]:
            print(f"  - {e['file']}: {e.get('error', 'Unknown')[:80]}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more (see report)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process PDF files from a specified folder using Reducto SDK (concurrent)"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default="txt",
        help="Folder path containing PDF files to process (default: txt)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.folder))
