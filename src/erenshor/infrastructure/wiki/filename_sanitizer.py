"""MediaWiki filename sanitization utilities.

Handles sanitization of filenames for MediaWiki upload, which prohibits certain
characters in file titles. Also provides utilities for creating redirect pages
from original names to sanitized names.

MediaWiki has restrictions on file titles to prevent conflicts with wiki syntax
and markup. This module provides utilities to sanitize filenames by removing
prohibited characters while maintaining readability.

Common use case: Game entities with colons (e.g., "Aura: Ancient Presence")
must be uploaded as "Aura Ancient Presence.png" with a redirect created from
the original name for wiki template compatibility.

Example:
    >>> from erenshor.infrastructure.wiki.filename_sanitizer import sanitize_wiki_filename
    >>> sanitize_wiki_filename("Aura: Ancient Presence")
    'Aura Ancient Presence'
    >>> sanitize_wiki_filename("Blueprint: Stone Bank")
    'Blueprint Stone Bank'
"""

from __future__ import annotations

__all__ = ["MEDIAWIKI_PROHIBITED_CHARS", "needs_redirect", "sanitize_wiki_filename"]

# Characters prohibited in MediaWiki file titles
# Source: https://www.mediawiki.org/wiki/Manual:Page_title
#
# These characters have special meaning in MediaWiki and cannot appear in titles:
# - : (colon) - namespace separator (e.g., "File:", "User:")
# - | (pipe) - template parameter separator
# - # (hash) - anchor/fragment identifier
# - < > (angle brackets) - HTML tag delimiters
# - [ ] (square brackets) - wikilink syntax
# - { } (curly braces) - template/parser function syntax
MEDIAWIKI_PROHIBITED_CHARS = {
    ":": "",  # Colon - namespace separator
    "|": "",  # Pipe - template/table syntax
    "#": "",  # Hash - anchor/fragment identifier
    "<": "",  # Less-than - HTML tag
    ">": "",  # Greater-than - HTML tag
    "[": "",  # Left bracket - wikilink syntax
    "]": "",  # Right bracket - wikilink syntax
    "{": "",  # Left brace - template syntax
    "}": "",  # Right brace - template syntax
}


def sanitize_wiki_filename(filename: str) -> str:
    """Sanitize filename for MediaWiki upload.

    Removes characters prohibited in MediaWiki file titles while preserving
    readability. Designed for use without file extension - the .png extension
    should be added separately after sanitization.

    The function removes prohibited characters and normalizes whitespace by
    collapsing multiple consecutive spaces into single spaces.

    Args:
        filename: Original filename without extension (e.g., "Aura: Ancient Presence").

    Returns:
        Sanitized filename without extension, with normalized whitespace
        (e.g., "Aura Ancient Presence").

    Examples:
        >>> sanitize_wiki_filename("Aura: Ancient Presence")
        'Aura Ancient Presence'
        >>> sanitize_wiki_filename("Blueprint: Stone Bank")
        'Blueprint Stone Bank'
        >>> sanitize_wiki_filename("Normal Item")
        'Normal Item'
        >>> sanitize_wiki_filename("Multiple  :  Colons")
        'Multiple Colons'

    Note:
        If the filename consists entirely of prohibited characters, this will
        return an empty string. Callers should validate the result if this is
        a concern for their use case.
    """
    sanitized = filename

    # Remove prohibited characters
    for char, replacement in MEDIAWIKI_PROHIBITED_CHARS.items():
        sanitized = sanitized.replace(char, replacement)

    # Collapse multiple spaces to single space and strip leading/trailing whitespace
    sanitized = " ".join(sanitized.split())

    return sanitized.strip()


def needs_redirect(original: str, sanitized: str) -> bool:
    """Check if a redirect page is needed for a sanitized filename.

    A redirect page is needed when the sanitized filename differs from the
    original, indicating that prohibited characters were removed during
    sanitization. This allows wiki templates and links to use the original
    name while the actual file exists under the sanitized name.

    Args:
        original: Original filename before sanitization.
        sanitized: Filename after sanitization.

    Returns:
        True if the names differ (redirect needed), False if identical.

    Examples:
        >>> needs_redirect("Aura: Ancient Presence", "Aura Ancient Presence")
        True
        >>> needs_redirect("Normal Item", "Normal Item")
        False
        >>> needs_redirect("Test::", "Test")
        True
    """
    return original != sanitized
