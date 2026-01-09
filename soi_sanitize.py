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

# Keywords that indicate a row is a SHORT POSITION (liability)
# These should have NEGATIVE fair values, but some documents display them as positive
# "market value" - we need to convert them to negative for correct arithmetic
SHORT_POSITION_KEYWORDS = frozenset({
    "written call options",
    "written put options",
    "call options written",
    "put options written",
    "options written",
    "short position",
    "short positions",
    "securities sold short",
    "sold short",
    "short sales",
})

# ---------------------------------------------------------------------------
# Liability / Contra-Entry Detection
# ---------------------------------------------------------------------------

# Keywords that indicate a row is a liability or contra-entry, not a regular holding
# These rows should be excluded from arithmetic validation totals
LIABILITY_KEYWORDS = frozenset({
    "at redemption value",
    "redemption value",
    "preferred stock, at redemption",
    "preferred shares",  # When at root level with negative value
    "other assets less liabilities",
    "other assets and liabilities",
    "assets less liabilities",
    "liabilities",
    "net unrealized depreciation",
    "unrealized depreciation",
    "net unrealized loss",
    "contra",
    "payable",
    "accrued expenses",
    "deferred",
})

# More specific patterns that strongly indicate liability rows
LIABILITY_PATTERNS = [
    re.compile(r"preferred\s+stock.*redemption", re.IGNORECASE),
    re.compile(r"preferred\s+shares.*redemption", re.IGNORECASE),
    re.compile(r"other\s+assets.*liabilities", re.IGNORECASE),
    re.compile(r"net\s+assets", re.IGNORECASE),
]


def is_liability_row(row: Dict[str, Any]) -> bool:
    """
    Detect rows that are liabilities or contra-entries, not regular holdings.
    
    These rows appear in SOI documents but should NOT be summed with regular holdings.
    They typically represent:
    - Redemption value disclosures (informational only)
    - Liabilities that offset assets
    - "Other assets less liabilities" line items
    - Net unrealized depreciation entries
    
    Returns True if the row appears to be a liability/contra-entry.
    """
    investment = unwrap_value(row.get("investment")) or ""
    label = unwrap_value(row.get("label")) or ""
    text = (investment + " " + label).lower().strip()
    
    if not text:
        return False
    
    # Check against keyword list
    for keyword in LIABILITY_KEYWORDS:
        if keyword in text:
            return True
    
    # Check against regex patterns
    for pattern in LIABILITY_PATTERNS:
        if pattern.search(text):
            return True
    
    return False


def should_exclude_from_totals(row: Dict[str, Any]) -> bool:
    """
    Determine if a row should be excluded from arithmetic validation.
    
    Exclusion criteria:
    1. Row matches liability/contra-entry keywords
    2. HOLDING row with negative fair_value at root level (likely misclassified)
    3. Row has liability-like investment name with negative value
    
    Returns True if the row should be excluded from sum calculations.
    """
    # Check if it's a known liability row pattern
    if is_liability_row(row):
        return True
    
    # Check for negative fair_value at root level
    row_type = unwrap_value(row.get("row_type"))
    if row_type != "HOLDING":
        return False
    
    fv_raw = unwrap_value(row.get("fair_value_raw"))
    if not fv_raw:
        return False
    
    fv = parse_decimal_simple(fv_raw)
    if fv is None or fv >= 0:
        return False
    
    # Negative fair_value HOLDING at root or shallow section = likely contra-entry
    section_path = normalize_section_path(row.get("section_path"))
    if len(section_path) <= 1:
        # Root level or single-level section with negative value
        return True
    
    return False


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

def _get_row_original_page(row: Dict[str, Any]) -> Optional[int]:
    """
    Extract the original_page from a row's citations.
    
    Checks key fields (investment, label, fair_value_raw, section_path) for citation info.
    Returns the first valid original_page found, or None.
    """
    # Fields to check for citations (in priority order)
    fields_to_check = ["investment", "label", "fair_value_raw", "quantity_raw", "percent_net_assets_raw"]
    
    for field_name in fields_to_check:
        field_obj = row.get(field_name)
        if field_obj is None:
            continue
        
        # Handle wrapped {value, citations} format
        if isinstance(field_obj, dict):
            citations = field_obj.get("citations", [])
            if isinstance(citations, list):
                for cit in citations:
                    bbox = cit.get("bbox", {})
                    original_page = bbox.get("original_page")
                    if original_page is not None:
                        try:
                            return int(original_page)
                        except (TypeError, ValueError):
                            continue
    
    # Also check section_path items (which may have citations)
    section_path = row.get("section_path")
    if isinstance(section_path, list):
        for item in section_path:
            if isinstance(item, dict):
                citations = item.get("citations", [])
                if isinstance(citations, list):
                    for cit in citations:
                        bbox = cit.get("bbox", {})
                        original_page = bbox.get("original_page")
                        if original_page is not None:
                            try:
                                return int(original_page)
                            except (TypeError, ValueError):
                                continue
    
    return None


# ---------------------------------------------------------------------------
# Page-based filtering with multi-heuristic rescue
# ---------------------------------------------------------------------------

# Threshold for Volume Rescue: if a "bad" page has more than this many rows,
# it's likely the main SOI (not a Summary table) and all rows are rescued.
VOLUME_RESCUE_THRESHOLD = 20

# Major total labels that should always be rescued (case-insensitive contains)
MAJOR_TOTAL_PATTERNS = frozenset({
    "total long term investments",
    "total short term investments",
    "total investments",
    "net assets",
    "total long-term investments",
    "total short-term investments",
})


