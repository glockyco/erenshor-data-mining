"""Formatting utilities for wiki page generators.

This module provides common formatting functions used across all page generators
for consistent wiki output.
"""


def format_description(text: str) -> str:
    """Format description text for wiki display.

    Converts newlines to <br> tags and Unity color tags to HTML spans.

    Args:
        text: Description text with newlines and possibly Unity color tags

    Returns:
        Text formatted for wiki display with <br> tags and HTML spans

    Examples:
        >>> format_description("Line 1\\nLine 2")
        'Line 1<br>Line 2'
        >>> format_description("Para 1\\n\\nPara 2")
        'Para 1<br><br>Para 2'
        >>> format_description("<color=green>text</color>")
        '<span style="color: #15e300;">text</span>'
    """
    import re

    # Strip leading and trailing whitespace
    result = text.strip()

    # Normalize line endings (handle Windows \r\n, Unix \n, old Mac \r)
    # Replace \r\n with \n first, then replace any remaining \r with \n
    result = result.replace("\r\n", "\n").replace("\r", "\n")

    # Replace newlines with <br>
    result = result.replace("\n", "<br>")

    # Collapse more than 2 consecutive <br> tags into exactly 2
    # This prevents excessive spacing while preserving paragraph breaks
    result = re.sub(r"(<br>){3,}", "<br><br>", result)

    # Convert Unity green color tags to HTML spans
    # Handles: <color=green>content</color> or <color=green> content </color> (with spaces)
    result = re.sub(
        r"<color=green>\s*([^<]*?)\s*</color>", r'<span style="color: #15e300;">\1</span>', result, flags=re.IGNORECASE
    )

    return result


def safe_str(value: object, zero_as_blank: bool = False) -> str:
    """Convert value to string for wiki display.

    Args:
        value: Value to convert (can be None, bool, int, float, or str).
        zero_as_blank: If True, return empty string for 0 values.

    Returns:
        String representation suitable for wiki templates:
        - None: empty string
        - bool: "True" or empty string
        - 0 (if zero_as_blank=True): empty string
        - float: rounded to 2 decimal places
        - int/str: converted to string

    Examples:
        >>> safe_str(None)
        ''
        >>> safe_str(True)
        'True'
        >>> safe_str(False)
        ''
        >>> safe_str(42)
        '42'
        >>> safe_str(0)
        '0'
        >>> safe_str(0, zero_as_blank=True)
        ''
        >>> safe_str(0.10000000149011612)
        '0.1'
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else ""
    if zero_as_blank and value == 0:
        return ""
    if isinstance(value, float):
        return str(round(value, 2))
    if isinstance(value, int):
        return str(value)
    return str(value)
