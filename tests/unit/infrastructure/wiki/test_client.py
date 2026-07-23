"""Unit tests for MediaWiki API client.

These tests verify the MediaWiki client's behavior without requiring MediaWiki
credentials. HTTP behavior is scripted through httpx.MockTransport; the one
real loopback contract lives under tests/contract.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs

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
    MediaWikiTitleStatus,
)
from erenshor.infrastructure.wiki.client import MediaWikiPageSnapshot


@dataclass(slots=True)
class _CapturedWikiRequest:
    method: str
    path: str
    query: dict[str, str]
    data: dict[str, str]
    headers: dict[str, str]


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
    transport: httpx.BaseTransport = field(init=False)

    def __post_init__(self) -> None:
        self.transport = httpx.MockTransport(self.handle)

    def next_response(self) -> _FakeResponse:
        if not self.responses:
            raise AssertionError("Fake MediaWiki API received more requests than configured responses")
        scripted = self.responses.pop(0)
        if isinstance(scripted, _FakeResponse):
            return scripted
        return _FakeResponse(body=scripted)

    def handle(self, request: httpx.Request) -> httpx.Response:
        query = {key: values[-1] for key, values in parse_qs(request.url.query.decode()).items()}
        data = {key: values[-1] for key, values in parse_qs(request.content.decode()).items()}
        self.requests.append(
            _CapturedWikiRequest(
                method=request.method,
                path=request.url.raw_path.split(b"?", 1)[0].decode(),
                query=query,
                data=data,
                headers=dict(request.headers),
            )
        )
        scripted = self.next_response()
        headers = {"Content-Type": "application/json", **scripted.headers}
        return httpx.Response(scripted.status_code, headers=headers, json=scripted.body, request=request)


class _MediaWikiAPIScenario:
    def __init__(self, responses: list[dict[str, Any] | _FakeResponse]) -> None:
        self.api = _FakeWikiAPI(responses=list(responses))
        self.transport = self.api.transport
        self.api_url = "https://erenshor.wiki.gg/api.php"

    def __enter__(self) -> tuple[str, _FakeWikiAPI]:
        return self.api_url, self.api

    def __exit__(self, *args: Any) -> None:
        return None


def _mediawiki_api_server(
    responses: list[dict[str, Any] | _FakeResponse],
) -> _MediaWikiAPIScenario:
    return _MediaWikiAPIScenario(responses)


def _mock_client(
    responses: list[dict[str, Any] | _FakeResponse],
    **kwargs: Any,
) -> tuple[MediaWikiClient, _FakeWikiAPI]:
    scenario = _MediaWikiAPIScenario(responses)
    client = MediaWikiClient(
        api_url=scenario.api_url,
        transport=scenario.transport,
        **kwargs,
    )
    return client, scenario.api


class _CountingTransport(httpx.BaseTransport):
    def __init__(self) -> None:
        self.close_count = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"query": {"pages": {}}}, request=request)

    def close(self) -> None:
        self.close_count += 1


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

    def test_close_closes_owned_transport_exactly_once(self) -> None:
        """Closing a client repeatedly closes its owned requestor once."""
        transport = _CountingTransport()
        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            transport=transport,
            clock=MockClock(),
        )

        client.close()
        client.close()

        assert transport.close_count == 1


class TestMediaWikiClientLogin:
    """Test MediaWiki login functionality."""

    def test_login_success(self) -> None:
        """Test successful login with bot credentials."""
        client, api = _mock_client(
            [
                {"query": {"tokens": {"logintoken": "test_login_token"}}},
                {"login": {"result": "Success"}},
            ],
            bot_username="TestBot@TestBot",
            bot_password="testpass",
            clock=MockClock(),
        )

        client.login()

        assert [request.method for request in api.requests] == ["GET", "POST"]
        assert api.requests[0].query["format"] == "json"
        assert api.requests[0].query["maxlag"] == "5"
        assert "formatversion" not in api.requests[0].query

    def test_login_missing_credentials(self) -> None:
        """Test login fails when credentials not provided."""
        client, _ = _mock_client([], clock=MockClock())

        with pytest.raises(ValueError, match="Bot username and password required"):
            client.login()

    def test_login_failure(self) -> None:
        """Test login fails with invalid credentials."""
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"logintoken": "test_login_token"}}},
                {"login": {"result": "Failed", "reason": "Incorrect password"}},
            ],
            bot_username="TestBot@TestBot",
            bot_password="wrongpass",
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiAuthenticationError, match="Login failed"):
            client.login()


class TestMediaWikiClientGetPage:
    """Test fetching single wiki pages."""

    def test_get_page_success(self) -> None:
        """Test successful page fetch."""
        client, api = _mock_client(
            [
                {
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
            ],
            clock=MockClock(),
        )
        content = client.get_page("Item:Sword")

        assert content == "{{Item|name=Sword|damage=10}}"
        assert api.requests[0].method == "GET"

    def test_get_page_missing(self) -> None:
        """Test fetching non-existent page returns None."""
        client, _ = _mock_client(
            [{"query": {"pages": {"-1": {"title": "Item:NonExistent", "missing": ""}}}}],
            clock=MockClock(),
        )
        assert client.get_page("Item:NonExistent") is None

    def test_get_page_network_error(self) -> None:
        """Test network error handling."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.NetworkError("Connection failed", request=request)

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            transport=httpx.MockTransport(handler),
            clock=MockClock(),
        )
        with pytest.raises(MediaWikiNetworkError, match="Network error"):
            client.get_page("Item:Sword")


