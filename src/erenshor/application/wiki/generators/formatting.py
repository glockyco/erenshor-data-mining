"""Formatting utilities for wiki page generators.

This module provides common formatting functions used across all page generators
for consistent wiki output.
"""


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
