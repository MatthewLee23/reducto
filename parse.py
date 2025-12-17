import os
import json
import re
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from reducto import AsyncReducto
from upload import upload_pdf

load_dotenv()


def extract_soi_pages(split_result_str: str) -> list[int]:
    """
    Extract SOI page numbers from a split result string.
    
    Args:
        split_result_str: String representation of SplitResponse
        
    Returns:
        List of page numbers for SOI section
    """
    # Extract SOI pages using regex
    # Pattern: name='SOI', pages=[10, 11, 12, ...]
    pattern = r"name='SOI',\s*pages=\[([^\]]+)\]"
    match = re.search(pattern, split_result_str)
    
    if not match:
        return []
    
    pages_str = match.group(1)
    # Parse the pages list
    pages = [int(p.strip()) for p in pages_str.split(',') if p.strip()]
    return pages


def get_parse_config(remote_input: str, pages: list[int]) -> dict:
    """
    Get parse configuration for Schedule of Investments pages.
    
    Args:
        remote_input: Remote input reference (file ID or presigned URL)
        pages: List of page numbers to parse
        
    Returns:
        Parse configuration dictionary
    """
    config = {
        "input": remote_input,
        "enhance": {
            "agentic": [
                { "scope": "text" },
                {
                    "scope": "table",
                    "prompt": "Extract Schedule of Investments tables from SEC N-CSR/N-CSRS. Preserve merged headers, multi-line security descriptions, and page-spanning tables. Prefer table structure that keeps numeric columns aligned (Principal/Shares, Cost, Fair Value, %Net Assets, Interest Rate, Maturity)."
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
            "persist_results": True,
            "return_images": ["table"]
        }
    }
    
    # Add page range if pages are specified
    if pages:
        # Convert 1-indexed pages to page range
        # Pages are typically 1-indexed, so we use the min and max
        min_page = min(pages)
        max_page = max(pages)
        config["settings"]["page_range"] = {
            "start": min_page,
            "end": max_page
        }
    
    return config


async def process_split_result(
    client: AsyncReducto,
    split_result_path: Path,
    pdf_dir: Path,
    output_dir: Path
) -> dict:
    """
    Process a single split result file and parse SOI pages.
    
    Args:
        client: AsyncReducto client instance
        split_result_path: Path to split result JSON file
        pdf_dir: Directory containing original PDF files
        output_dir: Directory to save parse results
        
    Returns:
        Dictionary with processing status
    """
    try:
        basename = split_result_path.stem.replace("_split_result", "")
        print(f"Processing {basename}...")
        
        # Read split result
        with open(split_result_path, "r") as f:
            split_result_str = f.read().strip()
        
        # Extract SOI pages
        soi_pages = extract_soi_pages(split_result_str)
        
        if not soi_pages:
            print(f"  No SOI pages found in {basename}")
            return {
                "file": basename,
                "status": "skipped",
                "reason": "No SOI pages found"
            }
        
        print(f"  Found {len(soi_pages)} SOI pages: {soi_pages}")
        
        # Find corresponding PDF file
        pdf_path = pdf_dir / f"{basename}.pdf"
        if not pdf_path.exists():
            # Try alternative naming patterns
            pdf_files = list(pdf_dir.glob(f"{basename}*.pdf"))
            if pdf_files:
                pdf_path = pdf_files[0]
            else:
                raise FileNotFoundError(f"PDF file not found for {basename}")
        
        # Upload PDF file
        remote_input = await upload_pdf(client, pdf_path)
        print(f"  PDF uploaded. Using remote input: {remote_input}")
        
        # Get parse configuration
        parse_config = get_parse_config(remote_input, soi_pages)
        
        # Run parse job
        print(f"  Parsing SOI pages...")
        response = await client.parse.run(**parse_config)
        
        # Save response to JSON file
        output_filename = output_dir / f"{basename}_parse_result.json"
        with open(output_filename, "w") as f:
            json.dump(response, f, indent=2, default=str)
        
        print(f"  {basename} completed successfully! Results saved to {output_filename}")
        return {
            "file": basename,
            "status": "success",
            "output": str(output_filename),
            "soi_pages": soi_pages
        }
    
    except Exception as e:
        error_msg = f"Error processing {split_result_path.name}: {str(e)}"
        print(f"  {error_msg}")
        return {
            "file": split_result_path.stem.replace("_split_result", ""),
            "status": "error",
            "error": str(e)
        }


async def main():
    """Main function to process all split results."""
    client = AsyncReducto(
        api_key=os.environ.get("REDUCTO_API_KEY"),
        environment="production",
    )
    
    # Use split_results directory (user mentioned renaming from test_results)
    split_results_dir = Path("split_results")
    if not split_results_dir.exists():
        # Fallback to test_results if split_results doesn't exist
        split_results_dir = Path("test_results")
    
    pdf_dir = Path("test_batch")
    output_dir = Path("parse_results")
    output_dir.mkdir(exist_ok=True)
    
    # Find all split result JSON files
    split_result_files = list(split_results_dir.glob("*_split_result.json"))
    
    if not split_result_files:
        print(f"No split result files found in {split_results_dir}")
        return
    
    print(f"Found {len(split_result_files)} split result file(s) to process")
    print(f"Output directory: {output_dir}\n")
    
    # Process all files sequentially (to avoid overwhelming the API)
    results = []
    for split_result_file in split_result_files:
        result = await process_split_result(
            client, split_result_file, pdf_dir, output_dir
        )
        results.append(result)
    
    # Report results
    print("\n" + "="*60)
    print("Parse Processing Summary")
    print("="*60)
    
    success_count = 0
    skipped_count = 0
    error_count = 0
    
    for result in results:
        if result.get("status") == "success":
            success_count += 1
        elif result.get("status") == "skipped":
            skipped_count += 1
        else:
            error_count += 1
    
    print(f"\nTotal files: {len(split_result_files)}")
    print(f"Successful: {success_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Errors: {error_count}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