class TestMediaWikiClientGetPages:
    """Test batch fetching of multiple pages."""

    def test_get_pages_success(self) -> None:
        """Test successful batch fetch."""
        client, _ = _mock_client(
            [
                {
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
                            "-1": {"title": "Item:Missing", "missing": ""},
                        }
                    }
                }
            ],
            clock=MockClock(),
        )
        pages = client.get_pages(["Item:Sword", "Item:Shield", "Item:Missing"])

        assert len(pages) == 3
        assert pages["Item:Sword"] == "Sword content"
        assert pages["Item:Shield"] == "Shield content"
        assert pages["Item:Missing"] is None

    def test_get_pages_empty_list(self) -> None:
        """Test batch fetch with empty list returns empty dict."""
        client, api = _mock_client([], clock=MockClock())
        assert client.get_pages([]) == {}
        assert api.requests == []

    def test_get_pages_batching(self) -> None:
        """Test batch fetch splits large requests."""
        client, api = _mock_client([{"query": {"pages": {}}}] * 3, batch_size=25, clock=MockClock())
        client.get_pages([f"Page:{i}" for i in range(60)])
        assert len(api.requests) == 3

    def test_get_page_snapshots_parses_source_revision_and_timestamp(self) -> None:
        """One response provides source, revision guard, and missing state for every title."""
        client, api = _mock_client(
            [
                {
                    "curtimestamp": "2026-06-04T12:02:00Z",
                    "query": {
                        "pages": {
                            "123": {
                                "pageid": 123,
                                "title": "Item:Sword",
                                "revisions": [
                                    {
                                        "revid": 456,
                                        "timestamp": "2026-06-04T12:00:00Z",
                                        "slots": {"main": {"*": "Sword content"}},
                                    }
                                ],
                            },
                            "-1": {"title": "Item:Missing", "missing": ""},
                        }
                    },
                }
            ],
            clock=MockClock(),
        )
        snapshots = client.get_page_snapshots(["Item:Sword", "Item:Missing"], assertion="bot", assert_user="Bot")

        assert isinstance(snapshots["Item:Sword"], MediaWikiPageSnapshot)
        assert snapshots["Item:Sword"].source_text == "Sword content"
        assert snapshots["Item:Sword"].revision is not None
        assert snapshots["Item:Sword"].revision.revision_id == 456
        assert snapshots["Item:Sword"].start_timestamp == "2026-06-04T12:02:00Z"
        assert snapshots["Item:Missing"].source_text is None
        assert snapshots["Item:Missing"].revision is None
        request_params = api.requests[0].query
        assert request_params["rvprop"] == "ids|timestamp|content|contentmodel"
        assert request_params["curtimestamp"] == "1"
        assert request_params["assert"] == "bot"
        assert request_params["assertuser"] == "Bot"
        assert request_params["format"] == "json"
        assert request_params["maxlag"] == "5"
        assert "formatversion" not in request_params

    """Test wiki page editing."""

    def test_edit_page_success(self) -> None:
        """Test successful page edit."""
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"edit": {"result": "Success"}},
            ],
            clock=MockClock(),
        )
        client.edit_page(title="Item:Sword", content="{{Item|name=Sword|damage=10}}", summary="Update item stats")
        assert [request.method for request in api.requests] == ["GET", "POST"]

    def test_null_edit_pages_sends_guards_and_unchanged_content(self) -> None:
        """Null edits reparse existing content under the requested API guards."""
        client, api = _mock_client(
            [
                {
                    "query": {
                        "pages": {
                            "123": {
                                "pageid": 123,
                                "title": "Item:Sword",
                                "revisions": [{"slots": {"main": {"*": "unchanged source"}}}],
                            }
                        }
                    }
                },
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"edit": {"result": "Success"}},
            ],
            clock=MockClock(),
        )
        assert client.null_edit_pages(("Item:Sword",), assertion="bot", assert_user="ErenshorBot") == ("Item:Sword",)
        call_data = api.requests[-1].data
        assert call_data["text"] == "unchanged source"
        assert call_data["assert"] == "bot"
        assert call_data["assertuser"] == "ErenshorBot"
        assert call_data["nocreate"] == "1"

    def test_edit_page_failure(self) -> None:
        """Test edit failure handling."""
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"edit": {"result": "Failure", "error": "Permission denied"}},
            ],
            clock=MockClock(),
        )
        with pytest.raises(MediaWikiEditError, match="Edit failed"):
            client.edit_page(title="Item:Sword", content="new content")

    def test_edit_page_uses_defaults(self) -> None:
        """Test edit uses default summary and minor flag."""
        client, api = _mock_client(
            [{"query": {"tokens": {"csrftoken": "test_csrf_token"}}}, {"edit": {"result": "Success"}}],
            edit_summary="Default summary",
            minor_edit=True,
            clock=MockClock(),
        )
        client.edit_page(title="Item:Sword", content="new content")
        call_data = api.requests[-1].data
        assert call_data["summary"] == "Default summary"
        assert call_data["minor"] == "1"


