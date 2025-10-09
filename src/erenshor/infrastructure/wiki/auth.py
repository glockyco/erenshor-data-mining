"""MediaWiki bot authentication management."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from erenshor.domain.exceptions import WikiAPIError
from erenshor.infrastructure.wiki.constants import (
    WIKI_API_TIMEOUT_SECONDS,
    WIKI_DEFAULT_USER_AGENT,
    WIKI_MIN_REQUEST_DELAY_SECONDS,
)

__all__ = ["BotCredentials", "MediaWikiAuth"]

logger = logging.getLogger(__name__)


@dataclass
class BotCredentials:
    """Bot account credentials for MediaWiki authentication."""

    username: str
    password: str  # Bot password from Special:BotPasswords, not main account password
    api_url: str
    user_agent: str = WIKI_DEFAULT_USER_AGENT


class MediaWikiAuth:
    """Handle MediaWiki bot authentication with proper token management."""

    def __init__(self, credentials: BotCredentials):
        """Initialize authentication manager with bot credentials."""
        self.credentials = credentials
        self.session = httpx.Client()
        self.session.headers.update({"User-Agent": credentials.user_agent})

        # Authentication state
        self.login_token: Optional[str] = None
        self.csrf_token: Optional[str] = None
        self.logged_in = False

        # Rate limiting
        self.last_request_time = 0.0
        self.min_request_delay = WIKI_MIN_REQUEST_DELAY_SECONDS

    def get_session(self) -> httpx.Client:
        """Get the authenticated session for use by WikiAPIClient.

        Returns:
            Authenticated httpx.Client
        """
        return self.session

    def get_login_token(self) -> str:
        """Get login token for authentication."""
        params = {
            "action": "query",
            "meta": "tokens",
            "type": "login",
            "format": "json",
        }
        response = self._request(params)
        token = str(response["query"]["tokens"]["logintoken"])
        self.login_token = token
        return token

    def login(self) -> bool:
        """Perform bot login with MediaWiki two-step authentication process."""
        try:
            logger.info(f"Authenticating bot user: {self.credentials.username}")

            # Step 1: Get login token
            self.get_login_token()
            logger.info("Login token obtained")

            # Step 2: Login with credentials and token
            login_params = {
                "action": "login",
                "lgname": self.credentials.username,
                "lgpassword": self.credentials.password,
                "lgtoken": self.login_token,
                "format": "json",
            }
            response = self._request(login_params, method="POST")

            login_result = response.get("login", {})
            result = login_result.get("result")

            if result == "Success":
                self.logged_in = True
                logger.info("Bot authentication successful")
                return True
            else:
                error_msg = f"Login failed: {result}"
                if "reason" in login_result:
                    error_msg += f" - {login_result['reason']}"
                logger.error(error_msg)
                return False

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def get_csrf_token(self) -> str:
        """Get CSRF token for editing operations."""
        if not self.logged_in:
            raise WikiAPIError("Must be logged in to get CSRF token")

        params = {"action": "query", "meta": "tokens", "format": "json"}
        response = self._request(params)
        token = str(response["query"]["tokens"]["csrftoken"])
        self.csrf_token = token
        return token

    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self.logged_in

    def logout(self) -> None:
        """Logout and clear authentication state."""
        if self.logged_in:
            try:
                params = {"action": "logout", "format": "json"}
                self._request(params, method="POST")
            except Exception as e:
                logger.warning(f"Logout failed: {e}")
            finally:
                self._clear_auth_state()

    def _clear_auth_state(self) -> None:
        """Clear all authentication state."""
        self.login_token = None
        self.csrf_token = None
        self.logged_in = False
        self.session.cookies.clear()

    def _rate_limit(self) -> None:
        """Implement rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_delay:
            sleep_time = self.min_request_delay - elapsed
            time.sleep(sleep_time)

    def _request(self, params: Dict[str, Any], method: str = "GET") -> Dict[str, Any]:
        """Make authenticated API request with error handling and rate limiting."""
        self._rate_limit()

        try:
            if method.upper() == "GET":
                response = self.session.get(
                    self.credentials.api_url,
                    params=params,
                    timeout=WIKI_API_TIMEOUT_SECONDS,
                )
            else:
                response = self.session.post(
                    self.credentials.api_url,
                    data=params,
                    timeout=WIKI_API_TIMEOUT_SECONDS,
                )

            self.last_request_time = time.time()
            response.raise_for_status()

            data: Dict[str, Any] = response.json()

            # Check for API errors
            if "error" in data:
                error_info = data["error"]
                raise WikiAPIError(
                    f"API Error: {error_info.get('code')} - {error_info.get('info')}"
                )

            return data

        except httpx.RequestError as e:
            raise WikiAPIError(f"HTTP Request failed: {e}") from e
        except ValueError as e:
            raise WikiAPIError(f"Invalid JSON response: {e}") from e
