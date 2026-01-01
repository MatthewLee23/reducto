#!/usr/bin/env python3
"""
SEC N-CSR TXT → PDF Converter (Screen-like Landscape)

Converts SEC .txt filings to professional, readable PDFs using:
- Playwright/Chromium for HTML→PDF rendering
- Screen-like landscape page size (~1280px width)
- Monospace <pre> rendering for ASCII tables
- Table-aware pagination with header repetition
- Fixed pixel line-height synced between CSS and Python pagination
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Tuple

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

# SGML tags that should be stripped/ignored when counting visible lines
SGML_TAG_RE = re.compile(
    r"</?(?:S|C|CAPTION|FN|F\d+|PAGE)>",
    flags=re.IGNORECASE,
)

# Tags that are purely invisible (don't even leave whitespace)
INVISIBLE_LINE_RE = re.compile(
    r"^\s*</?(?:S|C|CAPTION|FN|F\d+|PAGE)>\s*$",
    flags=re.IGNORECASE,
)

PEM_HEADER_PREFIXES = (
    "-----BEGIN PRIVACY-ENHANCED MESSAGE-----",
    "-----BEGIN PKCS7-----",
    "-----BEGIN PKCS #7 SIGNED DATA-----",
)

SECTION_HEADER_RE = re.compile(
    r"^(ITEM\s+\d+[A-Z]?\b|PART\s+[IVXLC]+\b|MANAGEMENT['']S DISCUSSION\b|"
    r"SCHEDULE OF INVESTMENTS\b|STATEMENT OF ASSETS\b|STATEMENT OF OPERATIONS\b|"
    r"FINANCIAL HIGHLIGHTS\b|NOTES TO FINANCIAL STATEMENTS\b)",
    flags=re.IGNORECASE,
)

# Separator lines used in SEC ASCII tables
SEPARATOR_LINE_RE = re.compile(r"^[\s\-=_]{10,}$")

# Pattern for detecting numeric data rows (contains dollar amounts, percentages, or numbers)
NUMERIC_DATA_RE = re.compile(r"[\$]?\s*[\d,]+\.?\d*\s*%?|\(\s*[\d,]+\.?\d*\s*\)")

# Max lines for a "short" text block that should stay with following table
SHORT_PREFACE_MAX_LINES = 15


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
    header_lines: List[str] = field(default_factory=list)  # Detected header for repetition


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
# Block Segmentation (Text vs Table)
# =============================================================================

def _segment_into_blocks(text: str) -> List[Block]:
    """
    Segment text into TextBlock and TableBlock regions.
    
    SEC filings use <TABLE>...</TABLE> for ASCII tables with <S>, <C> tags.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
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
        tb = TableBlock(lines=table_lines)
        tb.header_lines = _extract_table_header(table_lines)
        blocks.append(tb)
        
        last_end = m.end()
    
    # Text after last table
    after = text[last_end:]
    if after.strip():
        blocks.append(TextBlock(lines=after.split("\n")))
    
    return blocks if blocks else [TextBlock(lines=text.split("\n"))]


def _extract_table_header(lines: List[str]) -> List[str]:
    """
    Extract the header portion of an SEC ASCII table for repetition.
    
    Conservative approach:
    - Include <CAPTION> region
    - Include <S> and <C> layout definition lines
    - Include the first separator line (----)
    - Stop before any line that looks like numeric data
    """
    header: List[str] = []
    in_caption = False
    found_separator = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        lower = stripped.lower()
        
        # Track caption region
        if "<caption>" in lower:
            in_caption = True
        if "</caption>" in lower:
            header.append(line)
            in_caption = False
            continue
        
        if in_caption:
            header.append(line)
            continue
        
        # Include <S> and <C> header definition lines
        if stripped.startswith("<S>") or stripped.startswith("<C>"):
            header.append(line)
            continue
        
        # Skip pure SGML tag lines (don't add to header, but don't stop)
        if INVISIBLE_LINE_RE.match(stripped):
            continue
        
        # Include separator lines (first one marks end of header)
        if SEPARATOR_LINE_RE.match(stripped):
            header.append(line)
            found_separator = True
            # After first separator, we're done with header
            break
        
        # Stop if we hit a line with numeric data (actual table content)
        if NUMERIC_DATA_RE.search(stripped):
            break
        
        # Include non-empty lines before separator (column headers)
        if stripped and not found_separator:
            header.append(line)
        
        # Stop if we hit too many header lines (safety limit)
        if len(header) > 10:
            break
    
    return header