def count_rows_by_page(
    rows: List[Dict[str, Any]],
) -> Dict[int, int]:
    """
    Count how many rows come from each page number.
    
    Used for Volume Rescue heuristic: Summary tables are short (5-15 rows),
    while the main SOI is long (50+ rows). If many rows cite the same "bad" page,
    it's likely the model hallucinated the page number for the entire section.
    
    Args:
        rows: List of row dicts with citation metadata
    
    Returns:
        Dict mapping page_number -> count of rows from that page
    """
    page_counts: Dict[int, int] = {}
    for row in rows:
        page = _get_row_original_page(row)
        if page is not None:
            page_counts[page] = page_counts.get(page, 0) + 1
    return page_counts


def get_rescue_pages(
    rows: List[Dict[str, Any]],
    soi_pages: set,
    threshold: int = VOLUME_RESCUE_THRESHOLD,
) -> set:
    """
    Identify "bad" pages that should be rescued via Volume Rescue heuristic.
    
    If a page outside soi_pages contributes more than `threshold` rows,
    it's likely the main SOI (model hallucinated page numbers) rather than
    a Summary/Highlights table.
    
    Args:
        rows: List of row dicts
        soi_pages: Set of valid SOI page numbers from the split step
        threshold: Minimum row count to trigger Volume Rescue
    
    Returns:
        Set of page numbers that should be rescued (all rows kept)
    """
    page_counts = count_rows_by_page(rows)
    rescue_pages: set = set()
    
    for page, count in page_counts.items():
        # Only consider pages that would otherwise be dropped
        if page not in soi_pages and count > threshold:
            rescue_pages.add(page)
    
    return rescue_pages


def is_high_confidence_holding(row: Dict[str, Any]) -> bool:
    """
    Check if a row has strong signals of being a detailed holding (Information Density).
    
    Used for Detail Rescue heuristic. Summary/Highlights tables show only
    Name + Value + %. The main SOI often has Interest Rates, Maturity Dates,
    Principal Amounts, CUSIP numbers, etc.
    
    For EQUITY holdings (which lack maturity dates/rates), we also check for:
    - ADR/GDR suffixes (American/Global Depositary Receipts)
    - Class A/B/C designations
    - Series A/B/C designations
    - PNA/PNB (Chilean preferred share classes)
    - Common Stock/Preferred Stock keywords
    
    Returns True if the row has detail that Summary tables lack.
    """
    # Check for detailed fields that summary tables rarely have
    if unwrap_value(row.get("interest_rate_raw")):
        return True
    if unwrap_value(row.get("maturity_date")):
        return True
    
    # Check for investment name complexity (dates, rates, equity indicators)
    inv = unwrap_value(row.get("investment")) or ""
    inv_upper = inv.upper()
    
    # BOND PATTERNS: "2.125%, 10/09/07" or similar (rate + date)
    # Loosened regex to allow optional space and various separators
    if re.search(r"\d+\.?\d*%[,\s]*\d+[/\-]\d+[/\-]\d+", inv):
        return True
    
    # Date ranges like "11/21/06 - 7/24/07"
    if re.search(r"\d+[/\-]\d+[/\-]\d+\s*[-–—]\s*\d+[/\-]\d+[/\-]\d+", inv):
        return True
    
    # EQUITY PATTERNS: These indicate detailed holdings, not summary rows
    
    # ADR/GDR patterns (American/Global Depositary Receipts)
    # Matches: ", ADR", " ADR", ",ADR", "ADR++" (with footnote markers)
    if re.search(r"[,\s]ADR\b", inv_upper) or re.search(r"[,\s]GDR\b", inv_upper):
        return True
    
    # Class designations: "Class A", "Class B", "Class C", etc.
    # Matches: ", Class A", " Class A,", "Class A+"
    if re.search(r"\bCLASS\s+[A-Z]\b", inv_upper):
        return True
    
    # Series designations: "Series A", "Series B", "Series B, ADR"
    if re.search(r"\bSERIES\s+[A-Z]\b", inv_upper):
        return True
    
    # Chilean preferred share classes: PNA, PNB (Preferidas Nominativas)
    # These are specific to Chilean equities like Embotelladora Andina S.A.
    if re.search(r"[,\s]PN[AB]\b", inv_upper):
        return True
    
    # Common/Preferred stock keywords
    if re.search(r"\bCOMMON\s+STOCK\b", inv_upper):
        return True
    if re.search(r"\bPREFERRED\s+STOCK\b", inv_upper):
        return True
    if re.search(r"\bORDINARY\s+SHARES?\b", inv_upper):
        return True
    
    # Convertible notes/bonds with specific terms (e.g., "cv. sub. deb.", "cv. sr. notes")
    if re.search(r"\bcv\.\s*(sub\.|sr\.)", inv.lower()):
        return True
    
    # CUSIP-like patterns (9 alphanumeric characters)
    if re.search(r"\b[A-Z0-9]{9}\b", inv_upper):
        return True
        
    return False


def is_major_total_row(row: Dict[str, Any]) -> bool:
    """
    Check if a row is a major TOTAL that should always be rescued.
    
    These labels are standard across N-CSR documents and are critical
    for arithmetic validation. If the model mis-cites their page, we
    should still keep them.
    
    Returns True if the row is a TOTAL with a major label.
    """
    row_type = unwrap_value(row.get("row_type"))
    if row_type != "TOTAL":
        return False
    
    label = unwrap_value(row.get("label")) or ""
    label_lower = label.lower().strip()
    
    for pattern in MAJOR_TOTAL_PATTERNS:
        if pattern in label_lower:
            return True
    
    return False