class TestMediaWikiClientRevisionMetadata:
    """Test conflict-safe revision metadata fetching."""

    def test_get_page_revision_metadata_requests_revision_and_current_timestamps(self) -> None:
        """Test metadata fetch requests base revision data and API current timestamp."""
        client, api = _mock_client(
            [
                {
                    "curtimestamp": "2026-06-04T12:00:00Z",
                    "query": {
                        "pages": {
                            "42": {
                                "pageid": 42,
                                "title": "Template:Item",
                                "revisions": [{"revid": 1234, "timestamp": "2026-06-04T11:59:00Z"}],
                            }
                        }
                    },
                }
            ],
            clock=MockClock(),
        )
        revision = client.get_page_revision_metadata("Template:Item")

        assert revision == MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )
        call_params = api.requests[0].query
        assert call_params["action"] == "query"
        assert call_params["titles"] == "Template:Item"
        assert call_params["prop"] == "revisions"
        assert call_params["rvprop"] == "ids|timestamp"
        assert call_params["curtimestamp"] == "1"

    def test_get_page_revision_metadata_returns_none_for_missing_page(self) -> None:
        """Test missing pages do not produce fabricated revision metadata."""
        client, _ = _mock_client(
            [
                {
                    "curtimestamp": "2026-06-04T12:00:00Z",
                    "query": {"pages": {"-1": {"missing": True, "title": "Template:Missing"}}},
                }
            ],
            clock=MockClock(),
        )
        assert client.get_page_revision_metadata("Template:Missing") is None

    def test_get_edit_start_timestamp_requests_current_timestamp_with_assertion(self) -> None:
        """Test start timestamp fetch uses MediaWiki's current API timestamp and assertion guard."""
        with _mediawiki_api_server([{"curtimestamp": "2026-06-04T12:00:00Z", "query": {"pages": {}}}]) as (
            api_url,
            api,
        ):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())

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
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())

            new_revision_id = client.safe_create_page(
                title="Module:Erenshor/Data/Items",
                content="return {}",
                start_timestamp="2026-06-04T12:00:00Z",
                summary="Create repo-owned module",
                assertion="bot",
                assert_user="ErenshorBot",
                content_model="json",
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
        assert edit_request.data["contentmodel"] == "json"
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
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())

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
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())

            with pytest.raises(MediaWikiEditConflictError, match="creating") as excinfo:
                client.safe_create_page(
                    title="Module:Erenshor/Data/Items",
                    content="return {}",
                    start_timestamp="2026-06-04T12:00:00Z",
                )

        assert "Module:Erenshor/Data/Items" in str(excinfo.value)


