"""MediaWiki infrastructure module.

This module provides clients and utilities for interacting with MediaWiki APIs.
"""

from erenshor.infrastructure.wiki.client import (
    MediaWikiAPIError,
    MediaWikiAuthenticationError,
    MediaWikiClient,
    MediaWikiEditError,
    MediaWikiNetworkError,
    MediaWikiRateLimitError,
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
    "MediaWikiAuthenticationError",
    "MediaWikiClient",
    "MediaWikiEditError",
    "MediaWikiNetworkError",
    "MediaWikiRateLimitError",
    "TemplateNotFoundError",
    "TemplateParser",
    "TemplateParserError",
]
