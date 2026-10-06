"""MediaWiki file-title policy owned by the domain layer."""

from __future__ import annotations

__all__ = [
    "MEDIAWIKI_PROHIBITED_CHARS",
    "image_file_title",
    "needs_redirect",
    "sanitize_wiki_filename",
    "upload_file_title",
]

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


def image_file_title(*names: str | None) -> str:
    """Return the file title that a page names for an entity's picture.

    The title is the first non-empty name with ``.png``, or ``""`` when every
    name is empty. Callers pass the entity's image name first, then the
    names that stand in for it.
    """
    for name in names:
        if name:
            return f"{name}.png"
    return ""


def upload_file_title(title: str) -> str:
    """Return the title that an upload of the file ``title`` takes.

    MediaWiki forbids colons and other characters in uploaded file names, so
    they are dropped from the name and the extension is kept.
    """
    stem, dot, extension = title.rpartition(".")
    return f"{sanitize_wiki_filename(stem)}{dot}{extension}" if dot else sanitize_wiki_filename(title)