class TestMediaWikiClientSafeEditPage:
    """Test conflict-safe wiki page edits."""

    def test_safe_edit_page_sends_conflict_hash_and_assertion_parameters(self) -> None:
        """Test safe edits include base revision, start timestamp, MD5, and assertion guard."""
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"edit": {"result": "Success", "newrevid": 1235}},
            ],
            clock=MockClock(),
        )
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
            content_model="wikitext",
        )

        assert new_revision_id == 1235
        call_data = api.requests[-1].data
        assert call_data["action"] == "edit"
        assert call_data["title"] == "Template:Item"
        assert call_data["text"] == "new template source"
        assert call_data["summary"] == "Deploy repo-owned template"
        assert call_data["token"] == "test_csrf_token"
        assert call_data["baserevid"] == "1234"
        assert call_data["contentmodel"] == "wikitext"
        assert call_data["starttimestamp"] == "2026-06-04T12:00:00Z"
        assert call_data["md5"] == hashlib.md5(b"new template source", usedforsecurity=False).hexdigest()
        assert call_data["assert"] == "bot"
        assert call_data["assertuser"] == "ErenshorBot"
        assert call_data["bot"] == "1"

    def test_safe_edit_page_refreshes_csrf_token_once_after_badtoken(self) -> None:
        """Test stale CSRF tokens are refreshed once without changing the base revision guard."""
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "stale_token"}}},
                {"error": {"code": "badtoken", "info": "Invalid token"}},
                {"query": {"tokens": {"csrftoken": "fresh_token"}}},
                {"edit": {"result": "Success", "newrevid": 1235}},
            ],
            clock=MockClock(),
        )
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )
        assert (
            client.safe_edit_page(
                title="Template:Item",
                content="new template source",
                base_revision=base_revision,
                summary="Deploy repo-owned template",
            )
            == 1235
        )
        post_requests = [request for request in api.requests if request.method == "POST"]
        assert len(post_requests) == 2
        assert post_requests[0].data["token"] == "stale_token"
        assert post_requests[1].data["token"] == "fresh_token"
        assert post_requests[0].data["baserevid"] == post_requests[1].data["baserevid"] == "1234"

    def test_safe_edit_page_fails_after_second_badtoken(self) -> None:
        """Test token refresh is bounded to one retry."""
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "stale_token"}}},
                {"error": {"code": "badtoken", "info": "Invalid token"}},
                {"query": {"tokens": {"csrftoken": "still_bad_token"}}},
                {"error": {"code": "badtoken", "info": "Invalid token"}},
            ],
            clock=MockClock(),
        )
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
        assert len([request for request in api.requests if request.method == "POST"]) == 2

    def test_safe_edit_page_surfaces_edit_conflict(self) -> None:
        """Test edit conflicts are raised as explicit conflict failures."""
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"error": {"code": "editconflict", "info": "Edit conflict"}},
            ],
            clock=MockClock(),
        )
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )
        with pytest.raises(MediaWikiEditConflictError, match="Edit conflict"):
            client.safe_edit_page(title="Template:Item", content="new template source", base_revision=base_revision)

    def test_safe_edit_page_surfaces_assertion_failure(self) -> None:
        """Test assertion failures are raised separately from generic edit failures."""
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"error": {"code": "assertbotfailed", "info": "Not logged in as a bot"}},
            ],
            clock=MockClock(),
        )
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )
        with pytest.raises(MediaWikiAssertionError, match="Not logged in as a bot"):
            client.safe_edit_page(title="Template:Item", content="new template source", base_revision=base_revision)

    def test_safe_edit_page_surfaces_permission_failure(self) -> None:
        """Test permission failures are raised separately from generic edit failures."""
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"error": {"code": "permissiondenied", "info": "Permission denied"}},
            ],
            clock=MockClock(),
        )
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
        )
        with pytest.raises(MediaWikiPermissionError, match="Permission denied"):
            client.safe_edit_page(title="Template:Item", content="new template source", base_revision=base_revision)

    def test_safe_edit_page_returns_base_revision_on_no_change(self) -> None:
        """Test an identical-content edit (nochange) reports the existing revision, not a crash."""
        with _mediawiki_api_server(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"edit": {"result": "Success", "pageid": 7, "title": "Template:Item", "nochange": ""}},
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())
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

    def test_get_embeddedin_pages_handles_continuation_and_namespace_filters(self) -> None:
        """Test embeddedin discovery follows continuation and passes namespace filters."""
        client, api = _mock_client(
            [
                {
                    "continue": {"eicontinue": "10|123", "continue": "-||"},
                    "query": {
                        "embeddedin": [
                            {"pageid": 1, "ns": 0, "title": "Ember Longsword"},
                            {"pageid": 2, "ns": 0, "title": "Abyssal Plate"},
                        ]
                    },
                },
                {"query": {"embeddedin": [{"pageid": 3, "ns": 10, "title": "Template:WeaponTable"}]}},
            ],
            clock=MockClock(),
        )
        pages = client.get_embeddedin_pages("Template:Item", namespaces=(0, 10), assertion="bot")

        assert pages == ("Ember Longsword", "Abyssal Plate", "Template:WeaponTable")
        first_params = api.requests[0].query
        second_params = api.requests[1].query
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
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())

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
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())
            assert client.purge_pages([]) == ()
        assert api.requests == []