def filter_rows_by_page(
    rows: List[Dict[str, Any]],
    soi_pages: set,
    result: NormalizationResult,
) -> List[Dict[str, Any]]:
    """
    Filter out rows that come from pages NOT in the SOI split.
    
    This is the CRITICAL defense against "Top Holdings" and other non-SOI tables
    contaminating the extraction. Rows from pages like Page 1 (Highlights section)
    are dropped deterministically.
    
    MULTI-HEURISTIC RESCUE SYSTEM:
    Before dropping a row, we check three rescue conditions:
    
    1. Volume Rescue: If a "bad" page has >20 rows, it's likely the main SOI
       (model hallucinated page numbers), not a Summary table. Rescue all rows.
    
    2. Detail Rescue: If a row has bond-level detail (interest rate, maturity date,
       date/rate patterns in investment name), it's from the real SOI. Rescue it.
    
    3. Major Total Rescue: If a TOTAL row has a major label (e.g., "TOTAL INVESTMENTS",
       "NET ASSETS"), rescue it - these are critical for validation.
    
    Args:
        rows: List of row dicts
        soi_pages: Set of valid SOI page numbers from the split step
        result: NormalizationResult to update with fix logs
    
    Returns:
        List of rows that come from valid SOI pages only (or rescued rows)
    """
    if not soi_pages:
        # No page constraints - return all rows
        return rows
    
    # STEP 1: Compute Volume Rescue pages
    # Pages with many rows are likely the main SOI, not Summary tables
    rescue_pages = get_rescue_pages(rows, soi_pages, threshold=VOLUME_RESCUE_THRESHOLD)
    
    filtered_rows = []
    for idx, row in enumerate(rows):
        original_page = _get_row_original_page(row)
        
        if original_page is not None and original_page not in soi_pages:
            # Row is from a non-SOI page. Check rescue heuristics in priority order.
            row_type = unwrap_value(row.get("row_type")) or "UNKNOWN"
            rescue_reason: Optional[str] = None
            
            # Heuristic 1: Volume Rescue
            if original_page in rescue_pages:
                rescue_reason = "RESCUED_BY_VOLUME"
            
            # Heuristic 2: Detail Rescue (for HOLDINGs with bond-level detail)
            elif row_type == "HOLDING" and is_high_confidence_holding(row):
                rescue_reason = "RESCUED_BY_DETAIL"
            
            # Heuristic 3: Major Total Rescue
            elif is_major_total_row(row):
                rescue_reason = "RESCUED_BY_MAJOR_TOTAL"
            
            if rescue_reason:
                # KEEP the row and log the rescue
                result.fix_log.append(FixLogEntry(
                    row_idx=idx,
                    old_row_type=row_type,
                    new_row_type=row_type,
                    action="converted",  # Treated as 'fixed'/kept
                    reason_code=rescue_reason,
                    confidence="high",
                    row_signature=get_row_signature(row),
                    old_value=f"page={original_page}",
                    new_value=f"rescued (page not in {sorted(soi_pages)})",
                ))
                result.fix_count += 1
                result.converted_count += 1
                filtered_rows.append(row)
            else:
                # DROP the row - confirmed Summary/Highlights contamination
                result.fix_log.append(FixLogEntry(
                    row_idx=idx,
                    old_row_type=row_type,
                    new_row_type=None,
                    action="dropped",
                    reason_code="ROW_FROM_NON_SOI_PAGE",
                    confidence="high",
                    row_signature=get_row_signature(row),
                    old_value=f"page={original_page}",
                    new_value=f"valid_pages={sorted(soi_pages)}",
                ))
                result.dropped_count += 1
                result.fix_count += 1
        else:
            # Row is from a valid SOI page (or page unknown) - KEEP IT
            filtered_rows.append(row)
    
    return filtered_rows


# ---------------------------------------------------------------------------
# Content-based summary table detection
# ---------------------------------------------------------------------------

# Threshold: TOTAL rows with percent < this value indicate a "Top Holdings" table
SUMMARY_TABLE_PERCENT_THRESHOLD = Decimal("80")

# Maximum row count for a section to be considered a "summary table"
SUMMARY_TABLE_MAX_ROWS = 20


def _is_summary_total_row(row: Dict[str, Any]) -> bool:
    """
    Check if a TOTAL row indicates this is a summary/highlights table.
    
    Summary tables (like "Top Holdings") typically have:
    - A TOTAL row with percent_net_assets_raw < 80% (e.g., "Top 10 Holdings: 35.2%")
    - Few holdings (5-20)
    
    Returns True if the row is a TOTAL with a suspiciously low percentage.
    """
    row_type = unwrap_value(row.get("row_type"))
    if row_type != "TOTAL":
        return False
    
    pct_raw = unwrap_value(row.get("percent_net_assets_raw"))
    if not pct_raw:
        return False
    
    pct = parse_decimal_simple(pct_raw)
    if pct is None:
        return False
    
    # If the total is < 80% of net assets, this is likely a summary table
    # Real SOI totals are typically 90-160%
    return pct < SUMMARY_TABLE_PERCENT_THRESHOLD


