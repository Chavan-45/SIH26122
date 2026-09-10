import re
from typing import Optional


def normalize_activity_code(code: Optional[str]) -> str:
    """
    Normalizes a standalone activity code string into canonical uppercase hyphenated format.

    Examples:
    - 'CIV-101' -> 'CIV-101'
    - 'civ 101' -> 'CIV-101'
    - 'CIV_101' -> 'CIV-101'
    - 'civ_101' -> 'CIV-101'
    - '  pip 201 ' -> 'PIP-201'
    - 'CIV--101' -> 'CIV-101'
    """
    if not code:
        return ""

    cleaned = code.strip().upper()
    # Remove spaces between spaced letters e.g. "C I V" -> "CIV"
    cleaned = re.sub(r"\b([A-Z])\s+([A-Z])\s+([A-Z])\b", r"\1\2\3", cleaned)
    cleaned = re.sub(r"\b([A-Z])\s+([A-Z])\b", r"\1\2", cleaned)
    # Replace spaces or underscores between letter prefix and number suffix with hyphen
    cleaned = re.sub(r"([A-Z]{2,5})[\s_]+(\d{1,5})", r"\1-\2", cleaned)
    # Replace any remaining spaces or underscores with hyphens
    cleaned = re.sub(r"[\s_]+", "-", cleaned)
    # Collapse repeated hyphens
    cleaned = re.sub(r"-+", "-", cleaned)
    return cleaned


def extract_and_normalize_activity_code(text: Optional[str]) -> Optional[str]:
    """
    Extracts an activity-code-like candidate pattern from natural language text and normalizes it.

    Examples:
    - 'status of civ-101' -> 'CIV-101'
    - 'status of civ 101' -> 'CIV-101'
    - 'What is CIV-101?' -> 'CIV-101'
    - 'What is CIV 101?' -> 'CIV-101'
    - 'tell me about civ_101' -> 'CIV-101'
    - 'progress of PIP 201' -> 'PIP-201'
    - 'What is ELE 301?' -> 'ELE-301'
    - 'C I V 101' -> 'CIV-101'
    - 'What activities are overdue?' -> None
    """
    if not text or not text.strip():
        return None

    # 1. Match standard 2-5 letter prefix followed by optional space/hyphen/underscore and 1-5 digits
    match = re.search(r"\b([A-Za-z]{2,5})[\s_\-]*(\d{1,5})\b", text)
    if match:
        prefix = match.group(1).upper()
        digits = match.group(2)
        return f"{prefix}-{digits}"

    # 2. Match single-spaced letter prefix e.g. "C I V 101"
    spaced_match = re.search(r"\b([A-Za-z]\s+[A-Za-z](?:\s+[A-Za-z]){0,3})[\s_\-]*(\d{1,5})\b", text)
    if spaced_match:
        prefix = re.sub(r"\s+", "", spaced_match.group(1)).upper()
        digits = spaced_match.group(2)
        return f"{prefix}-{digits}"

    return None
