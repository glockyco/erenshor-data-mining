"""MediaWiki API infrastructure constants.

These constants configure the behavior of wiki API operations including
timeouts, rate limiting, and retry policies.
"""

__all__ = [
    "WIKI_API_TIMEOUT_SECONDS",
    "WIKI_MIN_REQUEST_DELAY_SECONDS",
    "WIKI_DEFAULT_MAX_RETRIES",
    "WIKI_DEFAULT_BACKOFF_BASE",
    "WIKI_DEFAULT_USER_AGENT",
    "WIKI_MAXLAG_SECONDS",
]

# HTTP timeouts
WIKI_API_TIMEOUT_SECONDS = 30
"""HTTP request timeout for MediaWiki API calls in seconds."""

# Rate limiting
WIKI_MIN_REQUEST_DELAY_SECONDS = 0.5
"""Minimum delay between wiki API requests to avoid rate limiting (seconds)."""

# Retry and backoff configuration
WIKI_DEFAULT_MAX_RETRIES = 6
"""Default maximum number of retry attempts for failed API requests."""

WIKI_DEFAULT_BACKOFF_BASE = 1.0
"""Base delay for exponential backoff calculation (seconds).

Actual delay is calculated as: backoff_base * (2 ** attempt)
"""

# MediaWiki configuration
WIKI_MAXLAG_SECONDS = "5"
"""Maximum database replication lag to tolerate (MediaWiki maxlag parameter)."""

# User agent
WIKI_DEFAULT_USER_AGENT = "erenshor-wiki-generator/1.0 (+https://erenshor.wiki.gg)"
"""Default user agent string for API requests."""
