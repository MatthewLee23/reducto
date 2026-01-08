#!/usr/bin/env python3
"""
Pick 10 random TXT files from txt/neat_txt and convert them to PDFs.

Outputs to pdfs-for-main-extraction/batch-N-pdfs (auto-incrementing).
"""
import random
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE_DIR = Path("txt/neat_txt")
NUM_FILES = 10


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

    print(f"Selected {len(selected)} random files:")
    for f in selected:
        print(f"  - {f.name}")
    print()

    # Create a temporary directory with copies of the selected files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        for f in selected:
            dest = tmp_path / f.name
            dest.write_bytes(f.read_bytes())

        # Run generate_neat_pdf.py - uses default output (pdfs-for-main-extraction/batch-N-pdfs)
        cmd = [
            sys.executable,
            "generate_neat_pdf.py",
            str(tmp_path),
        ]
        print(f"Running: {' '.join(cmd)}")
        print()
        result = subprocess.run(cmd)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

