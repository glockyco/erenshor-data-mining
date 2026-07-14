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

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any, Literal, NoReturn

import httpx
from loguru import logger

from erenshor.infrastructure.time import Clock, RealClock
from erenshor.infrastructure.wiki.rate_limit import MediaWikiRequestPolicy, retry_delay_for


class MediaWikiAPIError(Exception):
    """Base exception for MediaWiki API errors.

    This is the parent exception for all MediaWiki-specific errors.
    Catch this to handle all MediaWiki API failures.
    """

    def __init__(self, message: str, code: str | None = None, info: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.info = info


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


class MediaWikiEditConflictError(MediaWikiEditError):
    """Raised when MediaWiki rejects a safe edit due to an edit conflict."""


class MediaWikiAssertionError(MediaWikiEditError):
    """Raised when MediaWiki assertion guards reject the current session/user."""


class MediaWikiPermissionError(MediaWikiEditError):
    """Raised when MediaWiki rejects an edit due to page or account permissions."""


class MediaWikiRateLimitError(MediaWikiAPIError):
    """Raised when rate limit is exceeded.

    MediaWiki APIs have rate limits to prevent abuse. This error
    indicates that too many requests were made in a short period.

    The client automatically handles rate limiting with delays,
    but this error may still occur if limits are severely exceeded.
    """

    pass


@dataclass(frozen=True, slots=True)
class MediaWikiPageRevision:
    """Revision metadata used to guard conflict-safe MediaWiki edits."""

    title: str
    page_id: int
    revision_id: int
    timestamp: str
    start_timestamp: str


@dataclass(frozen=True, slots=True)
class MediaWikiPageSnapshot:
    """Page source and revision metadata from one revision-bound query."""

    title: str
    source_text: str | None
    revision: MediaWikiPageRevision | None
    start_timestamp: str
    content_model: str | None = None


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
        clock: Clock | None = None,
        request_policy: MediaWikiRequestPolicy | None = None,
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
            clock: Clock implementation for time operations (default: RealClock()).
            request_policy: Bounded retry/backoff policy for transient lag and
                rate-limit responses (default: MediaWikiRequestPolicy()).

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
        self.clock = clock if clock is not None else RealClock()
        self.request_policy = request_policy if request_policy is not None else MediaWikiRequestPolicy()

        # Session state with custom User-Agent (required by wiki.gg)
        # User-Agent should include bot name and contact info
        user_agent = f"{bot_username or 'ErenshorDataBot'}/0.3 (automated wiki updates) httpx"
        headers = {"User-Agent": user_agent}
        self._client = httpx.Client(timeout=timeout, headers=headers)
        self._csrf_token: str | None = None
        self._last_request_time: float = 0.0

        logger.debug(f"MediaWiki client initialized: api_url={api_url}, user_agent={user_agent}")

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
        elapsed = self.clock.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            self.clock.sleep(sleep_time)
        self._last_request_time = self.clock.time()

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
        # Add format=json and a server-friendly maxlag to every request.
        params["format"] = "json"
        if "maxlag" not in params:
            params["maxlag"] = str(self.request_policy.maxlag)
        policy = self.request_policy
        response = None
        result: dict[str, Any] | None = None
        json_error: Exception | None = None
        for attempt in range(policy.max_retries + 1):
            self._rate_limit()
            try:
                if method == "GET":
                    response = self._client.get(self.api_url, params=params)
                else:
                    response = self._client.post(self.api_url, params=params, data=data)
            except httpx.TimeoutException as e:
                logger.error(f"MediaWiki API request timeout: {e}")
                raise MediaWikiNetworkError(f"Request timeout: {e}") from e
            except httpx.NetworkError as e:
                logger.error(f"MediaWiki API network error: {e}")
                raise MediaWikiNetworkError(f"Network error: {e}") from e
            status_code = response.status_code if isinstance(response.status_code, int) else 200
            try:
                result = response.json()
                json_error = None
            except Exception as e:
                result = None
                json_error = e
            delay = retry_delay_for(
                status_code=status_code,
                headers=response.headers,
                payload=result if isinstance(result, dict) else {},
                text=response.text if isinstance(getattr(response, "text", None), str) else "",
                attempt=attempt,
                policy=policy,
            )
            if delay is None:
                break
            if attempt >= policy.max_retries:
                logger.warning(f"MediaWiki request exhausted {policy.max_retries} retries (status {status_code})")
                raise MediaWikiRateLimitError(f"MediaWiki request exhausted retries after {attempt + 1} attempts")
            logger.warning(f"MediaWiki transient response (status {status_code}); retrying in {delay:.1f}s")
            self.clock.sleep(delay)
        assert response is not None  # the retry loop always runs at least once
        # Surface non-retryable HTTP failures (4xx/5xx that are not lag or rate limit).
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"MediaWiki API HTTP error: {e.response.status_code}")
            raise MediaWikiNetworkError(f"HTTP {e.response.status_code}: {e}") from e
        if result is None:
            logger.error(f"Failed to parse MediaWiki API response: {json_error}")
            raise MediaWikiAPIError(f"Invalid JSON response: {json_error}") from json_error
        # Check for API errors
        if "error" in result:
            error_code = result["error"].get("code", "unknown")
            error_info = result["error"].get("info", "Unknown error")
            logger.error(f"MediaWiki API error: {error_code} - {error_info}")
            if error_code in ("badtoken", "notoken"):
                # Token expired, clear cached token
                self._csrf_token = None
            raise MediaWikiAPIError(f"API error ({error_code}): {error_info}", code=error_code, info=error_info)
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

    def get_current_user_rights(
        self,
        assertion: Literal["user", "bot"] = "user",
        assert_user: str | None = None,
    ) -> frozenset[str]:
        """Return rights for the authenticated API session's current user.

        The assertion parameters are sent to MediaWiki so a privileged caller
        cannot accidentally preflight a different account.  The response is
        validated strictly because this check gates interface-admin writes.
        """
        if assertion not in ("user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")

        params: dict[str, Any] = {
            "action": "query",
            "meta": "userinfo",
            "uiprop": "rights",
            "assert": assertion,
        }
        if assert_user is not None:
            params["assertuser"] = assert_user

        result = self._request(params)
        query = result.get("query")
        if not isinstance(query, dict):
            raise MediaWikiAPIError(f"Invalid user rights response: missing query object: {result}")
        userinfo = query.get("userinfo")
        if not isinstance(userinfo, dict):
            raise MediaWikiAPIError(f"Invalid user rights response: missing userinfo object: {result}")
        rights = userinfo.get("rights")
        if not isinstance(rights, list) or not all(isinstance(right, str) and right for right in rights):
            raise MediaWikiAPIError(
                f"Invalid user rights response: rights must be a list of non-empty strings: {result}"
            )
        return frozenset(rights)

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

    def expand_templates(self, text: str) -> str:
        """Expand wikitext through the parser and return the rendered result.
        Used to resolve what a template or module invocation produces, e.g. the
        generated value of an infobox field with no override applied.
        """
        result = self._request({"action": "expandtemplates", "text": text, "prop": "wikitext"})
        expanded = result.get("expandtemplates", {})
        wikitext = expanded.get("wikitext", "")
        return wikitext if isinstance(wikitext, str) else ""

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

    def get_page_snapshots(
        self,
        titles: Sequence[str],
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> dict[str, MediaWikiPageSnapshot]:
        """Fetch page source and its guarding revision in one API query per batch.

        ``start_timestamp`` is MediaWiki's ``curtimestamp`` from the same response
        as each page's source and revision. Missing pages are represented by a
        snapshot whose ``source_text`` and ``revision`` are ``None``.
        """
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")
        if not titles:
            return {}

        snapshots: dict[str, MediaWikiPageSnapshot] = {}
        for i in range(0, len(titles), self.batch_size):
            batch = titles[i : i + self.batch_size]
            params: dict[str, Any] = {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "revisions",
                "rvprop": "ids|timestamp|content|contentmodel",
                "rvslots": "main",
                "curtimestamp": "1",
            }
            if assertion is not None:
                params["assert"] = assertion
            if assert_user is not None:
                params["assertuser"] = assert_user

            result = self._request(params)
            start_timestamp = result.get("curtimestamp")
            if not isinstance(start_timestamp, str) or not start_timestamp:
                raise MediaWikiAPIError("Missing curtimestamp while fetching page snapshots")

            pages = result.get("query", {}).get("pages", {})
            if not isinstance(pages, dict):
                raise MediaWikiAPIError("Invalid page snapshot response")
            pages_by_title = {
                page.get("title"): page
                for page in pages.values()
                if isinstance(page, dict) and isinstance(page.get("title"), str)
            }
            for requested_title in batch:
                page = pages_by_title.get(requested_title)
                if page is None:
                    snapshots[requested_title] = MediaWikiPageSnapshot(
                        title=requested_title,
                        source_text=None,
                        revision=None,
                        start_timestamp=start_timestamp,
                    )
                    continue

                page_id_value = page.get("pageid")
                page_id = int(page_id_value) if page_id_value is not None else None
                page_title = str(page.get("title", requested_title))
                if page_id is None or page_id < 0 or page.get("missing") is True:
                    snapshots[requested_title] = MediaWikiPageSnapshot(
                        title=page_title,
                        source_text=None,
                        revision=None,
                        start_timestamp=start_timestamp,
                    )
                    continue

                try:
                    raw_revision = page["revisions"][0]
                    revision_id = int(raw_revision["revid"])
                    revision_timestamp = str(raw_revision["timestamp"])
                    revision_content_model = raw_revision.get("contentmodel", page.get("contentmodel"))
                    if revision_content_model is not None and not isinstance(revision_content_model, str):
                        raise TypeError("contentmodel is not text")
                    source_text = raw_revision["slots"]["main"]["*"]
                    if not isinstance(source_text, str):
                        raise TypeError("revision source is not text")
                    revision = MediaWikiPageRevision(
                        title=page_title,
                        page_id=int(page.get("pageid", page_id)),
                        revision_id=revision_id,
                        timestamp=revision_timestamp,
                        start_timestamp=start_timestamp,
                    )
                except (KeyError, IndexError, TypeError, ValueError) as e:
                    raise MediaWikiAPIError(f"Invalid page snapshot response for '{requested_title}': {e}") from e
                snapshots[requested_title] = MediaWikiPageSnapshot(
                    title=page_title,
                    source_text=source_text,
                    revision=revision,
                    start_timestamp=start_timestamp,
                    content_model=revision_content_model,
                )

        return snapshots

    def null_edit_pages(
        self,
        titles: Sequence[str],
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        """Reparse existing pages with unchanged wikitext so Cargo rows refresh."""
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")
        pages = self.get_pages(titles)
        refreshed: list[str] = []
        for title in titles:
            content = pages.get(title)
            if content is None:
                raise MediaWikiAPIError(f"Cannot null-edit missing page: {title}")
            self.edit_page(
                title,
                content,
                summary="Refresh item-owned Cargo rows",
                bot=True,
                no_create=True,
                assertion=assertion,
                assert_user=assert_user,
            )
            refreshed.append(title)
        return tuple(refreshed)

    def get_embeddedin_pages(
        self,
        title: str,
        namespaces: Sequence[int] = (0,),
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        """Return pages that transclude the given page via MediaWiki embeddedin."""
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")

        params = {
            "action": "query",
            "list": "embeddedin",
            "eititle": title,
            "eilimit": "max",
        }
        if namespaces:
            params["einamespace"] = "|".join(str(namespace) for namespace in namespaces)
        if assertion is not None:
            params["assert"] = assertion
        if assert_user is not None:
            params["assertuser"] = assert_user

        pages: list[str] = []
        continue_params: dict[str, str] = {}
        while True:
            result = self._request(params | continue_params)
            for page in result.get("query", {}).get("embeddedin", []):
                page_title = page.get("title")
                if isinstance(page_title, str):
                    pages.append(page_title)

            continuation = result.get("continue")
            if not isinstance(continuation, dict):
                break
            continue_params = {key: str(value) for key, value in continuation.items()}

        return tuple(pages)

    def purge_pages(
        self,
        titles: Sequence[str],
        force_link_update: bool = True,
        force_recursive_link_update: bool = False,
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        """Purge pages, forcing a synchronous link/Cargo table update by default.
        A template or module change does not refresh the pages that transclude
        it; their stored link, category, and Cargo data stay stale until each
        dependent page is reparsed. ``action=purge`` with ``forcelinkupdate``
        runs that reparse and LinksUpdate synchronously, which is the reliable
        way to refresh dependents (a no-op edit performs no save and no update).
        """
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")
        if not titles:
            return ()
        purged: list[str] = []
        for i in range(0, len(titles), self.batch_size):
            batch = titles[i : i + self.batch_size]
            data = {"action": "purge", "titles": "|".join(batch)}
            if force_link_update:
                data["forcelinkupdate"] = "1"
            if force_recursive_link_update:
                data["forcerecursivelinkupdate"] = "1"
            if assertion is not None:
                data["assert"] = assertion
            if assert_user is not None:
                data["assertuser"] = assert_user
            data["token"] = self.get_csrf_token()
            result = self._request({}, method="POST", data=data)
            for entry in result.get("purge", []):
                page_title = entry.get("title")
                if "purged" in entry and isinstance(page_title, str):
                    purged.append(page_title)
        logger.info(f"Purged {len(purged)} pages (force_link_update={force_link_update})")
        return tuple(purged)

    def delete_page(
        self,
        title: str,
        reason: str,
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> dict[str, Any]:
        """Delete a wiki page through the Action API and return the delete payload."""
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")
        data = {
            "action": "delete",
            "title": title,
            "token": self.get_csrf_token(),
            "reason": reason,
            "formatversion": "2",
        }
        if assertion is not None:
            data["assert"] = assertion
        if assert_user is not None:
            data["assertuser"] = assert_user
        result = self._request({}, method="POST", data=data)
        delete_result = result.get("delete", {})
        if not isinstance(delete_result, dict):
            raise MediaWikiAPIError(f"Invalid delete response for '{title}': {result}")
        return delete_result

    def recreate_cargo_tables(
        self,
        template: str,
        create_replacement: bool = False,
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> dict[str, Any]:
        """Run Cargo's schema recreation API for all tables associated with a template."""
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")
        data: dict[str, Any] = {
            "action": "cargorecreatetables",
            "template": template,
            "token": self.get_csrf_token(),
            "formatversion": "2",
        }
        if create_replacement:
            data["createReplacement"] = "1"
        if assertion is not None:
            data["assert"] = assertion
        if assert_user is not None:
            data["assertuser"] = assert_user
        return self._request({}, method="POST", data=data)

    def recreate_cargo_data(
        self,
        template: str,
        table: str,
        replace_old_rows: bool = True,
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> dict[str, Any]:
        """Enqueue Cargo row recreation jobs for one owning template/table pair."""
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")
        data: dict[str, Any] = {
            "action": "cargorecreatedata",
            "template": template,
            "table": table,
            "token": self.get_csrf_token(),
            "formatversion": "2",
        }
        if replace_old_rows:
            data["replaceOldRows"] = "1"
        if assertion is not None:
            data["assert"] = assertion
        if assert_user is not None:
            data["assertuser"] = assert_user
        return self._request({}, method="POST", data=data)

    def query_cargo_table(
        self,
        tables: str,
        fields: str,
        where: str | None = None,
        limit: int = 50,
        offset: int | None = None,
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a Cargo query and return the raw ``cargoquery`` rows."""
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")
        params: dict[str, Any] = {
            "action": "cargoquery",
            "tables": tables,
            "fields": fields,
            "limit": str(limit),
            "formatversion": "2",
        }
        if where is not None:
            params["where"] = where
        if offset is not None:
            params["offset"] = str(offset)
        if assertion is not None:
            params["assert"] = assertion
        if assert_user is not None:
            params["assertuser"] = assert_user
        result = self._request(params)
        rows = result.get("cargoquery", [])
        if not isinstance(rows, list):
            raise MediaWikiAPIError(f"Invalid Cargo query response: {result}")
        return rows

    def get_page_revision_metadata(
        self,
        title: str,
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> MediaWikiPageRevision | None:
        """Fetch current page revision metadata and API start timestamp.

        The returned ``start_timestamp`` is MediaWiki's ``curtimestamp`` value and
        must be sent back on safe edit requests to make stale deployment reads
        fail closed.
        """
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")

        logger.debug(f"Fetching revision metadata for page: {title}")

        params = {
            "action": "query",
            "titles": title,
            "prop": "revisions",
            "rvprop": "ids|timestamp",
            "curtimestamp": "1",
        }
        if assertion is not None:
            params["assert"] = assertion
        if assert_user is not None:
            params["assertuser"] = assert_user

        result = self._request(params)
        start_timestamp = result.get("curtimestamp")
        if not isinstance(start_timestamp, str) or not start_timestamp:
            raise MediaWikiAPIError(f"Missing curtimestamp while fetching revision metadata for '{title}'")

        pages = result.get("query", {}).get("pages", {})
        if not pages:
            raise MediaWikiAPIError(f"No page data returned while fetching revision metadata for '{title}'")

        page_id_text = next(iter(pages.keys()))
        page = pages[page_id_text]
        page_id = int(page_id_text)
        if page_id < 0 or page.get("missing") is True:
            logger.debug(f"Page doesn't exist while fetching revision metadata: {title}")
            return None

        try:
            revision = page["revisions"][0]
            revision_id = int(revision["revid"])
            revision_timestamp = str(revision["timestamp"])
            revision_title = str(page["title"])
            revision_page_id = int(page.get("pageid", page_id))
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise MediaWikiAPIError(f"Invalid revision metadata response for '{title}': {e}") from e

        return MediaWikiPageRevision(
            title=revision_title,
            page_id=revision_page_id,
            revision_id=revision_id,
            timestamp=revision_timestamp,
            start_timestamp=start_timestamp,
        )

    def get_edit_start_timestamp(
        self,
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> str:
        """Fetch MediaWiki's current API timestamp for conflict-safe page creation."""
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")

        params = {
            "action": "query",
            "curtimestamp": "1",
        }
        if assertion is not None:
            params["assert"] = assertion
        if assert_user is not None:
            params["assertuser"] = assert_user

        result = self._request(params)
        start_timestamp = result.get("curtimestamp")
        if not isinstance(start_timestamp, str) or not start_timestamp:
            raise MediaWikiAPIError("Missing curtimestamp while fetching edit start timestamp")
        return start_timestamp

    def edit_page(
        self,
        title: str,
        content: str,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        create_only: bool = False,
        no_create: bool = False,
        assertion: Literal["user", "bot"] | None = None,
        assert_user: str | None = None,
    ) -> None:
        """Edit a wiki page with new content.

        Requires authentication (call login() first). Uses CSRF token for security.

        Args:
            title: Page title to edit.
            content: New page content (wikitext).
            summary: Edit summary (defaults to self.edit_summary).
            minor: Mark as minor edit (defaults to self.minor_edit).
            bot: Mark as bot edit (requires bot permissions).
            create_only: Only create page if it doesn't exist (fails if page exists).
            no_create: Only edit existing page (fails if page doesn't exist).
            assertion: Require the API session to be logged in as this user or bot.
            assert_user: Require this exact username for the API session.

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

        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")
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
        if bot:
            data["bot"] = "1"
        if create_only:
            data["createonly"] = "1"
        if no_create:
            data["nocreate"] = "1"
        if assertion is not None:
            data["assert"] = assertion
        if assert_user is not None:
            data["assertuser"] = assert_user

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

    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: Literal["user", "bot"] = "bot",
        assert_user: str | None = None,
        content_model: str | None = None,
    ) -> int:
        """Edit an existing page with conflict, timestamp, hash, and user guards."""
        if assertion not in ("user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")

        if summary is None:
            summary = self.edit_summary
        if minor is None:
            minor = self.minor_edit

        logger.info(f"Safely editing page: {title} at base revision {base_revision.revision_id}")

        data = {
            "action": "edit",
            "title": title,
            "text": content,
            "summary": summary,
            "baserevid": str(base_revision.revision_id),
            "starttimestamp": base_revision.start_timestamp,
            "md5": hashlib.md5(content.encode(), usedforsecurity=False).hexdigest(),
            "assert": assertion,
        }
        if assert_user is not None:
            data["assertuser"] = assert_user
        if content_model is not None:
            if content_model not in {"css", "javascript", "json", "vue", "wikitext"}:
                raise ValueError(f"unsupported content model: {content_model}")
            data["contentmodel"] = content_model
        if minor:
            data["minor"] = "1"
        if bot:
            data["bot"] = "1"

        last_error: MediaWikiAPIError | None = None
        for attempt in range(2):
            data["token"] = self.get_csrf_token()
            try:
                result = self._request({}, method="POST", data=data.copy())
            except MediaWikiAPIError as e:
                last_error = e
                if attempt == 0 and self._is_token_error(e):
                    logger.warning(f"CSRF token rejected while safely editing {title}; refreshing once")
                    continue
                logger.error(f"Safe edit request failed for {title}: {e}")
                self._raise_safe_write_api_error(title, e, "editing")

            edit_result = result.get("edit", {})
            if edit_result.get("result") != "Success":
                error = edit_result.get("error", "Unknown error")
                logger.error(f"Safe edit failed for {title}: {error}")
                raise MediaWikiEditError(f"Safe edit failed: {error}")

            if "nochange" in edit_result:
                logger.info(
                    f"Safe edit was a no-op for {title}; content already at revision {base_revision.revision_id}"
                )
                return base_revision.revision_id
            try:
                new_revision_id = int(edit_result["newrevid"])
            except (KeyError, TypeError, ValueError) as e:
                raise MediaWikiEditError(f"Safe edit response for '{title}' did not include newrevid") from e

            logger.info(f"Successfully safely edited page: {title} -> revision {new_revision_id}")
            return new_revision_id

        raise MediaWikiEditError(f"Failed to safely edit page '{title}': {last_error}")

    def safe_create_page(
        self,
        title: str,
        content: str,
        start_timestamp: str,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: Literal["user", "bot"] = "bot",
        assert_user: str | None = None,
        content_model: str | None = None,
    ) -> int:
        """Create a missing page with timestamp, hash, assertion, and create-only guards."""
        if assertion not in ("user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")

        if summary is None:
            summary = self.edit_summary
        if minor is None:
            minor = self.minor_edit

        logger.info(f"Safely creating page: {title}")

        data = {
            "action": "edit",
            "title": title,
            "text": content,
            "summary": summary,
            "createonly": "1",
            "starttimestamp": start_timestamp,
            "md5": hashlib.md5(content.encode(), usedforsecurity=False).hexdigest(),
            "assert": assertion,
        }
        if assert_user is not None:
            data["assertuser"] = assert_user
        if content_model is not None:
            if content_model not in {"css", "javascript", "json", "vue", "wikitext"}:
                raise ValueError(f"unsupported content model: {content_model}")
            data["contentmodel"] = content_model
        if minor:
            data["minor"] = "1"
        if bot:
            data["bot"] = "1"

        last_error: MediaWikiAPIError | None = None
        for attempt in range(2):
            data["token"] = self.get_csrf_token()
            try:
                result = self._request({}, method="POST", data=data.copy())
            except MediaWikiAPIError as e:
                last_error = e
                if attempt == 0 and self._is_token_error(e):
                    logger.warning(f"CSRF token rejected while safely creating {title}; refreshing once")
                    continue
                logger.error(f"Safe create request failed for {title}: {e}")
                self._raise_safe_write_api_error(title, e, "creating")

            edit_result = result.get("edit", {})
            if edit_result.get("result") != "Success":
                error = edit_result.get("error", "Unknown error")
                logger.error(f"Safe create failed for {title}: {error}")
                raise MediaWikiEditError(f"Safe create failed: {error}")

            try:
                new_revision_id = int(edit_result["newrevid"])
            except (KeyError, TypeError, ValueError) as e:
                raise MediaWikiEditError(f"Safe create response for '{title}' did not include newrevid") from e

            logger.info(f"Successfully safely created page: {title} -> revision {new_revision_id}")
            return new_revision_id

        raise MediaWikiEditError(f"Failed to safely create page '{title}': {last_error}")

    @staticmethod
    def _is_token_error(error: MediaWikiAPIError) -> bool:
        """Return whether an API error came from a rejected edit token."""
        return error.code in ("badtoken", "notoken")

    @staticmethod
    def _raise_safe_write_api_error(title: str, error: MediaWikiAPIError, operation: str) -> NoReturn:
        """Raise a safe-write-specific exception for known MediaWiki edit failures.
        ``operation`` is the present participle of the attempted action
        (``"editing"`` or ``"creating"``) so the surfaced message names what
        actually failed.
        """
        if error.code == "editconflict":
            raise MediaWikiEditConflictError(
                f"Edit conflict while safely {operation} page '{title}': {error}"
            ) from error
        if error.code == "articleexists":
            raise MediaWikiEditConflictError(
                f"Lost create race while safely {operation} page '{title}': {error}"
            ) from error
        if error.code in ("assertuserfailed", "assertbotfailed", "assertnameduserfailed"):
            raise MediaWikiAssertionError(
                f"Assertion failed while safely {operation} page '{title}': {error}"
            ) from error
        if error.code in ("permissiondenied", "protectedpage", "cantcreate", "noedit"):
            raise MediaWikiPermissionError(
                f"Permission denied while safely {operation} page '{title}': {error}"
            ) from error
        raise MediaWikiEditError(f"Failed while safely {operation} page '{title}': {error}") from error

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
        from datetime import datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(days=days)
        rc_start = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "action": "query",
            "list": "recentchanges",
            "rcstart": rc_start,
            "rcprop": "title|timestamp",  # Get both title and timestamp
            "rclimit": min(limit, 500),  # API max is 500
            "rctype": "edit|new",  # Only edits and new pages, not logs
            # No rcshow parameter = include ALL edits (bot, minor, anon, everything)
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

    def upload_file(
        self,
        file_path: str,
        filename: str,
        comment: str,
        text: str = "",
        ignore_warnings: bool = False,
        bot: bool = True,
    ) -> dict[str, Any]:
        """Upload a file to the wiki.

        Requires authentication (call login() first). Uses CSRF token for security.

        Args:
            file_path: Path to the file on disk.
            filename: Target filename on wiki (e.g., "Sword.png").
            comment: Upload comment/summary.
            text: Wiki text for the file description page.
            ignore_warnings: Ignore API warnings (e.g., duplicate files).
            bot: Mark as bot upload (requires bot permissions).

        Returns:
            API response dict containing upload result.

        Raises:
            MediaWikiAPIError: If upload fails or not authenticated.
            FileNotFoundError: If file_path doesn't exist.

        Example:
            >>> client = MediaWikiClient(
            ...     api_url="https://erenshor.wiki.gg/api.php",
            ...     bot_username="MyBot@MyBot",
            ...     bot_password="secret"
            ... )
            >>> client.login()
            >>> client.upload_file(
            ...     file_path="/path/to/sword.png",
            ...     filename="Sword.png",
            ...     comment="Upload sword icon",
            ...     text="{{ImageMetadata|type=item}}"
            ... )
        """

        # Check file exists
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Uploading file: {file_path} → File:{filename}")

        # Get CSRF token
        token = self.get_csrf_token()

        # Prepare upload data
        data = {
            "action": "upload",
            "filename": filename,
            "comment": comment,
            "text": text,
            "token": token,
            "format": "json",
        }

        if ignore_warnings:
            data["ignorewarnings"] = "1"

        if bot:
            data["bot"] = "1"

        # Open file and upload
        try:
            with Path(file_path).open("rb") as f:
                files = {"file": (filename, f, "image/png")}

                # Use httpx's files parameter for multipart upload
                response = self._client.post(
                    self.api_url,
                    data=data,
                    files=files,
                )
                response.raise_for_status()
                result: dict[str, Any] = response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during upload: {e.response.status_code}")
            raise MediaWikiAPIError(f"HTTP {e.response.status_code} during file upload") from e

        except httpx.RequestError as e:
            logger.error(f"Network error during upload: {e}")
            raise MediaWikiNetworkError(f"Network error during upload: {e}") from e

        # Check for API errors
        if "error" in result:
            error_info = result["error"]
            error_code = error_info.get("code", "unknown")
            error_text = error_info.get("info", "Unknown error")
            logger.error(f"Upload API error: {error_code} - {error_text}")
            raise MediaWikiAPIError(f"Upload failed ({error_code}): {error_text}")

        # Check upload result
        upload_result: dict[str, Any] = result.get("upload", {})
        if upload_result.get("result") != "Success":
            # Handle warnings
            if "warnings" in upload_result and not ignore_warnings:
                warnings = upload_result["warnings"]
                logger.error(f"Upload warnings: {warnings}")
                raise MediaWikiAPIError(f"Upload warnings: {warnings}")

            logger.error(f"Unexpected upload response: {result}")
            raise MediaWikiAPIError(f"Unexpected upload response: {result}")

        logger.info(f"Successfully uploaded: File:{filename}")
        return upload_result
