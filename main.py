import os
import json
import re
import asyncio
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import urlopen
from dotenv import load_dotenv
from reducto import AsyncReducto
from upload import upload_pdf
from split import run_split
from extract import get_extract_config

load_dotenv()


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
) -> dict:
    """Upload -> split -> extract SOI pages for a single file (PDF or TXT)."""
    try:
        print(f"Processing {pdf_path.name}...")

        split_output = split_dir / f"{pdf_path.stem}_split_result.json"
        extract_urls_output = extract_urls_dir / f"{pdf_path.stem}_extract_response.json"
        extract_output = extract_dir / f"{pdf_path.stem}_extract_result.json"

        # Short-circuit if raw extract already exists
        if extract_output.exists():
            print(f"  Raw extract already exists at: {extract_output}")
            return {
                "file": pdf_path.name,
                "status": "skipped",
                "reason": "extract already present",
                "split_output": str(split_output),
                "extract_response_output": str(extract_urls_output),
                "extract_output": str(extract_output),
                "soi_pages": [],
            }

        # Ensure split exists (reuse if present)
        split_json = _load_json(split_output)
        if split_json is None:
            print("  Running split...")
            remote_input_for_split = await upload_pdf(client, pdf_path)
            split_response = await run_split(client, remote_input_for_split)
            split_json = _to_jsonable(split_response)
            with open(split_output, "w") as f:
                json.dump(split_json, f, indent=2, default=str)
        else:
            print(f"  Using existing split: {split_output}")

        soi_pages = extract_soi_pages_from_split(split_json)
        if not soi_pages:
            print(f"  No SOI pages found in split for {pdf_path.name}; skipping extract.")
            return {
                "file": pdf_path.name,
                "status": "skipped",
                "reason": "No SOI pages found",
                "split_output": str(split_output),
            }

        print(f"  Found {len(soi_pages)} SOI pages: {soi_pages}")

        # Try to use existing extract response to download raw result
        extract_json = _load_json(extract_urls_output)
        downloaded = False
        if extract_json:
            result_url = extract_json.get("result", {}).get("url")
            if result_url:
                try:
                    with urlopen(result_url) as resp:
                        extract_output.write_bytes(resp.read())
                    print(f"  Downloaded raw extract result from existing response to: {extract_output}")
                    downloaded = True
                except Exception as download_err:
                    print(f"  Failed to download raw extract result from existing response: {download_err}")

        # If no existing extract or download failed, re-run extraction
        if not downloaded:
            remote_input = await upload_pdf(client, pdf_path)
            print(f"  {pdf_path.name} uploaded successfully. Using remote input: {remote_input}")

            extract_config = get_extract_config(remote_input, soi_pages)
            print("  Extracting SOI pages...")
            extract_response = await client.extract.run(**extract_config)
            extract_json = _to_jsonable(extract_response)

            with open(extract_urls_output, "w") as f:
                json.dump(extract_json, f, indent=2, default=str)

            result_url = extract_json.get("result", {}).get("url")
            if result_url:
                try:
                    with urlopen(result_url) as resp:
                        extract_output.write_bytes(resp.read())
                    print(f"  Downloaded raw extract result to: {extract_output}")
                except Exception as download_err:
                    print(f"  Failed to download raw extract result: {download_err}")
                    extract_output = None
            else:
                print("  No result.url found in extract response; skipping download.")
                extract_output = None

        print(f"  {pdf_path.name} completed successfully!")
        print(f"    Split saved to: {split_output}")
        print(f"    Extract response saved to: {extract_urls_output}")
        if extract_output:
            print(f"    Raw extract saved to: {extract_output}")

        return {
            "file": pdf_path.name,
            "status": "success",
            "split_output": str(split_output),
            "extract_response_output": str(extract_urls_output),
            "extract_output": str(extract_output) if extract_output else None,
            "soi_pages": soi_pages,
        }

    except Exception as e:
        error_msg = f"Error processing {pdf_path.name}: {str(e)}"
        print(f"  {error_msg}")
        return {
            "file": pdf_path.name,
            "status": "error",
            "error": str(e),
        }


async def main(input_folder: str = "txt"):
    client = AsyncReducto(
        api_key=os.environ.get("REDUCTO_API_KEY"),
        environment="production",
    )

    input_dir = Path(input_folder)
    split_dir = Path("split_results")
    extract_urls_dir = Path("extract_urls")
    extract_dir = Path("extract_results")
    split_dir.mkdir(exist_ok=True)
    extract_urls_dir.mkdir(exist_ok=True)
    extract_dir.mkdir(exist_ok=True)

    # Look for both PDF and TXT files
    pdf_files = list(input_dir.glob("*.pdf"))
    txt_files = list(input_dir.glob("*.txt"))
    all_files = pdf_files + txt_files

    if not all_files:
        print(f"No PDF or TXT files found in {input_dir}")
        return

    print(f"Found {len(all_files)} file(s) to process ({len(pdf_files)} PDF, {len(txt_files)} TXT)")
    print(f"Split output directory: {split_dir}")
    print(f"Extract URLs output directory: {extract_urls_dir}")
    print(f"Extract results output directory: {extract_dir}")
    print("Processing files sequentially (will stop on first error)...\n")

    success_count = 0
    skipped_count = 0
    processed_count = 0

    # Process files sequentially - stop on first error
    for file_path in all_files:
        processed_count += 1
        print(f"[{processed_count}/{len(all_files)}] Processing {file_path.name}...")
        
        try:
            result = await process_file(client, file_path, split_dir, extract_urls_dir, extract_dir)
            
            if result.get("status") == "success":
                success_count += 1
                print(f"✓ {file_path.name} completed successfully\n")
            elif result.get("status") == "skipped":
                skipped_count += 1
                print(f"⊘ {file_path.name} skipped: {result.get('reason', 'unknown')}\n")
            elif result.get("status") == "error":
                # Error occurred - stop processing
                error_msg = result.get("error", "Unknown error")
                print(f"\n✗ ERROR processing {file_path.name}: {error_msg}")
                print(f"\nStopping processing due to error on file: {file_path.name}")
                raise Exception(f"Error processing {file_path.name}: {error_msg}")
        except Exception as e:
            # Unhandled exception - stop processing
            print(f"\n✗ UNEXPECTED ERROR processing {file_path.name}: {str(e)}")
            print(f"\nStopping processing due to exception on file: {file_path.name}")
            raise

    print("\n" + "=" * 60)
    print("Batch Processing Summary")
    print("=" * 60)
    print(f"\nTotal files processed: {processed_count}")
    print(f"Successful: {success_count}")
    print(f"Skipped (no SOI pages): {skipped_count}")
    print(f"Errors: 0 (processing stopped on first error)")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process PDF files from a specified folder using Reducto SDK"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default="txt",
        help="Folder path containing PDF files to process (default: txt)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.folder))
