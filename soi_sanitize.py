"""
SOI Row Sanitizer - Detects and corrects misclassified rows in Reducto extract output.

Handles "phantom holdings" where column headers or subtotals are incorrectly
labeled as HOLDING rows, causing arithmetic validation errors.

Usage:
    from soi_sanitize import normalize_soi_rows
    
    sanitized_rows, fix_log = normalize_soi_rows(soi_rows)
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field, asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Column header phrases that should never be investment names
COLUMN_HEADER_PHRASES = frozenset({
    "principal amount",
    "principal amount:",
    "par amount",
    "par amount:",
    "value",
    "value:",
    "value (note 1)",
    "value (note 1):",
    "cost",
    "cost:",
    "shares",
    "shares:",
    "units",
    "units:",
    "amortized cost",
    "amortized cost:",
    "fair value",
    "fair value:",
    "notional",
    "notional:",
})

# Generic/short words that aren't real security names
GENERIC_INVESTMENT_WORDS = frozenset({
    "total", "subtotal", "amount", "value", "cost", "shares", "principal",
    "notes", "bonds", "stocks", "securities", "investments", "other",
})

# Regex for heading patterns like "Telecommunications -- 7.1%"
HEADING_PATTERN = re.compile(r"^[A-Za-z\s/&,]+\s*--\s*[\d.,]+%?$")

# Regex for extracting percentage from heading (e.g., "7.1%" from "Telecommunications -- 7.1%")
HEADING_PERCENT_PATTERN = re.compile(r"--\s*([\d.,]+%?)\s*$")

# Regex for extracting digits
DIGIT_PATTERN = re.compile(r"\d+")

# Regex for parsing numeric strings
NUMBER_PATTERN = re.compile(r"-?\d[\d.,]*")

# Regex for detecting misread percent (ends in 8, no % sign, has decimal)
MISREAD_PERCENT_PATTERN = re.compile(r"^-?(\d+)\.(\d*)8$")

# Regex for detecting percentages embedded in labels (e.g., "Consumer Goods 2.28" or "Retail 7.9%")
# Also handles separators like " - " or " -- " before the number
LABEL_EMBEDDED_PERCENT_PATTERN = re.compile(
    r"^(.+?)\s*[-–—]+\s*([\d]+\.[\d]+[8%]?)\s*$"  # Name - separator - decimal number
)

# Fallback pattern for labels without separators (e.g., "Consumer Goods 2.28")
LABEL_EMBEDDED_PERCENT_NO_SEP_PATTERN = re.compile(
    r"^(.+?)\s+([\d]+\.[\d]+[8%]?)\s*$"  # Name followed by decimal number (possibly ending in 8 or %)
)

# Pattern to clean trailing separators from labels
TRAILING_SEPARATOR_PATTERN = re.compile(r"\s*[-–—]+\s*$")

# Regex for category names that should be SUBTOTAL, not HOLDING
# These are typically summary/industry exposure lines
SUMMARY_CATEGORY_PATTERN = re.compile(
    r"^(Pharmaceuticals|Technology|Banking|Retail|Consumer|Telecommunications|"
    r"Transportation|Energy|Healthcare|Financial|Industrial|Materials|Utilities|"
    r"Real Estate|Media|Insurance|Aerospace|Advertising|Automotive|Chemicals|"
    r"Construction|Education|Entertainment|Food|Gaming|Hospitality|Internet|"
    r"Leisure|Manufacturing|Mining|Oil|Packaging|Paper|Semiconductor|Software|"
    r"Textiles|Tobacco|Wireless|Major Industry).*$",
    re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FixLogEntry:
    """Represents a single normalization fix applied to a row."""
    row_idx: int
    old_row_type: str
    new_row_type: Optional[str]  # None if dropped
    action: str  # "converted" | "dropped" | "percent_corrected"
    reason_code: str
    confidence: str  # "high" | "medium" | "low"
    row_signature: str  # Compact summary of the row
    old_value: Optional[str] = None  # For percent corrections
    new_value: Optional[str] = None  # For percent corrections
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizationResult:
    """Result of normalizing soi_rows."""
    rows: List[Dict[str, Any]]
    fix_log: List[FixLogEntry] = field(default_factory=list)
    fix_count: int = 0
    dropped_count: int = 0
    converted_count: int = 0
    percent_corrected_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fix_count": self.fix_count,
            "dropped_count": self.dropped_count,
            "converted_count": self.converted_count,
            "percent_corrected_count": self.percent_corrected_count,
            "fix_log": [e.to_dict() for e in self.fix_log],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def unwrap_value(field_obj: Any) -> Optional[str]:
    """Extract the 'value' from a {value, citations} wrapper, or return string as-is."""
    if field_obj is None:
        return None
    if isinstance(field_obj, dict):
        v = field_obj.get("value")
        return str(v) if v is not None else None
    return str(field_obj)


def set_wrapped_value(row: Dict[str, Any], field_name: str, value: Any) -> None:
    """Set a value in a {value, citations} wrapped field."""
    if field_name in row and isinstance(row[field_name], dict):
        row[field_name]["value"] = value
    else:
        row[field_name] = {"value": value, "citations": []}


def parse_decimal_simple(raw: Any) -> Optional[Decimal]:
    """
    Simple decimal parser - returns value or None.
    """
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
    
    # Remove currency symbols and whitespace
    cleaned = (
        value_str
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("¥", "")
        .replace(" ", "")
        .replace("\u00a0", "")
        .replace("\t", "")
        .replace(",", "")
        .replace("%", "")
    )
    
    # Remove common currency codes
    for code in ("USD", "CAD", "EUR", "GBP", "JPY"):
        cleaned = cleaned.replace(code, "")
    
    # Handle parentheses negatives
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1].strip()
    
    # Find numeric tokens
    matches = NUMBER_PATTERN.findall(cleaned)
    if not matches:
        return None
    
    try:
        number = Decimal(matches[0].replace(",", "").replace(".", "", matches[0].count(".") - 1 if matches[0].count(".") > 1 else 0))
    except InvalidOperation:
        return None
    
    if negative and number > 0:
        number = -number
    
    return number


def normalize_text(s: Optional[str]) -> str:
    """Normalize text for comparison: lowercase, strip, collapse whitespace."""
    if not s:
        return ""
    return " ".join(s.lower().split())


def get_row_signature(row: Dict[str, Any]) -> str:
    """Create a compact signature of a row for logging."""
    row_type = unwrap_value(row.get("row_type")) or "?"
    investment = unwrap_value(row.get("investment")) or ""
    label = unwrap_value(row.get("label")) or ""
    fv = unwrap_value(row.get("fair_value_raw")) or ""
    
    name = investment[:40] if investment else (label[:40] if label else "")
    return f"{row_type}:{name}|fv={fv}"


def normalize_section_path(section_path: Any) -> Tuple[str, ...]:
    """
    Normalize section_path to a tuple of strings.
    Handles wrapped {value, citations} elements.
    """
    if section_path is None:
        return ()
    
    if isinstance(section_path, str):
        return (section_path.strip(),) if section_path.strip() else ()
    
    if isinstance(section_path, (list, tuple)):
        result = []
        for elem in section_path:
            if isinstance(elem, dict):
                val = elem.get("value")
                if val:
                    result.append(str(val).strip())
            elif isinstance(elem, str) and elem.strip():
                result.append(elem.strip())
        return tuple(result)
    
    return ()


# ---------------------------------------------------------------------------
# Detection heuristics
# ---------------------------------------------------------------------------

def extract_heading_data(heading_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract section name and percentage from a heading like "Telecommunications -- 7.1%".
    
    Returns (section_name, percent_str) or (None, None) if not a heading.
    """
    heading_text = heading_text.strip()
    
    # Check if it matches the heading pattern
    if not HEADING_PATTERN.match(heading_text):
        return None, None
    
    # Extract the percentage
    pct_match = HEADING_PERCENT_PATTERN.search(heading_text)
    percent_str = None
    if pct_match:
        percent_str = pct_match.group(1)
        # Ensure it ends with %
        if not percent_str.endswith("%"):
            percent_str = percent_str + "%"
    
    # Extract the section name (everything before --)
    parts = heading_text.split("--")
    section_name = parts[0].strip() if parts else None
    
    return section_name, percent_str