class TestMediaWikiClientDeletePage:
    """Test wiki page deletion through the public Action API helper."""

    def test_delete_page_posts_token_and_assertion_guard(self) -> None:
        """Test delete helper sends CSRF, reason, and session assertion guards."""
        with _mediawiki_api_server(
            [
                {"query": {"tokens": {"csrftoken": "delete_csrf_token"}}},
                {"delete": {"title": "Project:CargoProbe/TemporaryPage", "reason": "Clean up probe"}},
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())

            deleted = client.delete_page(
                "Project:CargoProbe/TemporaryPage",
                reason="Clean up probe",
                assertion="bot",
                assert_user="ErenshorBot",
            )

        assert deleted == {"title": "Project:CargoProbe/TemporaryPage", "reason": "Clean up probe"}
        assert len(api.requests) == 2
        token_request, delete_request = api.requests
        assert token_request.method == "GET"
        assert token_request.query["action"] == "query"
        assert token_request.query["meta"] == "tokens"
        assert token_request.query["type"] == "csrf"
        assert delete_request.method == "POST"
        assert delete_request.data["action"] == "delete"
        assert delete_request.data["title"] == "Project:CargoProbe/TemporaryPage"
        assert delete_request.data["reason"] == "Clean up probe"
        assert delete_request.data["token"] == "delete_csrf_token"
        assert delete_request.data["assert"] == "bot"
        assert delete_request.data["assertuser"] == "ErenshorBot"


class TestMediaWikiClientCargoHelpers:
    """Test Cargo extension helper requests used by the storage probe."""

    def test_recreate_cargo_tables_posts_token_and_assertion_guard(self) -> None:
        """Test Cargo table recreation posts the template, CSRF token, and assertion guard."""
        expected_response = {"cargorecreatetables": {"status": "queued"}}
        with _mediawiki_api_server(
            [
                {"query": {"tokens": {"csrftoken": "cargo_tables_token"}}},
                expected_response,
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())

            response = client.recreate_cargo_tables(
                "CargoStorageProbe",
                create_replacement=True,
                assertion="bot",
                assert_user="ErenshorBot",
            )

        assert response == expected_response
        assert len(api.requests) == 2
        _, recreate_request = api.requests
        assert recreate_request.method == "POST"
        assert recreate_request.data["action"] == "cargorecreatetables"
        assert recreate_request.data["template"] == "CargoStorageProbe"
        assert recreate_request.data["createReplacement"] == "1"
        assert recreate_request.data["token"] == "cargo_tables_token"
        assert recreate_request.data["assert"] == "bot"
        assert recreate_request.data["assertuser"] == "ErenshorBot"

    def test_recreate_cargo_data_posts_table_token_and_assertion_guard(self) -> None:
        """Test Cargo row recreation posts the table scope, CSRF token, and assertion guard."""
        expected_response = {"cargorecreatedata": {"status": "done"}}
        with _mediawiki_api_server(
            [
                {"query": {"tokens": {"csrftoken": "cargo_data_token"}}},
                expected_response,
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())

            response = client.recreate_cargo_data(
                "CargoStorageProbe",
                table="CargoProbe",
                replace_old_rows=True,
                assertion="bot",
                assert_user="ErenshorBot",
            )

        assert response == expected_response
        assert len(api.requests) == 2
        _, recreate_request = api.requests
        assert recreate_request.method == "POST"
        assert recreate_request.data["action"] == "cargorecreatedata"
        assert recreate_request.data["template"] == "CargoStorageProbe"
        assert recreate_request.data["table"] == "CargoProbe"
        assert recreate_request.data["replaceOldRows"] == "1"
        assert recreate_request.data["token"] == "cargo_data_token"
        assert recreate_request.data["assert"] == "bot"
        assert recreate_request.data["assertuser"] == "ErenshorBot"
        assert "offset" not in recreate_request.data

    def test_query_cargo_table_gets_rows_with_assertion_guard(self) -> None:
        """Test Cargo queries return the raw cargoquery rows and send GET filters."""
        rows = [
            {"title": {"Page": "Project:CargoProbe/TemporaryPage", "ProbeKey": "probe-a"}},
            {"title": {"Page": "Project:CargoProbe/TemporaryPage", "ProbeKey": "probe-b"}},
        ]
        with _mediawiki_api_server([{"cargoquery": rows}]) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())

            result = client.query_cargo_table(
                tables="CargoProbe",
                fields="_pageName=Page,ProbeKey",
                where="ProbeKey LIKE 'probe-%'",
                limit=2,
                offset=4,
                assertion="bot",
                assert_user="ErenshorBot",
            )

        assert result == rows
        assert len(api.requests) == 1
        query_request = api.requests[0]
        assert query_request.method == "GET"
        assert query_request.query["action"] == "cargoquery"
        assert query_request.query["tables"] == "CargoProbe"
        assert query_request.query["fields"] == "_pageName=Page,ProbeKey"
        assert query_request.query["where"] == "ProbeKey LIKE 'probe-%'"
        assert query_request.query["limit"] == "2"
        assert query_request.query["offset"] == "4"
        assert query_request.query["assert"] == "bot"
        assert query_request.query["assertuser"] == "ErenshorBot"


class TestMediaWikiClientPageExists:
    """Test page existence checking."""

    def test_page_exists_true(self) -> None:
        """Test page existence check for existing page."""
        client, _ = _mock_client(
            [{"query": {"pages": {"123": {"pageid": 123, "title": "Item:Sword"}}}}], clock=MockClock()
        )
        assert client.page_exists("Item:Sword") is True

    def test_page_exists_false(self) -> None:
        """Test page existence check for missing page."""
        client, _ = _mock_client(
            [{"query": {"pages": {"-1": {"title": "Item:Missing", "missing": ""}}}}], clock=MockClock()
        )
        assert client.page_exists("Item:Missing") is False


class TestMediaWikiClientRateLimiting:
    """Test rate limiting behavior."""

    def test_rate_limiting_applied(self) -> None:
        """Test rate limiting delays requests."""
        mock_clock = MockClock()
        page_response = {"query": {"pages": {"1": {"revisions": [{"slots": {"main": {"*": "content"}}}]}}}}
        client, _ = _mock_client(
            [page_response] * 2,
            rate_limit_delay=1.0,
            clock=mock_clock,
        )
        client.get_page("Page1")
        time_after_first = mock_clock.time()
        mock_clock.advance(0.3)
        client.get_page("Page2")
        assert mock_clock.time() - time_after_first >= 1.0


class TestMediaWikiClientErrorHandling:
    """Test error handling for various failure scenarios."""

    def test_api_error_handling(self) -> None:
        """Test handling of API error responses."""
        client, _ = _mock_client([{"error": {"code": "badtoken", "info": "Invalid CSRF token"}}], clock=MockClock())
        with pytest.raises(MediaWikiAPIError, match="Invalid CSRF token") as excinfo:
            client.get_page("Item:Sword")
        assert excinfo.value.code == "badtoken"
        assert excinfo.value.info == "Invalid CSRF token"

    def test_timeout_error(self) -> None:
        """Test timeout error handling."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Request timeout", request=request)

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php", transport=httpx.MockTransport(handler), clock=MockClock()
        )
        with pytest.raises(MediaWikiNetworkError, match="Request timeout"):
            client.get_page("Item:Sword")

    def test_invalid_json_response(self) -> None:
        """Test handling of invalid JSON responses."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=b"not-json", headers={"Content-Type": "application/json"}, request=request
            )

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php", transport=httpx.MockTransport(handler), clock=MockClock()
        )
        with pytest.raises(MediaWikiAPIError, match="Invalid JSON response"):
            client.get_page("Item:Sword")


