from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import re

NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")

DEFAULT_INPUT = (
    Path(__file__).resolve().parent
    / "extract_urls"
    / "carlyle-2025-03-31_extract_response.json"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "extraction_holdings.csv"


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

    cleaned = (
        value_str.replace("$", "")
        .replace(",", "")
        .replace(" ", "")
        .replace("\u00a0", "")
    )

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


def format_dollar(amount: Decimal) -> str:
    """Format a Decimal as dollars with commas, rounded to nearest dollar."""
    rounded = amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"${rounded:,.0f}"


def is_holding(node: Any) -> bool:
    """Return True when a node represents a HOLDING row."""
    if not isinstance(node, dict):
        return False

    row_type = node.get("row_type")
    return isinstance(row_type, dict) and row_type.get("value") == "HOLDING"


def extract_investment_name(node: dict[str, Any]) -> str:
    """Choose the best available name field for the investment."""
    investment = node.get("investment")
    if isinstance(investment, dict):
        inv_value = investment.get("value")
        if isinstance(inv_value, str) and inv_value.strip():
            return inv_value.strip()

    label = node.get("label")
    if isinstance(label, dict):
        label_value = label.get("value")
        if isinstance(label_value, str) and label_value.strip():
            return label_value.strip()

    row_text = node.get("row_text")
    if isinstance(row_text, dict):
        row_text_value = row_text.get("value")
        if isinstance(row_text_value, str) and row_text_value.strip():
            return row_text_value.strip()

    for key, value in node.items():
        if "investment" in str(key).lower() and isinstance(value, dict):
            maybe_value = value.get("value")
            if isinstance(maybe_value, str) and maybe_value.strip():
                return maybe_value.strip()

    for value in node.values():
        if isinstance(value, dict):
            maybe_value = value.get("value")
            if isinstance(maybe_value, str) and maybe_value.strip():
                return maybe_value.strip()

    return ""


def find_holdings(node: Any) -> Iterable[Tuple[str, Optional[Decimal]]]:
    """Recursively yield (investment, fair_value) for HOLDING rows."""
    if isinstance(node, dict):
        if is_holding(node):
            name = extract_investment_name(node)
            fair_value_raw = node.get("fair_value_raw")
            number: Optional[Decimal] = None

            if isinstance(fair_value_raw, dict):
                number = parse_numeric_value(fair_value_raw.get("value"))

            yield name, number

        for value in node.values():
            yield from find_holdings(value)

    elif isinstance(node, list):
        for item in node:
            yield from find_holdings(item)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_csv(rows: Iterable[Tuple[str, Optional[Decimal]]], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["investment", "fair_value"])
        for name, amount in rows:
            display_value = format_dollar(amount) if amount is not None else ""
            writer.writerow([name, display_value])


def main(input_path: Optional[str] = None, output_path: Optional[str] = None) -> None:
    source = Path(input_path) if input_path else DEFAULT_INPUT
    destination = Path(output_path) if output_path else DEFAULT_OUTPUT

    if not source.is_file():
        raise SystemExit(f"Input file not found: {source}")

    data = load_json(source)
    holdings = list(find_holdings(data))
    write_csv(holdings, destination)
    print(f"Wrote {len(holdings)} holdings to {destination}")


if __name__ == "__main__":
    main()
