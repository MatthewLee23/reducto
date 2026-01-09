#!/usr/bin/env python3
"""
Pick 10 random TXT files from 800-for-testing, convert them to PDFs, and run main.py.

Workflow:
1. Select 10 random .txt files from 800-for-testing
2. Convert them to PDFs using generate_neat_pdf.py (auto-creates batch-N-pdfs folder)
3. Run main.py on the new batch folder to process the PDFs

Outputs to pdfs-for-main-extraction/batch-N-pdfs (auto-incrementing).
"""
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE_DIR = Path("800-for-testing")
OUTPUT_BASE = Path("pdfs-for-main-extraction")
NUM_FILES = 10


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
    if not SOURCE_DIR.exists():
        print(f"Error: Source directory does not exist: {SOURCE_DIR}")
        return 1

    all_files = list(SOURCE_DIR.glob("*.txt"))
    if len(all_files) < NUM_FILES:
        print(f"Warning: Only {len(all_files)} files available, using all of them")
        selected = all_files
    else:
        selected = random.sample(all_files, NUM_FILES)

    print(f"Selected {len(selected)} random files from {SOURCE_DIR}:")
    for f in selected:
        print(f"  - {f.name}")
    print()

    # Determine the output batch folder before running generate_neat_pdf.py
    batch_dir = _get_next_batch_dir(OUTPUT_BASE)
    print(f"Output batch folder: {batch_dir}")
    print()

    # Create a temporary directory with copies of the selected files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        for f in selected:
            dest = tmp_path / f.name
            dest.write_bytes(f.read_bytes())

        # Run generate_neat_pdf.py with explicit output directory
        pdf_cmd = [
            sys.executable,
            "generate_neat_pdf.py",
            str(tmp_path),
            "--output-dir",
            str(batch_dir),
        ]
        print(f"Running: {' '.join(pdf_cmd)}")
        print()
        pdf_result = subprocess.run(pdf_cmd)
        if pdf_result.returncode != 0:
            print(f"Error: generate_neat_pdf.py failed with return code {pdf_result.returncode}")
            return pdf_result.returncode

    # Run main.py on the new batch folder
    print()
    print("=" * 60)
    print(f"Running main.py on {batch_dir}")
    print("=" * 60)
    print()
    
    main_cmd = [
        sys.executable,
        "main.py",
        str(batch_dir),
    ]
    print(f"Running: {' '.join(main_cmd)}")
    print()
    main_result = subprocess.run(main_cmd)
    
    return main_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

