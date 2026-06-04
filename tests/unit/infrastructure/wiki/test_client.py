"""Unit tests for MediaWiki API client.

These tests verify the MediaWiki client's behavior without requiring MediaWiki
credentials. New HTTP-client behavior uses a local server instead of patching
the httpx client internals.
"""

import hashlib
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from erenshor.infrastructure.time import MockClock
from erenshor.infrastructure.wiki import (
    MediaWikiAPIError,
    MediaWikiAssertionError,
    MediaWikiAuthenticationError,
    MediaWikiClient,
    MediaWikiEditConflictError,
    MediaWikiEditError,
    MediaWikiNetworkError,
    MediaWikiPageRevision,
    MediaWikiPermissionError,
    MediaWikiRateLimitError,
    MediaWikiRequestPolicy,
)


@dataclass(slots=True)
class _CapturedWikiRequest:
    method: str
    path: str
    query: dict[str, str]
    data: dict[str, str]


@dataclass(slots=True)
class _FakeResponse:
    """A scripted HTTP response for the fake MediaWiki API."""

    body: dict[str, Any]
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class _FakeWikiAPI:
    responses: list[dict[str, Any] | _FakeResponse]
    requests: list[_CapturedWikiRequest] = field(default_factory=list)

    def next_response(self) -> _FakeResponse:
        if not self.responses:
            raise AssertionError("Fake MediaWiki API received more requests than configured responses")
        scripted = self.responses.pop(0)
        if isinstance(scripted, _FakeResponse):
            return scripted
        return _FakeResponse(body=scripted)


@contextmanager
def _mediawiki_api_server(
    responses: list[dict[str, Any] | _FakeResponse],
) -> Iterator[tuple[str, _FakeWikiAPI]]:
    api = _FakeWikiAPI(responses=list(responses))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._handle_request()

        def do_POST(self) -> None:
            self._handle_request()

        def log_message(self, format: str, *args: object) -> None:
            return

        def _handle_request(self) -> None:
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode() if length else ""
            api.requests.append(
                _CapturedWikiRequest(
                    method=self.command,
                    path=parsed.path,
                    query={key: values[-1] for key, values in parse_qs(parsed.query).items()},
                    data={key: values[-1] for key, values in parse_qs(body).items()},
                )
            )
            scripted = api.next_response()
            payload = json.dumps(scripted.body).encode()
            self.send_response(scripted.status_code)
            self.send_header("Content-Type", "application/json")
            for header_name, header_value in scripted.headers.items():
                self.send_header(header_name, header_value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api.php", api
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


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


class TestMediaWikiClientRevisionMetadata:
    """Test conflict-safe revision metadata fetching."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_get_page_revision_metadata_requests_revision_and_current_timestamps(
        self, mock_client_class: MagicMock
    ) -> None:
        """Test metadata fetch requests base revision data and API current timestamp."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        response = MagicMock()
        response.json.return_value = {
            "curtimestamp": "2026-06-04T12:00:00Z",
            "query": {
                "pages": {
                    "42": {
                        "pageid": 42,
                        "title": "Template:Item",
                        "revisions": [
                            {
                                "revid": 1234,
                                "timestamp": "2026-06-04T11:59:00Z",
                            }
                        ],
                    }
                }
            },
        }
        mock_http_client.get.return_value = response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        revision = client.get_page_revision_metadata("Template:Item")

        assert revision == MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )
        call_params = mock_http_client.get.call_args[1]["params"]
        assert call_params["action"] == "query"
        assert call_params["titles"] == "Template:Item"
        assert call_params["prop"] == "revisions"
        assert call_params["rvprop"] == "ids|timestamp"
        assert call_params["curtimestamp"] == "1"

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_get_page_revision_metadata_returns_none_for_missing_page(self, mock_client_class: MagicMock) -> None:
        """Test missing pages do not produce fabricated revision metadata."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        response = MagicMock()
        response.json.return_value = {
            "curtimestamp": "2026-06-04T12:00:00Z",
            "query": {"pages": {"-1": {"missing": True, "title": "Template:Missing"}}},
        }
        mock_http_client.get.return_value = response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        assert client.get_page_revision_metadata("Template:Missing") is None

    def test_get_edit_start_timestamp_requests_current_timestamp_with_assertion(self) -> None:
        """Test start timestamp fetch uses MediaWiki's current API timestamp and assertion guard."""
        with _mediawiki_api_server([{"curtimestamp": "2026-06-04T12:00:00Z", "query": {"pages": {}}}]) as (
            api_url,
            api,
        ):
            client = MediaWikiClient(api_url=api_url, clock=MockClock())

            timestamp = client.get_edit_start_timestamp(assertion="bot", assert_user="ErenshorBot")

        assert timestamp == "2026-06-04T12:00:00Z"
        assert len(api.requests) == 1
        request = api.requests[0]
        assert request.method == "GET"
        assert request.path == "/api.php"
        assert request.query["action"] == "query"
        assert request.query["curtimestamp"] == "1"
        assert request.query["assert"] == "bot"
        assert request.query["assertuser"] == "ErenshorBot"


