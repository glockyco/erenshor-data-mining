"""MediaWiki infrastructure module.

This module provides clients and utilities for interacting with MediaWiki APIs.
"""

from erenshor.infrastructure.wiki.client import (
    MediaWikiAPIError,
    MediaWikiAssertionError,
    MediaWikiAuthenticationError,
    MediaWikiClient,
    MediaWikiEditConflictError,
    MediaWikiEditError,
    MediaWikiNetworkError,
    MediaWikiPageRevision,
    MediaWikiPermissionError,
    MediaWikiRateLimitError,
)
from erenshor.infrastructure.wiki.filename_sanitizer import (
    needs_redirect,
    sanitize_wiki_filename,
)
from erenshor.infrastructure.wiki.rate_limit import (
    MediaWikiRequestError,
    MediaWikiRequestor,
    MediaWikiRequestPolicy,
    MediaWikiRetryableRequestError,
    MediaWikiUnretryableRequestError,
    RequestKind,
)
from erenshor.infrastructure.wiki.template_parser import (
    InvalidWikitextError,
    TemplateNotFoundError,
    TemplateParser,
    TemplateParserError,
)

__all__ = [
    "InvalidWikitextError",
    "MediaWikiAPIError",
    "MediaWikiAssertionError",
    "MediaWikiAuthenticationError",
    "MediaWikiClient",
    "MediaWikiEditConflictError",
    "MediaWikiEditError",
    "MediaWikiNetworkError",
    "MediaWikiPageRevision",
    "MediaWikiPermissionError",
    "MediaWikiRateLimitError",
    "MediaWikiRequestError",
    "MediaWikiRequestPolicy",
    "MediaWikiRequestor",
    "MediaWikiRetryableRequestError",
    "MediaWikiUnretryableRequestError",
    "RequestKind",
    "TemplateNotFoundError",
    "TemplateParser",
    "TemplateParserError",
    "needs_redirect",
    "sanitize_wiki_filename",
]
