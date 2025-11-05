"""Unit tests for MediaWiki API client.

These tests verify the MediaWiki client's behavior using mocks to avoid
requiring actual network connections or MediaWiki credentials.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from erenshor.infrastructure.time import MockClock
from erenshor.infrastructure.wiki import (
    MediaWikiAPIError,
    MediaWikiAuthenticationError,
    MediaWikiClient,
    MediaWikiEditError,
    MediaWikiNetworkError,
    MediaWikiRateLimitError,
)


class TestMediaWikiClientInitialization:
    """Test MediaWiki client initialization and validation."""

    def test_init_success(self) -> None:
        """Test successful initialization with valid parameters."""
        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            bot_username="TestBot@TestBot",
            bot_password="testpass",
            batch_size=25,
            rate_limit_delay=1.0,
            clock=MockClock(),
        )

        assert client.api_url == "https://erenshor.wiki.gg/api.php"
        assert client.bot_username == "TestBot@TestBot"
        assert client.bot_password == "testpass"
        assert client.batch_size == 25
        assert client.rate_limit_delay == 1.0

    def test_init_invalid_api_url(self) -> None:
        """Test initialization fails with invalid API URL."""
        with pytest.raises(ValueError, match=r"must end with /api\.php"):
            MediaWikiClient(api_url="https://erenshor.wiki.gg/", clock=MockClock())

        with pytest.raises(ValueError, match=r"must end with /api\.php"):
            MediaWikiClient(api_url="https://erenshor.wiki.gg/index.php", clock=MockClock())

    def test_init_invalid_batch_size(self) -> None:
        """Test initialization fails with invalid batch size."""
        with pytest.raises(ValueError, match="Batch size must be between 1 and 50"):
            MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", batch_size=0, clock=MockClock())

        with pytest.raises(ValueError, match="Batch size must be between 1 and 50"):
            MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", batch_size=51, clock=MockClock())

    def test_init_defaults(self) -> None:
        """Test default values are set correctly."""
        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        assert client.bot_username == ""
        assert client.bot_password == ""
        assert client.batch_size == 25
        assert client.rate_limit_delay == 1.0
        assert client.edit_summary == "Automated wiki update"
        assert client.minor_edit is True

    def test_context_manager(self) -> None:
        """Test client works as context manager."""
        with MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock()) as client:
            assert isinstance(client, MediaWikiClient)


class TestMediaWikiClientLogin:
    """Test MediaWiki login functionality."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_login_success(self, mock_client_class: MagicMock) -> None:
        """Test successful login with bot credentials."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Mock login token request
        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"logintoken": "test_login_token"}}}

        # Mock login request
        login_response = MagicMock()
        login_response.json.return_value = {"login": {"result": "Success"}}

        mock_http_client.get.return_value = token_response
        mock_http_client.post.return_value = login_response

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            bot_username="TestBot@TestBot",
            bot_password="testpass",
            clock=MockClock(),
        )

        client.login()

        # Verify requests were made
        assert mock_http_client.get.called
        assert mock_http_client.post.called

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_login_missing_credentials(self, mock_client_class: MagicMock) -> None:
        """Test login fails when credentials not provided."""
        mock_client_class.return_value = MagicMock()

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        with pytest.raises(ValueError, match="Bot username and password required"):
            client.login()

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_login_failure(self, mock_client_class: MagicMock) -> None:
        """Test login fails with invalid credentials."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Mock login token request
        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"logintoken": "test_login_token"}}}

        # Mock login failure
        login_response = MagicMock()
        login_response.json.return_value = {"login": {"result": "Failed", "reason": "Incorrect password"}}

        mock_http_client.get.return_value = token_response
        mock_http_client.post.return_value = login_response

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            bot_username="TestBot@TestBot",
            bot_password="wrongpass",
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiAuthenticationError, match="Login failed"):
            client.login()


class TestMediaWikiClientGetPage:
    """Test fetching single wiki pages."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_get_page_success(self, mock_client_class: MagicMock) -> None:
        """Test successful page fetch."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Mock page content response
        response = MagicMock()
        response.json.return_value = {
            "query": {
                "pages": {
                    "123": {
                        "pageid": 123,
                        "title": "Item:Sword",
                        "revisions": [{"slots": {"main": {"*": "{{Item|name=Sword|damage=10}}"}}}],
                    }
                }
            }
        }

        mock_http_client.get.return_value = response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        content = client.get_page("Item:Sword")

        assert content == "{{Item|name=Sword|damage=10}}"
        assert mock_http_client.get.called

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_get_page_missing(self, mock_client_class: MagicMock) -> None:
        """Test fetching non-existent page returns None."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Mock missing page response (negative page ID)
        response = MagicMock()
        response.json.return_value = {
            "query": {
                "pages": {
                    "-1": {
                        "title": "Item:NonExistent",
                        "missing": "",
                    }
                }
            }
        }

        mock_http_client.get.return_value = response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        content = client.get_page("Item:NonExistent")

        assert content is None

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_get_page_network_error(self, mock_client_class: MagicMock) -> None:
        """Test network error handling."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        mock_http_client.get.side_effect = httpx.NetworkError("Connection failed")

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        with pytest.raises(MediaWikiNetworkError, match="Network error"):
            client.get_page("Item:Sword")


