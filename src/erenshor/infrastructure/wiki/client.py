"""MediaWiki API client for fetching and publishing wiki pages.

This module provides a Python client for interacting with MediaWiki's API,
enabling programmatic management of wiki content.

Features:
- Login with bot credentials
- Fetch page content by title
- Batch fetch multiple pages efficiently
- Edit and create pages with revision, timestamp, and assertion guards
- CSRF token management
- Rate limiting to avoid API throttling
- Comprehensive error handling

The MediaWikiClient class provides a type-safe, testable interface for wiki
operations, designed to work with wiki.gg (https://erenshor.wiki.gg).
"""

import hashlib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NoReturn

import httpx
from loguru import logger

from erenshor.infrastructure.time import Clock, RealClock
from erenshor.infrastructure.wiki.rate_limit import (
    MediaWikiRequestor,
    MediaWikiRequestPolicy,
    MediaWikiRetryableRequestError,
    MediaWikiUnretryableRequestError,
    RateLimit,
)


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


class MediaWikiUploadWarningError(MediaWikiAPIError):
    """Raised when MediaWiki answers an upload with warnings instead of storing it.

    ``warnings`` maps each warning, such as ``exists`` or ``duplicate``, to its
    detail. ``filekey`` names the stashed upload, which ``confirm_upload`` can
    publish without sending the file again, or is None when MediaWiki stashed
    nothing.
    """

    def __init__(self, warnings: Mapping[str, Any], filekey: str | None = None) -> None:
        super().__init__(f"Upload warnings: {dict(warnings)}", code="warnings")
        self.warnings = dict(warnings)
        self.filekey = filekey


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
    """Revision metadata used to guard conflict-safe MediaWiki edits.

    ``user`` is the account that made the revision, or None when MediaWiki
    hides it.
    """

    title: str
    page_id: int
    revision_id: int
    timestamp: str
    start_timestamp: str
    user: str | None


@dataclass(frozen=True, slots=True)
class MediaWikiPageSnapshot:
    """Page source and revision metadata from one revision-bound query."""

    title: str
    source_text: str | None
    revision: MediaWikiPageRevision | None
    start_timestamp: str
    content_model: str | None = None


@dataclass(frozen=True, slots=True)
class MediaWikiTitleStatus:
    """Existence and redirect metadata for one requested wiki title."""

    requested: str
    normalized: str
    redirect_target: str | None
    exists: bool


@dataclass(frozen=True, slots=True)
class MediaWikiFileUpload:
    """The current upload of a file: the file's final title after redirects, its uploader, and its SHA-1."""

    title: str
    user: str
    sha1: str


@dataclass(frozen=True, slots=True)
class MediaWikiFile:
    """The current version of an uploaded file.

    ``title`` carries the ``File:`` namespace and uses spaces. ``user`` and
    ``comment`` are None when MediaWiki hides them.
    """

    title: str
    sha1: str
    user: str | None
    comment: str | None
    size: int
    width: int
    height: int
    timestamp: str
    url: str


@dataclass(frozen=True, slots=True)
class MediaWikiFileVersion:
    """One version in a file's history, newest first in a listing."""

    sha1: str
    user: str | None
    comment: str | None
    timestamp: str
    url: str


@dataclass(frozen=True, slots=True)
class MediaWikiFilePages:
    """The pages of the File namespace.

    ``redirects`` maps each redirect page to the page it names. MediaWiki
    shows a file through one file redirect only, so a redirect to another
    redirect shows nothing. ``pages`` holds every other existing page, with or
    without an uploaded file.
    """

    redirects: Mapping[str, str]
    pages: frozenset[str]


@dataclass(frozen=True, slots=True)
class _ResolvedTitle:
    """A requested title with its normalized form, redirect targets, and the final page of a query.

    ``redirect_target`` is the final page of a redirect chain and ``first_target``
    the page that the redirect names.
    """

    requested: str
    normalized: str
    redirect_target: str | None
    page: dict[str, Any]
    first_target: str | None = None


@dataclass(frozen=True, slots=True)
class MediaWikiParsedLink:
    """A page that a parsed text uses: a transcluded template or module, or a category."""

    title: str
    exists: bool


@dataclass(frozen=True, slots=True)
class MediaWikiParse:
    """What MediaWiki reports when it parses a text under a title.

    Category titles carry the ``Category:`` namespace and use spaces.
    """

    html: str
    templates: tuple[MediaWikiParsedLink, ...]
    categories: tuple[MediaWikiParsedLink, ...]


def _revision_user(raw_revision: dict[str, Any]) -> str | None:
    """Return the account that made a revision, or None when MediaWiki hides it."""
    if "userhidden" in raw_revision:
        return None
    user = raw_revision["user"]
    if not isinstance(user, str) or not user:
        raise TypeError("revision user is not text")
    return user


def _hidden_or_text(entry: Mapping[str, Any], key: str) -> str | None:
    """Return a text field of a file entry, or None when MediaWiki hides it."""
    if f"{key}hidden" in entry:
        return None
    value = entry.get(key)
    if not isinstance(value, str):
        raise MediaWikiAPIError(f"Invalid file response: missing {key}")
    return value


def _file_version(entry: object, title: str) -> MediaWikiFileVersion:
    """Read one version of a file from an ``imageinfo`` or ``allimages`` entry."""
    if not isinstance(entry, dict):
        raise MediaWikiAPIError(f"Invalid file response for {title!r}: malformed version")
    sha1, timestamp, url = entry.get("sha1"), entry.get("timestamp"), entry.get("url")
    if not isinstance(sha1, str) or not sha1 or not isinstance(timestamp, str) or not isinstance(url, str):
        raise MediaWikiAPIError(f"Invalid file response for {title!r}: missing hash, time, or URL")
    return MediaWikiFileVersion(
        sha1=sha1,
        user=_hidden_or_text(entry, "user"),
        comment=_hidden_or_text(entry, "comment"),
        timestamp=timestamp,
        url=url,
    )


