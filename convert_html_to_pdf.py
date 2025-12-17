#!/usr/bin/env python3
"""
HTML → PDF Converter (Browser Print-like Output)

Batch-converts HTML files to PDFs that look exactly like opening in a browser
and using Print → Save as PDF. Uses Playwright/Chromium to render each HTML
file as a webpage (via file:// URL so relative CSS/images resolve), then
generates a PDF with browser-like print defaults.

Usage examples:
    # Convert all .html files in txt/html_txt/ to pdf_out/ subfolder
    python convert_html_to_pdf.py --input-dir txt/html_txt

    # Custom output directory, overwrite existing PDFs
    python convert_html_to_pdf.py --input-dir txt/html_txt --output-dir my_pdfs --overwrite

    # For very large HTML files, increase timeout
    python convert_html_to_pdf.py --input-dir txt/html_txt --timeout-ms 120000

PDF settings:
    - Uses browser default page size (typically US Letter portrait)
    - Honors CSS @page rules if present in the HTML (prefer_css_page_size=True)
    - Prints background colors/images (print_background=True)
    - Standard browser print margins
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

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
# PDF Rendering
# =============================================================================

class HtmlPdfRenderer:
    """Context manager for Playwright-based HTML→PDF rendering."""

    def __init__(self, *, timeout_ms: int = 60000) -> None:
        self._timeout_ms = timeout_ms
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def __enter__(self) -> "HtmlPdfRenderer":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch()
        self._context = self._browser.new_context()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def render(self, html_path: Path, output_pdf: Path) -> None:
        """
        Render an HTML file to PDF.

        Navigates to the file:// URL so relative resources (CSS, images) resolve,
        then prints to PDF with browser-like defaults.
        """
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        if self._context is None:
            raise RuntimeError("HtmlPdfRenderer not started")

        page: Page = self._context.new_page()
        try:
            # Navigate to file:// URL so relative paths resolve correctly
            file_url = html_path.resolve().as_uri()
            page.goto(file_url, wait_until="networkidle", timeout=self._timeout_ms)

            # Generate PDF with browser-like print defaults
            # - No explicit width/height: uses browser default (Letter)
            # - prefer_css_page_size=True: honors CSS @page rules if present
            # - print_background=True: includes background colors/images
            page.pdf(
                path=str(output_pdf),
                print_background=True,
                prefer_css_page_size=True,
                timeout=self._timeout_ms,
            )
        finally:
            page.close()


# =============================================================================
# File Processing
# =============================================================================

def convert_one(
    html_path: Path,
    *,
    input_dir: Path,
    output_dir: Path,
    overwrite: bool,
    renderer: HtmlPdfRenderer,
) -> Optional[Path]:
    """Convert a single HTML file to PDF."""
    rel = html_path.relative_to(input_dir)
    output_pdf = (output_dir / rel).with_suffix(".pdf")

    if output_pdf.exists() and not overwrite:
        return None

    renderer.render(html_path, output_pdf)
    return output_pdf


def iter_input_files(input_dir: Path, pattern: str, recursive: bool) -> Iterable[Path]:
    """Iterate over input files matching the pattern."""
    if recursive:
        return sorted(input_dir.rglob(pattern))
    return sorted(input_dir.glob(pattern))


# =============================================================================
# CLI
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert HTML files to PDFs that match browser Print → Save as PDF output. "
            "Uses Playwright/Chromium to render HTML as a webpage, then generates PDF "
            "with browser-like defaults (Letter size, CSS @page honored, backgrounds printed)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Input/output
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("."),
        help="Folder containing HTML files to convert.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Where to write PDFs (default: <input-dir>/pdf_out).",
    )
    parser.add_argument(
        "--glob",
        dest="glob_pattern",
        default="*.html",
        help="Glob pattern for input files.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Recurse into subfolders.",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_false",
        dest="recursive",
        help="Do not recurse into subfolders.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing PDFs.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first error.",
    )

    # Timeouts
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=60000,
        help="Timeout in milliseconds for page navigation and PDF generation (increase for very large files).",
    )

    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = (args.output_dir or (input_dir / "pdf_out")).resolve()

    files = [p for p in iter_input_files(input_dir, args.glob_pattern, args.recursive) if p.is_file()]
    if not files:
        print(f"No files matched '{args.glob_pattern}' under {input_dir}")
        return 1

    print(f"Input:     {input_dir}")
    print(f"Output:    {output_dir}")
    print(f"Files:     {len(files)} (recursive={args.recursive}, glob={args.glob_pattern})")
    print(f"Timeout:   {args.timeout_ms}ms")
    print(f"Overwrite: {args.overwrite}")
    print()

    converted = 0
    skipped = 0
    errors = 0

    with HtmlPdfRenderer(timeout_ms=args.timeout_ms) as renderer:
        for i, path in enumerate(files, start=1):
            try:
                out = convert_one(
                    path,
                    input_dir=input_dir,
                    output_dir=output_dir,
                    overwrite=args.overwrite,
                    renderer=renderer,
                )
                if out is None:
                    skipped += 1
                    print(f"[{i}/{len(files)}] SKIP {path.relative_to(input_dir)} (exists)")
                else:
                    converted += 1
                    print(f"[{i}/{len(files)}] OK   {path.relative_to(input_dir)}")
            except Exception as e:
                errors += 1
                print(f"[{i}/{len(files)}] ERR  {path.relative_to(input_dir)}: {e}")
                if args.fail_fast:
                    raise

    print()
    print(f"Done. converted={converted} skipped={skipped} errors={errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