# =============================================================================
# Pagination Logic (Pixel-Synced)
# =============================================================================

def _count_visible_lines(lines: List[str]) -> int:
    """
    Count lines that actually render (ignoring invisible SGML tag-only lines).
    """
    count = 0
    for line in lines:
        if not INVISIBLE_LINE_RE.match(line):
            count += 1
    return count


def _is_safe_break_point(line: str) -> bool:
    """Check if a line is a good place to break (blank or separator)."""
    stripped = line.strip()
    if not stripped:
        return True
    if SEPARATOR_LINE_RE.match(stripped):
        return True
    if INVISIBLE_LINE_RE.match(stripped):
        return True
    return False


def _paginate_text_block(
    block: TextBlock,
    *,
    max_visible_lines: int,
    header_break_min_lines: int = 8,
    seek_window: int = 6,
) -> Iterator[List[str]]:
    """
    Paginate a TextBlock, respecting:
    - Form-feed characters as hard breaks
    - Section headers as break points
    - Line budget with blank-line preference
    """
    lines = block.lines
    current: List[str] = []
    visible_count = 0
    
    def flush() -> Optional[List[str]]:
        nonlocal current, visible_count
        if not current:
            return None
        chunk = current
        current = []
        visible_count = 0
        return chunk
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Form-feed = hard break
        if "\f" in line:
            parts = line.split("\f")
            for pi, part in enumerate(parts):
                if pi > 0:
                    flushed = flush()
                    if flushed:
                        yield flushed
                current.append(part)
                if not INVISIBLE_LINE_RE.match(part):
                    visible_count += 1
            i += 1
            continue
        
        # Section header = break before (if we have content)
        stripped = line.strip()
        if visible_count >= header_break_min_lines and SECTION_HEADER_RE.match(stripped):
            flushed = flush()
            if flushed:
                yield flushed
        
        current.append(line)
        if not INVISIBLE_LINE_RE.match(line):
            visible_count += 1
        
        # Check if we've hit the line budget
        if visible_count >= max_visible_lines:
            # Search backwards for a good break point
            best_break = None
            for back in range(min(seek_window, len(current))):
                idx = len(current) - 1 - back
                if _is_safe_break_point(current[idx]):
                    best_break = idx + 1  # Break after this line
                    break
            
            if best_break is None:
                # Search forward a bit
                for fwd in range(1, min(seek_window, len(lines) - i)):
                    if _is_safe_break_point(lines[i + fwd]):
                        # Pull forward lines into current
                        for ff in range(1, fwd + 1):
                            current.append(lines[i + ff])
                        i += fwd
                        best_break = len(current)
                        break
            
            if best_break is None:
                best_break = len(current)
            
            chunk = current[:best_break]
            remainder = current[best_break:]
            yield chunk
            current = remainder
            visible_count = _count_visible_lines(current)
        
        i += 1
    
    flushed = flush()
    if flushed:
        yield flushed


def _paginate_table_block(
    block: TableBlock,
    *,
    max_visible_lines: int,
    header_lines: List[str],
    preface_lines: int = 0,
) -> Iterator[Tuple[List[str], List[str], bool]]:
    """
    Paginate a TableBlock, yielding (header_for_page, body_chunk, is_continuation).
    
    Now includes header on the first page too, and accounts for preface lines.
    """
    all_lines = block.lines
    header_visible = _count_visible_lines(header_lines)
    
    # First page budget accounts for preface + header
    first_page_budget = max_visible_lines - preface_lines - header_visible
    if first_page_budget < 5:
        first_page_budget = max_visible_lines // 2  # Safety fallback
    
    # Continuation pages just have header
    continuation_budget = max_visible_lines - header_visible
    if continuation_budget < 5:
        continuation_budget = max_visible_lines // 2
    
    current: List[str] = []
    visible_count = 0
    is_first = True
    
    for line in all_lines:
        current.append(line)
        if not INVISIBLE_LINE_RE.match(line):
            visible_count += 1
        
        budget = first_page_budget if is_first else continuation_budget
        
        if visible_count >= budget:
            # Find a good break point (prefer separator or blank)
            best_break = None
            for back in range(min(6, len(current))):
                idx = len(current) - 1 - back
                if _is_safe_break_point(current[idx]):
                    best_break = idx + 1
                    break
            
            if best_break is None:
                best_break = len(current)
            
            chunk = current[:best_break]
            remainder = current[best_break:]
            
            # Yield: (header, body, is_continuation)
            yield (header_lines, chunk, not is_first)
            
            is_first = False
            current = remainder
            visible_count = _count_visible_lines(current)
    
    # Yield remaining content
    if current:
        yield (header_lines, current, not is_first)