def _group_rows_by_block(
    rows: List[Dict[str, Any]],
) -> List[Tuple[int, int, List[Dict[str, Any]]]]:
    """
    Group rows into "blocks" based on TOTAL row boundaries.
    
    A block is a sequence of rows ending with a TOTAL row. This helps identify
    isolated summary tables that have their own Total row.
    
    Returns:
        List of (start_idx, end_idx, rows_in_block) tuples
    """
    blocks: List[Tuple[int, int, List[Dict[str, Any]]]] = []
    current_block: List[Dict[str, Any]] = []
    block_start = 0
    
    for idx, row in enumerate(rows):
        current_block.append(row)
        row_type = unwrap_value(row.get("row_type"))
        
        if row_type == "TOTAL":
            # End of block
            blocks.append((block_start, idx, current_block))
            current_block = []
            block_start = idx + 1
    
    # Handle remaining rows without a TOTAL
    if current_block:
        blocks.append((block_start, len(rows) - 1, current_block))
    
    return blocks


def drop_summary_tables(
    rows: List[Dict[str, Any]],
    result: NormalizationResult,
) -> List[Dict[str, Any]]:
    """
    Detect and drop entire "summary table" blocks based on content analysis.
    
    A summary table (e.g., "Top 10 Holdings", "Largest Investments") is identified by:
    1. Having a TOTAL row with percent_net_assets_raw < 80%
    2. Having fewer than SUMMARY_TABLE_MAX_ROWS holdings in the block
    
    This is a content-based defense that catches summary tables even if they're
    on pages included in the SOI split (via gap-filling or splitter error).
    
    Args:
        rows: List of row dicts
        result: NormalizationResult to update with fix logs
    
    Returns:
        List of rows with summary table blocks removed
    """
    blocks = _group_rows_by_block(rows)
    
    # Identify blocks to drop
    indices_to_drop: set = set()
    
    for block_start, block_end, block_rows in blocks:
        # Count holdings in this block
        holding_count = sum(
            1 for r in block_rows 
            if unwrap_value(r.get("row_type")) == "HOLDING"
        )
        
        # Check if any TOTAL in this block indicates a summary table
        has_summary_total = any(_is_summary_total_row(r) for r in block_rows)
        
        if has_summary_total and holding_count < SUMMARY_TABLE_MAX_ROWS:
            # This block is a summary table - mark all rows for dropping
            for idx in range(block_start, block_end + 1):
                indices_to_drop.add(idx)
    
    if not indices_to_drop:
        return rows
    
    # Drop the identified rows
    cleaned_rows = []
    for idx, row in enumerate(rows):
        if idx in indices_to_drop:
            row_type = unwrap_value(row.get("row_type")) or "UNKNOWN"
            result.fix_log.append(FixLogEntry(
                row_idx=idx,
                old_row_type=row_type,
                new_row_type=None,
                action="dropped",
                reason_code="SUMMARY_TABLE_BLOCK_DETECTED",
                confidence="high",
                row_signature=get_row_signature(row),
            ))
            result.dropped_count += 1
            result.fix_count += 1
        else:
            cleaned_rows.append(row)
    
    return cleaned_rows


def fix_short_position_signs(
    rows: List[Dict[str, Any]],
    result: NormalizationResult,
) -> List[Dict[str, Any]]:
    """
    Convert positive fair values to negative for SHORT POSITION holdings.
    
    Some documents display short positions (written options, securities sold short)
    as positive "market value" but they are liabilities that should be subtracted
    from total investments. This function detects such rows and converts their
    fair_value_raw to negative.
    
    Args:
        rows: List of row dicts
        result: NormalizationResult to update with fix logs
    
    Returns:
        List of rows with short position signs corrected
    """
    corrected_rows = []
    
    for idx, row in enumerate(rows):
        row_type = unwrap_value(row.get("row_type"))
        if row_type not in ("HOLDING", "SUBTOTAL", "TOTAL"):
            corrected_rows.append(row)
            continue
        
        # Check section_path and label for short position indicators
        section_path = normalize_section_path(row.get("section_path"))
        label = (unwrap_value(row.get("label")) or "").lower()
        investment = (unwrap_value(row.get("investment")) or "").lower()
        path_str = " ".join(section_path).lower()
        
        # Check if this row is in a short position section
        is_short_position = any(
            kw in path_str or kw in label or kw in investment 
            for kw in SHORT_POSITION_KEYWORDS
        )
        
        if not is_short_position:
            corrected_rows.append(row)
            continue
        
        # Get fair_value
        fv_raw = unwrap_value(row.get("fair_value_raw"))
        if not fv_raw:
            corrected_rows.append(row)
            continue
        
        fv = parse_decimal_simple(fv_raw)
        if fv is None or fv <= 0:
            # Already negative or zero - no fix needed
            corrected_rows.append(row)
            continue
        
        # Positive fair_value in a short position section - convert to negative
        row_copy = copy.deepcopy(row)
        
        # Preserve the original format but make it negative
        # Handle cases like "2,500" -> "-2,500" or "$2,500" -> "-$2,500"
        fv_str = str(fv_raw).strip()
        if fv_str.startswith("$"):
            new_value = f"-${fv_str[1:]}"
        else:
            new_value = f"-{fv_str}"
        
        set_wrapped_value(row_copy, "fair_value_raw", new_value)
        corrected_rows.append(row_copy)
        
        result.fix_log.append(FixLogEntry(
            row_idx=idx,
            old_row_type=row_type,
            new_row_type=row_type,
            action="converted",
            reason_code="SHORT_POSITION_SIGN_CORRECTED",
            confidence="high",
            row_signature=get_row_signature(row),
            old_value=fv_raw,
            new_value=new_value,
        ))
        result.fix_count += 1
        result.converted_count += 1
    
    return corrected_rows


