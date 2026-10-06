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
    MediaWikiFile,
    MediaWikiFilePages,
    MediaWikiFileUpload,
    MediaWikiFileVersion,
    MediaWikiNetworkError,
    MediaWikiPageRevision,
    MediaWikiPageSnapshot,
    MediaWikiParse,
    MediaWikiParsedLink,
    MediaWikiPermissionError,
    MediaWikiRateLimitError,
    MediaWikiTitleStatus,
    MediaWikiUploadWarningError,
)
from erenshor.infrastructure.wiki.rate_limit import (
    MediaWikiRequestError,
    MediaWikiRequestor,
    MediaWikiRequestPolicy,
    MediaWikiRetryableRequestError,
    MediaWikiUnretryableRequestError,
    RateLimit,
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
    "MediaWikiFile",
    "MediaWikiFilePages",
    "MediaWikiFileUpload",
    "MediaWikiFileVersion",
    "MediaWikiNetworkError",
    "MediaWikiPageRevision",
    "MediaWikiPageSnapshot",
    "MediaWikiParse",
    "MediaWikiParsedLink",
    "MediaWikiPermissionError",
    "MediaWikiRateLimitError",
    "MediaWikiRequestError",
    "MediaWikiRequestPolicy",
    "MediaWikiRequestor",
    "MediaWikiRetryableRequestError",
    "MediaWikiTitleStatus",
    "MediaWikiUnretryableRequestError",
    "MediaWikiUploadWarningError",
    "RateLimit",
    "TemplateNotFoundError",
    "TemplateParser",
    "TemplateParserError",
]