# =============================================================================
# HTML Generation
# =============================================================================

def _strip_sgml_tags_for_display(text: str) -> str:
    """Remove SGML tags like <S>, <C>, <PAGE> for cleaner display."""
    # Remove tag-only lines entirely
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        if INVISIBLE_LINE_RE.match(line):
            continue
        # Remove inline tags
        line = SGML_TAG_RE.sub("", line)
        cleaned.append(line)
    return "\n".join(cleaned)


def _build_html(
    docs: List[SecDocument],
    *,
    primary_idx: int,
    line_height_px: int,
    page_height_px: int,
    safety_buffer_pct: float,
    font_size_px: int,
    page_width_px: int,
) -> str:
    """
    Build HTML from SEC documents with proper pagination.
    
    Uses fixed pixel line-height synced with Python pagination math.
    Keeps short preface text (last chunk before table) with the table.
    Skips empty pages after SGML stripping.
    """
    # Calculate max visible lines per page (with safety buffer)
    usable_height_px = page_height_px * (1.0 - safety_buffer_pct)
    max_visible_lines = int(usable_height_px / line_height_px)
    
    # Page dimensions in inches (96 dpi default)
    dpi = 96
    page_width_in = page_width_px / dpi
    page_height_in = page_height_px / dpi
    
    # Collect all page HTML parts
    all_pages: List[str] = []
    
    # Process documents in order (primary first)
    order = [primary_idx] + [i for i in range(len(docs)) if i != primary_idx]
    
    for doc_idx in order:
        doc = docs[doc_idx]
        heading = f'<div class="docHeader">DOCUMENT TYPE: {html_escape(doc.doc_type)}</div>'
        
        blocks = _segment_into_blocks(doc.text)
        
        # First page of each document gets the heading
        doc_first_page = True
        
        i = 0
        while i < len(blocks):
            block = blocks[i]
            
            if isinstance(block, TextBlock):
                # Check if next block is a table
                next_is_table = (i + 1 < len(blocks) and isinstance(blocks[i + 1], TableBlock))
                
                # Paginate the text block and collect all chunks
                chunks = list(_paginate_text_block(block, max_visible_lines=max_visible_lines))
                
                # If next block is table, check if last chunk is short enough to keep with table
                last_chunk_for_table: Optional[List[str]] = None
                if next_is_table and chunks:
                    last_chunk = chunks[-1]
                    last_chunk_visible = _count_visible_lines(last_chunk)
                    if last_chunk_visible <= SHORT_PREFACE_MAX_LINES:
                        last_chunk_for_table = chunks.pop()  # Remove from chunks, save for table
                
                # Emit all text chunks (except the one saved for table)
                for chunk in chunks:
                    clean_text = _strip_sgml_tags_for_display("\n".join(chunk))
                    
                    # Skip empty pages
                    if not clean_text.strip():
                        continue
                    
                    page_parts = []
                    if doc_first_page:
                        page_parts.append(heading)
                        doc_first_page = False
                    
                    page_parts.append(f'<pre class="filing">{html_escape(clean_text)}</pre>')
                    all_pages.append("".join(page_parts))
                
                # If we have a last chunk to keep with table, process table now
                if last_chunk_for_table is not None:
                    preface_lines = last_chunk_for_table
                    preface_visible = _count_visible_lines(preface_lines)
                    
                    # Move to the table block
                    i += 1
                    table_block = blocks[i]
                    
                    # Generate table pages with preface on first page
                    first_table_page = True
                    for header, body_chunk, is_continuation in _paginate_table_block(
                        table_block,
                        max_visible_lines=max_visible_lines,
                        header_lines=table_block.header_lines,
                        preface_lines=preface_visible if first_table_page else 0,
                    ):
                        page_parts = []
                        
                        # Add doc heading on first page of document
                        if doc_first_page:
                            page_parts.append(heading)
                            doc_first_page = False
                        
                        # Add preface on first table page
                        if first_table_page:
                            clean_preface = _strip_sgml_tags_for_display("\n".join(preface_lines))
                            if clean_preface.strip():
                                page_parts.append(f'<pre class="filing">{html_escape(clean_preface)}</pre>')
                            first_table_page = False
                        
                        # Add table header
                        clean_header = _strip_sgml_tags_for_display("\n".join(header))
                        if clean_header.strip():
                            page_parts.append(f'<pre class="filing table-header">{html_escape(clean_header)}</pre>')
                        
                        # Add table body
                        clean_body = _strip_sgml_tags_for_display("\n".join(body_chunk))
                        if clean_body.strip():
                            page_parts.append(f'<pre class="filing">{html_escape(clean_body)}</pre>')
                        
                        # Only emit page if there's actual content
                        if page_parts:
                            all_pages.append("".join(page_parts))
            
            elif isinstance(block, TableBlock):
                # Table without preface
                for header, body_chunk, is_continuation in _paginate_table_block(
                    block,
                    max_visible_lines=max_visible_lines,
                    header_lines=block.header_lines,
                ):
                    page_parts = []
                    
                    if doc_first_page:
                        page_parts.append(heading)
                        doc_first_page = False
                    
                    # Add table header (on all pages now)
                    clean_header = _strip_sgml_tags_for_display("\n".join(header))
                    if clean_header.strip():
                        page_parts.append(f'<pre class="filing table-header">{html_escape(clean_header)}</pre>')
                    
                    # Add table body
                    clean_body = _strip_sgml_tags_for_display("\n".join(body_chunk))
                    if clean_body.strip():
                        page_parts.append(f'<pre class="filing">{html_escape(clean_body)}</pre>')
                    
                    # Only emit page if there's actual content
                    if page_parts and any('<pre' in p for p in page_parts):
                        all_pages.append("".join(page_parts))
            
            i += 1
    
    # Join pages with page breaks
    body = '<div class="pagebreak"></div>'.join(all_pages)
    
    css = f"""
@page {{
  size: {page_width_in:.4f}in {page_height_in:.4f}in landscape;
  margin: 0.25in;
}}
html, body {{
  padding: 0;
  margin: 0;
}}
body {{
  color: #111;
  font-family: "Courier New", Courier, monospace;
  font-size: {font_size_px}px;
  line-height: {line_height_px}px;
}}
.docHeader {{
  font-family: Arial, Helvetica, sans-serif;
  font-weight: 700;
  font-size: 11px;
  margin: 0 0 6px 0;
  line-height: 14px;
}}
.docSection {{
  break-inside: avoid;
}}
.filing {{
  font-family: "Courier New", Courier, monospace;
  font-size: {font_size_px}px;
  line-height: {line_height_px}px;
  white-space: pre;
  margin: 0;
  padding: 0;
}}
.table-header {{
  border-bottom: 1px solid #ccc;
  margin-bottom: 2px;
  padding-bottom: 2px;
}}
.pagebreak {{
  break-before: page;
  page-break-before: always;
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
    
    def __init__(self, *, scale: float = 1.0) -> None:
        self._scale = scale
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def __enter__(self) -> "PdfRenderer":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch()
        self._context = self._browser.new_context(viewport={"width": 1440, "height": 900})
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def render(self, html: str, output_pdf: Path, *, page_width_in: float, page_height_in: float) -> None:
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        if self._context is None:
            raise RuntimeError("PdfRenderer not started")

        page: Page = self._context.new_page()
        try:
            page.set_content(html, wait_until="load")
            page.pdf(
                path=str(output_pdf),
                width=f"{page_width_in}in",
                height=f"{page_height_in}in",
                landscape=True,
                print_background=True,
                margin={"top": "0.25in", "bottom": "0.25in", "left": "0.25in", "right": "0.25in"},
                scale=self._scale,
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
    line_height_px: int,
    page_width_px: int,
    page_height_px: int,
    font_size_px: int,
    safety_buffer_pct: float,
    dpi: int,
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
        line_height_px=line_height_px,
        page_height_px=page_height_px,
        safety_buffer_pct=safety_buffer_pct,
        font_size_px=font_size_px,
        page_width_px=page_width_px,
    )

    if keep_html:
        output_html.parent.mkdir(parents=True, exist_ok=True)
        output_html.write_text(html, encoding="utf-8")

    page_width_in = page_width_px / dpi
    page_height_in = page_height_px / dpi
    renderer.render(html, output_pdf, page_width_in=page_width_in, page_height_in=page_height_in)
    return output_pdf


def iter_input_files(input_dir: Path, pattern: str, recursive: bool) -> Iterable[Path]:
    """Iterate over input files matching the pattern."""
    if recursive:
        return sorted(input_dir.rglob(pattern))
    return sorted(input_dir.glob(pattern))


def _generate_timestamped_output_dir(base_dir: Path) -> Path:
    """
    Generate a timestamped output directory path.
    
    Format: <base_dir>/output/<YYYY-MM-DD_HHMMSS>/
    If that exists, append -1, -2, etc.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_base = base_dir / "output"
    candidate = output_base / timestamp
    
    if not candidate.exists():
        return candidate
    
    # Add suffix if already exists
    suffix = 1
    while True:
        candidate = output_base / f"{timestamp}-{suffix}"
        if not candidate.exists():
            return candidate
        suffix += 1
        if suffix > 1000:  # Safety limit
            raise RuntimeError(f"Too many output directories with timestamp {timestamp}")


