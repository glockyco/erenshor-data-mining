"""MediaWiki API client for fetching and publishing wiki pages.

This module provides a Python client for interacting with MediaWiki's API,
enabling programmatic management of wiki content.

Features:
- Login with bot credentials
- Fetch page content by title
- Batch fetch multiple pages efficiently
- Edit pages with new content
- CSRF token management
- Rate limiting to avoid API throttling
- Comprehensive error handling

The MediaWikiClient class provides a type-safe, testable interface for wiki
operations, designed to work with wiki.gg (https://erenshor.wiki.gg).
"""

import time
from collections.abc import Sequence
from typing import Any

import httpx
from loguru import logger


class MediaWikiAPIError(Exception):
    """Base exception for MediaWiki API errors.

    This is the parent exception for all MediaWiki-specific errors.
    Catch this to handle all MediaWiki API failures.
    """

    pass


class MediaWikiNetworkError(MediaWikiAPIError):
    """Raised when network communication with MediaWiki fails.

    This can occur due to:
    - Network connectivity issues
    - DNS resolution failures
    - Timeouts
    - Invalid API URL
    """

    pass


class MediaWikiAuthenticationError(MediaWikiAPIError):
    """Raised when MediaWiki authentication fails.

    This occurs when:
    - Invalid bot username/password
    - Bot account not configured
    - Account lacks necessary permissions
    - Bot password expired
    """

    pass


class MediaWikiEditError(MediaWikiAPIError):
    """Raised when page edit operation fails.

    This can occur due to:
    - Invalid CSRF token
    - Page protection (edit permissions required)
    - Edit conflicts
    - Invalid page title
    - Content validation failures
    """

    pass


class MediaWikiRateLimitError(MediaWikiAPIError):
    """Raised when rate limit is exceeded.

    MediaWiki APIs have rate limits to prevent abuse. This error
    indicates that too many requests were made in a short period.

    The client automatically handles rate limiting with delays,
    but this error may still occur if limits are severely exceeded.
    """

    pass