def normalize_soi_rows(
    soi_rows: List[Dict[str, Any]],
    *,
    soi_pages: Optional[set] = None,
    convert_to_subtotal: bool = True,
    drop_unfixable: bool = True,
) -> Tuple[List[Dict[str, Any]], NormalizationResult]:
    """
    Normalize SOI rows by detecting and fixing misclassified rows.
    
    Args:
        soi_rows: List of row dicts from Reducto extraction
        soi_pages: Optional set of valid SOI page numbers. If provided, rows from
                   pages NOT in this set will be dropped. This is the primary defense
                   against "Top Holdings" contamination from non-SOI pages.
        convert_to_subtotal: If True, convert phantom holdings to SUBTOTAL when possible
        drop_unfixable: If True, drop rows that can't be safely converted
    
    Returns:
        (normalized_rows, result) where result contains fix log and statistics
    """
    result = NormalizationResult(rows=[])
    
    # FIRST: Apply page-based filtering to remove rows from non-SOI pages
    # This is the critical defense against "Top Holdings" and other non-SOI tables
    # contaminating the extraction. Must happen BEFORE any other processing.
    if soi_pages:
        soi_rows = filter_rows_by_page(soi_rows, soi_pages, result)
    
    # SECOND: Apply content-based summary table detection
    # This catches "Top Holdings" tables that slip through the page filter
    # (e.g., from gap-filled pages or splitter errors)
    soi_rows = drop_summary_tables(soi_rows, result)
    
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
        
        # Check for liability/contra-entry rows that should be excluded from totals
        # These are rows like "Preferred Stock, at redemption value" with negative values
        # that cause arithmetic validation failures when summed with regular holdings
        if should_exclude_from_totals(row):
            investment = unwrap_value(row.get("investment")) or ""
            fv_raw = unwrap_value(row.get("fair_value_raw")) or ""
            
            # Convert to SUBTOTAL with special marker to exclude from arithmetic
            # This preserves the row in the output while preventing validation errors
            fixed_row = copy.deepcopy(row)
            set_wrapped_value(fixed_row, "row_type", "SUBTOTAL")
            set_wrapped_value(fixed_row, "label", investment)
            set_wrapped_value(fixed_row, "investment", None)
            # Add marker to indicate this is a contra-entry
            fixed_row["_exclude_from_arithmetic"] = True
            
            result.rows.append(fixed_row)
            result.fix_log.append(FixLogEntry(
                row_idx=idx,
                old_row_type="HOLDING",
                new_row_type="SUBTOTAL",
                action="converted",
                reason_code="LIABILITY_CONTRA_ENTRY_DETECTED",
                confidence="high",
                row_signature=get_row_signature(row),
                old_value=f"investment='{investment}', fv='{fv_raw}'",
                new_value="Converted to SUBTOTAL, excluded from arithmetic",
            ))
            result.converted_count += 1
            result.fix_count += 1
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
    
    # CRITICAL: Infer missing fund names for multi-fund documents
    # This fixes the pattern where holdings have strategy categories at root level
    # instead of proper fund names (e.g., ['EVENT DRIVEN'] instead of ['FCT', 'EVENT DRIVEN'])
    result.rows = infer_missing_fund_names(result.rows, result)
    
    # Remove duplicate holdings (same investment + value but different section paths)
    result.rows = remove_duplicate_holdings(result.rows, result)
    
    # CRITICAL: Fix short position signs
    # Some documents display short positions (written options, sold short) as positive
    # market values, but they're liabilities that should be negative for correct arithmetic
    result.rows = fix_short_position_signs(result.rows, result)
    
    # Validate per-fund arithmetic (adds warnings for multi-fund documents)
    result.rows = validate_per_fund_arithmetic(result.rows, result)
    
    return result.rows, result


# ---------------------------------------------------------------------------
# Multi-fund inference: Detect and fix missing fund names in section_path
# ---------------------------------------------------------------------------

# Known strategy categories that should NOT be at root level in multi-fund docs
STRATEGY_CATEGORIES = frozenset({
    "event driven",
    "fixed income arbitrage",
    "equity arbitrage",
    "credit strategies",
    "long/short equity",
    "multi-strategy",
    "convertible arbitrage",
    "distressed/restructuring",
    "merger arbitrage",
    "global macro",
    "statistical arbitrage",
    "relative value",
    "capital structure arbitrage",
    "volatility arbitrage",
    "macro",
    "special situations",
})


def _is_strategy_category(name: str) -> bool:
    """Check if a name is a known strategy category (not a fund name)."""
    if not name:
        return False
    return name.lower().strip() in STRATEGY_CATEGORIES