class TestMediaWikiClientSafeCreatePage:
    """Test conflict-safe wiki page creation."""

    def test_safe_create_page_sends_create_hash_timestamp_and_assertion_parameters(self) -> None:
        """Test safe creates include create-only, start timestamp, MD5, and assertion guard."""
        with _mediawiki_api_server(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"edit": {"result": "Success", "newrevid": 1235}},
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, clock=MockClock())

            new_revision_id = client.safe_create_page(
                title="Module:Erenshor/Data/Items",
                content="return {}",
                start_timestamp="2026-06-04T12:00:00Z",
                summary="Create repo-owned module",
                assertion="bot",
                assert_user="ErenshorBot",
            )

        assert new_revision_id == 1235
        assert len(api.requests) == 2
        token_request, edit_request = api.requests
        assert token_request.method == "GET"
        assert token_request.query["action"] == "query"
        assert token_request.query["meta"] == "tokens"
        assert edit_request.method == "POST"
        assert edit_request.data["action"] == "edit"
        assert edit_request.data["title"] == "Module:Erenshor/Data/Items"
        assert edit_request.data["text"] == "return {}"
        assert edit_request.data["summary"] == "Create repo-owned module"
        assert edit_request.data["token"] == "test_csrf_token"
        assert edit_request.data["createonly"] == "1"
        assert edit_request.data["starttimestamp"] == "2026-06-04T12:00:00Z"
        assert edit_request.data["md5"] == hashlib.md5(b"return {}", usedforsecurity=False).hexdigest()
        assert edit_request.data["assert"] == "bot"
        assert edit_request.data["assertuser"] == "ErenshorBot"
        assert edit_request.data["bot"] == "1"

    def test_safe_create_page_refreshes_csrf_token_once_after_badtoken(self) -> None:
        """Test stale CSRF tokens are refreshed once without changing the create guard."""
        with _mediawiki_api_server(
            [
                {"query": {"tokens": {"csrftoken": "stale_token"}}},
                {"error": {"code": "badtoken", "info": "Invalid token"}},
                {"query": {"tokens": {"csrftoken": "fresh_token"}}},
                {"edit": {"result": "Success", "newrevid": 1235}},
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, clock=MockClock())

            new_revision_id = client.safe_create_page(
                title="Module:Erenshor/Data/Items",
                content="return {}",
                start_timestamp="2026-06-04T12:00:00Z",
                summary="Create repo-owned module",
            )

        assert new_revision_id == 1235
        edit_requests = [request for request in api.requests if request.method == "POST"]
        assert len(edit_requests) == 2
        assert edit_requests[0].data["token"] == "stale_token"
        assert edit_requests[1].data["token"] == "fresh_token"
        assert edit_requests[0].data["createonly"] == edit_requests[1].data["createonly"] == "1"

    def test_safe_create_page_surfaces_existing_page_as_conflict(self) -> None:
        """Test losing the create race (articleexists) is a conflict, not a generic failure."""
        with _mediawiki_api_server(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"error": {"code": "articleexists", "info": "The page you tried to create has been created already."}},
            ]
        ) as (api_url, _api):
            client = MediaWikiClient(api_url=api_url, clock=MockClock())

            with pytest.raises(MediaWikiEditConflictError, match="creating") as excinfo:
                client.safe_create_page(
                    title="Module:Erenshor/Data/Items",
                    content="return {}",
                    start_timestamp="2026-06-04T12:00:00Z",
                )

        assert "Module:Erenshor/Data/Items" in str(excinfo.value)


