from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Optional

NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def parse_numeric_value(raw: Any) -> Optional[Decimal]:
    """Convert a raw fair value string to Decimal, handling currency formatting."""
    if raw is None:
        return None

    if isinstance(raw, (int, float, Decimal)):
        try:
            return Decimal(str(raw))
        except InvalidOperation:
            return None

    value_str = str(raw).strip()
    if not value_str:
        return None

    negative = value_str.startswith("(") and value_str.endswith(")")
    if negative:
        value_str = value_str[1:-1].strip()

    cleaned = value_str.replace("$", "").replace(",", "").replace(" ", "")
    match = NUMBER_PATTERN.search(cleaned)
    if not match:
        return None

    try:
        number = Decimal(match.group())
    except InvalidOperation:
        return None

    if negative and number >= 0:
        number = -number

    return number


def is_holding(node: Any) -> bool:
    """Return True when a node represents a HOLDING row."""
    if not isinstance(node, dict):
        return False

    row_type = node.get("row_type")
    return isinstance(row_type, dict) and row_type.get("value") == "HOLDING"


def find_fair_value_numbers(node: Any) -> Iterable[Decimal]:
    """Recursively yield fair_value_raw numbers for HOLDING rows."""
    if isinstance(node, dict):
        if is_holding(node) and "fair_value_raw" in node:
            candidate = node["fair_value_raw"]
            if isinstance(candidate, dict):
                number = parse_numeric_value(candidate.get("value"))
                if number is not None:
                    yield number

        for value in node.values():
            yield from find_fair_value_numbers(value)

    elif isinstance(node, list):
        for item in node:
            yield from find_fair_value_numbers(item)


def sum_file(path: Path) -> Decimal:
    """Sum all fair_value_raw numbers in a single JSON file."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    total = Decimal("0")
    for number in find_fair_value_numbers(data):
        total += number

    return total


def format_dollar(amount: Decimal) -> str:
    """Format a Decimal as dollars with commas, rounded to nearest dollar."""
    rounded = amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"${rounded:,.0f}"


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    source_dir = base_dir / "extract_urls"

    if not source_dir.is_dir():
        raise SystemExit(f"Directory not found: {source_dir}")

    print("file,sum_fair_value_raw")
    for json_file in sorted(source_dir.glob("*.json")):
        try:
            total = sum_file(json_file)
            print(f"{json_file.name},{format_dollar(total)}")
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"{json_file.name},ERROR: {exc}")


if __name__ == "__main__":
    main()
