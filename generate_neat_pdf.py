#!/usr/bin/env python3
"""
SEC TXT → Neat Multi-Page PDF Converter

Converts SEC .txt filings to professional, multi-page PDFs with:
- No table breaks: CSS 'break-inside: avoid' keeps tables intact
- No excessive whitespace: Collapses 3+ consecutive newlines to 2
- Wide landscape layout: Prevents ASCII table wrapping
- Playwright/Chromium rendering for high-quality output

Usage:
    python generate_neat_pdf.py --input-dir inputs_for_pdf_script --output-dir test-inputs/neat_pdfs
    python generate_neat_pdf.py  # Uses defaults
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from html import escape as html_escape
from pathlib import Path
from typing import Iterable, List, Optional

try:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
except ImportError as e:
    raise SystemExit(
        "Playwright is required.\n\n"
        "Install:\n"
        "  pip install playwright\n"
        "  python -m playwright install chromium\n"
    ) from e


# =============================================================================
# Constants
# =============================================================================

PEM_HEADER_PREFIXES = (
    "-----BEGIN PRIVACY-ENHANCED MESSAGE-----",
    "-----BEGIN PKCS7-----",
    "-----BEGIN PKCS #7 SIGNED DATA-----",
)

# SGML tags to strip for cleaner display
SGML_TAG_RE = re.compile(
    r"</?(?:S|C|CAPTION|FN|F\d+|PAGE)>",
    flags=re.IGNORECASE,
)

# Tags that are purely invisible (entire line is just a tag)
INVISIBLE_LINE_RE = re.compile(
    r"^\s*</?(?:S|C|CAPTION|FN|F\d+|PAGE)>\s*$",
    flags=re.IGNORECASE,
)

# Pattern to match 3+ consecutive newlines
EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")

# Pattern to match form-feed characters
FORM_FEED_RE = re.compile(r"\f")

# Pattern to detect summary/reconciliation blocks that should be glued to the previous block
# Matches: "Total", "Net Assets", "Members' Capital", "Liabilities", double underlines
SUMMARY_CHUNK_RE = re.compile(
    r"(?:total|net\s+assets|members['\u2019]?\s*capital|liabilities|excess|deficiency|={3,}|-{3,})",
    flags=re.IGNORECASE,
)

# Pattern to detect subsection headers that should be glued to the FOLLOWING block
# Matches: "CATEGORY NAME-X.XX%" or "CATEGORY NAME -- X.XX%" (geographic/type subsections)
# Examples: "GRAND CAYMAN-1.36%", "CHILEAN MUTUAL FUNDS-1.48%", "U.S. TREASURY BILLS-0.5%"
SUBSECTION_HEADER_RE = re.compile(
    r"^\s*[A-Z][A-Za-z\s.&/\-\']+[-\u2013\u2014]\s*\d+\.?\d*\s*%\s*$",
    flags=re.MULTILINE,
)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass(frozen=True)
class SecDocument:
    """A single <DOCUMENT> block from an SEC filing."""
    doc_type: str
    text: str


@dataclass
class TextBlock:
    """A block of plain text (not inside a <TABLE>)."""
    lines: List[str] = field(default_factory=list)


@dataclass
class TableBlock:
    """A block of text inside a <TABLE>...</TABLE> region."""
    lines: List[str] = field(default_factory=list)


Block = TextBlock | TableBlock


# =============================================================================
# Parsing Helpers
# =============================================================================

def _strip_pem_envelope(raw: str) -> str:
    """Strip PEM envelope if present, preserving SEC content."""
    if not raw.startswith(PEM_HEADER_PREFIXES):
        return raw
    idx = raw.find("<SEC-DOCUMENT>")
    if idx != -1:
        return raw[idx:]
    return raw


def _extract_documents_from_sec_txt(raw: str) -> List[SecDocument]:
    """Extract <DOCUMENT> blocks from an SEC filing."""
    doc_matches = list(re.finditer(r"<DOCUMENT>(.*?)</DOCUMENT>", raw, flags=re.DOTALL | re.IGNORECASE))
    if not doc_matches:
        text = _strip_pem_envelope(raw)
        return [SecDocument(doc_type="UNKNOWN", text=text)]

    docs: List[SecDocument] = []
    for m in doc_matches:
        block = m.group(1)
        type_match = re.search(r"<TYPE>([^\r\n<]+)", block, flags=re.IGNORECASE)
        doc_type = (type_match.group(1).strip() if type_match else "UNKNOWN").upper()

        text_match = re.search(r"<TEXT>(.*?)</TEXT>", block, flags=re.DOTALL | re.IGNORECASE)
        if text_match:
            text = text_match.group(1)
        else:
            text_start = re.search(r"<TEXT>(.*)$", block, flags=re.DOTALL | re.IGNORECASE)
            text = text_start.group(1) if text_start else block

        text = _strip_pem_envelope(text)
        docs.append(SecDocument(doc_type=doc_type, text=text))

    return docs


def _pick_primary_doc(docs: List[SecDocument]) -> int:
    """Pick the primary document (prefer N-CSR types, else largest)."""
    preferred = {"N-CSR", "N-CSRS", "NCSR", "NCSRS"}
    for i, d in enumerate(docs):
        if d.doc_type in preferred:
            return i
    return max(range(len(docs)), key=lambda i: len(docs[i].text))


# =============================================================================
# Text Sanitization
# =============================================================================

def _sanitize_text(text: str) -> str:
    """
    Clean up text for neat PDF output:
    - Normalize line endings
    - Remove form-feed characters
    - Collapse 3+ consecutive newlines to 2
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Remove form-feed characters (they cause artificial page breaks)
    text = FORM_FEED_RE.sub("", text)
    
    # Collapse 3+ consecutive newlines to exactly 2
    text = EXCESSIVE_NEWLINES_RE.sub("\n\n", text)
    
    return text