def _extract_fund_name_from_total(row: Dict[str, Any]) -> Optional[str]:
    """
    Try to extract a fund name from a TOTAL row's label or section_path.
    
    TOTAL rows often contain fund-identifying information like:
    - "MEMBERS' CAPITAL - FCT"
    - "TOTAL INVESTMENTS - Multi-Strategy Series M"
    - section_path = ['Multi-Strategy Series M']
    """
    label = unwrap_value(row.get("label")) or ""
    section_path = normalize_section_path(row.get("section_path"))
    
    # Check section_path first - if it has a fund name, use it
    if section_path:
        first_elem = section_path[0]
        if not _is_strategy_category(first_elem):
            return first_elem
    
    # Try to extract from label patterns
    label_lower = label.lower()
    
    # Pattern: "MEMBERS' CAPITAL - FCT" -> "FCT"
    if " - " in label:
        parts = label.split(" - ")
        for part in parts:
            part = part.strip()
            # Skip generic parts
            if part.lower() in ("total investments", "members' capital", "net assets"):
                continue
            if len(part) > 2 and not _is_strategy_category(part):
                return part
    
    # Pattern: "TOTAL INVESTMENTS (Fund Name)" -> "Fund Name"
    paren_match = re.search(r"\(([^)]+)\)", label)
    if paren_match:
        potential_fund = paren_match.group(1).strip()
        if not _is_strategy_category(potential_fund) and len(potential_fund) > 2:
            return potential_fund
    
    return None


def detect_multi_fund_mislabeling(
    rows: List[Dict[str, Any]]
) -> Tuple[bool, Dict[str, str], List[int]]:
    """
    Detect when holdings have strategy categories at root level instead of fund names.
    
    Pattern detection:
    1. Some holdings have section_path = ["STRATEGY_NAME"] (no fund)
    2. Other holdings have section_path = ["FUND_NAME", "STRATEGY_NAME"]
    3. Both use the SAME strategy names (EVENT DRIVEN, EQUITY ARBITRAGE, etc.)
    
    Returns:
        (is_multi_fund_mislabeled, fund_name_mapping, affected_row_indices)
        
        - is_multi_fund_mislabeled: True if we detected the mislabeling pattern
        - fund_name_mapping: Dict mapping strategy names to inferred fund names
        - affected_row_indices: List of row indices that need fund name prepended
    """
    # Collect section_path patterns
    root_strategies: Dict[str, List[int]] = {}  # strategy -> [row_indices]
    nested_strategies: Dict[str, List[Tuple[str, int]]] = {}  # strategy -> [(fund_name, row_idx)]
    total_rows: List[Dict[str, Any]] = []
    
    for idx, row in enumerate(rows):
        row_type = unwrap_value(row.get("row_type"))
        section_path = normalize_section_path(row.get("section_path"))
        
        if row_type == "TOTAL":
            total_rows.append(row)
            continue
        
        if not section_path:
            continue
        
        first_elem = section_path[0].upper()
        
        if len(section_path) == 1:
            # Root-level category
            if _is_strategy_category(first_elem.lower()):
                if first_elem not in root_strategies:
                    root_strategies[first_elem] = []
                root_strategies[first_elem].append(idx)
        elif len(section_path) >= 2:
            # Nested category - first element might be fund name
            second_elem = section_path[1].upper() if len(section_path) > 1 else ""
            if _is_strategy_category(second_elem.lower()):
                # First element is likely a fund name
                fund_name = section_path[0]
                if second_elem not in nested_strategies:
                    nested_strategies[second_elem] = []
                nested_strategies[second_elem].append((fund_name, idx))
    
    # Check if we have the mislabeling pattern:
    # Same strategy names appearing both at root and nested under fund names
    is_mislabeled = False
    fund_name_mapping: Dict[str, str] = {}
    affected_indices: List[int] = []
    
    # Find strategies that appear both at root and nested
    common_strategies = set(root_strategies.keys()) & set(nested_strategies.keys())
    
    if common_strategies and root_strategies:
        # We have the pattern! Try to infer the fund name for root-level holdings
        is_mislabeled = True
        
        # Try to get fund name from TOTAL rows
        inferred_fund_name: Optional[str] = None
        for total_row in total_rows:
            fund_name = _extract_fund_name_from_total(total_row)
            if fund_name:
                # Check if this fund name is NOT already used in nested strategies
                used_fund_names = set()
                for strategy, entries in nested_strategies.items():
                    for fn, _ in entries:
                        used_fund_names.add(fn.upper())
                
                if fund_name.upper() not in used_fund_names:
                    inferred_fund_name = fund_name
                    break
        
        # If we couldn't infer from TOTAL rows, use a generic name
        if not inferred_fund_name:
            # Look at what fund names are already used
            existing_funds = set()
            for strategy, entries in nested_strategies.items():
                for fn, _ in entries:
                    existing_funds.add(fn)
            
            # If there's only one other fund, the root-level holdings belong to "Fund 1"
            if len(existing_funds) == 1:
                inferred_fund_name = "Fund 1"
            else:
                inferred_fund_name = "Unnamed Fund"
        
        # Build the mapping
        for strategy in root_strategies:
            fund_name_mapping[strategy] = inferred_fund_name
            affected_indices.extend(root_strategies[strategy])
    
    return is_mislabeled, fund_name_mapping, affected_indices


