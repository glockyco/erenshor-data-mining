"""Text parsing and formatting utilities."""

import re

__all__ = ["parse_name_and_id"]


def parse_name_and_id(text: str) -> tuple[str, str] | None:
    """Parse strings of the form 'Name (12345)' into (Name, Id).

    This pattern is commonly used in game data to combine display names with IDs,
    e.g., "Time Stone (12345)" or "Fireball (98765)".

    Args:
        text: Input string in format "Name (ID)"

    Returns:
        Tuple of (name, id) if pattern matches, None otherwise

    Examples:
        >>> parse_name_and_id("Time Stone (12345)")
        ("Time Stone", "12345")
        >>> parse_name_and_id("Fireball (98765)")
        ("Fireball", "98765")
        >>> parse_name_and_id("Invalid")
        None
    """
    # Match: optional name + whitespace + (digits)
    m = re.search(r"^(.*?)\s*\((\d+)\)", text or "")
    if not m:
        return None
    return m.group(1).strip(), m.group(2)