class MediaWikiClient:
    """Client for MediaWiki API operations.

    This class provides a Python interface to MediaWiki's API for fetching
    and editing wiki pages. It handles authentication, CSRF tokens, rate
    limiting, and error handling.

    Attributes:
        api_url: Full URL to MediaWiki API endpoint (e.g., "https://erenshor.wiki.gg/api.php").
        bot_username: Bot account username for authentication.
        bot_password: Bot account password for authentication.
        batch_size: Number of pages to fetch per batch request.
        rate_limit_delay: Minimum delay between API requests (seconds).
        edit_summary: Default edit summary for page updates.
        minor_edit: Whether edits should be marked as minor by default.

    Example:
        >>> # Initialize client
        >>> client = MediaWikiClient(
        ...     api_url="https://erenshor.wiki.gg/api.php",
        ...     bot_username="MyBot@MyBot",
        ...     bot_password="bot_password_here"
        ... )

        >>> # Login (required before editing)
        >>> client.login()

        >>> # Fetch single page
        >>> content = client.get_page("Item:Sword")
        >>> print(content)

        >>> # Fetch multiple pages
        >>> pages = client.get_pages(["Item:Sword", "Item:Shield", "Character:Goblin"])
        >>> for title, content in pages.items():
        ...     print(f"{title}: {len(content)} characters")

        >>> # Edit page
        >>> client.edit_page(
        ...     title="Item:Sword",
        ...     content="{{Item|name=Sword|damage=10}}",
        ...     summary="Update item stats from database"
        ... )
    """

    def __init__(
        self,
        api_url: str,
        bot_username: str = "",
        bot_password: str = "",
        batch_size: int = 25,
        rate_limit_delay: float = 1.0,
        edit_summary: str = "Automated wiki update",
        minor_edit: bool = True,
        timeout: float = 30.0,
    ) -> None:
        """Initialize MediaWiki API client.

        Args:
            api_url: Full URL to MediaWiki API endpoint (must end with /api.php).
            bot_username: Bot account username (format: "BotName@BotName").
            bot_password: Bot account password (bot password from Special:BotPasswords).
            batch_size: Number of pages to fetch per batch request (max 50).
            rate_limit_delay: Minimum delay between API requests in seconds.
            edit_summary: Default edit summary for page updates.
            minor_edit: Whether edits should be marked as minor by default.
            timeout: HTTP request timeout in seconds.

        Raises:
            ValueError: If api_url doesn't end with /api.php or batch_size is invalid.
        """
        if not api_url.endswith("/api.php"):
            raise ValueError(f"API URL must end with /api.php, got: {api_url}")

        if not 1 <= batch_size <= 50:
            raise ValueError(f"Batch size must be between 1 and 50, got: {batch_size}")

        self.api_url = api_url
        self.bot_username = bot_username
        self.bot_password = bot_password
        self.batch_size = batch_size
        self.rate_limit_delay = rate_limit_delay
        self.edit_summary = edit_summary
        self.minor_edit = minor_edit
        self.timeout = timeout

        # Session state
        self._client = httpx.Client(timeout=timeout)
        self._csrf_token: str | None = None
        self._last_request_time: float = 0.0

        logger.debug(f"MediaWiki client initialized: api_url={api_url}, batch_size={batch_size}")

    def __enter__(self) -> "MediaWikiClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit - closes HTTP client."""
        self.close()

    def close(self) -> None:
        """Close HTTP client and release resources.

        Should be called when done with the client, or use context manager.
        """
        self._client.close()
        logger.debug("MediaWiki client closed")

    def _rate_limit(self) -> None:
        """Apply rate limiting delay between requests.

        Ensures minimum delay between API requests to avoid throttling.
        """
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _request(
        self,
        params: dict[str, Any],
        method: str = "GET",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request to MediaWiki API.

        Args:
            params: Query parameters for API request.
            method: HTTP method (GET or POST).
            data: Form data for POST requests.

        Returns:
            JSON response from API.

        Raises:
            MediaWikiNetworkError: If network request fails.
            MediaWikiRateLimitError: If rate limit exceeded.
            MediaWikiAPIError: If API returns error response.
        """
        # Apply rate limiting
        self._rate_limit()

        # Add format=json to all requests
        params["format"] = "json"

        # Add maxlag parameter for batch operations (recommended for non-interactive tasks)
        # Higher values = more aggressive, lower values = nicer to server
        # 5 seconds is a good balance for batch operations
        if "maxlag" not in params:
            params["maxlag"] = "5"

        try:
            if method == "GET":
                response = self._client.get(self.api_url, params=params)
            else:
                response = self._client.post(self.api_url, params=params, data=data)

            response.raise_for_status()

        except httpx.TimeoutException as e:
            logger.error(f"MediaWiki API request timeout: {e}")
            raise MediaWikiNetworkError(f"Request timeout: {e}") from e

        except httpx.NetworkError as e:
            logger.error(f"MediaWiki API network error: {e}")
            raise MediaWikiNetworkError(f"Network error: {e}") from e

        except httpx.HTTPStatusError as e:
            logger.error(f"MediaWiki API HTTP error: {e.response.status_code}")
            if e.response.status_code == 429:
                # Check for Retry-After header
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    logger.warning(f"Rate limit exceeded. Retry-After: {retry_after}s")
                    raise MediaWikiRateLimitError(f"Rate limit exceeded. Retry after {retry_after}s") from e
                else:
                    logger.warning("Rate limit exceeded (no Retry-After header)")
                    raise MediaWikiRateLimitError("Rate limit exceeded") from e
            raise MediaWikiNetworkError(f"HTTP {e.response.status_code}: {e}") from e

        # Parse JSON response
        try:
            result: dict[str, Any] = response.json()
        except Exception as e:
            logger.error(f"Failed to parse MediaWiki API response: {e}")
            raise MediaWikiAPIError(f"Invalid JSON response: {e}") from e

        # Check for API errors
        if "error" in result:
            error_code = result["error"].get("code", "unknown")
            error_info = result["error"].get("info", "Unknown error")
            logger.error(f"MediaWiki API error: {error_code} - {error_info}")

            if error_code in ("badtoken", "notoken"):
                # Token expired, clear cached token
                self._csrf_token = None

            raise MediaWikiAPIError(f"API error ({error_code}): {error_info}")

        return result

    def login(self) -> None:
        """Login to MediaWiki with bot credentials.

        Establishes authenticated session using bot username and password.
        Required before performing edit operations.

        Raises:
            MediaWikiAuthenticationError: If login fails.
            ValueError: If bot credentials not configured.

        Example:
            >>> client = MediaWikiClient(
            ...     api_url="https://erenshor.wiki.gg/api.php",
            ...     bot_username="MyBot@MyBot",
            ...     bot_password="secret"
            ... )
            >>> client.login()
        """
        if not self.bot_username or not self.bot_password:
            raise ValueError("Bot username and password required for login")

        logger.info(f"Logging in as: {self.bot_username}")

        # Get login token
        params = {
            "action": "query",
            "meta": "tokens",
            "type": "login",
        }

        try:
            result = self._request(params)
            login_token = result["query"]["tokens"]["logintoken"]

        except (KeyError, MediaWikiAPIError) as e:
            logger.error(f"Failed to get login token: {e}")
            raise MediaWikiAuthenticationError("Failed to get login token") from e

        # Perform login
        data = {
            "action": "login",
            "lgname": self.bot_username,
            "lgpassword": self.bot_password,
            "lgtoken": login_token,
        }

        try:
            result = self._request({}, method="POST", data=data)

            if result.get("login", {}).get("result") != "Success":
                reason = result.get("login", {}).get("reason", "Unknown reason")
                logger.error(f"Login failed: {reason}")
                raise MediaWikiAuthenticationError(f"Login failed: {reason}")

            logger.info("Successfully logged in to MediaWiki")

        except MediaWikiAPIError as e:
            logger.error(f"Login request failed: {e}")
            raise MediaWikiAuthenticationError(f"Login failed: {e}") from e

    def get_csrf_token(self) -> str:
        """Get CSRF token for edit operations.

        CSRF tokens are required for all state-changing operations (edits, moves, etc).
        Token is cached and reused until it expires.

        Returns:
            CSRF token string.

        Raises:
            MediaWikiAPIError: If token request fails.

        Example:
            >>> client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php")
            >>> token = client.get_csrf_token()
        """
        # Return cached token if available
        if self._csrf_token:
            return self._csrf_token

        logger.debug("Fetching CSRF token")

        params = {
            "action": "query",
            "meta": "tokens",
            "type": "csrf",
        }

        try:
            result = self._request(params)
            token: str = result["query"]["tokens"]["csrftoken"]
            self._csrf_token = token
            logger.debug("CSRF token obtained")
            return self._csrf_token

        except (KeyError, MediaWikiAPIError) as e:
            logger.error(f"Failed to get CSRF token: {e}")
            raise MediaWikiAPIError("Failed to get CSRF token") from e

    def get_page(self, title: str) -> str | None:
        """Fetch content of a single wiki page.

        Args:
            title: Page title (e.g., "Item:Sword", "Character:Goblin").

        Returns:
            Page content as wikitext string, or None if page doesn't exist.

        Raises:
            MediaWikiAPIError: If API request fails.

        Example:
            >>> client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php")
            >>> content = client.get_page("Item:Sword")
            >>> if content:
            ...     print(f"Page exists: {len(content)} characters")
            ... else:
            ...     print("Page doesn't exist")
        """
        logger.debug(f"Fetching page: {title}")

        params = {
            "action": "query",
            "titles": title,
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
        }

        result = self._request(params)

        # Extract page content from response
        pages = result.get("query", {}).get("pages", {})

        # Get first (and only) page from response
        if not pages:
            logger.warning(f"No page data returned for: {title}")
            return None

        page_id = next(iter(pages.keys()))
        page = pages[page_id]

        # Check if page exists (missing pages have negative IDs)
        if int(page_id) < 0:
            logger.debug(f"Page doesn't exist: {title}")
            return None

        # Extract content from revision
        try:
            content: str = page["revisions"][0]["slots"]["main"]["*"]
            logger.debug(f"Fetched page: {title} ({len(content)} characters)")
            return content

        except (KeyError, IndexError) as e:
            logger.error(f"Failed to extract content for {title}: {e}")
            return None

    def get_pages(self, titles: Sequence[str]) -> dict[str, str | None]:
        """Fetch content of multiple wiki pages efficiently.

        Uses batch API requests to fetch multiple pages. Automatically handles
        pagination if more than batch_size pages are requested.

        Args:
            titles: List of page titles to fetch.

        Returns:
            Dictionary mapping page titles to content (None if page doesn't exist).

        Raises:
            MediaWikiAPIError: If API request fails.

        Example:
            >>> client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php")
            >>> pages = client.get_pages(["Item:Sword", "Item:Shield", "Character:Goblin"])
            >>> for title, content in pages.items():
            ...     if content:
            ...         print(f"{title}: exists")
            ...     else:
            ...         print(f"{title}: missing")
        """
        if not titles:
            return {}

        logger.info(f"Fetching {len(titles)} pages in batches of {self.batch_size}")

        result_dict: dict[str, str | None] = {}

        # Process in batches
        for i in range(0, len(titles), self.batch_size):
            batch = titles[i : i + self.batch_size]
            logger.debug(f"Fetching batch {i // self.batch_size + 1}: {len(batch)} pages")

            params = {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
            }

            result = self._request(params)

            # Extract content from response
            pages = result.get("query", {}).get("pages", {})

            for page_id, page in pages.items():
                title = page.get("title", "")

                # Check if page exists
                if int(page_id) < 0:
                    result_dict[title] = None
                    continue

                # Extract content
                try:
                    content = page["revisions"][0]["slots"]["main"]["*"]
                    result_dict[title] = content
                except (KeyError, IndexError):
                    result_dict[title] = None

        logger.info(f"Fetched {len(result_dict)} pages ({sum(1 for v in result_dict.values() if v)} exist)")
        return result_dict

    def edit_page(
        self,
        title: str,
        content: str,
        summary: str | None = None,
        minor: bool | None = None,
        create_only: bool = False,
        no_create: bool = False,
    ) -> None:
        """Edit a wiki page with new content.

        Requires authentication (call login() first). Uses CSRF token for security.

        Args:
            title: Page title to edit.
            content: New page content (wikitext).
            summary: Edit summary (defaults to self.edit_summary).
            minor: Mark as minor edit (defaults to self.minor_edit).
            create_only: Only create page if it doesn't exist (fails if page exists).
            no_create: Only edit existing page (fails if page doesn't exist).

        Raises:
            MediaWikiEditError: If edit operation fails.
            MediaWikiAPIError: If API request fails.

        Example:
            >>> client = MediaWikiClient(
            ...     api_url="https://erenshor.wiki.gg/api.php",
            ...     bot_username="MyBot@MyBot",
            ...     bot_password="secret"
            ... )
            >>> client.login()
            >>> client.edit_page(
            ...     title="Item:Sword",
            ...     content="{{Item|name=Sword|damage=10}}",
            ...     summary="Update item stats from database"
            ... )
        """
        if summary is None:
            summary = self.edit_summary
        if minor is None:
            minor = self.minor_edit

        logger.info(f"Editing page: {title}")

        # Get CSRF token
        token = self.get_csrf_token()

        # Build edit parameters
        data = {
            "action": "edit",
            "title": title,
            "text": content,
            "summary": summary,
            "token": token,
        }

        # Add optional flags
        if minor:
            data["minor"] = "1"
        if create_only:
            data["createonly"] = "1"
        if no_create:
            data["nocreate"] = "1"

        try:
            result = self._request({}, method="POST", data=data)

            # Check edit result
            edit_result = result.get("edit", {})

            if edit_result.get("result") != "Success":
                error = edit_result.get("error", "Unknown error")
                logger.error(f"Edit failed for {title}: {error}")
                raise MediaWikiEditError(f"Edit failed: {error}")

            logger.info(f"Successfully edited page: {title}")

        except MediaWikiAPIError as e:
            logger.error(f"Edit request failed for {title}: {e}")
            raise MediaWikiEditError(f"Failed to edit page '{title}': {e}") from e

    def page_exists(self, title: str) -> bool:
        """Check if a page exists on the wiki.

        Args:
            title: Page title to check.

        Returns:
            True if page exists, False otherwise.

        Raises:
            MediaWikiAPIError: If API request fails.

        Example:
            >>> client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php")
            >>> if client.page_exists("Item:Sword"):
            ...     print("Page exists")
            ... else:
            ...     print("Page doesn't exist")
        """
        logger.debug(f"Checking if page exists: {title}")

        params = {
            "action": "query",
            "titles": title,
        }

        result = self._request(params)

        # Check if page ID is positive (negative means page doesn't exist)
        pages = result.get("query", {}).get("pages", {})
        if not pages:
            return False

        page_id = next(iter(pages.keys()))
        exists = int(page_id) > 0

        logger.debug(f"Page {title}: {'exists' if exists else 'does not exist'}")
        return exists

    def get_recent_changes(self, days: int = 30, limit: int = 500) -> dict[str, str]:
        """Get pages that were recently modified with their modification timestamps.

        Uses MediaWiki's recentchanges API to efficiently identify pages that
        have been edited within the last N days, along with when they were last
        modified. This enables smart cache invalidation by comparing modification
        timestamps with fetch timestamps.

        Args:
            days: Number of days to look back (default: 30).
            limit: Maximum number of results to return (default: 500, max: 500).

        Returns:
            Dictionary mapping page title to ISO 8601 timestamp of last modification.
            If a page appears multiple times, only the most recent timestamp is kept.

        Raises:
            MediaWikiAPIError: If API request fails.

        Example:
            >>> client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php")
            >>> recent = client.get_recent_changes(days=30)
            >>> print(f"{len(recent)} pages modified in last 30 days")
            >>> for title, timestamp in list(recent.items())[:5]:
            ...     print(f"{title}: {timestamp}")
        """
        logger.info(f"Fetching recent changes (last {days} days, limit {limit})")

        # Calculate timestamp for N days ago (MediaWiki format: ISO 8601)
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rc_start = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "action": "query",
            "list": "recentchanges",
            "rcstart": rc_start,
            "rcprop": "title|timestamp",  # Get both title and timestamp
            "rclimit": min(limit, 500),  # API max is 500
            "rctype": "edit|new",  # Only edits and new pages, not logs
        }

        result = self._request(params)

        # Extract page titles with timestamps
        # If a page appears multiple times, keep the most recent timestamp
        changes = result.get("query", {}).get("recentchanges", [])
        page_timestamps: dict[str, str] = {}

        for change in changes:
            title = change.get("title")
            timestamp = change.get("timestamp")

            if not title or not timestamp:
                continue

            # Keep most recent timestamp for each page
            if title not in page_timestamps or timestamp > page_timestamps[title]:
                page_timestamps[title] = timestamp

        logger.info(f"Found {len(page_timestamps)} pages modified in last {days} days")
        return page_timestamps