def infer_missing_fund_names(
    rows: List[Dict[str, Any]],
    result: NormalizationResult,
) -> List[Dict[str, Any]]:
    """
    Detect and fix holdings that have strategy categories at root level instead of fund names.
    
    In multi-fund documents, holdings should have section_path = [FUND_NAME, STRATEGY, ...].
    If the extraction model failed to include the fund name, this function:
    1. Detects the pattern (same strategies at different depths)
    2. Infers the missing fund name from TOTAL rows or document context
    3. Prepends the fund name to affected section_paths
    
    This is a FALLBACK fix for when the extraction prompt improvements don't work.
    
    Args:
        rows: List of row dicts
        result: NormalizationResult to update with fix logs
    
    Returns:
        List of rows with corrected section_paths
    """
    is_mislabeled, fund_mapping, affected_indices = detect_multi_fund_mislabeling(rows)
    
    if not is_mislabeled or not affected_indices:
        return rows
    
    affected_set = set(affected_indices)
    corrected_rows = []
    
    for idx, row in enumerate(rows):
        if idx not in affected_set:
            corrected_rows.append(row)
            continue
        
        # Get the current section_path
        section_path = normalize_section_path(row.get("section_path"))
        if not section_path:
            corrected_rows.append(row)
            continue
        
        first_elem = section_path[0].upper()
        inferred_fund = fund_mapping.get(first_elem)
        
        if not inferred_fund:
            corrected_rows.append(row)
            continue
        
        # Create corrected row with fund name prepended
        row_copy = copy.deepcopy(row)
        
        # Build new section_path with fund name first
        old_path = row.get("section_path", [])
        if isinstance(old_path, list):
            new_section_path = []
            # Add the inferred fund name as first element
            if old_path and isinstance(old_path[0], dict):
                # Preserve wrapped format
                fund_elem = copy.deepcopy(old_path[0])
                fund_elem["value"] = inferred_fund
                new_section_path.append(fund_elem)
            else:
                new_section_path.append({"value": inferred_fund, "citations": []})
            
            # Add original path elements
            for elem in old_path:
                new_section_path.append(copy.deepcopy(elem) if isinstance(elem, dict) else {"value": elem, "citations": []})
            
            row_copy["section_path"] = new_section_path
        
        corrected_rows.append(row_copy)
        
        # Log the fix
        row_type = unwrap_value(row.get("row_type")) or "UNKNOWN"
        result.fix_log.append(FixLogEntry(
            row_idx=idx,
            old_row_type=row_type,
            new_row_type=row_type,
            action="converted",
            reason_code="FUND_NAME_INFERRED",
            confidence="medium",
            row_signature=get_row_signature(row),
            old_value=" > ".join(section_path),
            new_value=f"{inferred_fund} > " + " > ".join(section_path),
        ))
        result.converted_count += 1
        result.fix_count += 1
    
    return corrected_rows


def detect_duplicate_holdings(rows: List[Dict[str, Any]]) -> List[int]:
    """
    Detect holdings that appear twice with different section_paths.
    
    Pattern: Same (investment_name, fair_value) but different section_paths.
    This indicates cross-fund contamination in multi-fund documents where
    the extraction model assigned the same holding to multiple funds.
    
    Returns indices of duplicate rows to remove (keep the first occurrence).
    """
    seen: Dict[Tuple[str, str], int] = {}  # (name, value) -> first_index
    duplicates: List[int] = []
    
    for idx, row in enumerate(rows):
        if unwrap_value(row.get("row_type")) != "HOLDING":
            continue
        
        inv = normalize_text(unwrap_value(row.get("investment")) or "")
        fv = unwrap_value(row.get("fair_value_raw")) or ""
        
        # Skip if no meaningful investment name or value
        if not inv or len(inv) < 5:
            continue
        if not fv:
            continue
        
        key = (inv, fv)
        if key in seen:
            # This is a duplicate - same holding appears twice
            duplicates.append(idx)
        else:
            seen[key] = idx
    
    return duplicates


def detect_cross_fund_duplicates(rows: List[Dict[str, Any]]) -> List[Tuple[int, str, str]]:
    """
    Detect when the same holding appears under multiple fund names.
    
    This is a more specific form of duplicate detection that catches cross-fund
    contamination where the same holding is extracted with different fund prefixes
    in section_path.
    
    Pattern: Same (investment_name, fair_value) but different FUND names
    (first element of section_path).
    
    Returns:
        List of (row_idx, fund_name, reason) tuples for rows to flag
    """
    # Group holdings by (investment, fair_value)
    holding_groups: Dict[Tuple[str, str], List[Tuple[int, Tuple[str, ...]]]] = {}
    
    for idx, row in enumerate(rows):
        if unwrap_value(row.get("row_type")) != "HOLDING":
            continue
        
        inv = normalize_text(unwrap_value(row.get("investment")) or "")
        fv = unwrap_value(row.get("fair_value_raw")) or ""
        section_path = normalize_section_path(row.get("section_path"))
        
        # Skip if no meaningful investment name or value
        if not inv or len(inv) < 5:
            continue
        if not fv:
            continue
        
        key = (inv, fv)
        if key not in holding_groups:
            holding_groups[key] = []
        holding_groups[key].append((idx, section_path))
    
    # Find groups with multiple fund names
    cross_fund_issues: List[Tuple[int, str, str]] = []
    
    for (inv, fv), occurrences in holding_groups.items():
        if len(occurrences) < 2:
            continue
        
        # Extract fund names (first element of section_path)
        fund_names: Dict[str, List[int]] = {}
        for idx, path in occurrences:
            fund_name = path[0] if path else "(root)"
            if fund_name not in fund_names:
                fund_names[fund_name] = []
            fund_names[fund_name].append(idx)
        
        # If same holding appears under different fund names, flag it
        if len(fund_names) > 1:
            # Keep the first occurrence, flag the rest
            first_fund = list(fund_names.keys())[0]
            for fund_name, indices in fund_names.items():
                if fund_name != first_fund:
                    for idx in indices:
                        cross_fund_issues.append((
                            idx,
                            fund_name,
                            f"Holding '{inv[:40]}' (${fv}) appears under multiple funds: {list(fund_names.keys())}"
                        ))
    
    return cross_fund_issues