def _strip_sgml_tags_for_display(text: str) -> str:
    """Remove SGML tags like <S>, <C>, <PAGE> for cleaner display."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        # Skip lines that are purely SGML tags
        if INVISIBLE_LINE_RE.match(line):
            continue
        # Remove inline tags
        line = SGML_TAG_RE.sub("", line)
        cleaned.append(line)
    return "\n".join(cleaned)


# =============================================================================
# Block Segmentation (Text vs Table)
# =============================================================================

def _segment_into_blocks(text: str) -> List[Block]:
    """
    Segment text into TextBlock and TableBlock regions.
    
    SEC filings use <TABLE>...</TABLE> for ASCII tables.
    """
    # Find all <TABLE>...</TABLE> regions
    table_re = re.compile(r"<TABLE>(.*?)</TABLE>", flags=re.DOTALL | re.IGNORECASE)
    
    blocks: List[Block] = []
    last_end = 0
    
    for m in table_re.finditer(text):
        # Text before this table
        before = text[last_end:m.start()]
        if before.strip():
            blocks.append(TextBlock(lines=before.split("\n")))
        
        # The table content
        table_content = m.group(1)
        table_lines = table_content.split("\n")
        blocks.append(TableBlock(lines=table_lines))
        
        last_end = m.end()
    
    # Text after last table
    after = text[last_end:]
    if after.strip():
        blocks.append(TextBlock(lines=after.split("\n")))
    
    return blocks if blocks else [TextBlock(lines=text.split("\n"))]


# =============================================================================
# HTML Generation
# =============================================================================

# Maximum visible lines for a text block to be considered a "header candidate"
HEADER_MAX_LINES = 20

# Maximum total visible lines to accumulate as headers before a table
MAX_ACCUMULATED_HEADER_LINES = 35

# Maximum visible lines for a text block to be considered a "footer candidate"
FOOTER_MAX_LINES = 10

# Maximum total visible lines to accumulate as footers after a table
MAX_ACCUMULATED_FOOTER_LINES = 15

# Pattern to detect new section headers (e.g., "Category Name -- X.X%")
SECTION_HEADER_RE = re.compile(
    r"^\s*[A-Z][A-Za-z\s/&]+\s*--\s*\d+\.?\d*\s*%",
    flags=re.MULTILINE,
)


def _count_visible_lines(text: str) -> int:
    """Count non-empty lines in text after stripping SGML tags."""
    lines = text.split("\n")
    count = 0
    for line in lines:
        stripped = line.strip()
        if stripped and not INVISIBLE_LINE_RE.match(line):
            count += 1
    return count


def _is_header_candidate(block: TextBlock) -> bool:
    """
    Check if a text block qualifies as a header candidate.
    
    Header candidates are short blocks that typically contain:
    - Section titles (e.g., "SCHEDULE OF INVESTMENTS")
    - Dates (e.g., "June 30, 2003")
    - Separator lines (e.g., "----------------")
    - Page numbers
    - Footnotes markers (e.g., "* Prior years have been adjusted...")
    - Column headers (e.g., "Prin. Amt.", "or Shares", "Value (A)")
    
    We are permissive here - better to glue too much than too little.
    """
    block_text = "\n".join(block.lines)
    clean_text = _strip_sgml_tags_for_display(block_text)
    visible_lines = _count_visible_lines(clean_text)
    return visible_lines <= HEADER_MAX_LINES


def _is_footer_candidate(block: TextBlock) -> bool:
    """
    Check if a text block qualifies as a footer candidate.
    
    Footer candidates are short blocks that typically contain:
    - Subtotal/total lines (e.g., "3,989,082")
    - Separator lines (dashes, whitespace)
    - Footnote markers
    - Summary lines
    
    Returns False if the block looks like a new section header.
    """
    block_text = "\n".join(block.lines)
    clean_text = _strip_sgml_tags_for_display(block_text)
    visible_lines = _count_visible_lines(clean_text)
    
    # Must be short enough
    if visible_lines > FOOTER_MAX_LINES:
        return False
    
    # Reject if it looks like a new section header (e.g., "Category -- X.X%")
    if SECTION_HEADER_RE.search(clean_text):
        return False
    
    return True


def _is_summary_chunk(chunk: str, max_lines: int = 15) -> bool:
    """
    Check if a chunk looks like a summary/reconciliation block.
    
    Summary chunks (totals, net assets, members' capital lines) should be
    glued to the previous chunk to prevent awkward page breaks.
    """
    line_count = len([ln for ln in chunk.split("\n") if ln.strip()])
    if line_count > max_lines:
        return False
    return bool(SUMMARY_CHUNK_RE.search(chunk))


def _is_subsection_header_chunk(chunk: str, max_lines: int = 5) -> bool:
    """
    Check if a chunk looks like a subsection header (e.g., "GRAND CAYMAN-1.36%").
    
    Subsection headers should be glued to the FOLLOWING chunk to keep
    them together with their content. These are short chunks that contain
    a category/geographic name followed by a percentage.
    
    Examples:
    - "GRAND CAYMAN-1.36%"
    - "CHILEAN MUTUAL FUNDS-1.48%"
    - "U.S. TREASURY BILLS-0.5%"
    """
    lines = [ln for ln in chunk.split("\n") if ln.strip()]
    if len(lines) > max_lines:
        return False
    # Check if any line matches the subsection header pattern
    for line in lines:
        if SUBSECTION_HEADER_RE.match(line.strip()):
            return True
    return False


def _render_chunked_table(clean_text: str) -> str:
    """
    Split table content into logical chunks and wrap each in a protected div.
    
    Chunks are identified by blank lines (double newlines) which typically
    separate logical row groups in SEC filings. Each chunk gets 
    `break-inside: avoid` via CSS to prevent mid-entry page breaks.
    
    Merging logic:
    1. Summary/reconciliation chunks (e.g., "Total Investment Income",
       "MEMBERS' CAPITAL") are merged into the PRECEDING chunk (backward merge).
    2. Subsection header chunks (e.g., "GRAND CAYMAN-1.36%") are merged into
       the FOLLOWING chunk (forward merge) to keep headers with their content.
    
    Returns HTML string with each chunk wrapped in <div class="table-chunk">.
    """
    # Split by double newlines to identify logical row groups
    raw_chunks = re.split(r"\n\n+", clean_text)
    
    # First pass: backward merge summary chunks into previous chunk
    backward_merged: List[str] = []
    for chunk in raw_chunks:
        chunk = chunk.rstrip()  # Preserve leading whitespace for column alignment
        if not chunk:
            continue
        
        # Check if this is a summary chunk that should be glued to the previous
        if _is_summary_chunk(chunk) and backward_merged:
            # Merge into the previous chunk with double newline to preserve spacing
            backward_merged[-1] = backward_merged[-1] + "\n\n" + chunk
        else:
            # Start a new chunk
            backward_merged.append(chunk)
    
    # Second pass: forward merge subsection headers into the following chunk
    # We process in reverse to handle consecutive headers correctly
    final_chunks: List[str] = []
    pending_header: Optional[str] = None
    
    for chunk in reversed(backward_merged):
        if pending_header:
            # Prepend the pending header to this chunk
            chunk = pending_header + "\n\n" + chunk
            pending_header = None
        
        # Check if this chunk is a subsection header that should be glued to the next
        if _is_subsection_header_chunk(chunk):
            # Hold this chunk to prepend to the next one
            if final_chunks:
                # Prepend to the most recent chunk we've built
                final_chunks[-1] = chunk + "\n\n" + final_chunks[-1]
            else:
                # No following chunk yet, save as pending
                pending_header = chunk
        else:
            final_chunks.append(chunk)
    
    # If there's a leftover pending header, add it as its own chunk
    if pending_header:
        final_chunks.append(pending_header)
    
    # Reverse back to original order
    final_chunks.reverse()
    
    # Emit each merged chunk as a single protected div
    html_chunks: List[str] = []
    for chunk in final_chunks:
        html_chunks.append(
            f'<div class="table-chunk"><pre class="filing">{html_escape(chunk)}</pre></div>'
        )
    
    return "\n".join(html_chunks)


def _collect_header_blocks(blocks: List[Block], table_idx: int) -> List[int]:
    """
    Scan backwards from a table block to collect all preceding header candidate blocks.
    
    Returns a list of block indices (in forward order) that should be glued to the table.
    Stops when we hit:
    - A non-header (long text block)
    - Another TableBlock
    - The beginning of the block list
    - Exceeded maximum accumulated lines
    
    This function is intentionally permissive - it's better to glue too much
    context (keeping headers with their tables) than to leave orphan headers
    on a previous page.
    """
    header_indices: List[int] = []
    total_lines = 0
    
    # Scan backwards from the block before the table
    for i in range(table_idx - 1, -1, -1):
        block = blocks[i]
        
        # Stop if we hit another table
        if isinstance(block, TableBlock):
            break
        
        # Must be a TextBlock
        if not isinstance(block, TextBlock):
            break
        
        # Get the clean text and line count
        block_text = "\n".join(block.lines)
        clean_text = _strip_sgml_tags_for_display(block_text)
        block_lines = _count_visible_lines(clean_text)
        
        # Skip empty blocks but continue scanning
        if block_lines == 0:
            continue
        
        # Check if it's a header candidate
        if not _is_header_candidate(block):
            break
        
        # Check accumulated line limit
        if total_lines + block_lines > MAX_ACCUMULATED_HEADER_LINES:
            break
        
        # This block qualifies - add it
        header_indices.append(i)
        total_lines += block_lines
    
    # Reverse to get forward order
    header_indices.reverse()
    return header_indices


def _collect_footer_blocks(blocks: List[Block], table_idx: int) -> List[int]:
    """
    Scan forwards from a table block to collect all following footer candidate blocks.
    
    Returns a list of block indices that should be glued to the table.
    Stops when we hit:
    - A non-footer (long text block or new section header)
    - Another TableBlock
    - The end of the block list
    - Exceeded maximum accumulated lines
    
    This keeps totals/subtotals with their tables.
    """
    footer_indices: List[int] = []
    total_lines = 0
    
    # Scan forwards from the block after the table
    for i in range(table_idx + 1, len(blocks)):
        block = blocks[i]
        
        # Stop if we hit another table
        if isinstance(block, TableBlock):
            break
        
        # Must be a TextBlock
        if not isinstance(block, TextBlock):
            break
        
        # Get the clean text and line count
        block_text = "\n".join(block.lines)
        clean_text = _strip_sgml_tags_for_display(block_text)
        block_lines = _count_visible_lines(clean_text)
        
        # Skip empty blocks but continue scanning
        if block_lines == 0:
            continue
        
        # Check if it's a footer candidate
        if not _is_footer_candidate(block):
            break
        
        # Check accumulated line limit
        if total_lines + block_lines > MAX_ACCUMULATED_FOOTER_LINES:
            break
        
        # This block qualifies - add it
        footer_indices.append(i)
        total_lines += block_lines
    
    return footer_indices


def _build_html(
    docs: List[SecDocument],
    *,
    primary_idx: int,
    font_size_px: int = 10,
    line_height_px: int = 13,
) -> str:
    """
    Build HTML from SEC documents with CSS-based pagination.
    
    Uses 'break-inside: avoid' on table blocks to prevent table splits.
    Glues preceding header blocks and following footer blocks to tables.
    """
    html_parts: List[str] = []
    
    # Process documents in order (primary first)
    order = [primary_idx] + [i for i in range(len(docs)) if i != primary_idx]
    
    for doc_idx in order:
        doc = docs[doc_idx]
        
        # Document header
        html_parts.append(f'<div class="doc-header">DOCUMENT TYPE: {html_escape(doc.doc_type)}</div>')
        
        # Sanitize the document text
        sanitized_text = _sanitize_text(doc.text)
        
        # Segment into blocks
        blocks = _segment_into_blocks(sanitized_text)
        
        # Track which blocks have been consumed (glued to a table)
        consumed: set[int] = set()
        
        # First pass: identify all table blocks and their associated headers/footers
        # table_idx -> (header_indices, footer_indices)
        table_groups: dict[int, tuple[List[int], List[int]]] = {}
        for i, block in enumerate(blocks):
            if isinstance(block, TableBlock):
                header_indices = _collect_header_blocks(blocks, i)
                footer_indices = _collect_footer_blocks(blocks, i)
                table_groups[i] = (header_indices, footer_indices)
                consumed.update(header_indices)
                consumed.update(footer_indices)
        
        # Second pass: emit HTML in order
        i = 0
        while i < len(blocks):
            # Skip if already consumed as a header or footer
            if i in consumed:
                i += 1
                continue
            
            current_block = blocks[i]
            
            # Check if this is a table with associated headers/footers
            if isinstance(current_block, TableBlock) and i in table_groups:
                header_indices, footer_indices = table_groups[i]
                
                # Get table content
                table_text = "\n".join(current_block.lines)
                clean_table = _strip_sgml_tags_for_display(table_text)
                
                has_context = header_indices or footer_indices
                
                if has_context:
                    # Wrap headers + table + footers in a shared container
                    html_parts.append('<div class="table-with-context">')
                    
                    # Emit all header blocks
                    for h_idx in header_indices:
                        header_block = blocks[h_idx]
                        header_text = "\n".join(header_block.lines)
                        clean_header = _strip_sgml_tags_for_display(header_text)
                        if clean_header.strip():
                            html_parts.append(f'<pre class="filing header-text">{html_escape(clean_header)}</pre>')
                    
                    # Emit the table as chunks
                    if clean_table.strip():
                        html_parts.append(_render_chunked_table(clean_table))
                    
                    # Emit all footer blocks
                    for f_idx in footer_indices:
                        footer_block = blocks[f_idx]
                        footer_text = "\n".join(footer_block.lines)
                        clean_footer = _strip_sgml_tags_for_display(footer_text)
                        if clean_footer.strip():
                            html_parts.append(f'<pre class="filing footer-text">{html_escape(clean_footer)}</pre>')
                    
                    html_parts.append('</div>')
                else:
                    # Table without context - render as chunks
                    if clean_table.strip():
                        html_parts.append('<div class="table-wrapper">')
                        html_parts.append(_render_chunked_table(clean_table))
                        html_parts.append('</div>')
                
                i += 1
                continue
            
            # Normal processing for standalone text blocks
            block_text = "\n".join(current_block.lines)
            clean_text = _strip_sgml_tags_for_display(block_text)
            
            # Skip empty blocks
            if not clean_text.strip():
                i += 1
                continue
            
            if isinstance(current_block, TableBlock):
                # Orphan table (shouldn't happen, but handle it)
                html_parts.append('<div class="table-wrapper">')
                html_parts.append(_render_chunked_table(clean_text))
                html_parts.append('</div>')
            else:
                # Regular text block (not consumed as header/footer)
                html_parts.append(
                    f'<pre class="filing">{html_escape(clean_text)}</pre>'
                )
            
            i += 1
        
        # Add separator between documents
        if doc_idx != order[-1]:
            html_parts.append('<div class="doc-separator"></div>')
    
    body = "\n".join(html_parts)
    
    # CSS with landscape layout and table protection
    css = f"""
@page {{
    size: 14in 8.5in landscape;
    margin: 0.3in 0.2in;
}}

html, body {{
    margin: 0;
    padding: 0;
}}

body {{
    font-family: "Courier New", Courier, monospace;
    font-size: {font_size_px}px;
    line-height: {line_height_px}px;
    color: #111;
}}

.doc-header {{
    font-family: Arial, Helvetica, sans-serif;
    font-weight: 700;
    font-size: 11px;
    margin: 0 0 8px 0;
    padding: 4px 8px;
    background: #f0f0f0;
    border-bottom: 1px solid #ccc;
}}

.doc-separator {{
    height: 20px;
    border-top: 2px solid #333;
    margin: 20px 0;
    break-before: page;
}}

.filing {{
    font-family: "Courier New", Courier, monospace;
    font-size: {font_size_px}px;
    line-height: {line_height_px}px;
    white-space: pre;
    margin: 0;
    padding: 0;
    widows: 5;
    orphans: 5;
}}

.table-wrapper {{
    margin: 4px 0;
}}

.table-wrapper .filing {{
    background: #fafafa;
    border-left: 2px solid #ddd;
    padding-left: 4px;
}}

.table-with-context {{
    display: block;
    break-before: auto;
    margin: 4px 0;
}}

.table-chunk {{
    break-inside: avoid;
    page-break-inside: avoid;
}}

.table-with-context .filing {{
    margin: 0;
    padding: 0;
}}

.table-with-context .header-text {{
    margin: 0;
    padding: 0;
    break-after: avoid;
    page-break-after: avoid;
}}

.table-with-context .table-content {{
    background: #fafafa;
    border-left: 2px solid #ddd;
    padding-left: 4px;
    margin: 0;
    break-before: avoid;
    page-break-before: avoid;
    break-after: avoid;
    page-break-after: avoid;
}}

.table-with-context .footer-text {{
    margin: 0;
    padding: 0;
    break-before: avoid;
    page-break-before: avoid;
}}
"""

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>{css}</style>
  </head>
  <body>
    {body}
  </body>
</html>"""


# =============================================================================
# PDF Rendering
# =============================================================================

class PdfRenderer:
    """Context manager for Playwright-based PDF rendering."""
    
    def __init__(self, *, timeout_ms: int = 60000) -> None:
        self._timeout_ms = timeout_ms
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def __enter__(self) -> "PdfRenderer":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch()
        self._context = self._browser.new_context(viewport={"width": 1600, "height": 900})
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def render(self, html: str, output_pdf: Path) -> None:
        """Render HTML to PDF with CSS-driven pagination."""
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        if self._context is None:
            raise RuntimeError("PdfRenderer not started")

        page: Page = self._context.new_page()
        try:
            page.set_content(html, wait_until="load", timeout=self._timeout_ms)
            page.pdf(
                path=str(output_pdf),
                print_background=True,
                prefer_css_page_size=True,
            )
        finally:
            page.close()


# =============================================================================
# File Processing
# =============================================================================

def convert_one(
    txt_path: Path,
    *,
    input_dir: Path,
    output_dir: Path,
    overwrite: bool,
    keep_html: bool,
    renderer: PdfRenderer,
    font_size_px: int,
    line_height_px: int,
) -> Optional[Path]:
    """Convert a single .txt file to PDF."""
    rel = txt_path.relative_to(input_dir)
    output_pdf = (output_dir / rel).with_suffix(".pdf")
    output_html = output_pdf.with_suffix(".html")

    if output_pdf.exists() and not overwrite:
        return None

    raw = txt_path.read_text(encoding="utf-8", errors="replace")
    docs = _extract_documents_from_sec_txt(raw)
    primary_idx = _pick_primary_doc(docs)

    html = _build_html(
        docs,
        primary_idx=primary_idx,
        font_size_px=font_size_px,
        line_height_px=line_height_px,
    )

    if keep_html:
        output_html.parent.mkdir(parents=True, exist_ok=True)
        output_html.write_text(html, encoding="utf-8")

    renderer.render(html, output_pdf)
    return output_pdf


def iter_input_files(input_dir: Path, pattern: str, recursive: bool) -> Iterable[Path]:
    """Iterate over input files matching the pattern."""
    if recursive:
        return sorted(input_dir.rglob(pattern))
    return sorted(input_dir.glob(pattern))


# =============================================================================
# CLI
# =============================================================================

# Default output base directory for batch folders
DEFAULT_OUTPUT_BASE = Path("pdfs-for-main-extraction")


def _get_next_batch_dir(base_dir: Path) -> Path:
    """
    Find the next batch-N-pdfs folder in the base directory.
    
    Scans for existing batch-N-pdfs folders and returns batch-(N+1)-pdfs.
    If no batch folders exist, returns batch-1-pdfs.
    """
    base_dir = base_dir.resolve()
    if not base_dir.exists():
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / "batch-1-pdfs"
    
    # Find all existing batch-N-pdfs folders
    batch_pattern = re.compile(r"^batch-(\d+)-pdfs$", re.IGNORECASE)
    max_batch = 0
    
    for entry in base_dir.iterdir():
        if entry.is_dir():
            match = batch_pattern.match(entry.name)
            if match:
                batch_num = int(match.group(1))
                max_batch = max(max_batch, batch_num)
    
    next_batch = max_batch + 1
    return base_dir / f"batch-{next_batch}-pdfs"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert SEC .txt filings to neat multi-page PDFs with intact tables.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    # Positional argument for input (optional, falls back to --input-dir)
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=None,
        help="Input folder containing .txt filings (positional, or use --input-dir).",
    )
    
    # Input/output (flags for backward compatibility)
    parser.add_argument(
        "--input-dir", 
        type=Path, 
        default=None,
        help="Folder containing .txt filings.",
    )
    parser.add_argument(
        "--output-dir", 
        type=Path, 
        default=None,
        help="Where to write PDFs. If not specified, auto-creates next batch folder.",
    )
    parser.add_argument(
        "--output-base",
        type=Path,
        default=DEFAULT_OUTPUT_BASE,
        help="Base directory for auto-created batch folders.",
    )
    parser.add_argument(
        "--glob", 
        dest="glob_pattern", 
        default="*.txt",
        help="Glob pattern for input files.",
    )
    parser.add_argument(
        "--recursive", 
        action="store_true", 
        default=False,
        help="Recurse into subfolders.",
    )
    parser.add_argument(
        "--overwrite", 
        action="store_true",
        help="Overwrite existing PDFs.",
    )
    parser.add_argument(
        "--keep-html", 
        action="store_true",
        help="Save intermediate HTML for debugging.",
    )
    parser.add_argument(
        "--fail-fast", 
        action="store_true",
        help="Stop on first error.",
    )
    
    # Typography
    parser.add_argument(
        "--font-size-px", 
        type=int, 
        default=10,
        help="Monospace font size in pixels.",
    )
    parser.add_argument(
        "--line-height-px", 
        type=int, 
        default=13,
        help="Line height in pixels.",
    )
    
    # Timeout
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=60000,
        help="Timeout in milliseconds for PDF generation.",
    )
    
    args = parser.parse_args()
    
    # Resolve input directory (positional takes precedence over --input-dir)
    if args.input is not None:
        input_dir = args.input.resolve()
    elif args.input_dir is not None:
        input_dir = args.input_dir.resolve()
    else:
        input_dir = Path("inputs_for_pdf_script").resolve()
    
    # Resolve output directory (explicit --output-dir or auto-generate batch folder)
    if args.output_dir is not None:
        output_dir = args.output_dir.resolve()
    else:
        output_dir = _get_next_batch_dir(args.output_base)
    
    if not input_dir.exists():
        print(f"Error: Input directory does not exist: {input_dir}")
        return 1
    
    files = [p for p in iter_input_files(input_dir, args.glob_pattern, args.recursive) if p.is_file()]
    if not files:
        print(f"No files matched '{args.glob_pattern}' under {input_dir}")
        return 1
    
    print(f"Input:       {input_dir}")
    print(f"Output:      {output_dir}")
    print(f"Files:       {len(files)} (recursive={args.recursive}, glob={args.glob_pattern})")
    print(f"Font:        {args.font_size_px}px, line-height: {args.line_height_px}px")
    print(f"Overwrite:   {args.overwrite}")
    print()
    
    converted = 0
    skipped = 0
    errors = 0
    
    with PdfRenderer(timeout_ms=args.timeout_ms) as renderer:
        for i, path in enumerate(files, start=1):
            try:
                out = convert_one(
                    path,
                    input_dir=input_dir,
                    output_dir=output_dir,
                    overwrite=args.overwrite,
                    keep_html=args.keep_html,
                    renderer=renderer,
                    font_size_px=args.font_size_px,
                    line_height_px=args.line_height_px,
                )
                if out is None:
                    skipped += 1
                    print(f"[{i}/{len(files)}] SKIP {path.relative_to(input_dir)} (exists)")
                else:
                    converted += 1
                    print(f"[{i}/{len(files)}] OK   {path.relative_to(input_dir)}")
            except Exception as e:
                errors += 1
                print(f"[{i}/{len(files)}] ERR  {path}: {e}")
                if args.fail_fast:
                    raise
    
    print()
    print(f"Done. converted={converted} skipped={skipped} errors={errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

