import shutil
from pathlib import Path


def is_html_file(file_path: Path) -> bool:
    """Check if a file contains HTML content by looking for <html> or <!DOCTYPE html> tags."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            # Read the first portion of the file to check for HTML tags
            content = f.read(50000)  # Read first 50KB to check
            content_lower = content.lower()
            return "<html" in content_lower or "<!doctype html" in content_lower
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return True  # Assume HTML if we can't read it, to be safe


def separate_files():
    """Separate neat text files from HTML-embedded files."""
    # Define paths
    source_dir = Path("txt/txt")
    target_dir = Path("txt/neat_txt")

    # Check if source directory exists
    if not source_dir.exists():
        print(f"Error: Source directory '{source_dir}' does not exist.")
        return

    # Create target directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Target directory: {target_dir}")

    # Get all .txt files in source directory
    txt_files = list(source_dir.glob("*.txt"))
    print(f"Found {len(txt_files)} .txt files in {source_dir}")

    neat_count = 0
    html_count = 0

    for file_path in txt_files:
        if is_html_file(file_path):
            html_count += 1
            print(f"  [HTML] {file_path.name}")
        else:
            neat_count += 1
            # Move the file to the target directory
            target_path = target_dir / file_path.name
            shutil.move(str(file_path), str(target_path))
            print(f"  [NEAT] {file_path.name} -> moved to {target_dir}")

    print(f"\nSummary:")
    print(f"  Neat files moved: {neat_count}")
    print(f"  HTML files remaining: {html_count}")


if __name__ == "__main__":
    separate_files()















