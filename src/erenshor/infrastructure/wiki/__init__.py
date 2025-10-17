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

__all__ = [
    "MediaWikiAPIError",
    "MediaWikiAuthenticationError",
    "MediaWikiClient",
    "MediaWikiEditError",
    "MediaWikiNetworkError",
    "MediaWikiRateLimitError",
]
