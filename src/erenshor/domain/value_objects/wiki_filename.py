"""MediaWiki file-title policy owned by the domain layer."""

from __future__ import annotations

__all__ = ["MEDIAWIKI_PROHIBITED_CHARS", "needs_redirect", "sanitize_wiki_filename"]

# Characters with MediaWiki title or wikitext semantics that cannot remain in
# uploaded file-title bases. Extensions are added by callers after sanitizing.
MEDIAWIKI_PROHIBITED_CHARS = {
    ":": "",
    "|": "",
    "#": "",
    "<": "",
    ">": "",
    "[": "",
    "]": "",
    "{": "",
    "}": "",
}


def sanitize_wiki_filename(filename: str) -> str:
    """Return a MediaWiki-safe file-title base with normalized whitespace."""
    sanitized = filename
    for character, replacement in MEDIAWIKI_PROHIBITED_CHARS.items():
        sanitized = sanitized.replace(character, replacement)
    return " ".join(sanitized.split()).strip()


def needs_redirect(original: str, sanitized: str) -> bool:
    """Return whether sanitization changed the requested file-title base."""
    return original != sanitized