class TestMediaWikiClientCSRFToken:
    """Test CSRF token management."""

    def test_csrf_token_cached(self) -> None:
        """Test CSRF token is cached and reused."""
        client, api = _mock_client([{"query": {"tokens": {"csrftoken": "test_token"}}}], clock=MockClock())
        assert client.get_csrf_token() == "test_token"
        assert client.get_csrf_token() == "test_token"
        assert len(api.requests) == 1

    def test_csrf_token_cleared_on_error(self) -> None:
        """Test CSRF token is cleared when badtoken error occurs."""
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_token"}}},
                {"error": {"code": "badtoken", "info": "Invalid token"}},
            ],
            clock=MockClock(),
        )
        client.get_csrf_token()
        with pytest.raises(MediaWikiAPIError):
            client.get_page("Item:Sword")
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
            client = MediaWikiClient(
                api_url=api_url, transport=api.transport, clock=MockClock(), request_policy=self._FAST_POLICY
            )
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
            client = MediaWikiClient(
                api_url=api_url, transport=api.transport, clock=MockClock(), request_policy=self._FAST_POLICY
            )
            content = client.get_page("Item:Sword")
        assert content == "content"
        assert len(api.requests) == 2

    def test_request_retries_after_503_maxlag_payload_then_succeeds(self) -> None:
        """A maxlag payload remains retryable even without transport retry headers."""
        page_payload = {"query": {"pages": {"1": {"revisions": [{"slots": {"main": {"*": "content"}}}]}}}}
        maxlag = _FakeResponse(
            body={"error": {"code": "maxlag", "info": "Server lag", "lag": 6}},
            status_code=503,
        )
        with _mediawiki_api_server([maxlag, page_payload]) as (api_url, api):
            client = MediaWikiClient(
                api_url=api_url, transport=api.transport, clock=MockClock(), request_policy=self._FAST_POLICY
            )

            content = client.get_page("Item:Sword")

        assert content == "content"
        assert len(api.requests) == 2

    def test_request_raises_after_exhausting_retries_on_persistent_rate_limit(self) -> None:
        """Persistent 429 responses raise after the bounded retry budget is exhausted."""
        rate_limited = _FakeResponse(
            body={"error": {"code": "ratelimited"}}, status_code=429, headers={"Retry-After": "0"}
        )
        with _mediawiki_api_server([rate_limited, rate_limited, rate_limited]) as (api_url, api):
            client = MediaWikiClient(
                api_url=api_url, transport=api.transport, clock=MockClock(), request_policy=self._FAST_POLICY
            )
            with pytest.raises(MediaWikiRateLimitError):
                client.get_page("Item:Sword")
        assert len(api.requests) == 3