class TestMediaWikiClientSafeEditPage:
    """Test conflict-safe wiki page edits."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_safe_edit_page_sends_conflict_hash_and_assertion_parameters(self, mock_client_class: MagicMock) -> None:
        """Test safe edits include base revision, start timestamp, MD5, and assertion guard."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"csrftoken": "test_csrf_token"}}}

        edit_response = MagicMock()
        edit_response.json.return_value = {"edit": {"result": "Success", "newrevid": 1235}}

        mock_http_client.get.return_value = token_response
        mock_http_client.post.return_value = edit_response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )

        new_revision_id = client.safe_edit_page(
            title="Template:Item",
            content="new template source",
            base_revision=base_revision,
            summary="Deploy repo-owned template",
            assertion="bot",
            assert_user="ErenshorBot",
        )

        assert new_revision_id == 1235
        call_data = mock_http_client.post.call_args[1]["data"]
        assert call_data["action"] == "edit"
        assert call_data["title"] == "Template:Item"
        assert call_data["text"] == "new template source"
        assert call_data["summary"] == "Deploy repo-owned template"
        assert call_data["token"] == "test_csrf_token"
        assert call_data["baserevid"] == "1234"
        assert call_data["starttimestamp"] == "2026-06-04T12:00:00Z"
        assert call_data["md5"] == hashlib.md5(b"new template source", usedforsecurity=False).hexdigest()
        assert call_data["assert"] == "bot"
        assert call_data["assertuser"] == "ErenshorBot"
        assert call_data["bot"] == "1"

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_safe_edit_page_refreshes_csrf_token_once_after_badtoken(self, mock_client_class: MagicMock) -> None:
        """Test stale CSRF tokens are refreshed once without changing the base revision guard."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        first_token_response = MagicMock()
        first_token_response.json.return_value = {"query": {"tokens": {"csrftoken": "stale_token"}}}

        badtoken_response = MagicMock()
        badtoken_response.json.return_value = {"error": {"code": "badtoken", "info": "Invalid token"}}

        second_token_response = MagicMock()
        second_token_response.json.return_value = {"query": {"tokens": {"csrftoken": "fresh_token"}}}

        success_response = MagicMock()
        success_response.json.return_value = {"edit": {"result": "Success", "newrevid": 1235}}

        mock_http_client.get.side_effect = [first_token_response, second_token_response]
        mock_http_client.post.side_effect = [badtoken_response, success_response]

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )

        new_revision_id = client.safe_edit_page(
            title="Template:Item",
            content="new template source",
            base_revision=base_revision,
            summary="Deploy repo-owned template",
        )

        assert new_revision_id == 1235
        assert mock_http_client.post.call_count == 2
        first_data = mock_http_client.post.call_args_list[0][1]["data"]
        second_data = mock_http_client.post.call_args_list[1][1]["data"]
        assert first_data["token"] == "stale_token"
        assert second_data["token"] == "fresh_token"
        assert first_data["baserevid"] == second_data["baserevid"] == "1234"

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_safe_edit_page_fails_after_second_badtoken(self, mock_client_class: MagicMock) -> None:
        """Test token refresh is bounded to one retry."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        first_token_response = MagicMock()
        first_token_response.json.return_value = {"query": {"tokens": {"csrftoken": "stale_token"}}}
        second_token_response = MagicMock()
        second_token_response.json.return_value = {"query": {"tokens": {"csrftoken": "still_bad_token"}}}
        badtoken_response = MagicMock()
        badtoken_response.json.return_value = {"error": {"code": "badtoken", "info": "Invalid token"}}

        mock_http_client.get.side_effect = [first_token_response, second_token_response]
        mock_http_client.post.side_effect = [badtoken_response, badtoken_response]

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )

        with pytest.raises(MediaWikiEditError, match="Invalid token"):
            client.safe_edit_page(
                title="Template:Item",
                content="new template source",
                base_revision=base_revision,
                summary="Deploy repo-owned template",
            )

        assert mock_http_client.post.call_count == 2

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_safe_edit_page_surfaces_edit_conflict(self, mock_client_class: MagicMock) -> None:
        """Test edit conflicts are raised as explicit conflict failures."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"csrftoken": "test_csrf_token"}}}
        conflict_response = MagicMock()
        conflict_response.json.return_value = {"error": {"code": "editconflict", "info": "Edit conflict"}}

        mock_http_client.get.return_value = token_response
        mock_http_client.post.return_value = conflict_response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )

        with pytest.raises(MediaWikiEditConflictError, match="Edit conflict"):
            client.safe_edit_page(
                title="Template:Item",
                content="new template source",
                base_revision=base_revision,
            )

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_safe_edit_page_surfaces_assertion_failure(self, mock_client_class: MagicMock) -> None:
        """Test assertion failures are raised separately from generic edit failures."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"csrftoken": "test_csrf_token"}}}
        assertion_response = MagicMock()
        assertion_response.json.return_value = {"error": {"code": "assertbotfailed", "info": "Not logged in as a bot"}}

        mock_http_client.get.return_value = token_response
        mock_http_client.post.return_value = assertion_response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )

        with pytest.raises(MediaWikiAssertionError, match="Not logged in as a bot"):
            client.safe_edit_page(
                title="Template:Item",
                content="new template source",
                base_revision=base_revision,
            )

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_safe_edit_page_surfaces_permission_failure(self, mock_client_class: MagicMock) -> None:
        """Test permission failures are raised separately from generic edit failures."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        token_response = MagicMock()
        token_response.json.return_value = {"query": {"tokens": {"csrftoken": "test_csrf_token"}}}
        permission_response = MagicMock()
        permission_response.json.return_value = {"error": {"code": "permissiondenied", "info": "Permission denied"}}
        mock_http_client.get.return_value = token_response
        mock_http_client.post.return_value = permission_response

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )

        with pytest.raises(MediaWikiPermissionError, match="Permission denied"):
            client.safe_edit_page(
                title="Template:Item",
                content="new template source",
                base_revision=base_revision,
            )

    def test_safe_edit_page_returns_base_revision_on_no_change(self) -> None:
        """Test an identical-content edit (nochange) reports the existing revision, not a crash."""
        with _mediawiki_api_server(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"edit": {"result": "Success", "pageid": 7, "title": "Template:Item", "nochange": ""}},
            ]
        ) as (api_url, _api):
            client = MediaWikiClient(api_url=api_url, clock=MockClock())
            base_revision = MediaWikiPageRevision(
                title="Template:Item",
                page_id=7,
                revision_id=1234,
                timestamp="2026-06-04T11:59:00Z",
                start_timestamp="2026-06-04T12:00:00Z",
            )

            revision_id = client.safe_edit_page(
                title="Template:Item",
                content="identical source",
                base_revision=base_revision,
            )

        assert revision_id == 1234


class TestMediaWikiClientEmbeddedIn:
    """Test reverse transclusion dependency discovery."""

    @patch("erenshor.infrastructure.wiki.client.httpx.Client")
    def test_get_embeddedin_pages_handles_continuation_and_namespace_filters(
        self, mock_client_class: MagicMock
    ) -> None:
        """Test embeddedin discovery follows continuation and passes namespace filters."""
        mock_http_client = MagicMock()
        mock_client_class.return_value = mock_http_client

        first_response = MagicMock()
        first_response.json.return_value = {
            "continue": {"eicontinue": "10|123", "continue": "-||"},
            "query": {
                "embeddedin": [
                    {"pageid": 1, "ns": 0, "title": "Ember Longsword"},
                    {"pageid": 2, "ns": 0, "title": "Abyssal Plate"},
                ]
            },
        }
        second_response = MagicMock()
        second_response.json.return_value = {
            "query": {"embeddedin": [{"pageid": 3, "ns": 10, "title": "Template:WeaponTable"}]},
        }
        mock_http_client.get.side_effect = [first_response, second_response]

        client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php", clock=MockClock())

        pages = client.get_embeddedin_pages("Template:Item", namespaces=(0, 10), assertion="bot")

        assert pages == ("Ember Longsword", "Abyssal Plate", "Template:WeaponTable")
        first_params = mock_http_client.get.call_args_list[0][1]["params"]
        second_params = mock_http_client.get.call_args_list[1][1]["params"]
        assert first_params["action"] == "query"
        assert first_params["list"] == "embeddedin"
        assert first_params["eititle"] == "Template:Item"
        assert first_params["einamespace"] == "0|10"
        assert first_params["eilimit"] == "max"
        assert first_params["assert"] == "bot"
        assert "eicontinue" not in first_params
        assert second_params["eicontinue"] == "10|123"


class TestMediaWikiClientPurgePages:
    """Test forced link-update purges of dependent pages."""

    def test_purge_pages_forces_link_update_with_assertion(self) -> None:
        """Test purge requests force a link-table update and carry the bot assertion."""
        with _mediawiki_api_server(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {
                    "purge": [
                        {"ns": 0, "title": "Ember Longsword", "purged": "", "linkupdate": ""},
                        {"ns": 0, "title": "Abyssal Plate", "purged": "", "linkupdate": ""},
                    ]
                },
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, clock=MockClock())

            purged = client.purge_pages(
                ["Ember Longsword", "Abyssal Plate"],
                assertion="bot",
                assert_user="ErenshorBot",
            )

        assert purged == ("Ember Longsword", "Abyssal Plate")
        purge_request = next(request for request in api.requests if request.method == "POST")
        assert purge_request.data["action"] == "purge"
        assert purge_request.data["titles"] == "Ember Longsword|Abyssal Plate"
        assert purge_request.data["forcelinkupdate"] == "1"
        assert purge_request.data["assert"] == "bot"
        assert purge_request.data["assertuser"] == "ErenshorBot"
        assert purge_request.data["token"] == "test_csrf_token"

    def test_purge_pages_returns_empty_without_titles(self) -> None:
        """Test purging no titles performs no request."""
        with _mediawiki_api_server([]) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, clock=MockClock())
            assert client.purge_pages([]) == ()
        assert api.requests == []


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


class TestMediaWikiClientRequestRetry:
    """Test bounded backoff retry for transient lag and rate-limit responses."""

    _FAST_POLICY = MediaWikiRequestPolicy(read_delay=0.0, write_delay=0.0, base_backoff=1.0, jitter=0.0, max_retries=2)

    def test_request_retries_after_maxlag_error_then_succeeds(self) -> None:
        """A maxlag error is honored with a bounded wait, then the request succeeds."""
        page_payload = {"query": {"pages": {"1": {"revisions": [{"slots": {"main": {"*": "content"}}}]}}}}
        with _mediawiki_api_server(
            [
                _FakeResponse(
                    body={"error": {"code": "maxlag", "info": "Waiting for a server", "lag": 6}},
                    headers={"Retry-After": "0"},
                ),
                page_payload,
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, clock=MockClock(), request_policy=self._FAST_POLICY)
            content = client.get_page("Item:Sword")
        assert content == "content"
        assert len(api.requests) == 2

    def test_request_retries_after_503_with_retry_signal_then_succeeds(self) -> None:
        """A 503 carrying a Retry-After header is retried rather than failing immediately."""
        page_payload = {"query": {"pages": {"1": {"revisions": [{"slots": {"main": {"*": "content"}}}]}}}}
        with _mediawiki_api_server(
            [
                _FakeResponse(body={}, status_code=503, headers={"Retry-After": "0"}),
                page_payload,
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, clock=MockClock(), request_policy=self._FAST_POLICY)
            content = client.get_page("Item:Sword")
        assert content == "content"
        assert len(api.requests) == 2

    def test_request_raises_after_exhausting_retries_on_persistent_rate_limit(self) -> None:
        """Persistent 429 responses raise after the bounded retry budget is exhausted."""
        rate_limited = _FakeResponse(
            body={"error": {"code": "ratelimited"}}, status_code=429, headers={"Retry-After": "0"}
        )
        with _mediawiki_api_server([rate_limited, rate_limited, rate_limited]) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, clock=MockClock(), request_policy=self._FAST_POLICY)
            with pytest.raises(MediaWikiRateLimitError):
                client.get_page("Item:Sword")
        assert len(api.requests) == 3