class TestMediaWikiClientGetPages:
    """Test batch fetching of multiple pages."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_get_pages_success(self, mock_client_class: MagicMock) -> None:
        """Test successful batch fetch."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Mock batch response
        response = MagicMock()
        response.json.return_value = {
            "query": {
                "pages": {
                    "123": {
                        "pageid": 123,
                        "title": "Item:Sword",
                        "revisions": [{"slots": {"main": {"*": "Sword content"}}}],
                    },
                    "124": {
                        "pageid": 124,
                        "title": "Item:Shield",
                        "revisions": [{"slots": {"main": {"*": "Shield content"}}}],
                    },
                    "-1": {
                        "title": "Item:Missing",
                        "missing": "",
                    },
                }
            }
        }

        mock_http_client.get.return_value = response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        pages = client.get_pages(["Item:Sword", "Item:Shield", "Item:Missing"])

        assert len(pages) == 3
        assert pages["Item:Sword"] == "Sword content"
        assert pages["Item:Shield"] == "Shield content"
        assert pages["Item:Missing"] is None

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_get_pages_empty_list(self, mock_client_class: MagicMock) -> None:
        """Test batch fetch with empty list returns empty dict."""
        mock_client_class.return_value = MagicMock()

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        pages = client.get_pages([])

        assert pages == {}

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_get_pages_batching(self, mock_client_class: MagicMock) -> None:
        """Test batch fetch splits large requests."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Mock response for each batch
        response = MagicMock()
        response.json.return_value = {"query": {"pages": {}}}
        mock_http_client.get.return_value = response

        # Request 60 pages with batch size 25 (should make 3 requests)
        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", batch_size=25, clock=MockClock())
        titles = [f"Page:{i}" for i in range(60)]
        client.get_pages(titles)

        # Verify 3 GET requests were made
        assert mock_http_client.get.call_count == 3


class TestMediaWikiClientEditPage:
    """Test wiki page editing."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_edit_page_success(self, mock_client_class: MagicMock) -> None:
        """Test successful page edit."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Mock CSRF token request
        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"csrftoken": "test_csrf_token"}}}

        # Mock edit request
        edit_response = MagicMock()
        edit_response.json.return_value = {"edit": {"result": "Success"}}

        mock_http_client.get.return_value = token_response
        mock_http_client.post.return_value = edit_response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        client.edit_page(
            title="Item:Sword",
            content="{{Item|name=Sword|damage=10}}",
            summary="Update item stats",
        )

        # Verify requests were made
        assert mock_http_client.get.called  # CSRF token
        assert mock_http_client.post.called  # Edit

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_edit_page_failure(self, mock_client_class: MagicMock) -> None:
        """Test edit failure handling."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # Mock CSRF token request
        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"csrftoken": "test_csrf_token"}}}

        # Mock edit failure
        edit_response = MagicMock()
        edit_response.json.return_value = {"edit": {"result": "Failure", "error": "Permission denied"}}

        mock_http_client.get.return_value = token_response
        mock_http_client.post.return_value = edit_response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        with pytest.raises(MediaWikiEditError, match="Edit failed"):
            client.edit_page(title="Item:Sword", content="new content")

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_edit_page_uses_defaults(self, mock_client_class: MagicMock) -> None:
        """Test edit uses default summary and minor flag."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"csrftoken": "test_csrf_token"}}}

        edit_response = MagicMock()
        edit_response.json.return_value = {"edit": {"result": "Success"}}

        mock_http_client.get.return_value = token_response
        mock_http_client.post.return_value = edit_response

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            edit_summary="Default summary",
            minor_edit=True,
            clock=MockClock(),
        )

        client.edit_page(title="Item:Sword", content="new content")

        # Verify post was called with data containing defaults
        call_data = mock_http_client.post.call_args[1]["data"]
        assert call_data["summary"] == "Default summary"
        assert call_data["minor"] == "1"


class TestMediaWikiClientPageExists:
    """Test page existence checking."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_page_exists_true(self, mock_client_class: MagicMock) -> None:
        """Test page existence check for existing page."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        response = MagicMock()
        response.json.return_value = {"query": {"pages": {"123": {"pageid": 123, "title": "Item:Sword"}}}}

        mock_http_client.get.return_value = response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        exists = client.page_exists("Item:Sword")

        assert exists is True

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_page_exists_false(self, mock_client_class: MagicMock) -> None:
        """Test page existence check for missing page."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        response = MagicMock()
        response.json.return_value = {"query": {"pages": {"-1": {"title": "Item:Missing", "missing": ""}}}}

        mock_http_client.get.return_value = response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        exists = client.page_exists("Item:Missing")

        assert exists is False


