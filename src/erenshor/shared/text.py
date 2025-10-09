"""Text utilities: sanitization and normalization.

FALSY VALUE HANDLING GUIDELINES
================================

This codebase handles database IDs that can be "0" (string), which is truthy in
Python but falsy when incorrectly coerced. Follow these rules:

1. **Database IDs (Items.Id, Characters.Guid, Spells.Id)**
   - IDs are stored as varchar (strings) in the database
   - ID "0" is a VALID value (e.g., Metal Girdle has Items.Id = "0")
   - NEVER use: `id or default` - this converts "0" to default
   - ALWAYS use: `id if id is not None else default`

2. **Optional String Fields**
   - Empty string "" and None are DIFFERENT
   - Empty string "" is falsy but valid data
   - Use `is not None` checks for optional fields
   - WRONG: `if field:` (skips "" and "0")
   - RIGHT: `if field is not None:` (only skips None)

3. **Numeric Values**
   - Integer/float 0 is falsy but valid
   - Use explicit comparisons: `if value != 0:`
   - For None defaults: `value if value is not None else 0`

4. **Common Patterns to Avoid**
   - `item.Id or ""` → Bug! Converts "0" to ""
   - `if db_id:` → Bug! Skips db_id="0"
   - `char.Guid or char.Id` → Bug! Skips Guid="0"

5. **Correct Patterns**
   - `item.Id if item.Id is not None else ""`
   - `if db_id is not None:`
   - `char.Guid if char.Guid is not None else char.Id`

Examples of fixed bugs:
- application/generators/items/*.py: Changed `itemid=item.Id or ""` to proper None check
- application/reporting.py: Changed `if db_id:` to `if db_id is not None:`
- domain/entities/page.py: Changed `char.Guid or char.Id` to proper None check

See commit history for complete fixes.
"""

from __future__ import annotations

import logging
import re

__all__ = [
    "normalize_wikitext",
    "parse_name_and_id",
    "sanitize_filename",
    "sanitize_page_name",
    "seconds_to_duration",
    "to_blank",
    "to_string_or_blank",
    "to_zero",
]


logger = logging.getLogger(__name__)


# Characters invalid in Windows filenames (also problematic on other OS)
_invalid_filename = re.compile(r"[\\/*?:\"<>|]")


def sanitize_filename(name: str) -> str:
    return _invalid_filename.sub("", name).strip()


def sanitize_page_name(name: str) -> str:
    """Return a MediaWiki-friendly page name.

    Historically we only strip ':' to avoid namespace-like titles; callers that
    need filesystem-safe names should use sanitize_filename() explicitly.
    """
    return name.replace(":", "").strip()


def normalize_wikitext(text: str) -> str:
    # Normalize newlines and trim trailing whitespace on each line
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip() + "\n"


def seconds_to_duration(seconds: int | float) -> str:
    if seconds < 0:
        raise ValueError("seconds cannot be negative")
    if seconds == 0:
        return ""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0 and secs > 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''} {secs} second{'s' if secs != 1 else ''}"
    if minutes > 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    if secs > 0:
        return f"{secs} second{'s' if secs != 1 else ''}"
    return ""


def to_blank(v: int | float | str | None) -> str:
    """Return empty string for None or zero numeric values; else str(v)."""
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return "" if v == 0 else str(v)
    return str(v)


def to_string_or_blank(
    value: int | float | str | None, zero_as_blank: bool = False
) -> str:
    """Convert value to string or blank, with proper zero handling.

    Args:
        value: Value to convert
        zero_as_blank: If True, numeric 0 becomes ""; if False, becomes "0"

    Returns:
        String representation or empty string

    Examples:
        >>> to_string_or_blank(0, zero_as_blank=False)
        "0"
        >>> to_string_or_blank(0, zero_as_blank=True)
        ""
        >>> to_string_or_blank(None, zero_as_blank=False)
        ""
        >>> to_string_or_blank(42, zero_as_blank=False)
        "42"
    """
    if value is None:
        return ""
    if zero_as_blank and value == 0:
        return ""
    if isinstance(value, (int, float)):
        # Keep integer-like numbers without trailing .0 when possible
        try:
            iv = int(value)
            if float(iv) == float(value):
                return str(iv)
        except (ValueError, OverflowError) as e:
            logger.warning(f"Failed to convert numeric value {value} to integer: {e}")
        return str(value)
    return str(value)


def to_zero(v: int | float | str | None) -> str:
    """Return '0' for None or zero numeric values; else str(v).

    Used for item stats where explicit zeros are desired instead of blanks.
    """
    if v is None:
        return "0"
    if isinstance(v, (int, float)):
        # Keep integer-like numbers without trailing .0 when possible
        try:
            iv = int(v)
            if float(iv) == float(v):
                return str(iv)
        except (ValueError, OverflowError) as e:
            logger.warning(f"Failed to convert numeric value {v} to integer: {e}")
        return str(v)
    return str(v)


def parse_name_and_id(text: str) -> tuple[str, str] | None:
    """Parse strings of the form 'Name (12345)' into (Name, Id).

    Example: "Time Stone (12345)" -> ("Time Stone", "12345")
    """
    import re

    # Match: optional name + whitespace + (digits)
    m = re.search(r"^(.*?)\s*\((\d+)\)", text or "")
    if not m:
        return None
    return m.group(1).strip(), m.group(2)
