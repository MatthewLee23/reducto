"""
Deterministic validation for Reducto extract response JSON files.

Validates:
1) File + response shape (required fields, types)
2) Citation integrity (bbox bounds, value↔content consistency)
3) Row-level invariants (row_type, section_path, coherence)
4) Numeric parseability + arithmetic (holdings→subtotals→totals)
5) Metadata consistency (as_of_date vs filename)
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants / tolerances (tight)
# ---------------------------------------------------------------------------
DOLLAR_TOLERANCE = Decimal("1")
PERCENT_TOLERANCE = Decimal("0.01")

VALID_ROW_TYPES = {"HOLDING", "SUBTOTAL", "TOTAL"}

# Regex for extracting digits (for citation/value consistency)
DIGIT_PATTERN = re.compile(r"\d+")

# Regex for parsing numeric strings (including European-style thousands dots)
NUMBER_PATTERN = re.compile(r"-?\d[\d.,]*")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    """Represents a single validation issue."""
    severity: str  # "error" | "warning"
    code: str  # e.g., "MISSING_FIELD", "ARITH_MISMATCH"
    message: str
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    """Result of validating one extract response JSON."""
    source_name: str
    total_rows: int = 0
    holding_count: int = 0
    subtotal_count: int = 0
    total_count: int = 0
    issues: List[Issue] = field(default_factory=list)
    computed_sums: Dict[str, Any] = field(default_factory=dict)
    # New fields for enhanced reporting
    has_arithmetic_error: bool = False
    max_dollar_diff: Decimal = field(default_factory=lambda: Decimal("0"))
    root_sum_mismatch: bool = False
    calculated_total_fv: Optional[Decimal] = None
    extracted_total_fv: Optional[Decimal] = None
    # Normalization metadata (set by caller after sanitizing rows)
    normalization: Optional[Dict[str, Any]] = None

    def add(self, severity: str, code: str, message: str, **context: Any) -> None:
        self.issues.append(Issue(severity=severity, code=code, message=message, context=context))

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def top_error_code(self) -> Optional[str]:
        """Return the most frequent error code, or None if no errors."""
        from collections import Counter
        error_codes = [i.code for i in self.issues if i.severity == "error"]
        if not error_codes:
            return None
        return Counter(error_codes).most_common(1)[0][0]

    def to_dict(self) -> Dict[str, Any]:
        # Sort issues with arithmetic errors at the top for easy diagnosis
        sorted_issues = self._sort_issues_for_display()
        
        result = {
            "source_name": self.source_name,
            "total_rows": self.total_rows,
            "holding_count": self.holding_count,
            "subtotal_count": self.subtotal_count,
            "total_count": self.total_count,
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "has_arithmetic_error": self.has_arithmetic_error,
            "max_dollar_diff": str(self.max_dollar_diff),
            "root_sum_mismatch": self.root_sum_mismatch,
            "calculated_total_fv": str(self.calculated_total_fv) if self.calculated_total_fv is not None else None,
            "extracted_total_fv": str(self.extracted_total_fv) if self.extracted_total_fv is not None else None,
            "computed_sums": self.computed_sums,
            "issues": [i.to_dict() for i in sorted_issues],
        }
        # Include normalization metadata if present
        if self.normalization:
            result["normalization"] = self.normalization
        return result

    def _sort_issues_for_display(self) -> List[Issue]:
        """
        Sort issues so arithmetic errors appear at the top, ordered by dollar diff descending.
        
        Priority order:
        1. Arithmetic errors (MISMATCH codes) - sorted by diff amount descending
        2. Other errors - sorted by code
        3. Warnings - sorted by code
        """
        # Define arithmetic error codes (where numbers don't add up)
        ARITHMETIC_ERROR_CODES = {
            "ROOT_TOTAL_MISMATCH_FV",
            "ROOT_TOTAL_MISMATCH_COST", 
            "ROOT_TOTAL_MISMATCH_PCT",
            "TOTAL_MISMATCH_FV",
            "TOTAL_MISMATCH_COST",
            "TOTAL_MISMATCH_PCT",
            "GRAND_TOTAL_MISMATCH_FV",
            "GRAND_TOTAL_MISMATCH_COST",
            "GRAND_TOTAL_MISMATCH_PCT",
            "ARITH_MISMATCH_FV",
            "ARITH_MISMATCH_COST",
            "ARITH_MISMATCH_PCT",
            "SHIFTED_SUBTOTAL_DETECTED",
        }
        
        def get_diff_value(issue: Issue) -> Decimal:
            """Extract the diff value from issue context for sorting."""
            ctx = issue.context or {}
            diff_str = ctx.get("diff", "0")
            try:
                return Decimal(str(diff_str).replace(",", ""))
            except (InvalidOperation, ValueError, TypeError):
                return Decimal("0")
        
        def sort_key(issue: Issue) -> tuple:
            """
            Return a tuple for sorting:
            (priority_group, -diff_value, code, message)
            
            priority_group: 0 = arithmetic errors, 1 = other errors, 2 = warnings
            """
            is_arithmetic = issue.code in ARITHMETIC_ERROR_CODES
            is_error = issue.severity == "error"
            
            if is_arithmetic:
                priority = 0
                # Negative diff so larger diffs come first
                diff = -get_diff_value(issue)
            elif is_error:
                priority = 1
                diff = Decimal("0")
            else:  # warning
                priority = 2
                diff = Decimal("0")
            
            return (priority, diff, issue.code, issue.message)
        
        return sorted(self.issues, key=sort_key)


# ---------------------------------------------------------------------------
# Helpers: unwrap {value, citations} fields
# ---------------------------------------------------------------------------


def unwrap_value(field_obj: Any) -> Optional[str]:
    """Extract the 'value' from a {value, citations} wrapper, or return string as-is."""
    if field_obj is None:
        return None
    if isinstance(field_obj, dict):
        v = field_obj.get("value")
        return str(v) if v is not None else None
    return str(field_obj)


def unwrap_citations(field_obj: Any) -> List[Dict[str, Any]]:
    """Extract citations list from a {value, citations} wrapper."""
    if isinstance(field_obj, dict):
        cits = field_obj.get("citations")
        if isinstance(cits, list):
            return cits
    return []


# ---------------------------------------------------------------------------
# Helpers: Decimal parsing
# ---------------------------------------------------------------------------


def parse_decimal(raw: Any, field_name: Optional[str] = None) -> Tuple[Optional[Decimal], Optional[str]]:
    """
    Parse a raw amount/percent string into Decimal.

    Returns (value, error_message).
    Handles:
      - Currency symbols ($, S, €, CAD, etc.)
      - Commas as thousands separators
      - Parentheses for negatives
      - SEPARATOR DASHES: Dashes followed by whitespace are layout separators, not negative signs
      - Multiple numeric tokens → error
      
    Args:
        raw: The raw value to parse
        field_name: Optional field name for contextual validation warnings
    """
    if raw is None:
        return None, None

    if isinstance(raw, (int, float, Decimal)):
        try:
            return Decimal(str(raw)), None
        except InvalidOperation:
            return None, f"Cannot convert {raw!r} to Decimal"

    value_str = str(raw).strip()
    if not value_str:
        return None, None

    # SEPARATOR DASH DETECTION (CRITICAL):
    # Financial documents use "Category -- 1.8%" or "Category - 5.2%" format.
    # A dash followed by whitespace and then a number is a SEPARATOR, not a negative sign.
    # Pattern: look for "- " or "-- " followed by digits (separator dash)
    # vs "-1.8" with no space (actual negative)
    separator_dash_pattern = re.compile(r"[-–—]+\s+(\d)")
    has_separator_dash = bool(separator_dash_pattern.search(value_str))
    
    # If we detect a separator dash pattern, strip everything before the numeric portion
    if has_separator_dash:
        # Find where the actual number starts (after the separator dash and whitespace)
        match = separator_dash_pattern.search(value_str)
        if match:
            # Get the position where the digit starts
            digit_start = match.start(1)
            # Keep only from the digit onwards (preserving any trailing % or currency)
            value_str = value_str[digit_start - 0:] if digit_start > 0 else value_str
            # Re-strip to clean up
            value_str = value_str.strip()

    # Remove currency symbols and whitespace FIRST (before checking for parentheses)
    cleaned = (
        value_str
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("¥", "")
        .replace(" ", "")
        .replace("\u00a0", "")
        .replace("\t", "")
    )
    # Remove common currency codes
    for code in ("USD", "CAD", "EUR", "GBP", "JPY", "S"):
        cleaned = cleaned.replace(code, "")
    # Remove percent sign
    cleaned = cleaned.replace("%", "")

    # Handle parentheses negatives (after currency symbols removed)
    # This correctly handles cases like "$ (31,950)" -> "(31,950)" -> negative
    # Parentheses are the CANONICAL way to indicate negatives in financial documents
    negative_by_parens = cleaned.startswith("(") and cleaned.endswith(")")
    if negative_by_parens:
        cleaned = cleaned[1:-1].strip()
    
    # Check for leading dash (potential negative, but could be extraction error)
    # A leading dash WITHOUT parentheses in a % Net Assets field is suspicious
    negative_by_dash = cleaned.startswith("-") and not negative_by_parens
    if negative_by_dash:
        cleaned = cleaned[1:].strip()

    # Find all numeric tokens
    matches = NUMBER_PATTERN.findall(cleaned)

    if not matches:
        return None, None  # no numeric content

    if len(matches) > 1:
        # Multiple numeric tokens: extraction error
        return None, f"Multiple numeric tokens in '{raw}': {matches}"

    num_str = matches[0]

    # Handle European-style thousands separators (e.g., "2.425.216" means 2,425,216)
    # Heuristic: if there are multiple dots, treat dots as thousands sep
    dot_count = num_str.count(".")
    comma_count = num_str.count(",")

    if dot_count > 1:
        # Multiple dots → dots are thousands separators
        num_str = num_str.replace(".", "")
    elif comma_count > 0 and dot_count == 1:
        # e.g., "1,234.56" → standard US format
        num_str = num_str.replace(",", "")
    elif comma_count > 0 and dot_count == 0:
        # e.g., "1,234,567" → commas are thousands
        num_str = num_str.replace(",", "")
    elif dot_count == 1 and comma_count == 0:
        # e.g., "1234.56" or "17.216" could be decimal or thousands
        # If the part after dot has 3 digits and part before is short, likely thousands
        parts = num_str.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
            # Could be European thousands like "17.216" = 17216
            # But could also be decimal... Treat as decimal by default
            pass
        # Keep as-is

    try:
        number = Decimal(num_str)
    except InvalidOperation:
        return None, f"Cannot parse '{num_str}' as Decimal (from '{raw}')"

    # Apply negative sign
    if negative_by_parens and number > 0:
        number = -number
    elif negative_by_dash and number > 0:
        # Leading dash without parentheses - apply it but it might be suspicious
        number = -number
        # For percent_net_assets fields, a leading dash is suspicious (likely separator error)
        if field_name == "percent_net_assets_raw":
            return number, f"SUSPICIOUS_NEGATIVE: '{raw}' parsed as negative but uses dash instead of parentheses - may be separator extraction error"

    return number, None


def extract_digits(s: str) -> str:
    """Extract all digit characters from a string."""
    return "".join(DIGIT_PATTERN.findall(s))


# ---------------------------------------------------------------------------
# Helpers: section_path normalization
# ---------------------------------------------------------------------------


def normalize_section_path(section_path: Any) -> Tuple[str, ...]:
    """
    Normalize a section_path (list of {value: str} or strings) to a stable tuple.
    """
    if section_path is None:
        return ()
    if not isinstance(section_path, list):
        return ()

    result = []
    for item in section_path:
        if isinstance(item, dict):
            v = item.get("value")
            if v is not None:
                result.append(str(v))
        elif isinstance(item, str):
            result.append(item)
    return tuple(result)


def _find_suspect_percent_values(rows: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """
    Find rows that have suspect percent values (ending in '8' without '%').
    
    These are likely OCR errors where '%' was misread as '8'.
    Example: '2.78' should probably be '2.7%'
    
    Works with both HOLDING rows (checks 'investment') and SUBTOTAL rows (checks 'label').
    
    Returns:
        List of (row_name, suspect_value) tuples
    """
    suspects = []
    for row in rows:
        pct = unwrap_value(row.get("percent_net_assets_raw"))
        if not pct:
            continue
        cleaned = pct.strip()
        # Check pattern: ends in 8, has decimal, no % sign
        if cleaned.endswith("8") and "." in cleaned and "%" not in cleaned:
            # Try to get a name from either investment or label
            row_name = unwrap_value(row.get("investment"))
            if not row_name:
                row_name = unwrap_value(row.get("label"))
            if not row_name:
                row_name = "Unknown"
            suspects.append((row_name[:40], cleaned))
    return suspects


# ---------------------------------------------------------------------------
# Validation: response shape
# ---------------------------------------------------------------------------


def validate_response_shape(data: Any, result: ValidationResult) -> bool:
    """
    Validate top-level structure.
    Returns False if critical structure is missing and we can't proceed.
    """
    if not isinstance(data, dict):
        result.add("error", "INVALID_JSON_STRUCTURE", "Root is not a dict")
        return False

    # Check required top-level fields
    required_fields = ["result", "usage", "job_id"]
    for f in required_fields:
        if f not in data:
            result.add("error", "MISSING_TOP_FIELD", f"Missing required field '{f}'")

    # Validate job_id is UUID-like
    job_id = data.get("job_id")
    if job_id:
        try:
            uuid.UUID(str(job_id))
        except ValueError:
            result.add("warning", "INVALID_JOB_ID", f"job_id '{job_id}' is not a valid UUID")

    # Validate studio_link contains job_id
    studio_link = data.get("studio_link", "")
    if job_id and studio_link and str(job_id) not in str(studio_link):
        result.add("warning", "STUDIO_LINK_MISMATCH", "studio_link does not contain job_id")

    # Check result structure
    res = data.get("result")
    if not isinstance(res, dict):
        result.add("error", "INVALID_RESULT", "result is not a dict")
        return False

    soi_rows = res.get("soi_rows")
    if soi_rows is None:
        result.add("error", "MISSING_SOI_ROWS", "result.soi_rows is missing")
        return False

    if not isinstance(soi_rows, list):
        result.add("error", "INVALID_SOI_ROWS", "result.soi_rows is not a list")
        return False

    return True


# ---------------------------------------------------------------------------
# Validation: citations
# ---------------------------------------------------------------------------


def validate_citation(
    citation: Dict[str, Any],
    num_pages: Optional[int],
    result: ValidationResult,
    field_name: str,
    row_idx: int,
) -> None:
    """Validate a single citation object."""
    required = ["type", "bbox", "content", "confidence"]
    for key in required:
        if key not in citation:
            result.add(
                "warning",
                "CITATION_MISSING_KEY",
                f"Citation missing '{key}'",
                field=field_name,
                row=row_idx,
            )

    bbox = citation.get("bbox")
    if isinstance(bbox, dict):
        for dim in ["left", "top", "width", "height"]:
            val = bbox.get(dim)
            if val is not None:
                try:
                    v = float(val)
                    if not (0.0 <= v <= 1.0):
                        result.add(
                            "warning",
                            "BBOX_OUT_OF_RANGE",
                            f"bbox.{dim}={v} out of [0,1]",
                            field=field_name,
                            row=row_idx,
                        )
                except (TypeError, ValueError):
                    pass

        page = bbox.get("page")
        if page is not None and num_pages is not None:
            try:
                p = int(page)
                if p < 1 or p > num_pages:
                    result.add(
                        "warning",
                        "BBOX_PAGE_OUT_OF_RANGE",
                        f"bbox.page={p} outside [1, {num_pages}]",
                        field=field_name,
                        row=row_idx,
                    )
            except (TypeError, ValueError):
                pass


def validate_value_citation_consistency(
    value: Optional[str],
    citations: List[Dict[str, Any]],
    result: ValidationResult,
    field_name: str,
    row_idx: int,
) -> None:
    """
    For numeric fields, check that digits in value substantially overlap
    with digits in citation content.
    
    Escalates to ERROR when overlap is very low (<50%), indicating
    the extracted value doesn't match what's in the PDF.
    """
    if value is None:
        return

    # Check if field appears numeric
    value_digits = extract_digits(value)
    if len(value_digits) < 2:
        return  # not meaningfully numeric

    for i, cit in enumerate(citations):
        content = cit.get("content", "")
        if not content:
            continue

        content_digits = extract_digits(str(content))

        # Check if value digits are a subsequence of content or vice versa
        if value_digits and content_digits:
            # Calculate overlap ratio
            matching = sum(1 for d in value_digits if d in content_digits)
            overlap_ratio = matching / len(value_digits) if len(value_digits) > 0 else 1.0
            
            # Escalate to error if overlap is very low - indicates wrong extraction
            if overlap_ratio < 0.5:
                result.add(
                    "error",
                    "CITATION_VALUE_MISMATCH",
                    f"Value digits '{value_digits}' don't match citation content digits '{content_digits}' (overlap: {overlap_ratio:.0%})",
                    field=field_name,
                    row=row_idx,
                    citation_idx=i,
                    overlap_ratio=overlap_ratio,
                )


# ---------------------------------------------------------------------------
# Validation: Semantic Sanity Checks
# ---------------------------------------------------------------------------

# Keywords that indicate options/derivatives (where negative values are expected)
DERIVATIVE_KEYWORDS = {
    "option", "options", "put", "puts", "call", "calls", "swap", "swaps",
    "forward", "forwards", "future", "futures", "short", "written",
    "collateralized", "covered", "liability", "liabilities",
}

# Reasonable price bounds for sanity checks
MIN_REASONABLE_PRICE = Decimal("0.0001")  # $0.0001 per share minimum
MAX_REASONABLE_PRICE = Decimal("1000000")  # $1,000,000 per share maximum


def _is_derivative_section(section_path: Tuple[str, ...], investment: Optional[str]) -> bool:
    """
    Check if this row is likely a derivative/option based on section path or investment name.
    """
    # Check section path
    path_text = " ".join(section_path).lower() if section_path else ""
    for keyword in DERIVATIVE_KEYWORDS:
        if keyword in path_text:
            return True
    
    # Check investment name
    if investment:
        investment_lower = investment.lower()
        for keyword in DERIVATIVE_KEYWORDS:
            if keyword in investment_lower:
                return True
    
    return False


def validate_semantic_constraints(
    row: Dict[str, Any],
    row_idx: int,
    result: ValidationResult,
) -> None:
    """
    Validate semantic constraints that catch absurd extraction errors.
    
    Checks:
    1. Negative fair_value on non-derivative holdings
    2. Implied price (fair_value / quantity) is in a reasonable range
    """
    row_type = unwrap_value(row.get("row_type"))
    
    # Only check HOLDING rows
    if row_type != "HOLDING":
        return
    
    section_path = normalize_section_path(row.get("section_path"))
    investment = unwrap_value(row.get("investment"))
    
    # Extract values
    fv_raw = unwrap_value(row.get("fair_value_raw"))
    qty_raw = unwrap_value(row.get("quantity_raw"))
    
    fv, _ = parse_decimal(fv_raw, field_name="fair_value_raw") if fv_raw else (None, None)
    qty, _ = parse_decimal(qty_raw, field_name="quantity_raw") if qty_raw else (None, None)
    
    is_derivative = _is_derivative_section(section_path, investment)
    
    # Check 1: Negative fair_value on non-derivative
    if fv is not None and fv < 0 and not is_derivative:
        result.add(
            "error",
            "NEGATIVE_FAIR_VALUE",
            f"Non-derivative holding has negative fair_value: ${fv}",
            row=row_idx,
            investment=investment or "(unknown)",
            fair_value=str(fv),
            section_path=" > ".join(section_path) if section_path else "(root)",
        )
    
    # Check 2: Price sanity check (only for positive values and quantities)
    if fv is not None and qty is not None and qty != 0 and fv > 0 and qty > 0:
        implied_price = abs(fv / qty)
        
        if implied_price < MIN_REASONABLE_PRICE:
            result.add(
                "warning",
                "PRICE_TOO_LOW",
                f"Implied price ${implied_price:.6f} is suspiciously low (fair_value={fv}, quantity={qty})",
                row=row_idx,
                investment=investment or "(unknown)",
                implied_price=str(implied_price),
                fair_value=str(fv),
                quantity=str(qty),
            )
        elif implied_price > MAX_REASONABLE_PRICE:
            result.add(
                "warning",
                "PRICE_TOO_HIGH",
                f"Implied price ${implied_price:.2f} is suspiciously high (fair_value={fv}, quantity={qty})",
                row=row_idx,
                investment=investment or "(unknown)",
                implied_price=str(implied_price),
                fair_value=str(fv),
                quantity=str(qty),
            )


# ---------------------------------------------------------------------------
# Validation: row invariants
# ---------------------------------------------------------------------------


def validate_row(
    row: Dict[str, Any],
    row_idx: int,
    num_pages: Optional[int],
    result: ValidationResult,
) -> Tuple[Optional[str], Tuple[str, ...]]:
    """
    Validate a single soi_rows entry.
    Returns (row_type, section_path_tuple).
    """
    # row_type
    row_type_obj = row.get("row_type")
    row_type = unwrap_value(row_type_obj)

    if row_type is None:
        result.add("error", "MISSING_ROW_TYPE", "Row missing row_type", row=row_idx)
    elif row_type not in VALID_ROW_TYPES:
        result.add(
            "error",
            "INVALID_ROW_TYPE",
            f"Invalid row_type '{row_type}'",
            row=row_idx,
        )

    # section_path
    section_path = normalize_section_path(row.get("section_path"))
    
    # Check for "Unknown Section" - indicates extraction from Top Holdings or unrecognized table
    if section_path and "Unknown Section" in section_path:
        investment = unwrap_value(row.get("investment"))
        label = unwrap_value(row.get("label"))
        fair_value = unwrap_value(row.get("fair_value_raw"))
        result.add(
            "error",
            "UNKNOWN_SECTION_DETECTED",
            "Row assigned to 'Unknown Section' - likely from Top Holdings summary or unrecognized table",
            row=row_idx,
            row_type=row_type,
            investment=investment,
            label=label,
            fair_value_raw=fair_value,
        )

    # Type/field coherence
    if row_type == "HOLDING":
        investment = unwrap_value(row.get("investment"))
        if not investment or not investment.strip():
            result.add(
                "warning",
                "HOLDING_MISSING_INVESTMENT",
                "HOLDING row has empty investment",
                row=row_idx,
            )
    elif row_type in ("SUBTOTAL", "TOTAL"):
        label = unwrap_value(row.get("label"))
        if not label or not label.strip():
            result.add(
                "warning",
                "SUBTOTAL_MISSING_LABEL",
                f"{row_type} row has empty label",
                row=row_idx,
            )
        # If label starts with "Total", should have numeric fields
        if label and label.strip().lower().startswith("total"):
            fair_value = unwrap_value(row.get("fair_value_raw"))
            cost = unwrap_value(row.get("cost_raw")) or unwrap_value(row.get("amortized_cost_raw"))
            if not fair_value and not cost:
                result.add(
                    "warning",
                    "TOTAL_MISSING_NUMERIC",
                    f"Row labeled '{label}' has no fair_value_raw or cost fields",
                    row=row_idx,
                )

    # Validate citations for key fields
    numeric_fields = [
        "fair_value_raw",
        "cost_raw",
        "amortized_cost_raw",
        "quantity_raw",
        "percent_net_assets_raw",
    ]
    for field_name in numeric_fields:
        field_obj = row.get(field_name)
        if field_obj is None:
            continue
        value = unwrap_value(field_obj)
        citations = unwrap_citations(field_obj)

        for cit in citations:
            validate_citation(cit, num_pages, result, field_name, row_idx)

        validate_value_citation_consistency(value, citations, result, field_name, row_idx)

        # Check for multiple numeric tokens and suspicious negatives
        if value:
            _, parse_err = parse_decimal(value, field_name=field_name)
            if parse_err:
                if "Multiple numeric tokens" in parse_err:
                    result.add(
                        "error",
                        "MULTIPLE_NUMERIC_TOKENS",
                        parse_err,
                        field=field_name,
                        row=row_idx,
                    )
                elif "SUSPICIOUS_NEGATIVE" in parse_err:
                    # A negative percent without parentheses is likely an extraction error
                    # where a separator dash was mistaken for a minus sign
                    result.add(
                        "warning",
                        "SUSPICIOUS_NEGATIVE_PERCENT",
                        f"Value '{value}' appears negative but uses dash instead of parentheses - likely separator extraction error",
                        field=field_name,
                        row=row_idx,
                        raw_value=value,
                    )

    return row_type, section_path


# ---------------------------------------------------------------------------
# Validation: Structural Hierarchy Integrity
# ---------------------------------------------------------------------------


def _extract_category_keywords(label: str) -> List[str]:
    """
    Extract potential category keywords from a TOTAL/SUBTOTAL label.
    E.g., "Total Consumer Staples" -> ["consumer", "staples"]
    """
    if not label:
        return []
    
    # Common words to ignore
    stop_words = {
        "total", "subtotal", "investments", "securities", "cost", "value",
        "net", "assets", "the", "and", "of", "for", "at", "in", "a", "an",
    }
    
    # Clean and tokenize
    words = re.findall(r"[a-zA-Z]+", label.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    return keywords


def _path_contains_keywords(section_path: Tuple[str, ...], keywords: List[str]) -> bool:
    """
    Check if any of the keywords appear in the section path.
    """
    if not keywords:
        return True  # No keywords to check
    
    path_text = " ".join(section_path).lower()
    
    # Check if at least one keyword appears in the path
    for keyword in keywords:
        if keyword in path_text:
            return True
    
    return False


def validate_hierarchy_integrity(
    node: "ValidationNode",
    result: "ValidationResult",
) -> None:
    """
    Validate that TOTAL/SUBTOTAL labels are consistent with their section paths.
    This catches cases where Reducto assigns a Total row to the wrong section.
    """
    # Recursively check children first
    for child in node.children.values():
        validate_hierarchy_integrity(child, result)
    
    path_str = node.path_str()
    is_root = not node.path
    
    # Check SUBTOTAL rows
    for subtotal_row in node.subtotal_rows:
        label = unwrap_value(subtotal_row.get("label")) or ""
        keywords = _extract_category_keywords(label)
        
        # If label has meaningful keywords, check they appear in section path
        if keywords and not is_root and not _path_contains_keywords(node.path, keywords):
            result.add(
                "warning",
                "SUBTOTAL_PATH_MISMATCH",
                f"SUBTOTAL label '{label}' mentions categories not in section path",
                section_path=path_str,
                label=label,
                keywords=keywords,
            )
    
    # Check TOTAL rows
    for total_row in node.total_rows:
        label = unwrap_value(total_row.get("label")) or ""
        keywords = _extract_category_keywords(label)
        
        # If label has meaningful keywords, check they appear in section path
        if keywords and not is_root and not _path_contains_keywords(node.path, keywords):
            result.add(
                "warning",
                "TOTAL_PATH_MISMATCH",
                f"TOTAL label '{label}' mentions categories not in section path",
                section_path=path_str,
                label=label,
                keywords=keywords,
            )
    
    # Check for orphaned totals: TOTAL row but no holdings and no children
    if node.total_rows and not node.holdings and not node.children and not is_root:
        total_label = unwrap_value(node.total_rows[0].get("label")) or "TOTAL"
        result.add(
            "warning",
            "ORPHANED_TOTAL",
            f"Section has TOTAL row '{total_label}' but no holdings or child sections",
            section_path=path_str,
            label=total_label,
        )


# ---------------------------------------------------------------------------
# Validation: Hierarchical Tree Structure for Arithmetic
# ---------------------------------------------------------------------------


@dataclass
class ValidationNode:
    """
    A node in the validation tree representing a section.
    Holds holdings directly under this section and child sub-sections.
    """
    path: Tuple[str, ...]
    holdings: List[Dict[str, Any]] = field(default_factory=list)
    subtotal_rows: List[Dict[str, Any]] = field(default_factory=list)
    total_rows: List[Dict[str, Any]] = field(default_factory=list)
    children: Dict[str, "ValidationNode"] = field(default_factory=dict)
    
    # Calculated sums (bottom-up)
    calc_fv: Optional[Decimal] = None
    calc_cost: Optional[Decimal] = None
    calc_pct: Optional[Decimal] = None
    
    # Extracted sums (from SUBTOTAL rows)
    extracted_fv: Optional[Decimal] = None
    extracted_cost: Optional[Decimal] = None
    extracted_pct: Optional[Decimal] = None

    def path_str(self) -> str:
        return " > ".join(self.path) if self.path else "(root)"


def _build_validation_tree(rows: List[Dict[str, Any]]) -> ValidationNode:
    """
    Build a hierarchical tree from soi_rows based on section_path.
    TOTAL rows are now attached to their corresponding section node.
    
    Returns:
        root_node
    """
    root = ValidationNode(path=())
    
    for row in rows:
        row_type = unwrap_value(row.get("row_type"))
        section_path = normalize_section_path(row.get("section_path"))
        
        # Navigate/create path in tree
        current = root
        for i, segment in enumerate(section_path):
            if segment not in current.children:
                current.children[segment] = ValidationNode(path=section_path[:i+1])
            current = current.children[segment]
        
        # Add row to the appropriate node
        if row_type == "HOLDING":
            current.holdings.append(row)
        elif row_type == "SUBTOTAL":
            current.subtotal_rows.append(row)
        elif row_type == "TOTAL":
            current.total_rows.append(row)
    
    return root


def _extract_row_values(row: Dict[str, Any]) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    """Extract fair_value, cost, and percent from a row."""
    fv_raw = unwrap_value(row.get("fair_value_raw"))
    cost_raw = unwrap_value(row.get("cost_raw")) or unwrap_value(row.get("amortized_cost_raw"))
    pct_raw = unwrap_value(row.get("percent_net_assets_raw"))
    
    fv, _ = parse_decimal(fv_raw, field_name="fair_value_raw") if fv_raw else (None, None)
    cost, _ = parse_decimal(cost_raw, field_name="cost_raw") if cost_raw else (None, None)
    pct, _ = parse_decimal(pct_raw, field_name="percent_net_assets_raw") if pct_raw else (None, None)
    
    return fv, cost, pct


def _calculate_node_sums(node: ValidationNode, result: ValidationResult, computed: Dict[str, Any]) -> None:
    """
    Recursively calculate sums bottom-up.
    For leaf nodes: sum holdings.
    For parent nodes: sum child node calculated values.
    
    Enhanced bridging logic:
    - If holdings are missing percentages but we have SUBTOTAL rows with percentages,
      sum the SUBTOTAL row percentages (for multi-category sections like "Major Industry Exposure")
    - This handles summary tables where each row is a category subtotal, not a holding
    """
    # First, recursively calculate children
    for child in node.children.values():
        _calculate_node_sums(child, result, computed)
    
    # Calculate this node's sums
    fv_sum = Decimal("0")
    cost_sum = Decimal("0")
    pct_sum = Decimal("0")
    has_fv = False
    has_cost = False
    has_pct = False
    
    # Sum holdings directly in this node
    for holding in node.holdings:
        fv, cost, pct = _extract_row_values(holding)
        if fv is not None:
            fv_sum += fv
            has_fv = True
        if cost is not None:
            cost_sum += cost
            has_cost = True
        if pct is not None:
            pct_sum += pct
            has_pct = True
    
    # Sum child nodes' calculated values
    for child in node.children.values():
        if child.calc_fv is not None:
            fv_sum += child.calc_fv
            has_fv = True
        if child.calc_cost is not None:
            cost_sum += child.calc_cost
            has_cost = True
        if child.calc_pct is not None:
            pct_sum += child.calc_pct
            has_pct = True
    
    # Store calculated sums
    node.calc_fv = fv_sum if has_fv else None
    node.calc_cost = cost_sum if has_cost else None
    node.calc_pct = pct_sum if has_pct else None
    
    # Extract values from SUBTOTAL rows
    # For multi-category sections (like "Major Industry Exposure"), we may have multiple
    # SUBTOTAL rows that each represent a category percentage. Sum them all.
    # 
    # HIERARCHY DETECTION: If one subtotal's percentage roughly equals the sum of the
    # others, it's a parent-level subtotal and should be excluded from the sum.
    subtotal_fv_sum = Decimal("0")
    subtotal_cost_sum = Decimal("0")
    subtotal_pct_sum = Decimal("0")
    has_subtotal_fv = False
    has_subtotal_cost = False
    has_subtotal_pct = False
    
    # Collect all subtotal values for hierarchy detection
    subtotal_values: List[Tuple[int, Optional[Decimal], Optional[Decimal], Optional[Decimal]]] = []
    for idx, subtotal_row in enumerate(node.subtotal_rows):
        fv, cost, pct = _extract_row_values(subtotal_row)
        subtotal_values.append((idx, fv, cost, pct))
    
    # Detect hierarchy pattern: one subtotal's pct ~= sum of all others
    # This indicates a parent-level subtotal that would cause double-counting
    parent_subtotal_indices: set = set()
    if len(subtotal_values) >= 3:  # Need at least 3 to have meaningful hierarchy
        for check_idx, check_fv, check_cost, check_pct in subtotal_values:
            if check_pct is None or check_pct <= Decimal("0"):
                continue
            
            # Sum all other subtotal percentages
            other_pct_sum = Decimal("0")
            other_count = 0
            for other_idx, _, _, other_pct in subtotal_values:
                if other_idx != check_idx and other_pct is not None:
                    other_pct_sum += other_pct
                    other_count += 1
            
            # If this subtotal's pct roughly equals sum of others, it's the parent
            if other_count >= 2 and other_pct_sum > Decimal("0"):
                tolerance = max(Decimal("1.0"), check_pct * Decimal("0.05"))
                if abs(check_pct - other_pct_sum) <= tolerance:
                    parent_subtotal_indices.add(check_idx)
    
    # Sum subtotal values, excluding detected parent-level subtotals
    for idx, fv, cost, pct in subtotal_values:
        if idx in parent_subtotal_indices:
            continue  # Skip parent-level subtotal to avoid double-counting
        if fv is not None:
            subtotal_fv_sum += fv
            has_subtotal_fv = True
        if cost is not None:
            subtotal_cost_sum += cost
            has_subtotal_cost = True
        if pct is not None:
            subtotal_pct_sum += pct
            has_subtotal_pct = True
    
    # Store extracted values (use sum if multiple subtotals, otherwise first)
    if node.subtotal_rows:
        if len(node.subtotal_rows) == 1:
            # Single subtotal - use its values directly
            fv, cost, pct = _extract_row_values(node.subtotal_rows[0])
            node.extracted_fv = fv
            node.extracted_cost = cost
            node.extracted_pct = pct
        else:
            # Multiple subtotals - these are likely category breakdown rows
            # Each represents a portion that should sum to a Total
            # Parent-level subtotals have been excluded from the sum
            node.extracted_fv = subtotal_fv_sum if has_subtotal_fv else None
            node.extracted_cost = subtotal_cost_sum if has_subtotal_cost else None
            node.extracted_pct = subtotal_pct_sum if has_subtotal_pct else None
    
    # Bridge the gap: If holdings are missing percentages but we have extracted subtotal %,
    # use the extracted value for roll-up calculations. This handles documents where
    # individual holdings lack percentages but section headers provide them.
    pct_bridged = False
    if node.calc_pct is None or node.calc_pct == Decimal("0"):
        if node.extracted_pct is not None and node.extracted_pct > Decimal("0"):
            node.calc_pct = node.extracted_pct
            pct_bridged = True
    
    # Also bridge from summed subtotal percentages if holdings exist but lack percentages
    # This handles "Major Industry Exposure" type sections where categories are listed
    # with percentages but no holdings underneath
    if not has_pct and has_subtotal_pct and not node.holdings:
        # Section with only SUBTOTAL rows (each being a category line)
        # Use the sum of all subtotal percentages as the calculated value
        node.calc_pct = subtotal_pct_sum
        pct_bridged = True
    
    # Track if hierarchy detection was applied
    hierarchy_detected = len(parent_subtotal_indices) > 0
    
    # Add warning if hierarchy detection excluded parent subtotals
    if hierarchy_detected:
        excluded_labels = []
        for idx in parent_subtotal_indices:
            if idx < len(node.subtotal_rows):
                label = unwrap_value(node.subtotal_rows[idx].get("label")) or f"subtotal_{idx}"
                excluded_labels.append(label)
        
        result.add(
            "warning",
            "PERCENTAGE_HIERARCHY_DETECTED",
            f"Detected {len(parent_subtotal_indices)} parent-level subtotal(s) that duplicate child sums; excluded from percentage calculation",
            section_path=node.path_str(),
            excluded_labels=excluded_labels,
            original_subtotal_count=len(node.subtotal_rows),
            adjusted_subtotal_count=len(node.subtotal_rows) - len(parent_subtotal_indices),
        )
    
    # Store computed sums for reporting (only for non-root nodes with data)
    path_str = node.path_str()
    # We always want to report the root if it has data
    if (node.path or node.holdings or node.children) and (has_fv or has_cost or has_pct or pct_bridged):
        computed[path_str] = {
            "calculated_fv": str(node.calc_fv) if node.calc_fv is not None else None,
            "calculated_cost": str(node.calc_cost) if node.calc_cost is not None else None,
            "calculated_pct": str(node.calc_pct) if node.calc_pct is not None else None,
            "extracted_fv": str(node.extracted_fv) if node.extracted_fv is not None else None,
            "extracted_cost": str(node.extracted_cost) if node.extracted_cost is not None else None,
            "extracted_pct": str(node.extracted_pct) if node.extracted_pct is not None else None,
            "holding_count": len(node.holdings),
            "child_count": len(node.children),
            "subtotal_count": len(node.subtotal_rows),
            "total_count": len(node.total_rows),
            "pct_bridged_from_subtotal": pct_bridged,
            "multi_subtotal_sum": len(node.subtotal_rows) > 1,
            "hierarchy_detected": hierarchy_detected,
            "parent_subtotals_excluded": len(parent_subtotal_indices),
        }


def _validate_node_arithmetic(
    node: ValidationNode,
    result: ValidationResult,
    computed: Dict[str, Any],
    sibling_calcs: Optional[Dict[Tuple[str, ...], Decimal]] = None,
) -> None:
    """
    Validate arithmetic for a node: calculated vs extracted values.
    Recursively validates all children first.
    
    Root node is now validated for TOTAL rows to catch skipped sections.
    
    Args:
        node: The validation node to check
        result: ValidationResult to append issues to
        computed: Dict to store computed sums for reporting
        sibling_calcs: Optional dict of sibling section paths to their calc_fv values,
                       used to detect shifted subtotals (off-by-one attribution)
    """
    # Build sibling calculations map for children
    child_calcs: Dict[Tuple[str, ...], Decimal] = {}
    for child in node.children.values():
        if child.calc_fv is not None:
            child_calcs[child.path] = child.calc_fv
    
    # Validate children first, passing sibling information
    for child in node.children.values():
        _validate_node_arithmetic(child, result, computed, child_calcs)
    
    path_str = node.path_str()
    is_root = not node.path
    
    # For non-root nodes, validate SUBTOTAL arithmetic
    if not is_root:
        label = ""
        if node.subtotal_rows:
            label = unwrap_value(node.subtotal_rows[0].get("label")) or ""
        
        # Validate fair_value
        if node.calc_fv is not None and node.extracted_fv is not None:
            diff = abs(node.calc_fv - node.extracted_fv)
            if diff > DOLLAR_TOLERANCE:
                # Check if this is a shifted subtotal (off-by-one attribution)
                # by seeing if extracted_fv matches any sibling's calculated value
                shifted_from: Optional[str] = None
                if sibling_calcs:
                    for sibling_path, sibling_calc_fv in sibling_calcs.items():
                        if sibling_path != node.path and abs(sibling_calc_fv - node.extracted_fv) <= DOLLAR_TOLERANCE:
                            shifted_from = " > ".join(sibling_path)
                            break
                
                if shifted_from:
                    # This is a shifted subtotal - the extracted value belongs to another section
                    result.add(
                        "error",
                        "SHIFTED_SUBTOTAL_DETECTED",
                        f"SUBTOTAL fair_value ({node.extracted_fv}) appears to belong to section '{shifted_from}' (calc=${sibling_calcs.get(tuple(shifted_from.split(' > ')), 'N/A')}), not current section '{path_str}' (calc=${node.calc_fv})",
                        section_path=path_str,
                        label=label,
                        calculated=str(node.calc_fv),
                        extracted=str(node.extracted_fv),
                        diff=str(diff),
                        likely_correct_section=shifted_from,
                    )
                else:
                    result.add(
                        "error",
                        "ARITH_MISMATCH_FV",
                        f"Calculated fair_value ({node.calc_fv}) != extracted subtotal ({node.extracted_fv}), diff=${diff}",
                        section_path=path_str,
                        label=label,
                        calculated=str(node.calc_fv),
                        extracted=str(node.extracted_fv),
                        diff=str(diff),
                    )
                result.has_arithmetic_error = True
                if diff > result.max_dollar_diff:
                    result.max_dollar_diff = diff
        
        # Validate cost
        if node.calc_cost is not None and node.extracted_cost is not None:
            diff = abs(node.calc_cost - node.extracted_cost)
            if diff > DOLLAR_TOLERANCE:
                result.add(
                    "error",
                    "ARITH_MISMATCH_COST",
                    f"Calculated cost ({node.calc_cost}) != extracted subtotal ({node.extracted_cost}), diff=${diff}",
                    section_path=path_str,
                    label=label,
                    calculated=str(node.calc_cost),
                    extracted=str(node.extracted_cost),
                    diff=str(diff),
                )
                result.has_arithmetic_error = True
                if diff > result.max_dollar_diff:
                    result.max_dollar_diff = diff
        
        # Validate percent
        if node.calc_pct is not None and node.extracted_pct is not None:
            diff = abs(node.calc_pct - node.extracted_pct)
            if diff > PERCENT_TOLERANCE:
                # Check for suspect values (% misread as 8)
                suspects = _find_suspect_percent_values(node.holdings)
                
                # Also check subtotal rows for suspect values (for multi-category sections)
                subtotal_suspects = _find_suspect_percent_values(node.subtotal_rows)
                all_suspects = suspects + subtotal_suspects
                
                hint = ""
                if all_suspects:
                    suspect_list = ", ".join(f"'{v}' ({n})" for n, v in all_suspects[:3])
                    hint = f" HINT: Possible '%' misread as '8' in: {suspect_list}"
                
                result.add(
                    "error",
                    "ARITH_MISMATCH_PCT",
                    f"Calculated percent ({node.calc_pct}%) != extracted subtotal ({node.extracted_pct}%), diff={diff}%{hint}",
                    section_path=path_str,
                    label=label,
                    calculated=str(node.calc_pct),
                    extracted=str(node.extracted_pct),
                    diff=str(diff),
                    suspect_misread_percent=all_suspects[:5] if all_suspects else None,
                )
                result.has_arithmetic_error = True
        
        # Check for missing subtotal when we have holdings
        if node.holdings and not node.subtotal_rows and not node.children:
            # If we have a TOTAL row, that might be serving as the subtotal (common in some formats)
            if not node.total_rows:
                result.add(
                    "warning",
                    "MISSING_SUBTOTAL",
                    f"Section has {len(node.holdings)} holdings but no SUBTOTAL row",
                    section_path=path_str,
                )

    # Validate TOTAL rows if present for this section (INCLUDING ROOT)
    # This catches skipped sections: if grand total != sum of all holdings
    if node.total_rows:
        # Use first total row for primary validation
        total_row = node.total_rows[0]
        ext_fv, ext_cost, ext_pct = _extract_row_values(total_row)
        total_label = unwrap_value(total_row.get("label")) or "TOTAL"
        
        # Report this match in computed sums for debugging
        if path_str in computed:
             computed[path_str]["total_label"] = total_label
             computed[path_str]["total_extracted_fv"] = str(ext_fv) if ext_fv is not None else None

        # Validate fair_value against total
        if node.calc_fv is not None and ext_fv is not None:
            diff = abs(node.calc_fv - ext_fv)
            if diff > DOLLAR_TOLERANCE:
                error_code = "ROOT_TOTAL_MISMATCH_FV" if is_root else "TOTAL_MISMATCH_FV"
                error_msg = f"Grand total of all holdings ({node.calc_fv}) != extracted Total ({ext_fv}), diff=${diff}" if is_root else f"Section sum ({node.calc_fv}) != Total row ({ext_fv}), diff=${diff}"
                result.add(
                    "error",
                    error_code,
                    error_msg,
                    section_path=path_str,
                    label=total_label,
                    calculated=str(node.calc_fv),
                    extracted=str(ext_fv),
                    diff=str(diff),
                )
                result.has_arithmetic_error = True
                if is_root:
                    result.root_sum_mismatch = True
                    result.calculated_total_fv = node.calc_fv
                    result.extracted_total_fv = ext_fv
                if diff > result.max_dollar_diff:
                    result.max_dollar_diff = diff

        # Validate cost against total
        if node.calc_cost is not None and ext_cost is not None:
            diff = abs(node.calc_cost - ext_cost)
            if diff > DOLLAR_TOLERANCE:
                error_code = "ROOT_TOTAL_MISMATCH_COST" if is_root else "TOTAL_MISMATCH_COST"
                error_msg = f"Grand total cost ({node.calc_cost}) != extracted Total ({ext_cost}), diff=${diff}" if is_root else f"Section cost ({node.calc_cost}) != Total row ({ext_cost}), diff=${diff}"
                result.add(
                    "error",
                    error_code,
                    error_msg,
                    section_path=path_str,
                    label=total_label,
                    calculated=str(node.calc_cost),
                    extracted=str(ext_cost),
                    diff=str(diff),
                )
                result.has_arithmetic_error = True
                if is_root:
                    result.root_sum_mismatch = True
                if diff > result.max_dollar_diff:
                    result.max_dollar_diff = diff

        # Validate percent against total
        if node.calc_pct is not None and ext_pct is not None:
            diff = abs(node.calc_pct - ext_pct)
            if diff > PERCENT_TOLERANCE:
                error_code = "ROOT_TOTAL_MISMATCH_PCT" if is_root else "TOTAL_MISMATCH_PCT"
                
                # Check for suspect values (% misread as 8) - gather all holdings from this node
                all_holdings = list(node.holdings)
                # For root node, also check children's holdings
                def gather_holdings(n: ValidationNode) -> List[Dict[str, Any]]:
                    h = list(n.holdings)
                    for child in n.children.values():
                        h.extend(gather_holdings(child))
                    return h
                if is_root:
                    all_holdings = gather_holdings(node)
                
                suspects = _find_suspect_percent_values(all_holdings)
                hint = ""
                if suspects:
                    suspect_list = ", ".join(f"'{v}' ({n})" for n, v in suspects[:3])
                    hint = f" HINT: Possible '%' misread as '8' in: {suspect_list}"
                    if len(suspects) > 3:
                        hint += f" and {len(suspects) - 3} more"
                
                error_msg = f"Grand total percent ({node.calc_pct}%) != extracted Total ({ext_pct}%), diff={diff}%{hint}" if is_root else f"Section percent ({node.calc_pct}%) != Total row ({ext_pct}%), diff={diff}%{hint}"
                result.add(
                    "error",
                    error_code,
                    error_msg,
                    section_path=path_str,
                    label=total_label,
                    calculated=str(node.calc_pct),
                    extracted=str(ext_pct),
                    diff=str(diff),
                    suspect_misread_percent=suspects[:5] if suspects else None,
                )
                result.has_arithmetic_error = True
                if is_root:
                    result.root_sum_mismatch = True


def validate_arithmetic(
    rows: List[Dict[str, Any]],
    result: ValidationResult,
) -> None:
    """
    Validate that holdings sum to subtotals, and subtotals roll up correctly to totals.
    Uses a hierarchical tree structure for accurate bottom-up validation.
    
    Tolerances:
      - $1 for dollar amounts (fair_value, cost)
      - 0.01% for percentages
    """
    if not rows:
        return
    
    # Build the validation tree
    root = _build_validation_tree(rows)
    
    # Store computed sums for reporting
    computed: Dict[str, Any] = {}
    
    # Calculate sums bottom-up
    _calculate_node_sums(root, result, computed)
    
    # Validate arithmetic at each node (including Total rows attached to nodes)
    _validate_node_arithmetic(root, result, computed, sibling_calcs=None)
    
    # Validate hierarchy integrity (label vs path consistency)
    validate_hierarchy_integrity(root, result)
    
    result.computed_sums = computed


# ---------------------------------------------------------------------------
# Validation: metadata consistency
# ---------------------------------------------------------------------------


def _extract_soi_pages_from_split(split_json: Optional[Dict[str, Any]]) -> set:
    """
    Extract the set of SOI page numbers from a split result.
    
    Args:
        split_json: The split result JSON (may be None)
        
    Returns:
        Set of page numbers identified as SOI pages, or empty set if not available
    """
    if not split_json:
        return set()
    
    splits = split_json.get("result", {}).get("splits", [])
    for split in splits:
        if str(split.get("name", "")).lower() == "soi":
            pages = split.get("pages", []) or []
            return {int(p) for p in pages if isinstance(p, int) or str(p).isdigit()}
    
    return set()


def _get_row_original_page(row: Dict[str, Any]) -> Optional[int]:
    """
    Extract the original_page from a row's citations.
    
    Checks key fields (investment, label, fair_value_raw) for citation info.
    Returns the first valid original_page found, or None.
    """
    # Fields to check for citations (in priority order)
    fields_to_check = ["investment", "label", "fair_value_raw", "section_path"]
    
    for field_name in fields_to_check:
        field_obj = row.get(field_name)
        citations = unwrap_citations(field_obj)
        
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
                for cit in citations:
                    bbox = cit.get("bbox", {})
                    original_page = bbox.get("original_page")
                    if original_page is not None:
                        try:
                            return int(original_page)
                        except (TypeError, ValueError):
                            continue
    
    return None


def validate_row_pages(
    rows: List[Dict[str, Any]],
    soi_pages: set,
    result: ValidationResult,
) -> None:
    """
    Validate that rows come from expected SOI pages.
    
    Rows from pages not in the SOI split are flagged as warnings,
    as they likely come from Top Holdings or other non-SOI tables.
    
    Args:
        rows: List of soi_rows from extraction
        soi_pages: Set of page numbers identified as SOI pages
        result: ValidationResult to add issues to
    """
    if not soi_pages:
        return  # No split info available, skip validation
    
    for i, row in enumerate(rows):
        original_page = _get_row_original_page(row)
        
        if original_page is not None and original_page not in soi_pages:
            row_type = unwrap_value(row.get("row_type"))
            investment = unwrap_value(row.get("investment"))
            label = unwrap_value(row.get("label"))
            
            result.add(
                "warning",
                "ROW_FROM_NON_SOI_PAGE",
                f"Row from page {original_page} which is not in SOI split {sorted(soi_pages)}",
                row=i,
                row_type=row_type,
                investment=investment,
                label=label,
                original_page=original_page,
                soi_pages=sorted(soi_pages),
            )


def validate_metadata(
    data: Dict[str, Any],
    source_name: str,
    result: ValidationResult,
) -> None:
    """
    Validate metadata fields like as_of_date against filename patterns.
    """
    res = data.get("result", {})
    as_of_date = unwrap_value(res.get("as_of_date"))

    if not as_of_date:
        return

    # Try to extract date from filename (pattern: *-YYYY-MM-DD*)
    date_pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
    match = date_pattern.search(source_name)

    if match:
        file_year, file_month, file_day = match.groups()

        # Check if as_of_date contains these components
        as_of_lower = as_of_date.lower()

        # Extract year from as_of_date
        year_match = re.search(r"\b(20\d{2})\b", as_of_date)

        if year_match and year_match.group(1) != file_year:
            result.add(
                "warning",
                "DATE_MISMATCH",
                f"as_of_date year ({year_match.group(1)}) differs from filename ({file_year})",
                as_of_date=as_of_date,
                filename_date=f"{file_year}-{file_month}-{file_day}",
            )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def validate_extract_response(
    extract_json: Dict[str, Any],
    *,
    split_json: Optional[Dict[str, Any]] = None,
    source_name: str = "unknown",
) -> ValidationResult:
    """
    Run all deterministic validations on an extract response JSON.

    Args:
        extract_json: The parsed extract_urls/*_extract_response.json content
        split_json: Optional split result for cross-validation (not heavily used yet)
        source_name: Filename or identifier for reporting

    Returns:
        ValidationResult with all findings
    """
    result = ValidationResult(source_name=source_name)

    # 1) Response shape
    if not validate_response_shape(extract_json, result):
        return result  # Can't proceed without basic structure

    # Get usage info for page bounds
    usage = extract_json.get("usage", {})
    num_pages = usage.get("num_pages")
    if num_pages is not None:
        try:
            num_pages = int(num_pages)
        except (TypeError, ValueError):
            num_pages = None

    # Get rows
    soi_rows = extract_json.get("result", {}).get("soi_rows", [])
    result.total_rows = len(soi_rows)

    # 2) & 3) Validate each row
    for i, row in enumerate(soi_rows):
        row_type, _ = validate_row(row, i, num_pages, result)

        if row_type == "HOLDING":
            result.holding_count += 1
        elif row_type == "SUBTOTAL":
            result.subtotal_count += 1
        elif row_type == "TOTAL":
            result.total_count += 1
        
        # 3.5) Semantic sanity checks for each row
        validate_semantic_constraints(row, i, result)

    # 4) Arithmetic validation
    validate_arithmetic(soi_rows, result)

    # 5) Metadata consistency
    validate_metadata(extract_json, source_name, result)
    
    # 6) Page source validation (check rows come from expected SOI pages)
    soi_pages = _extract_soi_pages_from_split(split_json)
    if soi_pages:
        validate_row_pages(soi_rows, soi_pages, result)

    return result