class TestMediaWikiClientRateLimiting:
    """Test rate limiting behavior."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_rate_limiting_applied(self, mock_client_class: MagicMock) -> None:
        """Test rate limiting delays requests."""
        from erenshor.infrastructure.time import MockClock

        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        response = MagicMock()
        response.json.return_value = {"query": {"pages": {"1": {"revisions": [{"slots": {"main": {"*": "content"}}}]}}}}
        mock_http_client.get.return_value = response

        # Use MockClock to verify rate limiting behavior without actual delays
        mock_clock = MockClock()
        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", rate_limit_delay=1.0, clock=mock_clock)

        # Make first request (won't sleep since _last_request_time is 0.0)
        client.get_page("Page1")
        time_after_first = mock_clock.time()

        # Advance clock by less than rate limit to trigger sleep on next request
        mock_clock.advance(0.3)

        # Make second request - should sleep for 0.7s to maintain 1.0s rate limit
        client.get_page("Page2")
        time_after_second = mock_clock.time()

        # Time between requests should be at least rate_limit_delay
        time_between_requests = time_after_second - time_after_first
        assert time_between_requests >= 1.0


class TestMediaWikiClientErrorHandling:
    """Test error handling for various failure scenarios."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_api_error_handling(self, mock_client_class: MagicMock) -> None:
        """Test handling of API error responses."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        response = MagicMock()
        response.json.return_value = {"error": {"code": "badtoken", "info": "Invalid CSRF token"}}

        mock_http_client.get.return_value = response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        with pytest.raises(MediaWikiAPIError, match="Invalid CSRF token"):
            client.get_page("Item:Sword")

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_rate_limit_error(self, mock_client_class: MagicMock) -> None:
        """Test rate limit error handling."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        response = MagicMock()
        response.status_code = 429
        mock_http_client.get.side_effect = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=response)

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        with pytest.raises(MediaWikiRateLimitError, match="Rate limit exceeded"):
            client.get_page("Item:Sword")

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_timeout_error(self, mock_client_class: MagicMock) -> None:
        """Test timeout error handling."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        mock_http_client.get.side_effect = httpx.TimeoutException("Request timeout")

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        with pytest.raises(MediaWikiNetworkError, match="Request timeout"):
            client.get_page("Item:Sword")

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_invalid_json_response(self, mock_client_class: MagicMock) -> None:
        """Test handling of invalid JSON responses."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        response = MagicMock()
        response.json.side_effect = ValueError("Invalid JSON")

        mock_http_client.get.return_value = response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        with pytest.raises(MediaWikiAPIError, match="Invalid JSON response"):
            client.get_page("Item:Sword")


class TestMediaWikiClientCSRFToken:
    """Test CSRF token management."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_csrf_token_cached(self, mock_client_class: MagicMock) -> None:
        """Test CSRF token is cached and reused."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"csrftoken": "test_token"}}}

        mock_http_client.get.return_value = token_response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        # Get token twice
        token1 = client.get_csrf_token()
        token2 = client.get_csrf_token()

        assert token1 == "test_token"
        assert token2 == "test_token"

        # Verify only one GET request was made (token cached)
        assert mock_http_client.get.call_count == 1

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_csrf_token_cleared_on_error(self, mock_client_class: MagicMock) -> None:
        """Test CSRF token is cleared when badtoken error occurs."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        # First request succeeds with token
        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"csrftoken": "test_token"}}}

        # Second request returns badtoken error
        error_response = MagicMock()
        error_response.json.return_value = {"error": {"code": "badtoken", "info": "Invalid token"}}

        mock_http_client.get.side_effect = [token_response, error_response]

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        # Get token (succeeds)
        client.get_csrf_token()

        # Make request that fails with badtoken
        with pytest.raises(MediaWikiAPIError):
            client.get_page("Item:Sword")

        # Verify token was cleared
        assert client._csrf_token is None
