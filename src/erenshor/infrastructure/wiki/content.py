"""MediaWiki content normalization.

MediaWiki rewrites page text on save: CR and CRLF line endings collapse to LF,
and trailing whitespace is right-trimmed from the whole text. Leading and
internal whitespace is preserved. Comparing repo source against stored remote
text without applying this normalization makes every repo file with a trailing
newline look perpetually changed, breaking deploy idempotency.
"""

from __future__ import annotations

# PHP rtrim's default character set, which MediaWiki applies to saved text.
_MEDIAWIKI_RTRIM_CHARS = " \t\n\r\x00\x0b"


def normalize_saved_text(text: str) -> str:
    """Return ``text`` as MediaWiki would store it after a save.

    Converts CR/CRLF to LF and right-trims trailing whitespace. Two strings that
    normalize equal would produce no content change if uploaded, so deploy
    idempotency checks must compare normalized values.
    """
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    return unified.rstrip(_MEDIAWIKI_RTRIM_CHARS)