def is_column_header_holding(row: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Check if a HOLDING row is actually a column header misclassified.
    
    Returns (is_phantom, confidence).
    """
    investment = normalize_text(unwrap_value(row.get("investment")))
    row_text = normalize_text(unwrap_value(row.get("row_text")))
    quantity = unwrap_value(row.get("quantity_raw"))
    
    # Direct match on known column header phrases
    if investment in COLUMN_HEADER_PHRASES:
        return True, "high"
    
    # Check if investment is very short and ends with ":"
    if investment.endswith(":") and len(investment) < 25:
        return True, "high"
    
    # Check row_text for column header patterns
    if row_text:
        # Contains multiple column header keywords but no security-like content
        header_keywords = ["principal amount", "value", "cost", "shares", "par amount"]
        keyword_count = sum(1 for kw in header_keywords if kw in row_text)
        if keyword_count >= 2 and quantity is None:
            return True, "medium"
    
    return False, ""


def is_heading_row_as_holding(row: Dict[str, Any]) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Check if a HOLDING row is actually a section heading.
    
    Pattern: "Telecommunications -- 7.1%" with no meaningful numeric data.
    
    Returns (is_heading, confidence, section_name, percent_str).
    """
    investment = unwrap_value(row.get("investment")) or ""
    
    section_name, percent_str = extract_heading_data(investment)
    
    if section_name is not None:
        # Check if it has real numeric data beyond the embedded percentage
        fv = unwrap_value(row.get("fair_value_raw"))
        cost = unwrap_value(row.get("cost_raw"))
        qty = unwrap_value(row.get("quantity_raw"))
        
        # If it only has the percentage that's in the heading, it's a heading row
        if not fv and not cost and not qty:
            return True, "high", section_name, percent_str
        
        # If it has values, but no quantity, might still be a subtotal
        if not qty:
            return True, "medium", section_name, percent_str
    
    return False, "", None, None


def is_unlabeled_subtotal(row: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
    """
    Check if a HOLDING row is actually an unlabeled subtotal.
    
    Pattern: Has fair_value but no quantity, and investment is generic/short.
    
    Returns (is_subtotal, confidence, inferred_label).
    """
    investment = unwrap_value(row.get("investment")) or ""
    investment_norm = normalize_text(investment)
    quantity = unwrap_value(row.get("quantity_raw"))
    fair_value = unwrap_value(row.get("fair_value_raw"))
    
    # Must have fair_value but no quantity
    if not fair_value or quantity:
        return False, "", None
    
    # Parse the fair value
    fv_decimal = parse_decimal_simple(fair_value)
    if fv_decimal is None:
        return False, "", None
    
    # Check if investment looks generic
    words = set(investment_norm.split())
    if words and words.issubset(GENERIC_INVESTMENT_WORDS):
        return True, "medium", None
    
    # Very short investment name with colon
    if investment.strip().endswith(":") and len(investment) < 30:
        return True, "high", None
    
    # Check if it looks like a column header blob
    if investment_norm in COLUMN_HEADER_PHRASES:
        section_path = normalize_section_path(row.get("section_path"))
        label = section_path[-1] if section_path else None
        return True, "high", label
    
    return False, "", None


# ---------------------------------------------------------------------------
# Percent symbol misread detection and correction
# ---------------------------------------------------------------------------

def _get_decimal_places(value_str: str) -> int:
    """Get the number of decimal places in a numeric string."""
    # Clean the string
    cleaned = value_str.strip().replace("%", "").replace(",", "")
    if "." not in cleaned:
        return 0
    parts = cleaned.split(".")
    if len(parts) != 2:
        return 0
    return len(parts[1])


def _clean_label_separators(label: str) -> str:
    """
    Clean trailing separators (hyphens, dashes, whitespace) from a label.
    
    Examples:
        "Automotive -" -> "Automotive"
        "Health Care -- " -> "Health Care"
        "Banking/Savings and Loan --" -> "Banking/Savings and Loan"
    """
    if not label:
        return label
    # Remove trailing separators and whitespace
    cleaned = TRAILING_SEPARATOR_PATTERN.sub("", label).strip()
    return cleaned


def _correct_percent_ocr(number_part: str) -> str:
    """
    Apply OCR correction to a percent value (conservative mode).
    
    Only treats trailing '8' as a misread '%' if:
    1. The string does NOT already contain a '%' sign (presence of % means OCR got it right)
    2. The '8' appears at the very end AND there are 3+ decimal places
    
    This prevents valid values like "2.68%" or "2.68" from being corrupted to "2.6%".
    
    Examples:
        "1.728" -> "1.72%"  (3 decimals ending in 8 -> likely OCR error)
        "2.68" -> "2.68%"   (only 2 decimals -> keep the 8, just add %)
        "2.68%" -> "2.68%"  (already has % -> return as-is)
        "7.9%" -> "7.9%"    (already correct)
        "2.2" -> "2.2%"     (add % sign)
    """
    number_part = number_part.strip()
    
    # Guard clause: if string already contains %, never trigger 8-replacement logic
    # The presence of a real % implies OCR captured the symbol correctly
    if "%" in number_part:
        return number_part
    
    # Only treat trailing '8' as misread '%' if there are 3+ decimal places
    # This protects valid 2-decimal values like "2.68" from corruption
    if number_part.endswith("8") and "." in number_part:
        parts = number_part.split(".")
        if len(parts) == 2:
            decimal_places = len(parts[1])
            if decimal_places >= 3:
                # Likely OCR error: e.g., "1.728" -> "1.72%"
                return number_part[:-1] + "%"
    
    # No 8-replacement needed - just ensure it has a % sign
    return number_part + "%"


def extract_percent_from_label(label: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract a percentage value embedded at the end of a label.
    
    Handles various formats including OCR errors where '%' is misread as '8'.
    
    Examples:
        "Consumer Goods 2.28" -> ("Consumer Goods", "2.2%")  # 8 is misread %
        "Retail 7.9%" -> ("Retail", "7.9%")
        "Technology -- 11.2%" -> ("Technology", "11.2%")
        "Automotive - 1.38" -> ("Automotive", "1.3%")  # 8 is misread %, separator stripped
        "Health Care -- 1.68" -> ("Health Care", "1.6%")
        "Financial and Insurance - 1.98" -> ("Financial and Insurance", "1.9%")
        "Pharmaceuticals" -> (None, None)  # No embedded percent
    
    Returns:
        (clean_label, percent_value) or (None, None) if no embedded percent found
    """
    if not label:
        return None, None
    
    label = label.strip()
    
    # First, try to extract from "Category -- X.X%" format using existing pattern
    section_name, percent_str = extract_heading_data(label)
    if section_name and percent_str:
        # Clean any trailing separators from the section name
        clean_name = _clean_label_separators(section_name)
        # Apply OCR correction to the percentage
        corrected_pct = _correct_percent_ocr(percent_str)
        return clean_name, corrected_pct
    
    # Try the embedded percent pattern with separator (e.g., "Automotive - 1.38")
    match = LABEL_EMBEDDED_PERCENT_PATTERN.match(label)
    if match:
        name_part = _clean_label_separators(match.group(1))
        number_part = match.group(2).strip()
        
        # Apply OCR correction
        corrected = _correct_percent_ocr(number_part)
        return name_part, corrected
    
    # Try the fallback pattern without separator (e.g., "Consumer Goods 2.28")
    match = LABEL_EMBEDDED_PERCENT_NO_SEP_PATTERN.match(label)
    if match:
        name_part = _clean_label_separators(match.group(1))
        number_part = match.group(2).strip()
        
        # Check if it looks like a real category name (not a security name)
        # Security names often have complex structures, dates, rates
        if SUMMARY_CATEGORY_PATTERN.match(name_part):
            # Apply OCR correction
            corrected = _correct_percent_ocr(number_part)
            return name_part, corrected
    
    return None, None


def is_summary_category_row(row: Dict[str, Any]) -> bool:
    """
    Check if a row appears to be a summary/industry exposure category.
    
    These are typically lines like:
    - "Pharmaceuticals 11.7%"
    - "Technology 11.2%"
    
    Which should be SUBTOTAL rows, not HOLDINGs.
    """
    investment = unwrap_value(row.get("investment")) or ""
    label = unwrap_value(row.get("label")) or ""
    
    text_to_check = investment or label
    if not text_to_check:
        return False
    
    # Check if it matches summary category pattern
    clean_label, percent = extract_percent_from_label(text_to_check)
    if clean_label and percent:
        return True
    
    # Also check for simple category names that match the pattern
    if SUMMARY_CATEGORY_PATTERN.match(text_to_check.strip()):
        # If it has a percent but no quantity, it's likely a summary row
        qty = unwrap_value(row.get("quantity_raw"))
        pct = unwrap_value(row.get("percent_net_assets_raw"))
        if pct and not qty:
            return True
    
    return False


def _is_suspect_percent_value(value_str: str, aggressive: bool = False) -> bool:
    """
    Check if a percent value looks like it might have a misread '%' as '8'.
    
    Conservative approach: Only flags values that:
    1. Do NOT contain a '%' sign (if % is present, OCR got it right)
    2. End in '8' with a decimal point
    3. Have 3+ decimal places (to protect valid 2-decimal values like "2.68")
    
    Args:
        value_str: The value string to check
        aggressive: Deprecated, kept for API compatibility. Now ignored.
    """
    if not value_str:
        return False
    cleaned = value_str.strip()
    
    # Guard clause: if % is present, the 8 is a real digit, not a misread %
    if "%" in cleaned:
        return False
    
    # Must have a decimal point
    if "." not in cleaned:
        return False
    
    # Must end in 8
    if not cleaned.endswith("8"):
        return False
    
    # Only suspect if there are 3+ decimal places
    # This protects valid values like "2.68" from being flagged
    if MISREAD_PERCENT_PATTERN.match(cleaned):
        parts = cleaned.replace("-", "").split(".")
        if len(parts) == 2:
            decimal_places = len(parts[1])
            if decimal_places >= 3:
                return True
    
    return False


def _correct_misread_percent(value_str: str) -> str:
    """
    Correct a misread percent value by replacing trailing '8' with '%'.
    
    Conservative approach:
    - Only corrects values that do NOT already contain '%'
    - Replaces trailing '8' with '%' (e.g., "1.728" -> "1.72%")
    
    Examples:
        "1.728" -> "1.72%" (trailing 8 replaced with %)
        "2.68%" -> "2.68%" (already has %, return as-is)
        "2.68" -> "2.6%" (trailing 8 replaced with %)
    """
    cleaned = value_str.strip()
    
    # Guard clause: if % is present, the 8 is a real digit
    if "%" in cleaned:
        return cleaned
    
    # Replace trailing '8' with '%'
    if cleaned.endswith("8"):
        return cleaned[:-1] + "%"
    
    return value_str


def fix_misread_percent_symbols(
    rows: List[Dict[str, Any]],
    result: NormalizationResult,
) -> List[Dict[str, Any]]:
    """
    Detect and correct percent values where '%' was misread as '8'.
    
    Conservative strategy:
    1. Find TOTAL rows to establish the expected decimal precision
    2. For each row with a suspect percent value:
       - Must NOT contain '%' (presence of % means OCR got it right)
       - Must end in '8' with 3+ decimal places (e.g., "1.728")
       - Must have MORE decimal places than the expected precision
       - Correct by replacing trailing '8' with '%'
    3. Also check labels for embedded percentages with OCR errors
    
    This protects valid values like "2.68" from being corrupted to "2.6%".
    
    Args:
        rows: List of row dicts (already processed by normalize_soi_rows)
        result: NormalizationResult to update with fix logs
    
    Returns:
        List of corrected rows
    """
    # First pass: find the decimal precision of TOTAL rows
    total_precisions: List[int] = []
    for row in rows:
        row_type = unwrap_value(row.get("row_type"))
        if row_type == "TOTAL":
            pct = unwrap_value(row.get("percent_net_assets_raw"))
            if pct:
                precision = _get_decimal_places(pct)
                total_precisions.append(precision)
    
    # Use the most common precision, or default to 1 decimal place
    if total_precisions:
        expected_precision = max(set(total_precisions), key=total_precisions.count)
    else:
        expected_precision = 1  # Default assumption
    
    # Second pass: check and correct suspect values
    corrected_rows = []
    for idx, row in enumerate(rows):
        row_copy = copy.deepcopy(row)
        pct = unwrap_value(row.get("percent_net_assets_raw"))
        
        # Conservative check: only flags values without %, ending in 8, with 3+ decimals
        if pct and _is_suspect_percent_value(pct):
            row_precision = _get_decimal_places(pct)
            
            # Only correct if this row has more decimal places than expected
            # This catches outliers like "1.728" when column uses 2 decimal places
            should_correct = row_precision > expected_precision
            
            if should_correct:
                corrected = _correct_misread_percent(pct)
                set_wrapped_value(row_copy, "percent_net_assets_raw", corrected)
                
                row_type = unwrap_value(row.get("row_type")) or "UNKNOWN"
                result.fix_log.append(FixLogEntry(
                    row_idx=idx,
                    old_row_type=row_type,
                    new_row_type=row_type,
                    action="percent_corrected",
                    reason_code="MISREAD_PERCENT_AS_8",
                    confidence="high",
                    row_signature=get_row_signature(row),
                    old_value=pct,
                    new_value=corrected,
                ))
                result.percent_corrected_count += 1
                result.fix_count += 1
        
        # Also check labels for embedded percentages
        label = unwrap_value(row.get("label"))
        if label:
            clean_label, embedded_pct = extract_percent_from_label(label)
            if clean_label and embedded_pct:
                # Update the label to just the name
                set_wrapped_value(row_copy, "label", clean_label)
                
                # If percent_net_assets_raw is empty, populate it
                existing_pct = unwrap_value(row_copy.get("percent_net_assets_raw"))
                if not existing_pct:
                    set_wrapped_value(row_copy, "percent_net_assets_raw", embedded_pct)
                    
                    row_type = unwrap_value(row.get("row_type")) or "UNKNOWN"
                    result.fix_log.append(FixLogEntry(
                        row_idx=idx,
                        old_row_type=row_type,
                        new_row_type=row_type,
                        action="percent_corrected",
                        reason_code="PERCENT_EXTRACTED_FROM_LABEL",
                        confidence="high",
                        row_signature=get_row_signature(row),
                        old_value=label,
                        new_value=f"label='{clean_label}', pct='{embedded_pct}'",
                    ))
                    result.percent_corrected_count += 1
                    result.fix_count += 1
        
        corrected_rows.append(row_copy)
    
    return corrected_rows


# ---------------------------------------------------------------------------
# Percentage hierarchy detection and deduplication
# ---------------------------------------------------------------------------

# Top-level asset class patterns that indicate section headers (not industry subtotals)
ASSET_CLASS_PATTERNS = frozenset({
    "convertible bonds",
    "convertible preferred",
    "preferred stocks",
    "common stocks",
    "mandatory convertible",
    "short-term securities",
    "short term securities",
    "money market",
    "corporate bonds",
    "government bonds",
    "municipal bonds",
    "equity securities",
    "debt securities",
    "fixed income",
    "total investments",
    "total net assets",
})


def _is_asset_class_label(label: str) -> bool:
    """
    Check if a label looks like a top-level asset class header.
    
    These are patterns like:
    - "CONVERTIBLE BONDS AND NOTES"
    - "CONVERTIBLE PREFERRED STOCKS"
    - "SHORT-TERM SECURITIES"
    """
    if not label:
        return False
    
    label_lower = label.lower().strip()
    
    for pattern in ASSET_CLASS_PATTERNS:
        if pattern in label_lower:
            return True
    
    return False


def _get_section_path_key(section_path: Any) -> str:
    """Get a string key from section_path for grouping."""
    path_tuple = normalize_section_path(section_path)
    return " > ".join(path_tuple) if path_tuple else "(root)"


def detect_percentage_hierarchy_duplicates(
    rows: List[Dict[str, Any]],
) -> List[int]:
    """
    Detect rows that are section-header-level SUBTOTALs that should be removed
    because their percentages duplicate the sum of their child industry subtotals.
    
    This fixes the "187.9% vs 100%" error where:
    - Section header "CONVERTIBLE BONDS AND NOTES -- 53.6%" is emitted as SUBTOTAL
    - Industry subtotals "Advertising -- 0.9%", "Aerospace -- 1.2%", etc. are also emitted
    - Result: 53.6% + 0.9% + 1.2% + ... = double-counting
    
    Detection strategy:
    1. Group SUBTOTAL rows by their section_path
    2. For each section that has multiple SUBTOTAL rows:
       - If one SUBTOTAL's label looks like an asset class header
       - AND its percentage approximately equals the sum of the other SUBTOTALs
       - Mark that SUBTOTAL row for removal
    
    Returns:
        List of row indices to remove
    """
    # Group SUBTOTAL rows by section_path
    subtotals_by_section: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}
    
    for idx, row in enumerate(rows):
        row_type = unwrap_value(row.get("row_type"))
        if row_type != "SUBTOTAL":
            continue
        
        section_key = _get_section_path_key(row.get("section_path"))
        if section_key not in subtotals_by_section:
            subtotals_by_section[section_key] = []
        subtotals_by_section[section_key].append((idx, row))
    
    # Check each section for duplicate hierarchy patterns
    rows_to_remove: List[int] = []
    
    for section_key, subtotal_entries in subtotals_by_section.items():
        if len(subtotal_entries) < 2:
            continue
        
        # Separate potential asset-class headers from industry subtotals
        asset_class_rows: List[Tuple[int, Dict[str, Any]]] = []
        industry_rows: List[Tuple[int, Dict[str, Any]]] = []
        
        for idx, row in subtotal_entries:
            label = unwrap_value(row.get("label")) or ""
            if _is_asset_class_label(label):
                asset_class_rows.append((idx, row))
            else:
                industry_rows.append((idx, row))
        
        # If we have both asset-class and industry subtotals, check for duplication
        if not asset_class_rows or not industry_rows:
            continue
        
        # Calculate sum of industry subtotal percentages
        industry_pct_sum = Decimal("0")
        industry_count = 0
        
        for _, row in industry_rows:
            pct_raw = unwrap_value(row.get("percent_net_assets_raw"))
            if pct_raw:
                pct_val = parse_decimal_simple(pct_raw)
                if pct_val is not None:
                    industry_pct_sum += pct_val
                    industry_count += 1
        
        # For each asset-class row, check if its percentage matches the industry sum
        for idx, row in asset_class_rows:
            pct_raw = unwrap_value(row.get("percent_net_assets_raw"))
            if not pct_raw:
                continue
            
            asset_pct = parse_decimal_simple(pct_raw)
            if asset_pct is None:
                continue
            
            # Check if asset class percentage roughly equals industry sum
            # Allow tolerance for rounding (~1% for small sections, ~2% for large)
            tolerance = max(Decimal("1.0"), asset_pct * Decimal("0.05"))
            diff = abs(asset_pct - industry_pct_sum)
            
            if diff <= tolerance and industry_count >= 2:
                # This asset-class SUBTOTAL is redundant - its percentage
                # is already accounted for by the industry subtotals
                rows_to_remove.append(idx)
    
    return rows_to_remove


def remove_duplicate_hierarchy_subtotals(
    rows: List[Dict[str, Any]],
    result: NormalizationResult,
) -> List[Dict[str, Any]]:
    """
    Remove SUBTOTAL rows that represent duplicate percentage hierarchy.
    
    When an extraction creates both:
    - Section header SUBTOTAL: "CONVERTIBLE BONDS AND NOTES", pct=53.6%
    - Industry SUBTOTALs: "Advertising" 0.9%, "Aerospace" 1.2%, etc.
    
    The section header percentage is already included in the industry breakdown,
    so it should be removed to avoid double-counting in validation.
    
    Args:
        rows: List of row dicts (already processed by normalize_soi_rows)
        result: NormalizationResult to update with fix logs
    
    Returns:
        List of rows with duplicates removed
    """
    indices_to_remove = set(detect_percentage_hierarchy_duplicates(rows))
    
    if not indices_to_remove:
        return rows
    
    cleaned_rows = []
    for idx, row in enumerate(rows):
        if idx in indices_to_remove:
            # Log the removal
            result.fix_log.append(FixLogEntry(
                row_idx=idx,
                old_row_type=unwrap_value(row.get("row_type")) or "SUBTOTAL",
                new_row_type=None,
                action="dropped",
                reason_code="DUPLICATE_PERCENTAGE_HIERARCHY",
                confidence="high",
                row_signature=get_row_signature(row),
            ))
            result.dropped_count += 1
            result.fix_count += 1
        else:
            cleaned_rows.append(row)
    
    return cleaned_rows


# ---------------------------------------------------------------------------
# Shifted subtotal detection and correction
# ---------------------------------------------------------------------------

def _sum_holdings_fair_value(
    holdings: List[Dict[str, Any]]
) -> Optional[Decimal]:
    """Sum fair_value_raw for a list of HOLDING rows."""
    total = Decimal("0")
    has_value = False
    
    for row in holdings:
        fv_raw = unwrap_value(row.get("fair_value_raw"))
        if fv_raw:
            fv = parse_decimal_simple(fv_raw)
            if fv is not None:
                total += fv
                has_value = True
    
    return total if has_value else None


def detect_shifted_subtotals(
    rows: List[Dict[str, Any]]
) -> List[Tuple[int, str, str, str]]:
    """
    Detect SUBTOTAL rows that appear to have been attributed to the wrong section.
    
    This detects the "off-by-one" pattern where a SUBTOTAL's fair_value matches
    the PREVIOUS section's holdings sum rather than its own section's holdings.
    
    Detection strategy:
    1. Build a list of sections in document order
    2. For each section with holdings and a SUBTOTAL:
       - Calculate the sum of holdings in that section
       - Get the SUBTOTAL's fair_value
       - If they don't match, check if the SUBTOTAL's value matches the PREVIOUS section's sum
       - If so, flag as a shifted subtotal
    
    Returns:
        List of (row_idx, current_path_str, correct_path_str, reason) tuples
    """
    # Group rows by section_path (in document order)
    sections_order: List[Tuple[str, ...]] = []
    section_holdings: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}
    section_subtotals: Dict[Tuple[str, ...], List[Tuple[int, Dict[str, Any]]]] = {}
    
    for idx, row in enumerate(rows):
        row_type = unwrap_value(row.get("row_type"))
        path = normalize_section_path(row.get("section_path"))
        
        # Only consider leaf-level paths (with at least 2 levels: asset class + industry)
        if len(path) < 2:
            continue
        
        if path not in section_holdings:
            section_holdings[path] = []
            section_subtotals[path] = []
            sections_order.append(path)
        
        if row_type == "HOLDING":
            section_holdings[path].append(row)
        elif row_type == "SUBTOTAL":
            section_subtotals[path].append((idx, row))
    
    # Now check for shifted subtotals
    shifted: List[Tuple[int, str, str, str]] = []
    
    # For each section (except the first), check if its SUBTOTAL value matches previous section's holdings
    for i, path in enumerate(sections_order):
        subtotals = section_subtotals.get(path, [])
        if not subtotals:
            continue
        
        holdings = section_holdings.get(path, [])
        holdings_sum = _sum_holdings_fair_value(holdings)
        
        for row_idx, subtotal_row in subtotals:
            subtotal_fv_raw = unwrap_value(subtotal_row.get("fair_value_raw"))
            if not subtotal_fv_raw:
                continue
            
            subtotal_fv = parse_decimal_simple(subtotal_fv_raw)
            if subtotal_fv is None:
                continue
            
            # Check if subtotal matches its own holdings
            if holdings_sum is not None and abs(holdings_sum - subtotal_fv) <= Decimal("1"):
                # Matches - no issue
                continue
            
            # Check if subtotal matches PREVIOUS section's holdings
            if i > 0:
                prev_path = sections_order[i - 1]
                prev_holdings = section_holdings.get(prev_path, [])
                prev_sum = _sum_holdings_fair_value(prev_holdings)
                
                if prev_sum is not None and abs(prev_sum - subtotal_fv) <= Decimal("1"):
                    # This SUBTOTAL's value matches the PREVIOUS section!
                    # It was likely assigned to the wrong section
                    shifted.append((
                        row_idx,
                        " > ".join(path),
                        " > ".join(prev_path),
                        f"SUBTOTAL fair_value ${subtotal_fv} matches previous section '{prev_path[-1]}' holdings sum (${prev_sum}), not current section"
                    ))
    
    return shifted


def fix_shifted_subtotals(
    rows: List[Dict[str, Any]],
    result: NormalizationResult,
) -> List[Dict[str, Any]]:
    """
    Detect and correct SUBTOTAL rows that were attributed to the wrong section.
    
    When a SUBTOTAL's fair_value matches the PREVIOUS section's holdings sum
    (instead of its own section's), reassign its section_path to the correct section.
    
    Args:
        rows: List of row dicts
        result: NormalizationResult to update with fix logs
    
    Returns:
        List of corrected rows
    """
    shifted = detect_shifted_subtotals(rows)
    
    if not shifted:
        return rows
    
    # Build a set of row indices to correct
    corrections: Dict[int, Tuple[str, ...]] = {}
    for row_idx, current_path_str, correct_path_str, reason in shifted:
        # Parse the correct path back to a tuple
        correct_path = tuple(correct_path_str.split(" > "))
        corrections[row_idx] = correct_path
    
    corrected_rows = []
    for idx, row in enumerate(rows):
        if idx in corrections:
            correct_path = corrections[idx]
            row_copy = copy.deepcopy(row)
            
            # Update section_path to the correct path
            # Handle wrapped section_path format
            old_path = row.get("section_path", [])
            if isinstance(old_path, list):
                new_section_path = []
                for i, segment in enumerate(correct_path):
                    if i < len(old_path) and isinstance(old_path[i], dict):
                        # Preserve the wrapped format
                        new_segment = copy.deepcopy(old_path[i])
                        new_segment["value"] = segment
                        new_section_path.append(new_segment)
                    else:
                        new_section_path.append({"value": segment, "citations": []})
                row_copy["section_path"] = new_section_path
            
            # Also update the label if it doesn't match the new path's last element
            label = unwrap_value(row_copy.get("label"))
            new_label = correct_path[-1] if correct_path else label
            if label != new_label:
                set_wrapped_value(row_copy, "label", new_label)
            
            corrected_rows.append(row_copy)
            
            # Log the fix
            result.fix_log.append(FixLogEntry(
                row_idx=idx,
                old_row_type=unwrap_value(row.get("row_type")) or "SUBTOTAL",
                new_row_type=unwrap_value(row.get("row_type")) or "SUBTOTAL",
                action="converted",
                reason_code="SHIFTED_SUBTOTAL_CORRECTED",
                confidence="high",
                row_signature=get_row_signature(row),
                old_value=" > ".join(normalize_section_path(row.get("section_path"))),
                new_value=" > ".join(correct_path),
            ))
            result.converted_count += 1
            result.fix_count += 1
        else:
            corrected_rows.append(row)
    
    return corrected_rows


# ---------------------------------------------------------------------------
# Main normalization function
# ---------------------------------------------------------------------------

def normalize_soi_rows(
    soi_rows: List[Dict[str, Any]],
    *,
    convert_to_subtotal: bool = True,
    drop_unfixable: bool = True,
) -> Tuple[List[Dict[str, Any]], NormalizationResult]:
    """
    Normalize SOI rows by detecting and fixing misclassified rows.
    
    Args:
        soi_rows: List of row dicts from Reducto extraction
        convert_to_subtotal: If True, convert phantom holdings to SUBTOTAL when possible
        drop_unfixable: If True, drop rows that can't be safely converted
    
    Returns:
        (normalized_rows, result) where result contains fix log and statistics
    """
    result = NormalizationResult(rows=[])
    
    # Track current heading context for label inference
    current_heading: Optional[str] = None
    
    for idx, row in enumerate(soi_rows):
        # Skip non-dict entries (malformed rows)
        if not isinstance(row, dict):
            continue
        
        row_type = unwrap_value(row.get("row_type"))
        
        # Process SUBTOTAL and TOTAL rows for label cleaning
        if row_type in ("SUBTOTAL", "TOTAL"):
            row_copy = copy.deepcopy(row)
            label = unwrap_value(row.get("label"))
            
            if label:
                # Check for embedded percentages in label (e.g., "Automotive - 1.38")
                clean_label, embedded_pct = extract_percent_from_label(label)
                
                if clean_label and embedded_pct:
                    # Update the label to just the name (no trailing separators or percent)
                    set_wrapped_value(row_copy, "label", clean_label)
                    
                    # If percent_net_assets_raw is empty, populate it
                    existing_pct = unwrap_value(row_copy.get("percent_net_assets_raw"))
                    if not existing_pct:
                        set_wrapped_value(row_copy, "percent_net_assets_raw", embedded_pct)
                        
                        result.fix_log.append(FixLogEntry(
                            row_idx=idx,
                            old_row_type=row_type,
                            new_row_type=row_type,
                            action="percent_corrected",
                            reason_code="SUBTOTAL_LABEL_CLEANED",
                            confidence="high",
                            row_signature=get_row_signature(row),
                            old_value=label,
                            new_value=f"label='{clean_label}', pct='{embedded_pct}'",
                        ))
                        result.percent_corrected_count += 1
                        result.fix_count += 1
                    elif clean_label != label:
                        # Label was cleaned but pct already existed
                        result.fix_log.append(FixLogEntry(
                            row_idx=idx,
                            old_row_type=row_type,
                            new_row_type=row_type,
                            action="percent_corrected",
                            reason_code="SUBTOTAL_LABEL_STRIPPED",
                            confidence="high",
                            row_signature=get_row_signature(row),
                            old_value=label,
                            new_value=clean_label,
                        ))
                        result.fix_count += 1
                else:
                    # No embedded percent, but still clean trailing separators
                    cleaned = _clean_label_separators(label)
                    if cleaned != label:
                        set_wrapped_value(row_copy, "label", cleaned)
                        result.fix_log.append(FixLogEntry(
                            row_idx=idx,
                            old_row_type=row_type,
                            new_row_type=row_type,
                            action="percent_corrected",
                            reason_code="LABEL_SEPARATOR_STRIPPED",
                            confidence="high",
                            row_signature=get_row_signature(row),
                            old_value=label,
                            new_value=cleaned,
                        ))
                        result.fix_count += 1
                
                # Update heading context from section headings
                current_heading = clean_label or _clean_label_separators(label)
            
            result.rows.append(row_copy)
            continue
        
        # Only process HOLDING rows for phantom detection
        if row_type != "HOLDING":
            result.rows.append(copy.deepcopy(row))
            continue
        
        # Check for column header as holding
        is_phantom, confidence = is_column_header_holding(row)
        if is_phantom:
            if convert_to_subtotal:
                # Convert to SUBTOTAL
                fixed_row = copy.deepcopy(row)
                set_wrapped_value(fixed_row, "row_type", "SUBTOTAL")
                
                # Create a label from section_path or investment
                section_path = normalize_section_path(row.get("section_path"))
                investment = unwrap_value(row.get("investment")) or ""
                
                label = f"Subtotal {section_path[-1]}" if section_path else f"Subtotal"
                set_wrapped_value(fixed_row, "label", label)
                set_wrapped_value(fixed_row, "investment", None)
                
                result.rows.append(fixed_row)
                result.fix_log.append(FixLogEntry(
                    row_idx=idx,
                    old_row_type="HOLDING",
                    new_row_type="SUBTOTAL",
                    action="converted",
                    reason_code="COLUMN_HEADER_AS_HOLDING",
                    confidence=confidence,
                    row_signature=get_row_signature(row),
                ))
                result.converted_count += 1
                result.fix_count += 1
            elif drop_unfixable:
                # Drop the row
                result.fix_log.append(FixLogEntry(
                    row_idx=idx,
                    old_row_type="HOLDING",
                    new_row_type=None,
                    action="dropped",
                    reason_code="COLUMN_HEADER_AS_HOLDING",
                    confidence=confidence,
                    row_signature=get_row_signature(row),
                ))
                result.dropped_count += 1
                result.fix_count += 1
            else:
                result.rows.append(copy.deepcopy(row))
            continue
        
        # Check for heading row as holding
        is_heading, confidence, section_name, percent_str = is_heading_row_as_holding(row)
        if is_heading:
            # Convert heading rows to SUBTOTAL to preserve percentage data
            if convert_to_subtotal:
                investment = unwrap_value(row.get("investment")) or ""
                
                # Update heading context
                if section_name:
                    current_heading = section_name
                
                fixed_row = copy.deepcopy(row)
                set_wrapped_value(fixed_row, "row_type", "SUBTOTAL")
                
                # Use the original heading text as the label
                set_wrapped_value(fixed_row, "label", investment)
                set_wrapped_value(fixed_row, "investment", None)
                
                # Populate percent_net_assets_raw if we extracted a percentage
                if percent_str:
                    set_wrapped_value(fixed_row, "percent_net_assets_raw", percent_str)
                
                result.rows.append(fixed_row)
                result.fix_log.append(FixLogEntry(
                    row_idx=idx,
                    old_row_type="HOLDING",
                    new_row_type="SUBTOTAL",
                    action="converted",
                    reason_code="HEADING_ROW_AS_HOLDING",
                    confidence=confidence,
                    row_signature=get_row_signature(row),
                ))
                result.converted_count += 1
                result.fix_count += 1
            elif drop_unfixable:
                # Fall back to dropping if conversion is disabled
                investment = unwrap_value(row.get("investment")) or ""
                if section_name:
                    current_heading = section_name
                
                result.fix_log.append(FixLogEntry(
                    row_idx=idx,
                    old_row_type="HOLDING",
                    new_row_type=None,
                    action="dropped",
                    reason_code="HEADING_ROW_AS_HOLDING",
                    confidence=confidence,
                    row_signature=get_row_signature(row),
                ))
                result.dropped_count += 1
                result.fix_count += 1
            else:
                result.rows.append(copy.deepcopy(row))
            continue
        
        # Check for unlabeled subtotal
        is_subtotal, confidence, inferred_label = is_unlabeled_subtotal(row)
        if is_subtotal and convert_to_subtotal:
            fixed_row = copy.deepcopy(row)
            set_wrapped_value(fixed_row, "row_type", "SUBTOTAL")
            
            # Use inferred label or construct one
            if inferred_label:
                label = f"Subtotal {inferred_label}"
            elif current_heading:
                label = f"Subtotal {current_heading}"
            else:
                section_path = normalize_section_path(row.get("section_path"))
                label = f"Subtotal {section_path[-1]}" if section_path else "Subtotal"
            
            set_wrapped_value(fixed_row, "label", label)
            set_wrapped_value(fixed_row, "investment", None)
            
            result.rows.append(fixed_row)
            result.fix_log.append(FixLogEntry(
                row_idx=idx,
                old_row_type="HOLDING",
                new_row_type="SUBTOTAL",
                action="converted",
                reason_code="UNLABELED_SUBTOTAL",
                confidence=confidence,
                row_signature=get_row_signature(row),
            ))
            result.converted_count += 1
            result.fix_count += 1
            continue
        
        # Check for summary category rows (e.g., "Pharmaceuticals 11.7%" classified as HOLDING)
        if is_summary_category_row(row) and convert_to_subtotal:
            investment = unwrap_value(row.get("investment")) or ""
            clean_label, embedded_pct = extract_percent_from_label(investment)
            
            fixed_row = copy.deepcopy(row)
            set_wrapped_value(fixed_row, "row_type", "SUBTOTAL")
            
            if clean_label:
                set_wrapped_value(fixed_row, "label", clean_label)
                if embedded_pct:
                    set_wrapped_value(fixed_row, "percent_net_assets_raw", embedded_pct)
            else:
                set_wrapped_value(fixed_row, "label", investment)
            
            set_wrapped_value(fixed_row, "investment", None)
            
            result.rows.append(fixed_row)
            result.fix_log.append(FixLogEntry(
                row_idx=idx,
                old_row_type="HOLDING",
                new_row_type="SUBTOTAL",
                action="converted",
                reason_code="SUMMARY_CATEGORY_AS_HOLDING",
                confidence="medium",
                row_signature=get_row_signature(row),
            ))
            result.converted_count += 1
            result.fix_count += 1
            continue
        
        # No issues detected - keep the row as-is
        result.rows.append(copy.deepcopy(row))
    
    # Apply percent symbol misread correction
    result.rows = fix_misread_percent_symbols(result.rows, result)
    
    # Remove duplicate percentage hierarchy (section header + child industry subtotals)
    result.rows = remove_duplicate_hierarchy_subtotals(result.rows, result)
    
    # Fix shifted subtotals (off-by-one section attribution)
    result.rows = fix_shifted_subtotals(result.rows, result)
    
    return result.rows, result


def get_normalization_summary(result: NormalizationResult) -> Dict[str, Any]:
    """Get a summary of normalization results for reporting."""
    reason_counts: Dict[str, int] = {}
    for entry in result.fix_log:
        reason_counts[entry.reason_code] = reason_counts.get(entry.reason_code, 0) + 1
    
    return {
        "fix_count": result.fix_count,
        "dropped_count": result.dropped_count,
        "converted_count": result.converted_count,
        "by_reason": reason_counts,
    }