class TestMediaWikiClientExpandTemplates:
    """Test wikitext expansion via the expandtemplates API."""

    def test_expand_templates_returns_expanded_wikitext(self) -> None:
        """Test expansion sends the text and returns the rendered wikitext."""
        with _mediawiki_api_server([{"expandtemplates": {"wikitext": "Weapon"}}]) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())
            value = client.expand_templates("{{#invoke:Erenshor/Item|field|stablekey=item:ember|1=type}}")
        assert value == "Weapon"
        request = api.requests[0]
        assert request.query["action"] == "expandtemplates"
        assert request.query["prop"] == "wikitext"
        assert request.query["text"] == "{{#invoke:Erenshor/Item|field|stablekey=item:ember|1=type}}"


class TestMediaWikiClientSemanticLinkReads:
    """Test read-only title and semantic-link maintenance queries."""

    def test_get_title_statuses_batches_deduplicates_and_reconciles_titles(self) -> None:
        with _mediawiki_api_server(
            [
                {
                    "query": {
                        "normalized": [{"from": "foo bar", "to": "Foo bar"}],
                        "redirects": [{"from": "Foo bar", "to": "Canonical bar"}],
                        "pages": {
                            "1": {"pageid": 1, "title": "Canonical bar"},
                            "-1": {"title": "Missing", "missing": ""},
                        },
                    }
                },
                {
                    "query": {
                        "pages": {"2": {"pageid": 2, "title": "Other"}},
                    }
                },
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, batch_size=2, clock=MockClock())
            statuses = client.get_title_statuses(["foo bar", "foo bar", "Missing", "Other"])

        assert statuses == {
            "foo bar": MediaWikiTitleStatus(
                requested="foo bar",
                normalized="Foo bar",
                redirect_target="Canonical bar",
                exists=True,
            ),
            "Missing": MediaWikiTitleStatus(
                requested="Missing",
                normalized="Missing",
                redirect_target=None,
                exists=False,
            ),
            "Other": MediaWikiTitleStatus(
                requested="Other",
                normalized="Other",
                redirect_target=None,
                exists=True,
            ),
        }
        assert [request.query["titles"] for request in api.requests] == ["foo bar|Missing", "Other"]
        assert all(request.query["action"] == "query" for request in api.requests)
        assert all(request.query["prop"] == "info" for request in api.requests)
        assert all(request.query["redirects"] == "1" for request in api.requests)
        assert all(request.method == "GET" for request in api.requests)

    def test_get_title_statuses_returns_final_redirect_target(self) -> None:
        with _mediawiki_api_server(
            [
                {
                    "query": {
                        "redirects": [
                            {"from": "Old", "to": "Newer"},
                            {"from": "Newer", "to": "Canonical"},
                        ],
                        "pages": {"1": {"pageid": 1, "title": "Canonical"}},
                    }
                }
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())

            status = client.get_title_statuses(["Old"])["Old"]

        assert status.redirect_target == "Canonical"
        assert status.exists is True

    def test_get_wanted_pages_exhausts_continuation_and_filters_unique_namespace(self) -> None:
        with _mediawiki_api_server(
            [
                {
                    "continue": {"qpoffset": 2, "continue": "-||"},
                    "query": {
                        "querypage": {
                            "results": [
                                {"ns": 0, "title": "Zulu"},
                                {"ns": 10, "title": "Template:Nope"},
                                {"ns": 0, "title": "Alpha"},
                            ]
                        }
                    },
                },
                {"query": {"querypage": {"results": [{"ns": 0, "title": "Zulu"}]}}},
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())
            titles = client.get_wanted_pages(namespace=0)

        assert titles == ("Alpha", "Zulu")
        assert api.requests[0].query == {
            "action": "query",
            "list": "querypage",
            "qppage": "Wantedpages",
            "qplimit": "max",
            "format": "json",
            "maxlag": "5",
        }
        assert api.requests[1].query["qpoffset"] == "2"
        assert api.requests[1].query["continue"] == "-||"

    def test_get_linking_pages_by_title_batches_targets_and_continuation(self) -> None:
        with _mediawiki_api_server(
            [
                {
                    "continue": {"lhcontinue": "next", "continue": "-||"},
                    "query": {
                        "pages": {
                            "-1": {
                                "ns": 0,
                                "title": "Target A",
                                "missing": "",
                                "linkshere": [{"ns": 0, "title": "Source Z"}],
                            },
                            "-2": {
                                "ns": 0,
                                "title": "Target B",
                                "missing": "",
                                "linkshere": [
                                    {"ns": 0, "title": "Source B"},
                                    {"ns": 10, "title": "Template:Nope"},
                                ],
                            },
                        }
                    },
                },
                {
                    "query": {
                        "pages": {
                            "-1": {
                                "ns": 0,
                                "title": "Target A",
                                "missing": "",
                                "linkshere": [{"ns": 0, "title": "Source A"}],
                            }
                        }
                    }
                },
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, batch_size=2, clock=MockClock())
            linking = client.get_linking_pages_by_title(["Target B", "Target A", "Target B"], namespace=0)

        assert linking == {
            "Target A": ("Source A", "Source Z"),
            "Target B": ("Source B",),
        }
        assert api.requests[0].query["prop"] == "linkshere"
        assert api.requests[0].query["titles"] == "Target A|Target B"
        assert api.requests[0].query["lhnamespace"] == "0"
        assert api.requests[1].query["lhcontinue"] == "next"

    def test_get_linking_pages_and_category_members_use_namespace_and_continue(self) -> None:
        with _mediawiki_api_server(
            [
                {
                    "continue": {"blcontinue": "next", "continue": "-||"},
                    "query": {
                        "backlinks": [
                            {"ns": 0, "title": "Zulu"},
                            {"ns": 0, "title": "Alpha"},
                            {"ns": 10, "title": "Template:Nope"},
                        ]
                    },
                },
                {"query": {"backlinks": [{"ns": 0, "title": "Zulu"}]}},
                {
                    "continue": {"cmcontinue": "next-category", "continue": "-||"},
                    "query": {
                        "categorymembers": [
                            {"ns": 14, "title": "Category:Other"},
                            {"ns": 14, "title": "Category:Alpha"},
                        ]
                    },
                },
                {"query": {"categorymembers": [{"ns": 14, "title": "Category:Alpha"}]}},
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())
            linking = client.get_linking_pages("Target", namespace=0)
            members = client.get_category_members("Category:Things", namespace=14)

        assert linking == ("Alpha", "Zulu")
        assert members == ("Category:Alpha", "Category:Other")
        assert api.requests[0].query["list"] == "backlinks"
        assert api.requests[0].query["bltitle"] == "Target"
        assert api.requests[0].query["blnamespace"] == "0"
        assert api.requests[1].query["blcontinue"] == "next"
        assert api.requests[2].query["list"] == "categorymembers"
        assert api.requests[2].query["cmtitle"] == "Category:Things"
        assert api.requests[2].query["cmnamespace"] == "14"
        assert api.requests[3].query["cmcontinue"] == "next-category"

    def test_read_only_api_errors_use_existing_exception(self) -> None:
        with _mediawiki_api_server([{"error": {"code": "badvalue", "info": "Invalid title"}}]) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())
            with pytest.raises(MediaWikiAPIError, match="Invalid title"):
                client.get_title_statuses(["Bad"])