def _listed_file(entry: object) -> MediaWikiFile:
    """Read the current version of a file from an ``allimages`` entry."""
    if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
        raise MediaWikiAPIError("Invalid file listing response: malformed file")
    title = entry["title"]
    version = _file_version(entry, title)
    size, width, height = entry.get("size"), entry.get("width"), entry.get("height")
    if type(size) is not int or type(width) is not int or type(height) is not int:
        raise MediaWikiAPIError(f"Invalid file listing response for {title!r}: missing size")
    return MediaWikiFile(
        title=title,
        sha1=version.sha1,
        user=version.user,
        comment=version.comment,
        size=size,
        width=width,
        height=height,
        timestamp=version.timestamp,
        url=version.url,
    )


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

        >>> # Edit a page against the revision it was read at
        >>> revision = client.get_page_revision_metadata("Item:Sword", assertion="bot")
        >>> client.safe_edit_page(
        ...     title="Item:Sword",
        ...     content="{{Item|name=Sword|damage=10}}",
        ...     base_revision=revision,
        ...     summary="Update item stats from database"
        ... )
    """

    def __init__(
        self,
        api_url: str,
        bot_username: str = "",
        bot_password: str = "",
        batch_size: int = 25,
        edit_summary: str = "Automated wiki update",
        minor_edit: bool = True,
        timeout: float = 30.0,
        clock: Clock | None = None,
        request_policy: MediaWikiRequestPolicy | None = None,
        user_agent: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Initialize MediaWiki API client.

        Args:
            api_url: Full URL to MediaWiki API endpoint (must end with /api.php).
            bot_username: Bot account username (format: "BotName@BotName").
            bot_password: Bot account password (bot password from Special:BotPasswords).
            batch_size: Number of pages to fetch per batch request (max 50).
            edit_summary: Default edit summary for page updates.
            minor_edit: Whether edits should be marked as minor by default.
            timeout: HTTP request timeout in seconds.
            clock: Clock implementation for time operations (default: RealClock()).
            request_policy: Bounded retry/backoff policy for transient lag and
                rate-limit responses (default: MediaWikiRequestPolicy()).
            user_agent: User-Agent header for API requests when set.

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
        self.edit_summary = edit_summary
        self.minor_edit = minor_edit
        self.timeout = timeout
        self.clock = clock if clock is not None else RealClock()
        self.request_policy = request_policy if request_policy is not None else MediaWikiRequestPolicy()

        user_agent = user_agent or f"{bot_username or 'ErenshorDataBot'}/0.3 (automated wiki updates) httpx"
        self._requestor = MediaWikiRequestor(
            api_url=api_url,
            policy=self.request_policy,
            transport=transport,
            timeout=timeout,
            user_agent=user_agent,
            # Client response parsers rely on the legacy Action API shape.
            formatversion=None,
            clock=self.clock,
        )
        self._csrf_token: str | None = None
        self._closed = False

        logger.debug(f"MediaWiki client initialized: api_url={api_url}, user_agent={user_agent}")

    def __enter__(self) -> "MediaWikiClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit - closes HTTP client."""
        self.close()

    def close(self) -> None:
        """Close the owned requestor and its HTTP client exactly once."""
        if not self._closed:
            self._requestor.close()
            self._closed = True
        logger.debug("MediaWiki client closed")

    @property
    def requestor(self) -> MediaWikiRequestor:
        """Return the borrowed request capability for specialized adapters."""
        return self._requestor

    @property
    def edit_account(self) -> str:
        """Return the account that MediaWiki records for the edits of this client.

        A bot-password login name is ``<account>@<bot name>``, and MediaWiki
        records its edits under ``<account>``. A user name reads underscores as
        spaces and starts with a capital letter.
        """
        account = self.bot_username.split("@", 1)[0].replace("_", " ").strip()
        return account[:1].upper() + account[1:]

    def _request(
        self,
        params: dict[str, Any],
        method: str = "GET",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request through the shared requestor policy."""
        # Add format=json and a server-friendly maxlag to every request, as the
        # legacy client did.  The requestor deliberately leaves formatversion
        # untouched so these parsers continue receiving Action API v1 payloads.
        params = dict(params)
        params["format"] = "json"
        params.setdefault("maxlag", str(self.request_policy.maxlag))
        try:
            if method == "GET":
                return self._requestor.get(params)
            return self._requestor.post(params, data=data)
        except httpx.TimeoutException as e:
            logger.error(f"MediaWiki API request timeout: {e}")
            raise MediaWikiNetworkError(f"Request timeout: {e}") from e
        except httpx.NetworkError as e:
            logger.error(f"MediaWiki API network error: {e}")
            raise MediaWikiNetworkError(f"Network error: {e}") from e
        except MediaWikiRetryableRequestError as e:
            logger.warning(f"MediaWiki request retries exhausted: {e}")
            attempts = e.attempts or (self.request_policy.max_retries + 1)
            raise MediaWikiRateLimitError(f"MediaWiki request exhausted retries after {attempts} attempts") from e
        except MediaWikiUnretryableRequestError as e:
            if e.code is not None:
                if e.code in ("badtoken", "notoken"):
                    self._csrf_token = None
                info = e.info
                if info == "unknown MediaWiki API error":
                    info = "Unknown error"
                raise MediaWikiAPIError(str(e), code=e.code, info=info) from e
            raise MediaWikiNetworkError(str(e)) from e
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to parse MediaWiki API response: {e}")
            raise MediaWikiAPIError(f"Invalid JSON response: {e}") from e

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
            self._load_rate_limits()

        except MediaWikiAPIError as e:
            logger.error(f"Login request failed: {e}")
            raise MediaWikiAuthenticationError(f"Login failed: {e}") from e

    def _load_rate_limits(self) -> None:
        """Read the logged-in account's rate limits and rights."""
        result = self._request({"action": "query", "meta": "userinfo", "uiprop": "ratelimits|rights", "assert": "user"})
        query = result.get("query")
        userinfo = query.get("userinfo") if isinstance(query, dict) else None
        if not isinstance(userinfo, dict):
            raise MediaWikiAuthenticationError("Invalid userinfo response: missing account")
        rights = userinfo.get("rights")
        if not isinstance(rights, list) or not all(isinstance(right, str) for right in rights):
            raise MediaWikiAuthenticationError("Invalid userinfo response: missing rights")
        limits: dict[str, RateLimit] = {}
        if "noratelimit" not in rights:
            raw_limits = userinfo.get("ratelimits")
            if not isinstance(raw_limits, dict):
                raise MediaWikiAuthenticationError("Invalid userinfo response: missing rate limits")
            for action, buckets in raw_limits.items():
                if not isinstance(action, str) or not isinstance(buckets, dict):
                    raise MediaWikiAuthenticationError("Invalid userinfo response: invalid rate limits")
                for bucket in buckets.values():
                    if not isinstance(bucket, dict):
                        raise MediaWikiAuthenticationError("Invalid userinfo response: invalid rate limit bucket")
                    hits, seconds = bucket.get("hits"), bucket.get("seconds")
                    if type(hits) is not int or type(seconds) is not int or hits <= 0 or seconds <= 0:
                        raise MediaWikiAuthenticationError("Invalid userinfo response: invalid rate limit bucket")
                    candidate = RateLimit(hits=hits, seconds=seconds)
                    current = limits.get(action)
                    if current is None or candidate.seconds / candidate.hits > current.seconds / current.hits:
                        limits[action] = candidate
        self._requestor.set_rate_limits(limits)
        name = userinfo.get("name", self.edit_account)
        summary = ", ".join(f"{action} {limit.hits}/{limit.seconds}s" for action, limit in sorted(limits.items()))
        logger.info(f"Rate limits for {name}: {summary or 'none'}")

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

        query = result.get("query")
        pages = query.get("pages") if isinstance(query, dict) else None
        if not isinstance(pages, dict) or len(pages) != 1:
            raise MediaWikiAPIError(f"Invalid page response for {title!r}: expected one page")

        page = next(iter(pages.values()))
        if not isinstance(page, dict):
            raise MediaWikiAPIError(f"Invalid page response for {title!r}: malformed page")
        if "missing" in page:
            return None

        try:
            content = page["revisions"][0]["slots"]["main"]["*"]
            if not isinstance(content, str):
                raise TypeError("revision content is not text")
        except (KeyError, IndexError, TypeError) as error:
            raise MediaWikiAPIError(f"Invalid page response for {title!r}: missing revision content") from error
        logger.debug(f"Fetched page: {title} ({len(content)} characters)")
        return content

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
        pagination if more than batch_size pages are requested. Pages that a
        response truncated at the API result size limit are requested again.

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
        pending = list(titles)
        while pending:
            batch = pending[: self.batch_size]
            logger.debug(f"Fetching a batch of {len(batch)} pages")

            params = {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
            }

            result = self._request(params)

            query = result.get("query")
            if not isinstance(query, dict):
                raise MediaWikiAPIError(f"Invalid page response for {batch!r}: missing query")
            normalized = query.get("normalized", [])
            if not isinstance(normalized, list):
                raise MediaWikiAPIError(f"Invalid page response for {batch!r}: malformed normalized titles")
            aliases: dict[str, str] = {}
            for entry in normalized:
                if (
                    not isinstance(entry, dict)
                    or not isinstance(entry.get("from"), str)
                    or not isinstance(entry.get("to"), str)
                ):
                    raise MediaWikiAPIError(f"Invalid page response for {batch!r}: malformed normalized title")
                aliases[entry["from"]] = entry["to"]
            pages = query.get("pages")
            if not isinstance(pages, dict):
                raise MediaWikiAPIError(f"Invalid page response for {batch!r}: missing pages")

            truncated = "continue" in result
            by_title: dict[str, str | None] = {}
            left_out: set[str] = set()
            for page in pages.values():
                if not isinstance(page, dict) or not isinstance(page.get("title"), str):
                    raise MediaWikiAPIError(f"Invalid page response for {batch!r}: malformed page")
                title = page["title"]
                if "missing" in page:
                    by_title[title] = None
                    continue
                if truncated and not page.get("revisions"):
                    left_out.add(title)
                    continue

                try:
                    content = page["revisions"][0]["slots"]["main"]["*"]
                    if not isinstance(content, str):
                        raise TypeError("revision content is not text")
                except (KeyError, IndexError, TypeError) as error:
                    raise MediaWikiAPIError(f"Invalid page response for {title!r}: missing revision content") from error
                by_title[title] = content

            deferred: list[str] = []
            for requested in batch:
                normalized_title = aliases.get(requested, requested)
                if normalized_title in left_out:
                    deferred.append(requested)
                    continue
                if normalized_title not in by_title:
                    raise MediaWikiAPIError(f"Invalid page response for {requested!r}: page not returned")
                result_dict[requested] = by_title[normalized_title]
            if len(deferred) == len(batch):
                raise MediaWikiAPIError(f"Page response for {deferred[0]!r} is larger than the API result limit")
            pending = deferred + pending[len(batch) :]
        return result_dict

    def get_page_revision_ids(self, titles: Sequence[str]) -> dict[str, int | None]:
        """Return the current revision ID for each requested title.

        A missing page has no revision ID. A malformed or incomplete response fails.
        """
        revisions: dict[str, int | None] = {}
        for start in range(0, len(titles), self.batch_size):
            batch = titles[start : start + self.batch_size]
            result = self._request({"action": "query", "prop": "info", "titles": "|".join(batch)})
            query = result.get("query")
            if not isinstance(query, dict):
                raise MediaWikiAPIError(f"Invalid revision response for {batch!r}: missing query")
            normalized = query.get("normalized", [])
            if not isinstance(normalized, list):
                raise MediaWikiAPIError(f"Invalid revision response for {batch!r}: malformed normalized titles")
            aliases: dict[str, str] = {}
            for entry in normalized:
                if (
                    not isinstance(entry, dict)
                    or not isinstance(entry.get("from"), str)
                    or not isinstance(entry.get("to"), str)
                ):
                    raise MediaWikiAPIError(f"Invalid revision response for {batch!r}: malformed normalized title")
                aliases[entry["from"]] = entry["to"]
            pages = query.get("pages")
            if not isinstance(pages, dict):
                raise MediaWikiAPIError(f"Invalid revision response for {batch!r}: missing pages")
            by_title: dict[str, int | None] = {}
            for page in pages.values():
                if not isinstance(page, dict) or not isinstance(page.get("title"), str):
                    raise MediaWikiAPIError(f"Invalid revision response for {batch!r}: malformed page")
                title = page["title"]
                if "missing" in page:
                    by_title[title] = None
                    continue
                revision = page.get("lastrevid")
                if type(revision) is not int or revision <= 0:
                    raise MediaWikiAPIError(f"Invalid revision response for {title!r}: missing lastrevid")
                by_title[title] = revision
            for title in batch:
                normalized_title = aliases.get(title, title)
                if normalized_title not in by_title:
                    raise MediaWikiAPIError(f"Invalid revision response for {title!r}: page not returned")
                revisions[title] = by_title[normalized_title]
        return revisions

    def _query_continued(self, params: Mapping[str, Any], what: str) -> Iterator[dict[str, Any]]:
        """Yield each response of a query, following its continuation to the end.

        Every request repeats ``params`` with the whole ``continue`` object of
        the previous response, as the API asks. A malformed or repeated
        continuation fails and names ``what``, so a listing is never silently
        incomplete.
        """
        continuation: dict[str, str] = {}
        seen: set[tuple[tuple[str, str], ...]] = set()
        while True:
            result = self._request(dict(params) | continuation)
            yield result
            raw_continue = result.get("continue")
            if raw_continue is None:
                return
            if (
                not isinstance(raw_continue, dict)
                or not raw_continue
                or not all(isinstance(key, str) and isinstance(value, str | int) for key, value in raw_continue.items())
            ):
                raise MediaWikiAPIError(f"Incomplete {what} response: invalid continuation")
            continuation = {key: str(value) for key, value in raw_continue.items()}
            marker = tuple(sorted(continuation.items()))
            if marker in seen:
                raise MediaWikiAPIError(f"Incomplete {what} response: repeated continuation")
            seen.add(marker)

    def list_user_created_pages(self, username: str) -> tuple[str, ...]:
        """List every article created by an account, including continued results."""
        if not username.strip():
            raise ValueError("A creator account is required")
        titles: set[str] = set()
        params = {
            "action": "query",
            "list": "usercontribs",
            "ucuser": username,
            "ucshow": "new",
            "ucnamespace": "0",
            "ucprop": "title|ids|user|flags",
            "uclimit": "max",
        }
        for result in self._query_continued(params, "user contributions"):
            query = result.get("query")
            entries = query.get("usercontribs") if isinstance(query, dict) else None
            if not isinstance(entries, list):
                raise MediaWikiAPIError("Incomplete user contributions response: missing contributions")
            for entry in entries:
                if (
                    not isinstance(entry, dict)
                    or not isinstance(entry.get("title"), str)
                    or not entry["title"]
                    or entry.get("user") != username
                    or entry.get("ns") != 0
                    or type(entry.get("pageid")) is not int
                    or entry["pageid"] <= 0
                    or type(entry.get("revid")) is not int
                    or entry["revid"] <= 0
                    or "new" not in entry
                ):
                    raise MediaWikiAPIError("Incomplete user contributions response: malformed creation")
                titles.add(entry["title"])
        return self._deterministic_unique_titles(tuple(titles))

    def get_title_statuses(self, titles: Sequence[str]) -> dict[str, MediaWikiTitleStatus]:
        """Return normalized, redirect, and existence status for each title.

        Requests are batched using the configured API batch size.  MediaWiki's
        ``normalized`` and ``redirects`` response maps are reconciled locally so
        callers retain the exact requested title as the result key.
        """
        statuses: dict[str, MediaWikiTitleStatus] = {}
        for resolved in self._resolve_titles(titles, "info"):
            page = resolved.page
            page_id = page.get("pageid")
            if page_id is None and "missing" not in page:
                raise MediaWikiAPIError("Invalid title status response: missing page id")
            exists = not bool(page.get("missing"))
            if page_id is None:
                exists = False
            else:
                try:
                    exists = exists and int(page_id) >= 0
                except (TypeError, ValueError) as error:
                    raise MediaWikiAPIError("Invalid title status response: malformed page id") from error
            statuses[resolved.requested] = MediaWikiTitleStatus(
                requested=resolved.requested,
                normalized=resolved.normalized,
                redirect_target=resolved.redirect_target,
                exists=exists,
            )
        return statuses

    def get_uploaded_files(self, titles: Sequence[str]) -> frozenset[str]:
        """Return the requested ``File:`` titles whose file has uploaded bytes.

        A redirect counts when its final target has an upload. A file
        description page without an upload does not count.
        """
        return frozenset(self.get_file_uploads(titles))

    def get_file_uploads(self, titles: Sequence[str]) -> dict[str, MediaWikiFileUpload]:
        """Return the current upload of each requested ``File:`` title that has one.

        A redirect resolves to its final target, whose upload counts. Titles
        without uploaded bytes are absent from the result.
        """
        uploads: dict[str, MediaWikiFileUpload] = {}
        for resolved in self._resolve_titles(titles, "imageinfo", {"iiprop": "user|sha1"}):
            info = resolved.page.get("imageinfo")
            if not info:
                continue
            latest = info[0]
            if not isinstance(latest, dict):
                raise MediaWikiAPIError(f"Invalid image info for {resolved.requested!r}")
            uploads[resolved.requested] = MediaWikiFileUpload(
                title=str(resolved.page["title"]),
                user=str(latest.get("user", "")),
                sha1=str(latest.get("sha1", "")),
            )
        return uploads

    def find_files_by_sha1(self, sha1: str) -> tuple[str, ...]:
        """Return the titles of the files whose current upload has the given SHA-1."""
        result = self._request({"action": "query", "list": "allimages", "aisha1": sha1, "ailimit": "max"})
        query = result.get("query")
        if not isinstance(query, dict) or not isinstance(query.get("allimages"), list):
            raise MediaWikiAPIError("Invalid file hash response: missing allimages")
        return tuple(sorted(str(image["title"]) for image in query["allimages"] if isinstance(image, dict)))

    def list_files(self) -> tuple[MediaWikiFile, ...]:
        """Return the current version of every uploaded file, in title order."""
        params = {
            "action": "query",
            "list": "allimages",
            "aiprop": "sha1|user|comment|size|timestamp|url",
            "ailimit": "max",
        }
        files: dict[str, MediaWikiFile] = {}
        for result in self._query_continued(params, "file listing"):
            query = result.get("query")
            entries = query.get("allimages") if isinstance(query, dict) else None
            if not isinstance(entries, list):
                raise MediaWikiAPIError("Incomplete file listing response: missing allimages")
            for entry in entries:
                file = _listed_file(entry)
                files[file.title] = file
        return tuple(files[title] for title in sorted(files))

    def list_file_pages(self) -> MediaWikiFilePages:
        """Return the redirects, with the page that each names, and the other existing pages of the File namespace.

        The ``allpages`` generator cannot resolve redirects, so the redirect
        pages are listed first and then resolved by title.
        """
        redirect_titles = self._list_page_titles(6, "redirects")
        redirects = {
            resolved.requested: resolved.first_target
            for resolved in self._resolve_titles(redirect_titles, "info")
            if resolved.first_target is not None
        }
        return MediaWikiFilePages(redirects=redirects, pages=frozenset(self._list_page_titles(6, "nonredirects")))

    def _list_page_titles(self, namespace: int, filterredir: Literal["redirects", "nonredirects"]) -> tuple[str, ...]:
        """Return the titles of every redirect or every other page of a namespace."""
        params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": str(namespace),
            "apfilterredir": filterredir,
            "aplimit": "max",
        }
        titles: list[str] = []
        for result in self._query_continued(params, "page listing"):
            query = result.get("query")
            entries = query.get("allpages") if isinstance(query, dict) else None
            if not isinstance(entries, list):
                raise MediaWikiAPIError("Incomplete page listing response: missing allpages")
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
                    raise MediaWikiAPIError("Incomplete page listing response: malformed page")
                titles.append(entry["title"])
        return tuple(titles)

    def is_file_used(self, title: str) -> bool:
        """Return whether a page shows the file, directly or through a redirect to it.

        A redirect that no page uses does not count as a use.
        """
        params = {"action": "query", "list": "imageusage", "iutitle": title, "iulimit": "max", "iuredirect": "1"}
        for result in self._query_continued(params, "image usage"):
            query = result.get("query")
            entries = query.get("imageusage") if isinstance(query, dict) else None
            if not isinstance(entries, list):
                raise MediaWikiAPIError("Incomplete image usage response: missing imageusage")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise MediaWikiAPIError("Incomplete image usage response: malformed use")
                if "redirect" not in entry or entry.get("redirlinks"):
                    return True
        return False

    def get_file_versions(self, title: str, limit: int = 50) -> tuple[MediaWikiFileVersion, ...]:
        """Return up to ``limit`` versions of a file, newest first, or none for a page without a file."""
        result = self._request(
            {
                "action": "query",
                "prop": "imageinfo",
                "titles": title,
                "iiprop": "sha1|user|comment|timestamp|url",
                "iilimit": str(limit),
            }
        )
        query = result.get("query")
        pages = query.get("pages") if isinstance(query, dict) else None
        if not isinstance(pages, dict) or len(pages) != 1:
            raise MediaWikiAPIError(f"Invalid file history response for {title!r}")
        page = next(iter(pages.values()))
        info = page.get("imageinfo", []) if isinstance(page, dict) else None
        if not isinstance(info, list):
            raise MediaWikiAPIError(f"Invalid file history response for {title!r}: malformed imageinfo")
        return tuple(_file_version(entry, title) for entry in info)

    def download(self, url: str) -> bytes:
        """Return the bytes at a URL of the wiki, such as a file's ``url``."""
        response = self._requestor.download(url)
        if response.status_code != 200:
            raise MediaWikiNetworkError(f"HTTP {response.status_code} downloading {url}")
        return response.content

    def _resolve_titles(
        self, titles: Sequence[str], prop: str, extra: Mapping[str, str] | None = None
    ) -> list[_ResolvedTitle]:
        """Query ``prop`` for each title and follow normalization and redirects to its final page."""
        resolved: list[_ResolvedTitle] = []
        requested_titles = list(dict.fromkeys(titles))
        for start in range(0, len(requested_titles), self.batch_size):
            batch = requested_titles[start : start + self.batch_size]
            result = self._request(
                {
                    "action": "query",
                    "prop": prop,
                    "redirects": "1",
                    "titles": "|".join(batch),
                    **(extra or {}),
                }
            )
            query = result.get("query")
            if not isinstance(query, dict):
                raise MediaWikiAPIError("Invalid title status response: missing query object")
            normalized = self._title_map(query, "normalized")
            redirects = self._title_map(query, "redirects")

            pages = query.get("pages")
            if not isinstance(pages, dict):
                raise MediaWikiAPIError("Invalid title status response: missing pages")
            pages_by_title: dict[str, dict[str, Any]] = {}
            for page in pages.values():
                if not isinstance(page, dict) or not isinstance(page.get("title"), str):
                    raise MediaWikiAPIError("Invalid title status response: malformed page entry")
                pages_by_title[page["title"]] = page

            for requested in batch:
                normalized_title = normalized.get(requested, requested)
                initial_redirect_target = redirects.get(normalized_title, redirects.get(requested))
                final_title = initial_redirect_target or normalized_title
                seen_titles: set[str] = set()
                while final_title not in seen_titles and final_title in redirects:
                    seen_titles.add(final_title)
                    final_title = redirects[final_title]
                if final_title not in pages_by_title:
                    raise MediaWikiAPIError(f"Invalid title status response for {requested!r}: page not returned")
                resolved.append(
                    _ResolvedTitle(
                        requested=requested,
                        normalized=normalized_title,
                        redirect_target=final_title if initial_redirect_target is not None else None,
                        first_target=initial_redirect_target,
                        page=pages_by_title[final_title],
                    )
                )
        return resolved

    @staticmethod
    def _title_map(query: dict[str, Any], key: str) -> dict[str, str]:
        """Read a ``normalized`` or ``redirects`` list of a query response as a map."""
        entries = query.get(key, [])
        if not isinstance(entries, list):
            raise MediaWikiAPIError(f"Invalid title status response: {key} must be a list")
        mapping: dict[str, str] = {}
        for item in entries:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("from"), str)
                or not isinstance(item.get("to"), str)
            ):
                raise MediaWikiAPIError(f"Invalid title status response: malformed {key} entry")
            mapping[item["from"]] = item["to"]
        return mapping

    @staticmethod
    def _deterministic_unique_titles(titles: Sequence[str]) -> tuple[str, ...]:
        """Return unique titles in a stable, case-insensitive order."""
        return tuple(sorted(set(titles), key=lambda title: (title.casefold(), title)))

    def get_wanted_pages(self, namespace: int = 0) -> tuple[str, ...]:
        """Return unique wanted-page titles in ``namespace``.

        QueryPage does not expose a namespace parameter for WantedPages, so the
        namespace is filtered from each returned result while all continuation
        pages are consumed.
        """
        titles: list[str] = []
        params: dict[str, Any] = {
            "action": "query",
            "list": "querypage",
            "qppage": "Wantedpages",
            "qplimit": "max",
        }
        for result in self._query_continued(params, "WantedPages"):
            query = result.get("query", {})
            querypage = query.get("querypage", []) if isinstance(query, dict) else []
            entries = querypage.get("results", []) if isinstance(querypage, dict) else querypage
            if not isinstance(entries, list):
                raise MediaWikiAPIError("Invalid WantedPages response")
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
                    raise MediaWikiAPIError("Invalid WantedPages response: malformed result")
                try:
                    entry_namespace = int(entry.get("ns", 0))
                except (TypeError, ValueError) as error:
                    raise MediaWikiAPIError("Invalid WantedPages response: malformed namespace") from error
                if entry_namespace == namespace:
                    titles.append(entry["title"])
        return self._deterministic_unique_titles(titles)

    def get_linking_pages_by_title(
        self,
        titles: Sequence[str],
        namespace: int = 0,
    ) -> dict[str, tuple[str, ...]]:
        """Return linking pages for many target titles using batched queries."""
        requested_titles = self._deterministic_unique_titles(titles)
        linking_pages: dict[str, list[str]] = {title: [] for title in requested_titles}
        requested_by_key = {title.replace("_", " ").strip().casefold(): title for title in requested_titles}
        for start in range(0, len(requested_titles), self.batch_size):
            batch = requested_titles[start : start + self.batch_size]
            continue_params: dict[str, str] = {}
            params: dict[str, Any] = {
                "action": "query",
                "prop": "linkshere",
                "titles": "|".join(batch),
                "lhnamespace": str(namespace),
                "lhlimit": "max",
            }
            while True:
                result = self._request(params | continue_params)
                query = result.get("query", {})
                pages = query.get("pages", {}) if isinstance(query, dict) else {}
                if not isinstance(pages, dict):
                    raise MediaWikiAPIError("Invalid linking-pages response")
                for page in pages.values():
                    if not isinstance(page, dict) or not isinstance(page.get("title"), str):
                        raise MediaWikiAPIError("Invalid linking-pages response: malformed target")
                    response_title = page["title"]
                    requested_title = requested_by_key.get(response_title.replace("_", " ").strip().casefold())
                    if requested_title is None:
                        raise MediaWikiAPIError("Invalid linking-pages response: unexpected target")
                    entries = page.get("linkshere", [])
                    if not isinstance(entries, list):
                        raise MediaWikiAPIError("Invalid linking-pages response")
                    for entry in entries:
                        if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
                            raise MediaWikiAPIError("Invalid linking-pages response: malformed result")
                        try:
                            entry_namespace = int(entry.get("ns", namespace))
                        except (TypeError, ValueError) as error:
                            raise MediaWikiAPIError("Invalid linking-pages response: malformed namespace") from error
                        if entry_namespace == namespace:
                            linking_pages[requested_title].append(entry["title"])
                continuation = result.get("continue")
                if not isinstance(continuation, dict):
                    break
                continue_params = {key: str(value) for key, value in continuation.items()}
        return {title: self._deterministic_unique_titles(linking_pages[title]) for title in requested_titles}

    def get_linking_pages(self, title: str, namespace: int = 0) -> tuple[str, ...]:
        """Return unique pages linking to ``title`` in ``namespace``."""
        titles: list[str] = []
        continue_params: dict[str, str] = {}
        params: dict[str, Any] = {
            "action": "query",
            "list": "backlinks",
            "bltitle": title,
            "blnamespace": str(namespace),
            "bllimit": "max",
        }
        while True:
            result = self._request(params | continue_params)
            query = result.get("query", {})
            entries = query.get("backlinks", []) if isinstance(query, dict) else []
            if not isinstance(entries, list):
                raise MediaWikiAPIError("Invalid linking-pages response")
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
                    raise MediaWikiAPIError("Invalid linking-pages response: malformed result")
                try:
                    entry_namespace = int(entry.get("ns", namespace))
                except (TypeError, ValueError) as error:
                    raise MediaWikiAPIError("Invalid linking-pages response: malformed namespace") from error
                if entry_namespace == namespace:
                    titles.append(entry["title"])
            continuation = result.get("continue")
            if not isinstance(continuation, dict):
                break
            continue_params = {key: str(value) for key, value in continuation.items()}
        return self._deterministic_unique_titles(titles)

    def get_category_members(self, title: str, namespace: int = 0) -> tuple[str, ...]:
        """Return unique members of category ``title`` in ``namespace``."""
        titles: list[str] = []
        continue_params: dict[str, str] = {}
        params: dict[str, Any] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": title,
            "cmnamespace": str(namespace),
            "cmlimit": "max",
        }
        while True:
            result = self._request(params | continue_params)
            query = result.get("query", {})
            entries = query.get("categorymembers", []) if isinstance(query, dict) else []
            if not isinstance(entries, list):
                raise MediaWikiAPIError("Invalid category-members response")
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
                    raise MediaWikiAPIError("Invalid category-members response: malformed result")
                try:
                    entry_namespace = int(entry.get("ns", namespace))
                except (TypeError, ValueError) as error:
                    raise MediaWikiAPIError("Invalid category-members response: malformed namespace") from error
                if entry_namespace == namespace:
                    titles.append(entry["title"])
            continuation = result.get("continue")
            if not isinstance(continuation, dict):
                break
            continue_params = {key: str(value) for key, value in continuation.items()}
        return self._deterministic_unique_titles(titles)

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

        MediaWiki truncates a response at its result size limit and returns the
        pages that did not fit without revisions, together with a ``continue``
        block. Those pages are requested again in a later query.
        """
        if assertion not in (None, "user", "bot"):
            raise ValueError(f"assertion must be 'user' or 'bot', got: {assertion}")
        if not titles:
            return {}

        snapshots: dict[str, MediaWikiPageSnapshot] = {}
        pending = list(titles)
        while pending:
            batch = pending[: self.batch_size]
            params: dict[str, Any] = {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "revisions",
                "rvprop": "ids|timestamp|user|content|contentmodel",
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

            query = result.get("query")
            if not isinstance(query, dict):
                raise MediaWikiAPIError(f"Invalid page snapshot response for {batch!r}: missing query")
            normalized = query.get("normalized", [])
            if not isinstance(normalized, list):
                raise MediaWikiAPIError(f"Invalid page snapshot response for {batch!r}: malformed normalized titles")
            aliases: dict[str, str] = {}
            for entry in normalized:
                if (
                    not isinstance(entry, dict)
                    or not isinstance(entry.get("from"), str)
                    or not isinstance(entry.get("to"), str)
                ):
                    raise MediaWikiAPIError(f"Invalid page snapshot response for {batch!r}: malformed normalized title")
                aliases[entry["from"]] = entry["to"]
            pages = query.get("pages")
            if not isinstance(pages, dict):
                raise MediaWikiAPIError(f"Invalid page snapshot response for {batch!r}: missing pages")
            pages_by_title: dict[str, dict[str, Any]] = {}
            for page in pages.values():
                if not isinstance(page, dict) or not isinstance(page.get("title"), str):
                    raise MediaWikiAPIError(f"Invalid page snapshot response for {batch!r}: malformed page")
                pages_by_title[page["title"]] = page
            truncated = "continue" in result
            deferred: list[str] = []
            for requested_title in batch:
                page = pages_by_title.get(aliases.get(requested_title, requested_title))
                if page is None:
                    raise MediaWikiAPIError(
                        f"Invalid page snapshot response for {requested_title!r}: page not returned"
                    )

                page_title = page["title"]
                if "missing" in page:
                    snapshots[requested_title] = MediaWikiPageSnapshot(
                        title=page_title,
                        source_text=None,
                        revision=None,
                        start_timestamp=start_timestamp,
                    )
                    continue

                page_id = page.get("pageid")
                if type(page_id) is not int or page_id <= 0:
                    raise MediaWikiAPIError(f"Invalid page snapshot response for {requested_title!r}: missing page ID")
                if truncated and not page.get("revisions"):
                    deferred.append(requested_title)
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
                        page_id=page_id,
                        revision_id=revision_id,
                        timestamp=revision_timestamp,
                        start_timestamp=start_timestamp,
                        user=_revision_user(raw_revision),
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
            if len(deferred) == len(batch):
                raise MediaWikiAPIError(
                    f"Page snapshot response for {deferred[0]!r} is larger than the API result limit"
                )
            pending = deferred + pending[len(batch) :]

        return snapshots

    def parse_wikitext(
        self,
        title: str,
        text: str,
        *,
        sandbox_title: str | None = None,
        sandbox_text: str | None = None,
        sandbox_content_model: str | None = None,
    ) -> MediaWikiParse:
        """Parse text under its page title, optionally replacing one transcluded page."""
        data = {
            "action": "parse",
            "title": title,
            "text": text,
            "prop": "text|templates|categories",
            "contentmodel": "wikitext",
            "disablelimitreport": "1",
            "formatversion": "2",
        }
        if sandbox_title is not None:
            if sandbox_text is None or sandbox_content_model is None:
                raise ValueError("Sandbox title requires text and a content model")
            data["templatesandboxtitle"] = sandbox_title
            data["templatesandboxtext"] = sandbox_text
            data["templatesandboxcontentmodel"] = sandbox_content_model
        elif sandbox_text is not None or sandbox_content_model is not None:
            raise ValueError("Sandbox text and content model require a title")
        result = self._request({}, method="POST", data=data)
        parse = result.get("parse")
        if not isinstance(parse, dict) or not isinstance(parse.get("text"), str):
            raise MediaWikiAPIError(f"Invalid parse response for {title!r}")
        try:
            templates = tuple(
                MediaWikiParsedLink(title=str(template["title"]), exists=bool(template.get("exists", False)))
                for template in parse.get("templates", [])
            )
            categories = tuple(
                MediaWikiParsedLink(
                    title="Category:" + str(category["category"]).replace("_", " "),
                    exists=not bool(category.get("missing", False)),
                )
                for category in parse.get("categories", [])
            )
        except (KeyError, TypeError) as error:
            raise MediaWikiAPIError(f"Invalid parse response for {title!r}: {error}") from error
        return MediaWikiParse(html=parse["text"], templates=templates, categories=categories)

    def get_page_categories(self, titles: Sequence[str]) -> dict[str, frozenset[str]]:
        """Return the categories of each existing page, including hidden categories.

        A missing page maps to no categories. Category titles carry the
        ``Category:`` namespace.
        """
        categories: dict[str, set[str]] = {title: set() for title in titles}
        for i in range(0, len(titles), self.batch_size):
            batch = titles[i : i + self.batch_size]
            params = {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "categories",
                "cllimit": "max",
                "formatversion": "2",
            }
            continue_params: dict[str, str] = {}
            while True:
                result = self._request(params | continue_params)
                query = result.get("query", {})
                normalized = {entry["from"]: entry["to"] for entry in query.get("normalized", [])}
                requested_by_title: dict[str, list[str]] = {}
                for requested in batch:
                    requested_by_title.setdefault(normalized.get(requested, requested), []).append(requested)
                for page in query.get("pages", []):
                    page_categories = {str(category["title"]) for category in page.get("categories", [])}
                    for requested in requested_by_title.get(page["title"], []):
                        categories[requested].update(page_categories)
                continuation = result.get("continue")
                if not isinstance(continuation, dict):
                    break
                continue_params = {key: str(value) for key, value in continuation.items()}
        return {title: frozenset(values) for title, values in categories.items()}

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
            logger.info(
                "Discovered {} transclusions for {}{}",
                len(pages),
                title,
                " (continuing)" if isinstance(result.get("continue"), dict) else "",
            )

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
        batch_count = (len(titles) + self.batch_size - 1) // self.batch_size
        for i in range(0, len(titles), self.batch_size):
            batch = titles[i : i + self.batch_size]
            batch_number = i // self.batch_size + 1
            logger.info(
                "Purging batch {}/{} ({} pages, {} of {} queued)",
                batch_number,
                batch_count,
                len(batch),
                min(i + len(batch), len(titles)),
                len(titles),
            )
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
            logger.info(
                "Purged batch {}/{} ({} total pages refreshed)",
                batch_number,
                batch_count,
                len(purged),
            )
        logger.info(f"Purged {len(purged)} pages (force_link_update={force_link_update})")
        return tuple(purged)

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
            "rvprop": "ids|timestamp|user",
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
            revision_user = _revision_user(revision)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise MediaWikiAPIError(f"Invalid revision metadata response for '{title}': {e}") from e

        return MediaWikiPageRevision(
            title=revision_title,
            page_id=revision_page_id,
            revision_id=revision_id,
            timestamp=revision_timestamp,
            start_timestamp=start_timestamp,
            user=revision_user,
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
        actually failed. Network, authentication, and rate-limit failures are
        not failures of the page, so they pass through unchanged.
        """
        if isinstance(error, MediaWikiNetworkError | MediaWikiAuthenticationError | MediaWikiRateLimitError):
            raise error
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

    def upload_file(
        self,
        file_path: str,
        filename: str,
        comment: str,
        text: str = "",
        ignore_warnings: bool = False,
    ) -> dict[str, Any]:
        """Upload a file to the wiki.

        Requires authentication (call login() first). ``comment`` belongs to
        this file version, while MediaWiki uses ``text`` only as the description
        page of a new file.

        Returns:
            The ``upload`` object of the API response.

        Raises:
            MediaWikiUploadWarningError: MediaWiki answered with warnings and
                stashed the file; ``confirm_upload`` can publish it.
            MediaWikiAPIError: If the upload fails.
            FileNotFoundError: If file_path doesn't exist.
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        logger.info(f"Uploading file: {file_path} → File:{filename}")
        data = {"action": "upload", "filename": filename, "comment": comment, "text": text}
        if ignore_warnings:
            data["ignorewarnings"] = "1"
        with Path(file_path).open("rb") as handle:
            return self._post_upload(filename, data, {"file": (filename, handle, "image/png")})

    def confirm_upload(self, filekey: str, filename: str, comment: str, text: str = "") -> dict[str, Any]:
        """Publish a stashed upload, accepting the warnings MediaWiki gave for it.

        Call this only after judging the warnings of the ``MediaWikiUploadWarningError``
        that carried ``filekey``: the confirmation waives every warning.
        """
        logger.info(f"Confirming stashed upload {filekey} → File:{filename}")
        data = {
            "action": "upload",
            "filekey": filekey,
            "filename": filename,
            "comment": comment,
            "text": text,
            "ignorewarnings": "1",
        }
        return self._post_upload(filename, data, None)

    def _post_upload(self, filename: str, data: dict[str, str], files: Mapping[str, Any] | None) -> dict[str, Any]:
        """Send an upload request and return its ``upload`` object, or raise its warnings or error."""
        data = data | {"token": self.get_csrf_token()}
        try:
            if files is None:
                result = self._requestor.post({"action": "upload"}, data=data)
            else:
                result = self._requestor.post_files({"action": "upload"}, data=data, files=files)
        except MediaWikiRetryableRequestError as e:
            attempts = e.attempts or (self.request_policy.max_retries + 1)
            raise MediaWikiRateLimitError(f"MediaWiki request exhausted retries after {attempts} attempts") from e
        except MediaWikiUnretryableRequestError as e:
            if e.status_code is not None:
                logger.error(f"HTTP error during upload: {e.status_code}")
                raise MediaWikiAPIError(f"HTTP {e.status_code} during file upload") from e
            error_info = e.info or "Unknown error"
            error_code = e.code or "unknown"
            logger.error(f"Upload API error: {error_code} - {error_info}")
            raise MediaWikiAPIError(
                f"Upload failed ({error_code}): {error_info}", code=error_code, info=error_info
            ) from e
        except httpx.RequestError as e:
            logger.error(f"Network error during upload: {e}")
            raise MediaWikiNetworkError(f"Network error during upload: {e}") from e
        upload_result = result.get("upload")
        if not isinstance(upload_result, dict):
            raise MediaWikiAPIError(f"Unexpected upload response: {result}")
        if upload_result.get("result") == "Warning" and isinstance(upload_result.get("warnings"), dict):
            filekey = upload_result.get("filekey")
            logger.warning(f"Upload warnings for File:{filename}: {upload_result['warnings']}")
            raise MediaWikiUploadWarningError(upload_result["warnings"], filekey if isinstance(filekey, str) else None)
        if upload_result.get("result") != "Success":
            logger.error(f"Unexpected upload response: {result}")
            raise MediaWikiAPIError(f"Unexpected upload response: {result}")
        logger.info(f"Successfully uploaded: File:{filename}")
        return upload_result

    def delete_page(self, title: str, reason: str) -> None:
        """Delete a page. Deleting a file page deletes every version of its file.

        Needs the ``delete`` right, which a bot password of an administrator
        has with the delete grant.
        """
        data = {"action": "delete", "title": title, "reason": reason, "token": self.get_csrf_token()}
        result = self._request({"action": "delete"}, method="POST", data=data)
        deleted = result.get("delete")
        if not isinstance(deleted, dict) or "logid" not in deleted:
            raise MediaWikiAPIError(f"Unexpected delete response: {result}")
        logger.info(f"Deleted {title}")

    def undelete_page(self, title: str, reason: str) -> None:
        """Restore every deleted revision of a page, and of a file page every deleted version of its file."""
        data = {"action": "undelete", "title": title, "reason": reason, "token": self.get_csrf_token()}
        result = self._request({"action": "undelete"}, method="POST", data=data)
        restored = result.get("undelete")
        if not isinstance(restored, dict) or not isinstance(restored.get("title"), str):
            raise MediaWikiAPIError(f"Unexpected undelete response: {result}")
        logger.info(f"Restored {title}")