# =============================================================================
# CLI
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert SEC N-CSR .txt filings to professional PDFs (screen-like landscape).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    # Input/output
    parser.add_argument("--input-dir", type=Path, default=Path("."),
                        help="Folder containing .txt filings.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Where to write PDFs (default: <input-dir>/output/<timestamp>/).")
    parser.add_argument("--glob", dest="glob_pattern", default="*.txt",
                        help="Glob pattern for input files.")
    parser.add_argument("--recursive", action="store_true", default=True,
                        help="Recurse into subfolders.")
    parser.add_argument("--no-recursive", action="store_false", dest="recursive")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing PDFs.")
    parser.add_argument("--keep-html", action="store_true",
                        help="Save intermediate HTML for debugging.")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Stop on first error.")
    
    # Page sizing (screen-like defaults)
    parser.add_argument("--page-width-px", type=int, default=1280,
                        help="Page width in pixels (screen-like).")
    parser.add_argument("--page-height-px", type=int, default=720,
                        help="Page height in pixels (screen-like).")
    parser.add_argument("--dpi", type=int, default=96,
                        help="DPI for px→inch conversion.")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="Chromium PDF scale factor.")
    
    # Typography (pixel-synced)
    parser.add_argument("--font-size-px", type=int, default=11,
                        help="Monospace font size in pixels.")
    parser.add_argument("--line-height-px", type=int, default=14,
                        help="Line height in pixels (must match CSS exactly).")
    parser.add_argument("--safety-buffer-pct", type=float, default=0.08,
                        help="Reserve bottom percentage of page to avoid overflow (0.0-0.2).")
    
    args = parser.parse_args()
    
    input_dir = args.input_dir.resolve()
    
    # Use timestamped output directory if not explicitly provided
    if args.output_dir is not None:
        output_dir = args.output_dir.resolve()
    else:
        output_dir = _generate_timestamped_output_dir(input_dir)
    
    files = [p for p in iter_input_files(input_dir, args.glob_pattern, args.recursive) if p.is_file()]
    if not files:
        print(f"No files matched '{args.glob_pattern}' under {input_dir}")
        return 1
    
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print(f"Files:  {len(files)} (recursive={args.recursive}, glob={args.glob_pattern})")
    print(f"Page:   {args.page_width_px}x{args.page_height_px}px @ {args.dpi}dpi")
    print(f"Font:   {args.font_size_px}px, line-height: {args.line_height_px}px")
    print(f"Buffer: {args.safety_buffer_pct*100:.0f}% bottom reserved")
    print()
    
    converted = 0
    skipped = 0
    errors = 0
    
    with PdfRenderer(scale=args.scale) as renderer:
        for i, path in enumerate(files, start=1):
            try:
                out = convert_one(
                    path,
                    input_dir=input_dir,
                    output_dir=output_dir,
                    overwrite=args.overwrite,
                    keep_html=args.keep_html,
                    renderer=renderer,
                    line_height_px=args.line_height_px,
                    page_width_px=args.page_width_px,
                    page_height_px=args.page_height_px,
                    font_size_px=args.font_size_px,
                    safety_buffer_pct=args.safety_buffer_pct,
                    dpi=args.dpi,
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