def validate_per_fund_arithmetic(
    rows: List[Dict[str, Any]],
    result: NormalizationResult,
) -> List[Dict[str, Any]]:
    """
    Validate that each fund's holdings sum to that fund's TOTAL row.
    
    This is a pre-validation check that can add warnings to the result
    when fund-level arithmetic doesn't match.
    
    For multi-fund documents, this helps identify:
    - Partial extraction (missing holdings for a fund)
    - Over-extraction (duplicate holdings or cross-fund contamination)
    - Misattributed holdings (wrong fund in section_path)
    
    Args:
        rows: List of row dicts
        result: NormalizationResult to update with warnings
    
    Returns:
        The same list of rows (no modifications, just validation)
    """
    # Group rows by fund name (first element of section_path)
    fund_holdings: Dict[str, List[Dict[str, Any]]] = {}
    fund_totals: Dict[str, Dict[str, Any]] = {}
    
    for row in rows:
        row_type = unwrap_value(row.get("row_type"))
        section_path = normalize_section_path(row.get("section_path"))
        
        # Get fund name (first element of section_path, or "(root)" if empty)
        fund_name = section_path[0] if section_path else "(root)"
        
        if row_type == "HOLDING":
            if fund_name not in fund_holdings:
                fund_holdings[fund_name] = []
            fund_holdings[fund_name].append(row)
        elif row_type == "TOTAL":
            # Only track TOTAL rows at fund level (section_path length <= 1)
            if len(section_path) <= 1:
                fund_totals[fund_name] = row
    
    # Check if this is a multi-fund document
    if len(fund_holdings) < 2:
        return rows  # Single fund or no fund structure
    
    # Validate each fund's arithmetic
    for fund_name, holdings in fund_holdings.items():
        if fund_name not in fund_totals:
            continue  # No TOTAL row for this fund
        
        total_row = fund_totals[fund_name]
        
        # Calculate sum of holdings
        holdings_sum = Decimal("0")
        for holding in holdings:
            fv_raw = unwrap_value(holding.get("fair_value_raw"))
            if fv_raw:
                fv = parse_decimal_simple(fv_raw)
                if fv is not None:
                    holdings_sum += fv
        
        # Get extracted total
        ext_fv_raw = unwrap_value(total_row.get("fair_value_raw"))
        ext_fv = parse_decimal_simple(ext_fv_raw) if ext_fv_raw else None
        
        if ext_fv is not None and ext_fv > 0:
            extraction_ratio = float(holdings_sum) / float(ext_fv)
            
            if extraction_ratio < 0.5:
                # Severe under-extraction
                result.fix_log.append(FixLogEntry(
                    row_idx=-1,  # Not a specific row
                    old_row_type="FUND_VALIDATION",
                    new_row_type="FUND_VALIDATION",
                    action="converted",  # Using "converted" to indicate a warning was added
                    reason_code="FUND_PARTIAL_EXTRACTION_WARNING",
                    confidence="high",
                    row_signature=f"Fund: {fund_name}",
                    old_value=f"calculated=${holdings_sum}",
                    new_value=f"expected=${ext_fv}, ratio={extraction_ratio:.1%}",
                ))
            elif extraction_ratio > 1.5:
                # Over-extraction (likely cross-fund contamination)
                result.fix_log.append(FixLogEntry(
                    row_idx=-1,
                    old_row_type="FUND_VALIDATION",
                    new_row_type="FUND_VALIDATION",
                    action="converted",
                    reason_code="FUND_OVER_EXTRACTION_WARNING",
                    confidence="high",
                    row_signature=f"Fund: {fund_name}",
                    old_value=f"calculated=${holdings_sum}",
                    new_value=f"expected=${ext_fv}, ratio={extraction_ratio:.1%}",
                ))
    
    return rows


def remove_duplicate_holdings(
    rows: List[Dict[str, Any]],
    result: NormalizationResult,
) -> List[Dict[str, Any]]:
    """
    Remove HOLDING rows that are duplicates (same investment + fair_value).
    
    This fixes multi-fund contamination where the same holding is extracted
    twice with different section_paths (e.g., once under root and once under
    a specific fund name).
    
    Keeps the first occurrence and removes subsequent duplicates.
    
    Args:
        rows: List of row dicts
        result: NormalizationResult to update with fix logs
    
    Returns:
        List of rows with duplicates removed
    """
    duplicates = set(detect_duplicate_holdings(rows))
    
    if not duplicates:
        return rows
    
    cleaned_rows = []
    for idx, row in enumerate(rows):
        if idx in duplicates:
            inv = unwrap_value(row.get("investment")) or ""
            fv = unwrap_value(row.get("fair_value_raw")) or ""
            section_path = normalize_section_path(row.get("section_path"))
            
            result.fix_log.append(FixLogEntry(
                row_idx=idx,
                old_row_type="HOLDING",
                new_row_type=None,
                action="dropped",
                reason_code="DUPLICATE_HOLDING_DETECTED",
                confidence="high",
                row_signature=get_row_signature(row),
                old_value=f"inv='{inv[:40]}', fv='{fv}'",
                new_value=f"section_path='{' > '.join(section_path)}'",
            ))
            result.dropped_count += 1
            result.fix_count += 1
        else:
            cleaned_rows.append(row)
    
    return cleaned_rows


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

