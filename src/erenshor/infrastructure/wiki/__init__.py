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
    MediaWikiPageSnapshot,
    MediaWikiPermissionError,
    MediaWikiRateLimitError,
    MediaWikiTitleStatus,
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
    "MediaWikiPageSnapshot",
    "MediaWikiPermissionError",
    "MediaWikiRateLimitError",
    "MediaWikiRequestError",
    "MediaWikiRequestPolicy",
    "MediaWikiRequestor",
    "MediaWikiRetryableRequestError",
    "MediaWikiTitleStatus",
    "MediaWikiUnretryableRequestError",
    "RequestKind",
    "TemplateNotFoundError",
    "TemplateParser",
    "TemplateParserError",
]
