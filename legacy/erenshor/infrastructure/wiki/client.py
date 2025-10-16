"""Thin HTTP client for MediaWiki API."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from erenshor.domain.exceptions import WikiAPIError
from erenshor.infrastructure.wiki.constants import (
    WIKI_API_TIMEOUT_SECONDS,
    WIKI_DEFAULT_BACKOFF_BASE,
    WIKI_DEFAULT_MAX_RETRIES,
    WIKI_DEFAULT_USER_AGENT,
    WIKI_MAXLAG_SECONDS,
)

__all__ = ["WikiAPIClient"]


@dataclass
class WikiAPIClient:
    """Thin HTTP client for MediaWiki API operations.

    Provides low-level API operations for fetching and uploading wiki pages.
    Handles retries, rate limiting, and error responses.
    """

    api_url: str
    user_agent: str = WIKI_DEFAULT_USER_AGENT
    session: httpx.Client = field(default_factory=httpx.Client)
    auth_session: httpx.Client | None = None  # Set by auth module for uploads

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        """Make a GET request to the MediaWiki API.

        Args:
            params: Query parameters for the API request

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        headers = {"User-Agent": self.user_agent}
        session = self.auth_session or self.session
        resp = session.get(
            self.api_url,
            params=params,
            headers=headers,
            timeout=WIKI_API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    def _post_request(self, data: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request to the MediaWiki API.

        Args:
            data: Form data for the API request

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        headers = {"User-Agent": self.user_agent}
        session = self.auth_session or self.session
        resp = session.post(
            self.api_url, data=data, headers=headers, timeout=WIKI_API_TIMEOUT_SECONDS
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    def _extract_content(self, page: dict[str, Any]) -> Optional[str]:
        """Extract page content from API response.

        Args:
            page: Page object from API response

        Returns:
            Page content with trailing newline, or None if page is missing
        """
        if page.get("missing"):
            return None
        revs = page.get("revisions") or []
        if not revs:
            return ""
        slots = revs[0].get("slots", {})
        main = slots.get("main") or {}
        content = main.get("content")
        if content is None:
            return ""
        content_str = str(content) if content else ""
        return content_str if content_str.endswith("\n") else content_str + "\n"

    def fetch_page(self, page_title: str) -> Optional[str]:
        """Fetch a single page from the wiki.

        Args:
            page_title: Title of the page to fetch

        Returns:
            Page content, or None if page doesn't exist
        """
        data = self._request(
            {
                "action": "query",
                "format": "json",
                "prop": "revisions",
                "rvslots": "main",
                "rvprop": "content|timestamp",
                "titles": page_title,
                "formatversion": "2",
                "maxlag": WIKI_MAXLAG_SECONDS,
            }
        )
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return None
        return self._extract_content(pages[0])

    def fetch_batch(
        self,
        titles: list[str],
        *,
        max_retries: int = WIKI_DEFAULT_MAX_RETRIES,
        backoff_base: float = WIKI_DEFAULT_BACKOFF_BASE,
    ) -> dict[str, Optional[str]]:
        """Fetch multiple pages in a single API request.

        Args:
            titles: List of page titles to fetch
            max_retries: Maximum number of retry attempts
            backoff_base: Base delay for exponential backoff (seconds)

        Returns:
            Mapping of title → content (or None if page is missing)
        """
        params = {
            "action": "query",
            "format": "json",
            "prop": "revisions",
            "rvslots": "main",
            "rvprop": "content|timestamp",
            "titles": "|".join(titles),
            "formatversion": "2",
            "maxlag": WIKI_MAXLAG_SECONDS,
        }
        attempt = 0
        while True:
            try:
                data = self._request(params)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (429, 503) and attempt < max_retries:
                    # Check for Retry-After header
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = backoff_base * (2**attempt)
                    else:
                        delay = backoff_base * (2**attempt)
                    time.sleep(delay)
                    attempt += 1
                    continue
                raise
            # Handle API error with maxlag
            if (
                isinstance(data, dict)
                and data.get("error", {}).get("code") == "maxlag"
                and attempt < max_retries
            ):
                delay = backoff_base * (2**attempt)
                time.sleep(delay)
                attempt += 1
                continue
            break

        pages = data.get("query", {}).get("pages", [])
        out: dict[str, Optional[str]] = {}
        for p in pages:
            title = p.get("title") or ""
            out[title] = self._extract_content(p)
        return out

    def list_pages(
        self,
        *,
        namespace: int,
        limit: int = 500,
        max_retries: int = WIKI_DEFAULT_MAX_RETRIES,
        backoff_base: float = WIKI_DEFAULT_BACKOFF_BASE,
    ) -> list[str]:
        """List all page titles in a namespace via continuation.

        Args:
            namespace: MediaWiki namespace ID (0 = main namespace)
            limit: Pages per API request
            max_retries: Maximum number of retry attempts
            backoff_base: Base delay for exponential backoff (seconds)

        Returns:
            List of all page titles in the namespace
        """
        titles: list[str] = []
        cont: Optional[str] = None
        while True:
            params = {
                "action": "query",
                "format": "json",
                "list": "allpages",
                "apnamespace": str(namespace),
                "aplimit": str(limit),
            }
            if cont:
                params["apcontinue"] = cont
            attempt = 0
            while True:
                try:
                    data = self._request(params)
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status in (429, 503) and attempt < max_retries:
                        # Check for Retry-After header
                        retry_after = e.response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = backoff_base * (2**attempt)
                        else:
                            delay = backoff_base * (2**attempt)
                        time.sleep(delay)
                        attempt += 1
                        continue
                    raise
                if (
                    isinstance(data, dict)
                    and data.get("error", {}).get("code") == "maxlag"
                    and attempt < max_retries
                ):
                    delay = backoff_base * (2**attempt)
                    time.sleep(delay)
                    attempt += 1
                    continue
                break
            for p in data.get("query", {}).get("allpages", []):
                t = p.get("title")
                if t:
                    titles.append(str(t))
            cont = data.get("continue", {}).get("apcontinue")
            if not cont:
                break
        return titles

    def upload_page(
        self,
        title: str,
        content: str,
        summary: str,
        minor: bool = True,
        bot: bool = True,
        max_retries: int = WIKI_DEFAULT_MAX_RETRIES,
        backoff_base: float = WIKI_DEFAULT_BACKOFF_BASE,
    ) -> dict[str, Any]:
        """Upload (edit) a page on the wiki with retry logic.

        This requires authentication to be set up via set_auth_session().

        Args:
            title: Page title
            content: Page content (wikitext)
            summary: Edit summary
            minor: Mark as minor edit
            bot: Mark as bot edit (requires bot permissions)
            max_retries: Maximum number of retry attempts for rate limits
            backoff_base: Base delay for exponential backoff (seconds)

        Returns:
            API response dict (contains newrevid, etc.)

        Raises:
            WikiAPIError: If upload fails or not authenticated
        """
        if not self.auth_session:
            raise WikiAPIError(
                "Authentication required for upload. Use set_auth_session()."
            )

        # Get CSRF token (requires authenticated session)
        token_data = self._request(
            {"action": "query", "meta": "tokens", "format": "json"}
        )
        csrf_token = token_data["query"]["tokens"]["csrftoken"]

        # Perform the edit with retry logic
        edit_params: dict[str, Any] = {
            "action": "edit",
            "title": title,
            "text": content,
            "summary": summary,
            "token": csrf_token,
            "format": "json",
        }

        if minor:
            edit_params["minor"] = "1"

        if bot:
            edit_params["bot"] = "1"

        attempt = 0
        while True:
            try:
                response = self._post_request(edit_params)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                # Retry on rate limit (429) or service unavailable (503)
                if status in (429, 503) and attempt < max_retries:
                    # Check for Retry-After header (server tells us how long to wait)
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            # Fallback to exponential backoff if header is invalid
                            delay = backoff_base * (2**attempt)
                    else:
                        # Use exponential backoff if no Retry-After header
                        delay = backoff_base * (2**attempt)
                    time.sleep(delay)
                    attempt += 1
                    continue
                raise

            # Check for API-level rate limit error (not HTTP 429, but error in JSON)
            if "error" in response:
                error_info = response["error"]
                error_code = error_info.get("code", "")

                # Handle rate limit as retryable error
                if error_code == "ratelimited" and attempt < max_retries:
                    # MediaWiki may provide wait time in error info
                    # Format: "You've exceeded your rate limit. Please wait some time and try again."
                    # Try exponential backoff
                    delay = backoff_base * (2**attempt)
                    time.sleep(delay)
                    attempt += 1
                    continue

                # Not retryable or out of retries
                error_msg = (
                    f"{error_code}: "
                    f"{error_info.get('info', 'no details')}"
                )
                raise WikiAPIError(f"Upload failed: {error_msg}")

            edit_result: dict[str, Any] = response.get("edit", {})
            if edit_result.get("result") != "Success":
                raise WikiAPIError(f"Upload failed: Unknown error")

            return edit_result

    def set_auth_session(self, session: httpx.Client) -> None:
        """Set authenticated session for upload operations.

        Args:
            session: Authenticated httpx.Client from MediaWikiAuth
        """
        self.auth_session = session

    def check_file_exists(self, filename: str) -> bool:
        """Check if a file already exists on the wiki.

        Args:
            filename: File name (e.g., "Sword.png")

        Returns:
            True if file exists, False otherwise
        """
        data = self._request(
            {
                "action": "query",
                "format": "json",
                "titles": f"File:{filename}",
                "prop": "imageinfo",
                "formatversion": "2",
            }
        )
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return False
        # File exists if page is not missing
        return not pages[0].get("missing", False)

    def upload_file(
        self,
        file_path: str,
        filename: str,
        comment: str,
        text: str = "",
        ignore_warnings: bool = False,
        bot: bool = True,
        max_retries: int = WIKI_DEFAULT_MAX_RETRIES,
        backoff_base: float = WIKI_DEFAULT_BACKOFF_BASE,
    ) -> dict[str, Any]:
        """Upload a file to the wiki with retry logic.

        This requires authentication to be set up via set_auth_session().

        Args:
            file_path: Path to the file on disk
            filename: Target filename on wiki (e.g., "Sword.png")
            comment: Upload comment/summary
            text: Wiki text for the file description page
            ignore_warnings: Ignore API warnings (e.g., duplicate files)
            bot: Mark as bot upload (requires bot permissions)
            max_retries: Maximum number of retry attempts for rate limits
            backoff_base: Base delay for exponential backoff (seconds)

        Returns:
            API response dict (contains imageinfo, etc.)

        Raises:
            WikiAPIError: If upload fails or not authenticated
        """
        if not self.auth_session:
            raise WikiAPIError(
                "Authentication required for upload. Use set_auth_session()."
            )

        # Get CSRF token (requires authenticated session)
        token_data = self._request(
            {"action": "query", "meta": "tokens", "format": "json"}
        )
        csrf_token = token_data["query"]["tokens"]["csrftoken"]

        attempt = 0
        while True:
            # Upload file with retry logic
            try:
                with open(file_path, "rb") as f:
                    files = {"file": (filename, f, "image/png")}
                    data: dict[str, Any] = {
                        "action": "upload",
                        "filename": filename,
                        "comment": comment,
                        "text": text,
                        "token": csrf_token,
                        "format": "json",
                    }

                    if ignore_warnings:
                        data["ignorewarnings"] = "1"

                    if bot:
                        data["bot"] = "1"

                    headers = {"User-Agent": self.user_agent}
                    response = self.auth_session.post(
                        self.api_url,
                        data=data,
                        files=files,
                        headers=headers,
                        timeout=WIKI_API_TIMEOUT_SECONDS,
                    )
                    response.raise_for_status()
                    result: dict[str, Any] = response.json()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                # Retry on rate limit (429) or service unavailable (503)
                if status in (429, 503) and attempt < max_retries:
                    # Check for Retry-After header (server tells us how long to wait)
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            # Fallback to exponential backoff if header is invalid
                            delay = backoff_base * (2**attempt)
                    else:
                        # Use exponential backoff if no Retry-After header
                        delay = backoff_base * (2**attempt)
                    time.sleep(delay)
                    attempt += 1
                    continue
                raise

            # Check for API-level rate limit error (not HTTP 429, but error in JSON)
            if "error" in result:
                error_info = result["error"]
                error_code = error_info.get("code", "")

                # Handle rate limit as retryable error
                if error_code == "ratelimited" and attempt < max_retries:
                    delay = backoff_base * (2**attempt)
                    time.sleep(delay)
                    attempt += 1
                    continue

                # Not retryable or out of retries
                raise WikiAPIError(
                    f"Upload failed: {error_code}: {error_info.get('info')}"
                )

            upload_result = result.get("upload", {})
            if upload_result.get("result") != "Success":
                # Handle warnings
                if "warnings" in upload_result and not ignore_warnings:
                    warnings = upload_result["warnings"]
                    raise WikiAPIError(f"Upload warnings: {warnings}")
                raise WikiAPIError(f"Unexpected upload response: {result}")

            return upload_result

    def fetch_templatedata(
        self,
        titles: list[str],
        *,
        max_retries: int = WIKI_DEFAULT_MAX_RETRIES,
        backoff_base: float = WIKI_DEFAULT_BACKOFF_BASE,
    ) -> dict[str, dict[str, Any]]:
        """Fetch TemplateData for a list of titles (best effort).

        Args:
            titles: List of template titles
            max_retries: Maximum number of retry attempts
            backoff_base: Base delay for exponential backoff (seconds)

        Returns:
            Mapping of title → templatedata dict
        """
        out: dict[str, dict[str, Any]] = {}
        if not titles:
            return out
        params = {
            "action": "templatedata",
            "format": "json",
            "titles": "|".join(titles),
        }
        attempt = 0
        while True:
            try:
                data = self._request(params)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (429, 503) and attempt < max_retries:
                    # Check for Retry-After header
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = backoff_base * (2**attempt)
                    else:
                        delay = backoff_base * (2**attempt)
                    time.sleep(delay)
                    attempt += 1
                    continue
                raise
            if (
                isinstance(data, dict)
                and data.get("error", {}).get("code") == "maxlag"
                and attempt < max_retries
            ):
                delay = backoff_base * (2**attempt)
                time.sleep(delay)
                attempt += 1
                continue
            break
        for p in data.get("pages", {}).values():
            title = p.get("title")
            if not title:
                continue
            out[str(title)] = p
        return out
