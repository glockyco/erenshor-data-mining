"""Unit tests for MediaWiki API client.

These tests verify the MediaWiki client's behavior without requiring MediaWiki
credentials. HTTP behavior is scripted through httpx.MockTransport; the one
real loopback contract lives under tests/contract.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
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
    MediaWikiFileUpload,
    MediaWikiNetworkError,
    MediaWikiPageRevision,
    MediaWikiPermissionError,
    MediaWikiRateLimitError,
    MediaWikiRequestPolicy,
    MediaWikiTitleStatus,
    MediaWikiUploadWarningError,
)
from erenshor.infrastructure.wiki.client import MediaWikiEditVerificationError, MediaWikiPageSnapshot


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


def _revision_response(
    title: str = "Template:Item",
    revision_id: int = 1234,
    *,
    source: str = "old source",
    parent_id: int = 1233,
    page_id: int = 42,
    content_model: str = "wikitext",
) -> dict[str, Any]:
    return {
        "curtimestamp": "2026-06-04T12:00:00Z",
        "query": {
            "pages": {
                str(page_id): {
                    "pageid": page_id,
                    "title": title,
                    "revisions": [
                        {
                            "revid": revision_id,
                            "parentid": parent_id,
                            "timestamp": "2026-06-04T11:59:00Z",
                            "user": "ErenshorBot",
                            "slots": {"main": {"*": source, "contentmodel": content_model}},
                        }
                    ],
                }
            }
        },
    }


def _missing_snapshot_response(title: str, *, requested: str | None = None) -> dict[str, Any]:
    return {
        "curtimestamp": "2026-06-04T12:00:00Z",
        "query": {
            "normalized": [] if requested is None else [{"from": requested, "to": title}],
            "pages": {"-1": {"title": title, "missing": ""}},
        },
    }


@pytest.mark.parametrize(
    "api_url",
    [
        "https://SecretUser:SecretPassword@example.invalid/api.php",
        "https://SecretUser:SecretPassword@example.invalid/not-an-api",
        "https://SecretUser@example.invalid/api.php",
        "https://:SecretPassword@example.invalid/api.php",
    ],
)
def test_client_rejects_url_credentials_without_disclosing_them(api_url: str) -> None:
    from loguru import logger

    messages: list[str] = []
    sink = logger.add(messages.append)
    try:
        with pytest.raises(ValueError, match="must not contain credentials") as error:
            MediaWikiClient(api_url=api_url, clock=MockClock())
    finally:
        logger.remove(sink)

    output = str(error.value) + "".join(messages)
    assert "SecretUser" not in output
    assert "SecretPassword" not in output
    assert api_url not in output


class TestMediaWikiRevisionLineage:
    @pytest.mark.parametrize("reader", ["current", "historical", "metadata"])
    @pytest.mark.parametrize("parent_id", [0, 41, None])
    def test_reads_actual_parent_or_preserves_legacy_absence(self, reader: str, parent_id: int | None) -> None:
        snapshot = self._read_revision(reader, {} if parent_id is None else {"parentid": parent_id})
        assert snapshot.parent_revision_id == parent_id

    @pytest.mark.parametrize("reader", ["current", "historical", "metadata"])
    @pytest.mark.parametrize("parent_id", [-1, True, "41", None])
    def test_rejects_malformed_returned_parent(self, reader: str, parent_id: Any) -> None:
        with pytest.raises(MediaWikiAPIError, match="parentid"):
            self._read_revision(reader, {"parentid": parent_id})

    @pytest.mark.parametrize("reader", ["current", "historical", "metadata"])
    @pytest.mark.parametrize(
        ("extra", "expected"),
        [
            ({"comment": "Reviewed [conversion-approval:abc123]"}, "Reviewed [conversion-approval:abc123]"),
            ({"comment": ""}, ""),
            ({}, None),
            ({"commenthidden": ""}, None),
            ({"commenthidden": "", "comment": "must not expose"}, None),
        ],
    )
    def test_reads_actual_revision_comment_or_hidden_absence(
        self, reader: str, extra: dict[str, Any], expected: str | None
    ) -> None:
        assert self._read_revision(reader, extra).comment == expected

    @pytest.mark.parametrize("reader", ["current", "historical", "metadata"])
    @pytest.mark.parametrize("comment", [None, 42, True])
    def test_rejects_malformed_returned_comment(self, reader: str, comment: Any) -> None:
        with pytest.raises(MediaWikiAPIError, match="comment"):
            self._read_revision(reader, {"comment": comment})

    @staticmethod
    def _read_revision(reader: str, extra: dict[str, Any]) -> MediaWikiPageRevision:
        client, _ = _mock_client(
            [
                {
                    "curtimestamp": "2026-10-17T12:00:00Z",
                    "query": {
                        "pages": {
                            "7": {
                                "pageid": 7,
                                "title": "Example",
                                "revisions": [
                                    {
                                        "revid": 42,
                                        "timestamp": "2026-10-16T12:00:00Z",
                                        "user": "Editor",
                                        "slots": {"main": {"*": "source", "contentmodel": "wikitext"}},
                                    }
                                    | extra
                                ],
                            }
                        }
                    },
                }
            ],
            clock=MockClock(),
        )
        if reader == "metadata":
            revision = client.get_page_revision_metadata("Example")
        elif reader == "current":
            revision = client.get_page_snapshots(["Example"])["Example"].revision
        else:
            revision = client.get_revision_snapshots([42])[42].revision
        assert revision is not None
        return revision

    def test_fake_tracks_actual_creation_and_edit_parent(self) -> None:
        from tests.fakes.mediawiki import MediaWikiFake

        client = MediaWikiFake()
        client.put_page("Example", "created")
        created = client.get_page_revision_metadata("Example")
        assert created is not None
        assert created.parent_revision_id == 0
        client.revisions["Example"] = 41
        client.put_page("Example", "edited")
        edited = client.get_page_snapshots(["Example"])["Example"].revision
        assert edited is not None
        assert edited.parent_revision_id == 41


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
            clock=MockClock(),
        )

        assert client.api_url == "https://erenshor.wiki.gg/api.php"
        assert client.bot_username == "TestBot@TestBot"
        assert client.bot_password == "testpass"
        assert client.batch_size == 25

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
                {
                    "query": {
                        "userinfo": {
                            "name": "TestBot",
                            "rights": ["edit"],
                            "ratelimits": {"edit": {"user": {"hits": 90, "seconds": 60}}},
                        }
                    }
                },
            ],
            bot_username="TestBot@TestBot",
            bot_password="testpass",
            clock=MockClock(),
        )

        client.login()

        assert [request.method for request in api.requests] == ["GET", "POST", "GET"]
        assert api.requests[0].query["format"] == "json"
        assert api.requests[0].query["maxlag"] == "5"
        assert "formatversion" not in api.requests[0].query
        assert api.requests[2].query["meta"] == "userinfo"
        assert api.requests[2].query["uiprop"] == "ratelimits|rights"
        assert api.requests[2].query["assert"] == "user"

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

    def test_get_page_rejects_missing_revision_content(self) -> None:
        client, _ = _mock_client(
            [{"query": {"pages": {"123": {"title": "Item:Sword", "pageid": 123}}}}],
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiAPIError, match=r"Item:Sword.*missing revision content"):
            client.get_page("Item:Sword")

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

    def test_get_pages_maps_normalized_title_to_request(self) -> None:
        client, _ = _mock_client(
            [
                {
                    "query": {
                        "normalized": [{"from": "a_page", "to": "A page"}],
                        "pages": {
                            "7": {
                                "pageid": 7,
                                "title": "A page",
                                "revisions": [{"slots": {"main": {"*": "Saved content"}}}],
                            }
                        },
                    }
                }
            ],
            clock=MockClock(),
        )

        assert client.get_pages(["a_page"]) == {"a_page": "Saved content"}

    def test_get_pages_empty_list(self) -> None:
        """Test batch fetch with empty list returns empty dict."""
        client, api = _mock_client([], clock=MockClock())
        assert client.get_pages([]) == {}
        assert api.requests == []

    def test_get_pages_batching(self) -> None:
        """Test batch fetch splits large requests."""
        responses = [
            {
                "query": {
                    "pages": {
                        str(index): {
                            "pageid": index,
                            "title": f"Page:{index}",
                            "revisions": [{"slots": {"main": {"*": "content"}}}],
                        }
                        for index in range(start, min(start + 25, 60))
                    }
                }
            }
            for start in (0, 25, 50)
        ]
        client, api = _mock_client(responses, batch_size=25, clock=MockClock())
        assert len(client.get_pages([f"Page:{i}" for i in range(60)])) == 60
        assert len(api.requests) == 3

    def test_get_pages_rejects_missing_revision_content(self) -> None:
        client, _ = _mock_client(
            [{"query": {"pages": {"123": {"title": "Item:Sword", "pageid": 123}}}}],
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiAPIError, match=r"Item:Sword.*missing revision content"):
            client.get_pages(["Item:Sword"])

    def test_get_pages_requests_again_what_a_truncated_response_left_out(self) -> None:
        client, api = _mock_client(
            [
                {
                    "continue": {"rvcontinue": "8|80", "continue": "||"},
                    "query": {
                        "pages": {
                            "7": {"pageid": 7, "title": "Big A", "revisions": [{"slots": {"main": {"*": "A"}}}]},
                            "8": {"pageid": 8, "title": "Big B"},
                        }
                    },
                },
                {
                    "query": {
                        "pages": {"8": {"pageid": 8, "title": "Big B", "revisions": [{"slots": {"main": {"*": "B"}}}]}}
                    }
                },
            ],
            clock=MockClock(),
        )

        assert client.get_pages(["Big A", "Big B"]) == {"Big A": "A", "Big B": "B"}
        assert api.requests[1].query["titles"] == "Big B"

    def test_revision_ids_resolve_normalized_and_missing_titles(self) -> None:
        client, api = _mock_client(
            [
                {
                    "query": {
                        "normalized": [{"from": "a_page", "to": "A page"}],
                        "pages": {
                            "7": {"pageid": 7, "title": "A page", "lastrevid": 42},
                            "-1": {"title": "Missing", "missing": ""},
                        },
                    }
                }
            ],
            clock=MockClock(),
        )

        assert client.get_page_revision_ids(["a_page", "Missing"]) == {"a_page": 42, "Missing": None}
        assert api.requests[0].query["prop"] == "info"

    def test_revision_ids_reject_missing_page_data(self) -> None:
        client, _ = _mock_client([{"query": {"pages": {}}}], clock=MockClock())

        with pytest.raises(MediaWikiAPIError, match=r"A Page.*page not returned"):
            client.get_page_revision_ids(["A Page"])

    def test_revision_ids_reject_missing_last_revision(self) -> None:
        client, _ = _mock_client(
            [{"query": {"pages": {"7": {"pageid": 7, "title": "A Page"}}}}],
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiAPIError, match=r"A Page.*lastrevid"):
            client.get_page_revision_ids(["A Page"])

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
                                        "user": "Editor",
                                        "slots": {"main": {"*": "Sword content", "contentmodel": "wikitext"}},
                                    }
                                ],
                            },
                            "124": {
                                "pageid": 124,
                                "title": "Item:Hidden",
                                "revisions": [
                                    {
                                        "revid": 457,
                                        "timestamp": "2026-06-04T12:01:00Z",
                                        "userhidden": "",
                                        "slots": {"main": {"*": "Hidden author"}},
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
        snapshots = client.get_page_snapshots(
            ["Item:Sword", "Item:Hidden", "Item:Missing"], assertion="bot", assert_user="Bot"
        )

        assert isinstance(snapshots["Item:Sword"], MediaWikiPageSnapshot)
        assert snapshots["Item:Sword"].source_text == "Sword content"
        assert snapshots["Item:Sword"].content_model == "wikitext"
        assert snapshots["Item:Sword"].revision is not None
        assert snapshots["Item:Sword"].revision.revision_id == 456
        assert snapshots["Item:Sword"].revision.user == "Editor"
        assert snapshots["Item:Hidden"].revision is not None
        assert snapshots["Item:Hidden"].revision.user is None
        assert snapshots["Item:Sword"].start_timestamp == "2026-06-04T12:02:00Z"
        assert snapshots["Item:Missing"].source_text is None
        assert snapshots["Item:Missing"].revision is None
        request_params = api.requests[0].query
        assert request_params["rvprop"] == "ids|timestamp|user|comment|content|contentmodel"
        assert request_params["curtimestamp"] == "1"
        assert request_params["assert"] == "bot"
        assert request_params["assertuser"] == "Bot"
        assert request_params["format"] == "json"
        assert request_params["maxlag"] == "5"
        assert "formatversion" not in request_params

    def test_get_page_snapshots_maps_normalized_title_to_request(self) -> None:
        client, _ = _mock_client(
            [
                {
                    "curtimestamp": "2026-09-27T12:01:00Z",
                    "query": {
                        "normalized": [{"from": "a_page", "to": "A page"}],
                        "pages": {
                            "7": {
                                "pageid": 7,
                                "title": "A page",
                                "revisions": [
                                    {
                                        "revid": 42,
                                        "timestamp": "2026-09-27T12:00:00Z",
                                        "user": "Editor",
                                        "slots": {"main": {"*": "Saved content"}},
                                    }
                                ],
                            }
                        },
                    },
                }
            ],
            clock=MockClock(),
        )

        assert client.get_page_snapshots(["a_page"])["a_page"].source_text == "Saved content"

    def test_get_page_snapshots_requests_again_what_a_truncated_response_left_out(self) -> None:
        """A page that did not fit the result size limit comes from a second query."""

        def page(page_id: int, title: str, revisions: list[dict[str, object]]) -> dict[str, object]:
            return {"pageid": page_id, "title": title, "revisions": revisions}

        def revision(revision_id: int, text: str) -> dict[str, object]:
            return {
                "revid": revision_id,
                "timestamp": "2026-10-03T12:00:00Z",
                "user": "WoWBot",
                "slots": {"main": {"*": text}},
            }

        client, api = _mock_client(
            [
                {
                    "curtimestamp": "2026-10-03T12:01:00Z",
                    "continue": {"rvcontinue": "8|80", "continue": "||"},
                    "query": {"pages": {"7": page(7, "Big A", [revision(70, "A")]), "8": page(8, "Big B", [])}},
                },
                {
                    "curtimestamp": "2026-10-03T12:02:00Z",
                    "query": {"pages": {"8": page(8, "Big B", [revision(80, "B")])}},
                },
            ],
            clock=MockClock(),
        )

        snapshots = client.get_page_snapshots(["Big A", "Big B"])

        assert snapshots["Big A"].source_text == "A"
        assert snapshots["Big B"].source_text == "B"
        assert snapshots["Big B"].start_timestamp == "2026-10-03T12:02:00Z"
        assert api.requests[1].query["titles"] == "Big B"

    def test_get_page_snapshots_fails_for_a_page_larger_than_the_result_limit(self) -> None:
        client, _ = _mock_client(
            [
                {
                    "curtimestamp": "2026-10-03T12:01:00Z",
                    "continue": {"rvcontinue": "8|80", "continue": "||"},
                    "query": {"pages": {"8": {"pageid": 8, "title": "Huge", "revisions": []}}},
                }
            ],
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiAPIError, match="larger than the API result limit"):
            client.get_page_snapshots(["Huge"])

    def test_get_revision_snapshots_keeps_each_same_page_historical_revision(self) -> None:
        client, api = _mock_client(
            [
                {
                    "curtimestamp": "2026-10-17T12:00:00Z",
                    "query": {
                        "pages": {
                            "7": {
                                "pageid": 7,
                                "title": "Module:Example",
                                "lastrevid": 99,
                                "contentmodel": "wikitext",
                                "revisions": [
                                    {
                                        "revid": 42,
                                        "timestamp": "2026-10-15T12:00:00Z",
                                        "user": "Editor",
                                        "contentmodel": "wikitext",
                                        "slots": {
                                            "main": {
                                                "*": "return {\r\n  old = true\r\n}\r\n",
                                                "contentmodel": "Scribunto",
                                            }
                                        },
                                    },
                                    {
                                        "revid": 43,
                                        "timestamp": "2026-10-16T12:00:00Z",
                                        "userhidden": "",
                                        "slots": {"main": {"*": "", "contentmodel": "Scribunto"}},
                                    },
                                ],
                            }
                        }
                    },
                }
            ],
            clock=MockClock(),
        )

        snapshots = client.get_revision_snapshots([43, 42, 43])

        assert set(snapshots) == {42, 43}
        assert snapshots[42].source_text == "return {\r\n  old = true\r\n}\r\n"
        assert snapshots[42].content_model == "Scribunto"
        assert snapshots[42].revision == MediaWikiPageRevision(
            title="Module:Example",
            page_id=7,
            revision_id=42,
            timestamp="2026-10-15T12:00:00Z",
            start_timestamp="2026-10-17T12:00:00Z",
            user="Editor",
        )
        assert snapshots[43].source_text == ""
        assert snapshots[43].revision is not None
        assert snapshots[43].revision.revision_id == 43
        assert snapshots[43].revision.user is None
        request = api.requests[0]
        assert request.method == "GET"
        assert request.query["revids"] == "43|42"
        assert request.query["prop"] == "revisions|info"
        assert request.query["rvslots"] == "main"
        assert request.query["rvprop"] == "ids|timestamp|user|comment|content|contentmodel"
        assert request.query["curtimestamp"] == "1"
        assert "titles" not in request.query

    @pytest.mark.parametrize(
        ("change", "message"),
        [
            ({"slots": {"main": {"contentmodel": "wikitext"}}}, "42.*"),
            ({"slots": {"main": {"*": None, "contentmodel": "wikitext"}}}, "42.*source"),
            ({"texthidden": ""}, "42.*hidden"),
            ({"slots": {"main": {"*": "hidden", "contentmodel": "wikitext", "texthidden": ""}}}, "42.*hidden"),
            ({"slots": {"main": {"*": "source"}}}, "42.*contentmodel"),
            ({"timestamp": None}, "42.*timestamp"),
            ({"user": None}, "42.*user"),
            ({"revid": 99}, "unexpected revision 99"),
        ],
    )
    def test_get_revision_snapshots_rejects_unreadable_revision(self, change: dict[str, Any], message: str) -> None:
        revision = {
            "revid": 42,
            "timestamp": "2026-10-16T12:00:00Z",
            "user": "Editor",
            "slots": {"main": {"*": "source", "contentmodel": "wikitext"}},
        } | change
        client, _ = _mock_client(
            [
                {
                    "curtimestamp": "2026-10-17T12:00:00Z",
                    "query": {
                        "pages": {
                            "7": {
                                "pageid": 7,
                                "title": "Example",
                                "contentmodel": "wikitext",
                                "revisions": [revision],
                            }
                        }
                    },
                }
            ],
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiAPIError, match=message):
            client.get_revision_snapshots([42])

    def test_get_revision_snapshots_rejects_missing_or_deleted_revision(self) -> None:
        client, _ = _mock_client(
            [
                {
                    "curtimestamp": "2026-10-17T12:00:00Z",
                    "query": {"badrevids": {"42": {"revid": 42, "missing": ""}}, "pages": {}},
                }
            ],
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiAPIError, match=r"not returned or unreadable.*42"):
            client.get_revision_snapshots([42])

    def test_get_revision_snapshots_batches_and_follows_continuation(self) -> None:
        def response(revision_id: int) -> dict[str, Any]:
            return {
                "curtimestamp": "2026-10-17T12:00:00Z",
                "query": {
                    "pages": {
                        "7": {
                            "pageid": 7,
                            "title": "Example",
                            "revisions": [
                                {
                                    "revid": revision_id,
                                    "timestamp": "2026-10-16T12:00:00Z",
                                    "user": "Editor",
                                    "contentmodel": "wikitext",
                                    "slots": {"main": {"*": str(revision_id)}},
                                }
                            ],
                        }
                    }
                },
            }

        client, api = _mock_client(
            [
                response(42) | {"continue": {"rvcontinue": "7|43", "continue": "||"}},
                response(43),
                response(44),
            ],
            batch_size=2,
            clock=MockClock(),
        )

        assert set(client.get_revision_snapshots([42, 43, 44])) == {42, 43, 44}
        assert api.requests[1].query["revids"] == "42|43"
        assert api.requests[1].query["rvcontinue"] == "7|43"
        assert api.requests[2].query["revids"] == "44"

    def test_get_revision_snapshots_empty_request_makes_no_request(self) -> None:
        client, api = _mock_client([], clock=MockClock())

        assert client.get_revision_snapshots([]) == {}
        assert api.requests == []

    @pytest.mark.parametrize("revision_id", [0, -1, True, "42"])
    def test_get_revision_snapshots_rejects_invalid_revision_ids(self, revision_id: Any) -> None:
        client, api = _mock_client([], clock=MockClock())

        with pytest.raises(ValueError, match="positive integers"):
            client.get_revision_snapshots([revision_id])
        assert api.requests == []

    """Test guarded page writes."""

    def test_safe_edit_page_reports_a_failed_edit_result(self) -> None:
        """A non-success edit result is an edit failure, not a silent success."""
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                _revision_response("Item:Sword"),
                {"edit": {"result": "Failure", "error": "Permission denied"}},
            ],
            clock=MockClock(),
        )
        base_revision = MediaWikiPageRevision(
            title="Item:Sword",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
            user="ErenshorBot",
        )
        with pytest.raises(MediaWikiEditError, match="Safe edit failed"):
            client.safe_edit_page(title="Item:Sword", content="new content", base_revision=base_revision)

    def test_safe_create_page_uses_client_default_summary_and_minor_flag(self) -> None:
        """A write without summary or minor flag takes the client defaults."""
        client, api = _mock_client(
            [
                _missing_snapshot_response("Item:Sword"),
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"edit": {"result": "Success", "oldrevid": 0, "newrevid": 7}},
                _revision_response("Item:Sword", 7, source="new content", parent_id=0),
            ],
            edit_summary="Default summary",
            minor_edit=True,
            clock=MockClock(),
        )
        client.safe_create_page(title="Item:Sword", content="new content", start_timestamp="2026-06-04T12:00:00Z")
        call_data = next(request.data for request in api.requests if request.method == "POST")
        assert call_data["summary"] == "Default summary"
        assert call_data["minor"] == "1"

    def test_safe_edit_page_keeps_network_failures_distinct_from_edit_failures(self) -> None:
        """A transport failure during a write is not a failure of the page."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                raise httpx.TimeoutException("Request timeout", request=request)
            if request.url.params.get("prop") == "revisions":
                return httpx.Response(200, json=_revision_response("Item:Sword"))
            return httpx.Response(200, json={"query": {"tokens": {"csrftoken": "test_csrf_token"}}})

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php", transport=httpx.MockTransport(handler), clock=MockClock()
        )
        base_revision = MediaWikiPageRevision(
            title="Item:Sword",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
            user="ErenshorBot",
        )
        with pytest.raises(MediaWikiNetworkError, match="Request timeout"):
            client.safe_edit_page(title="Item:Sword", content="new content", base_revision=base_revision)

    @pytest.mark.parametrize(
        ("user", "text", "parent_id", "landed"),
        [
            ("WoWBot", "new content\n", 1234, True),
            ("Ulor", "new content", 1234, False),
            ("WoWBot", "new content", 1233, False),
            ("WoWBot", "new content", None, False),
        ],
    )
    def test_a_timed_out_edit_counts_only_when_the_page_holds_it_from_this_account(
        self, user: str, text: str, parent_id: int | None, landed: bool
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                raise httpx.TimeoutException("Request timeout", request=request)
            if request.url.params.get("meta") == "tokens":
                return httpx.Response(200, json={"query": {"tokens": {"csrftoken": "test_csrf_token"}}})
            if request.url.params.get("rvprop") == "ids|timestamp|user|comment":
                return httpx.Response(200, json=_revision_response("Item:Sword"))
            revision = {
                "revid": 1235,
                "parentid": parent_id,
                "timestamp": "t",
                "user": user,
                "slots": {"main": {"*": text}},
            }
            page = {"pageid": 42, "title": "Item:Sword", "revisions": [revision]}
            return httpx.Response(200, json={"curtimestamp": "t", "query": {"pages": {"42": page}}})

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            transport=httpx.MockTransport(handler),
            clock=MockClock(),
            bot_username="WoWBot@Deploy",
        )
        base_revision = MediaWikiPageRevision("Item:Sword", 42, 1234, "t", "t", "WoWBot")

        if landed:
            assert client.safe_edit_page(title="Item:Sword", content="new content", base_revision=base_revision) == 1235
        else:
            with pytest.raises(MediaWikiNetworkError, match="Request timeout"):
                client.safe_edit_page(title="Item:Sword", content="new content", base_revision=base_revision)


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
                                "revisions": [
                                    {"revid": 1234, "timestamp": "2026-06-04T11:59:00Z", "user": "ErenshorBot"}
                                ],
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
            user="ErenshorBot",
        )
        call_params = api.requests[0].query
        assert call_params["action"] == "query"
        assert call_params["titles"] == "Template:Item"
        assert call_params["prop"] == "revisions"
        assert call_params["rvprop"] == "ids|timestamp|user|comment"
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

    @pytest.mark.parametrize(
        ("parent_id", "source", "model", "old_revision_id"),
        [
            (1234, "reviewed source", "json", 0),
            (0, "transformed source", "json", 0),
            (0, "reviewed source", "wikitext", 0),
            (0, "reviewed source", "json", None),
        ],
    )
    def test_create_requires_true_creation_source_and_requested_model(
        self, parent_id: int, source: str, model: str, old_revision_id: int | None
    ) -> None:
        responses = [
            _missing_snapshot_response("Example"),
            {"query": {"tokens": {"csrftoken": "token"}}},
            {"edit": {"result": "Success", "oldrevid": old_revision_id, "newrevid": 1235}},
            _revision_response("Example", 1235, source=source, parent_id=parent_id, content_model=model),
        ]
        if parent_id:
            responses.append(_revision_response("Example", parent_id, source="actual parent"))
        client, api = _mock_client(responses, clock=MockClock())

        with pytest.raises(MediaWikiEditVerificationError) as error:
            client.safe_create_page("Example", "reviewed source", "t", content_model="json")

        assert error.value.new_revision_id == 1235
        assert error.value.written_snapshot is not None
        assert (error.value.actual_parent_snapshot is not None) == bool(parent_id)
        assert sum(request.method == "POST" for request in api.requests) == 1

    def test_create_unreadable_history_retains_acknowledged_revision(self) -> None:
        client, _ = _mock_client(
            [
                _missing_snapshot_response("Example"),
                {"query": {"tokens": {"csrftoken": "token"}}},
                {"edit": {"result": "Success", "oldrevid": 0, "newrevid": 1235}},
                {"error": {"code": "permissiondenied", "info": "History unreadable"}},
            ],
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiEditVerificationError) as error:
            client.safe_create_page("Example", "reviewed source", "t")

        assert error.value.new_revision_id == 1235
        assert error.value.written_snapshot is None
        assert error.value.actual_parent_snapshot is None

    @pytest.mark.parametrize(
        ("parent_id", "model", "source", "landed"),
        [
            (0, "json", "reviewed source", True),
            (1234, "json", "reviewed source", False),
            (0, "wikitext", "reviewed source", False),
            (0, "json", "different source", False),
        ],
    )
    def test_lost_create_response_requires_creation_parent_source_and_model(
        self, parent_id: int, model: str, source: str, landed: bool
    ) -> None:
        posted = False

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal posted
            if request.method == "POST":
                posted = True
                raise httpx.TimeoutException("Request timeout", request=request)
            if request.url.params.get("meta") == "tokens":
                return httpx.Response(200, json={"query": {"tokens": {"csrftoken": "token"}}})
            if not posted:
                return httpx.Response(200, json=_missing_snapshot_response("Example"))
            return httpx.Response(
                200,
                json=_revision_response("Example", 1235, parent_id=parent_id, source=source, content_model=model),
            )

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            bot_username="ErenshorBot@Deploy",
            transport=httpx.MockTransport(handler),
            clock=MockClock(),
        )
        if landed:
            assert client.safe_create_page("Example", "reviewed source", "t", content_model="json") == 1235
        else:
            with pytest.raises(MediaWikiNetworkError):
                client.safe_create_page("Example", "reviewed source", "t", content_model="json")

    def test_create_resolves_native_canonical_title_before_posting(self) -> None:
        client, api = _mock_client(
            [
                _missing_snapshot_response("Example page", requested="example_page"),
                {"query": {"tokens": {"csrftoken": "token"}}},
                {"edit": {"result": "Success", "oldrevid": 0, "newrevid": 1235}},
                _revision_response("Example page", 1235, source="reviewed source", parent_id=0),
            ],
            clock=MockClock(),
        )

        assert client.safe_create_page("example_page", "reviewed source", "t") == 1235
        post = next(request for request in api.requests if request.method == "POST")
        assert post.data["title"] == "Example page"
        assert api.requests[0].query["titles"] == "example_page"

    def test_create_preflight_existing_page_never_posts(self) -> None:
        client, api = _mock_client([_revision_response("Example")], clock=MockClock())

        with pytest.raises(MediaWikiEditConflictError, match="already exists"):
            client.safe_create_page("Example", "reviewed source", "t")

        assert all(request.method == "GET" for request in api.requests)

    @pytest.mark.parametrize("content_model", ["json", "Scribunto", "sanitized-css"])
    def test_safe_create_page_sends_create_hash_timestamp_and_assertion_parameters(self, content_model: str) -> None:
        """Test safe creates include create-only, start timestamp, MD5, and assertion guard."""
        with _mediawiki_api_server(
            [
                _missing_snapshot_response("Module:Erenshor/Data/Items"),
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                {"edit": {"result": "Success", "oldrevid": 0, "newrevid": 1235}},
                _revision_response(
                    "Module:Erenshor/Data/Items", 1235, source="return {}", parent_id=0, content_model=content_model
                ),
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
                content_model=content_model,
            )

        assert new_revision_id == 1235
        assert len(api.requests) == 4
        canonical_request, token_request, edit_request, verification_request = api.requests
        assert canonical_request.query["titles"] == "Module:Erenshor/Data/Items"
        assert verification_request.query["revids"] == "1235"
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
        assert edit_request.data["contentmodel"] == content_model
        assert edit_request.data["bot"] == "1"

    def test_safe_create_page_refreshes_csrf_token_once_after_badtoken(self) -> None:
        """Test stale CSRF tokens are refreshed once without changing the create guard."""
        with _mediawiki_api_server(
            [
                _missing_snapshot_response("Module:Erenshor/Data/Items"),
                {"query": {"tokens": {"csrftoken": "stale_token"}}},
                {"error": {"code": "badtoken", "info": "Invalid token"}},
                {"query": {"tokens": {"csrftoken": "fresh_token"}}},
                {"edit": {"result": "Success", "oldrevid": 0, "newrevid": 1235}},
                _revision_response("Module:Erenshor/Data/Items", 1235, source="return {}", parent_id=0),
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
                _missing_snapshot_response("Module:Erenshor/Data/Items"),
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


class TestMediaWikiClientWriteReceipts:
    """Every failed historical verification retains the native acknowledgement."""

    @pytest.mark.parametrize("create", [False, True])
    @pytest.mark.parametrize("parent_read_fails", [False, True])
    @pytest.mark.parametrize(
        "failure_type", [httpx.RemoteProtocolError, httpx.ProxyError, RuntimeError, KeyError, KeyboardInterrupt]
    )
    def test_post_ack_failures_retain_receipt_and_available_source(
        self, create: bool, parent_read_fails: bool, failure_type: type[BaseException]
    ) -> None:
        posts = 0
        failed_reads = 0
        failures: list[BaseException] = []
        stored_source = "Actual\r\nsaved\u00a0"

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal posts, failed_reads
            if request.method == "POST":
                posts += 1
                return httpx.Response(
                    200, json={"edit": {"result": "Success", "oldrevid": 0 if create else 1234, "newrevid": 1236}}
                )
            if request.url.params.get("meta") == "tokens":
                return httpx.Response(200, json={"query": {"tokens": {"csrftoken": "token"}}})
            historical_id = request.url.params.get("revids")
            if historical_id is not None:
                if parent_read_fails and historical_id == "1236":
                    return httpx.Response(
                        200, json=_revision_response(revision_id=1236, parent_id=1235, source=stored_source)
                    )
                failed_reads += 1
                failure = failure_type("History failed")
                failures.append(failure)
                raise failure
            return httpx.Response(
                200, json=_missing_snapshot_response("Template:Item") if create else _revision_response()
            )

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            transport=httpx.MockTransport(handler),
            clock=MockClock(),
            request_policy=MediaWikiRequestPolicy(max_retries=1),
        )
        base = MediaWikiPageRevision("Template:Item", 42, 1234, "t", "t", "ErenshorBot")

        with pytest.raises(MediaWikiEditVerificationError, match="could not be verified") as error:
            if create:
                client.safe_create_page("Template:Item", "reviewed source", "t")
            else:
                client.safe_edit_page("Template:Item", "reviewed source", base)

        assert posts == 1
        assert failed_reads == (2 if issubclass(failure_type, httpx.TransportError) else 1)
        assert error.value.new_revision_id == 1236
        assert error.value.actual_parent_snapshot is None
        if parent_read_fails:
            assert error.value.written_snapshot is not None
            assert error.value.written_snapshot.source_text == stored_source
            assert error.value.written_snapshot.revision is not None
            assert error.value.written_snapshot.revision.parent_revision_id == 1235
        else:
            assert error.value.written_snapshot is None
        if issubclass(failure_type, httpx.TransportError):
            assert isinstance(error.value.__cause__, MediaWikiNetworkError)
            assert error.value.__cause__.__cause__ is failures[-1]
        else:
            assert error.value.__cause__ is failures[-1]

    @pytest.mark.parametrize("create", [False, True])
    def test_lost_post_answer_and_failed_attribution_remain_unknown_without_retry(self, create: bool) -> None:
        posts = 0
        attribution_reads = 0
        post_failure = httpx.RemoteProtocolError("POST answer lost")

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal posts, attribution_reads
            if request.method == "POST":
                posts += 1
                raise post_failure
            if request.url.params.get("meta") == "tokens":
                return httpx.Response(200, json={"query": {"tokens": {"csrftoken": "token"}}})
            if posts:
                attribution_reads += 1
                raise httpx.RemoteProtocolError("Attribution unavailable", request=request)
            return httpx.Response(
                200, json=_missing_snapshot_response("Template:Item") if create else _revision_response()
            )

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            transport=httpx.MockTransport(handler),
            clock=MockClock(),
            request_policy=MediaWikiRequestPolicy(max_retries=1),
        )
        base = MediaWikiPageRevision("Template:Item", 42, 1234, "t", "t", "ErenshorBot")

        with pytest.raises(MediaWikiNetworkError, match="POST answer lost") as error:
            if create:
                client.safe_create_page("Template:Item", "reviewed source", "t")
            else:
                client.safe_edit_page("Template:Item", "reviewed source", base)

        assert not isinstance(error.value, MediaWikiEditVerificationError)
        assert error.value.__cause__ is post_failure
        assert posts == 1
        assert attribution_reads == 2

    @pytest.mark.parametrize("failure_type", [httpx.RemoteProtocolError, httpx.ProxyError, httpx.ReadTimeout])
    def test_download_translates_exhausted_transport_failures(self, failure_type: type[httpx.TransportError]) -> None:
        attempts = 0
        failure = failure_type("Download failed")

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            raise failure

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            transport=httpx.MockTransport(handler),
            clock=MockClock(),
            request_policy=MediaWikiRequestPolicy(max_retries=1),
        )
        with pytest.raises(MediaWikiNetworkError) as error:
            client.download("https://erenshor.wiki.gg/images/example.png")

        assert error.value.__cause__ is failure
        assert attempts == 2


class TestMediaWikiClientSavedTextNormalization:
    """Saved-source comparisons share MediaWiki normalization without changing API strings."""

    @pytest.mark.parametrize("mode", ["edit", "create", "nochange", "lost-edit", "lost-create"])
    @pytest.mark.parametrize(
        ("requested", "stored", "matches"),
        [
            ("First\r\nSecond\rThird \t\n\r\x00\x0b", "First\nSecond\nThird", True),
            ("Source\u00a0 \t\n", "Source\u00a0", True),
            ("Source\u00a0", "Source", False),
            ("Source", "Source\u00a0", False),
            ("Source\u2003", "Source", False),
            ("Source\x0c", "Source", False),
        ],
    )
    def test_checked_writes_compare_only_saved_text_normalization(
        self, mode: str, requested: str, stored: str, matches: bool
    ) -> None:
        create = mode in {"create", "lost-create"}
        posts: list[dict[str, str]] = []
        saved_revision_id = 1234 if mode == "nochange" else 1235

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                posts.append({key: values[-1] for key, values in parse_qs(request.content.decode()).items()})
                if mode.startswith("lost-"):
                    raise httpx.RemoteProtocolError("POST answer lost", request=request)
                edit = {"result": "Success", "oldrevid": 0 if create else 1234, "newrevid": saved_revision_id}
                if mode == "nochange":
                    edit["nochange"] = ""
                return httpx.Response(200, json={"edit": edit})
            if request.url.params.get("meta") == "tokens":
                return httpx.Response(200, json={"query": {"tokens": {"csrftoken": "token"}}})
            if not posts:
                return httpx.Response(
                    200, json=_missing_snapshot_response("Template:Item") if create else _revision_response()
                )
            if request.url.params.get("revids") == "1234":
                return httpx.Response(200, json=_revision_response(source="Original\r\npreimage\u00a0"))
            return httpx.Response(
                200,
                json=_revision_response(revision_id=saved_revision_id, source=stored, parent_id=0 if create else 1234),
            )

        client = MediaWikiClient(
            api_url="https://erenshor.wiki.gg/api.php",
            bot_username="ErenshorBot@Deploy",
            transport=httpx.MockTransport(handler),
            clock=MockClock(),
        )
        base = MediaWikiPageRevision("Template:Item", 42, 1234, "t", "t", "ErenshorBot")

        def write() -> int:
            if create:
                return client.safe_create_page("Template:Item", requested, "t")
            return client.safe_edit_page("Template:Item", requested, base)

        if matches:
            assert write() == saved_revision_id
        elif mode.startswith("lost-"):
            with pytest.raises(MediaWikiNetworkError):
                write()
        elif mode == "nochange":
            with pytest.raises(MediaWikiEditConflictError):
                write()
        else:
            with pytest.raises(MediaWikiEditVerificationError) as error:
                write()
            assert error.value.new_revision_id == saved_revision_id
            assert error.value.written_snapshot is not None
            assert error.value.written_snapshot.source_text == stored
            if not create:
                assert error.value.actual_parent_snapshot is not None
                assert error.value.actual_parent_snapshot.source_text == "Original\r\npreimage\u00a0"
        assert len(posts) == 1
        assert posts[0]["text"] == requested
        assert posts[0]["md5"] == hashlib.md5(requested.encode(), usedforsecurity=False).hexdigest()


class TestMediaWikiClientSafeEditPage:
    """Test conflict-safe wiki page edits."""

    def test_edit_requires_requested_content_model(self) -> None:
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "token"}}},
                _revision_response(),
                {"edit": {"result": "Success", "oldrevid": 1234, "newrevid": 1235}},
                _revision_response(revision_id=1235, parent_id=1234, source="reviewed source"),
                _revision_response(),
            ],
            clock=MockClock(),
        )
        base = MediaWikiPageRevision("Template:Item", 42, 1234, "t", "t", "ErenshorBot")

        with pytest.raises(MediaWikiEditVerificationError) as error:
            client.safe_edit_page("Template:Item", "reviewed source", base, content_model="json")

        assert error.value.new_revision_id == 1235
        assert error.value.written_snapshot is not None
        assert error.value.written_snapshot.content_model == "wikitext"

    def test_stale_preflight_never_posts_an_edit(self) -> None:
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "token"}}},
                _revision_response(revision_id=1235),
            ],
            clock=MockClock(),
        )
        base = MediaWikiPageRevision("Template:Item", 42, 1234, "t", "t", "ErenshorBot")

        with pytest.raises(MediaWikiEditConflictError, match="before writing"):
            client.safe_edit_page("Template:Item", "reviewed source", base)

        assert all(request.method == "GET" for request in api.requests)

    @pytest.mark.parametrize(
        ("parent_id", "stored_source", "old_revision_id"),
        [
            (1235, "reviewed source\neditor paragraph", 1234),
            (1235, "reviewed source", 1235),
            (1234, "unexpected transformed source", 1234),
            (1234, "reviewed source", None),
        ],
    )
    def test_acknowledged_race_preserves_written_and_actual_parent_snapshots(
        self, parent_id: int, stored_source: str, old_revision_id: int | None
    ) -> None:
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "token"}}},
                _revision_response(),
                {"edit": {"result": "Success", "oldrevid": old_revision_id, "newrevid": 1236}},
                _revision_response(revision_id=1236, parent_id=parent_id, source=stored_source),
                _revision_response(revision_id=parent_id, source="actual parent with editor paragraph"),
            ],
            clock=MockClock(),
        )
        base = MediaWikiPageRevision("Template:Item", 42, 1234, "t", "t", "ErenshorBot")

        with pytest.raises(MediaWikiEditVerificationError) as error:
            client.safe_edit_page("Template:Item", "reviewed source", base)

        assert error.value.new_revision_id == 1236
        assert error.value.written_snapshot is not None
        assert error.value.written_snapshot.source_text == stored_source
        assert error.value.actual_parent_snapshot is not None
        assert error.value.actual_parent_snapshot.source_text == "actual parent with editor paragraph"
        assert error.value.actual_parent_snapshot.revision is not None
        assert error.value.actual_parent_snapshot.revision.revision_id == parent_id
        assert sum(request.method == "POST" for request in api.requests) == 1
        assert api.requests[-2].query["revids"] == "1236"
        assert api.requests[-1].query["revids"] == str(parent_id)

    @pytest.mark.parametrize("parent_read_fails", [False, True])
    def test_acknowledged_receipt_survives_unreadable_history(self, parent_read_fails: bool) -> None:
        responses: list[dict[str, Any]] = [
            {"query": {"tokens": {"csrftoken": "token"}}},
            _revision_response(),
            {"edit": {"result": "Success", "oldrevid": 1234, "newrevid": 1236}},
        ]
        if parent_read_fails:
            responses.append(_revision_response(revision_id=1236, parent_id=1235, source="merged source"))
        responses.append({"error": {"code": "permissiondenied", "info": "History unreadable"}})
        client, api = _mock_client(responses, clock=MockClock())
        base = MediaWikiPageRevision("Template:Item", 42, 1234, "t", "t", "ErenshorBot")

        with pytest.raises(MediaWikiEditVerificationError, match="could not be verified") as error:
            client.safe_edit_page("Template:Item", "reviewed source", base)

        assert error.value.new_revision_id == 1236
        assert (error.value.written_snapshot is not None) == parent_read_fails
        assert error.value.actual_parent_snapshot is None
        assert sum(request.method == "POST" for request in api.requests) == 1

    def test_nochange_does_not_substitute_a_newer_revision(self) -> None:
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "token"}}},
                _revision_response(),
                {"edit": {"result": "Success", "nochange": ""}},
                _revision_response(revision_id=1235, source="reviewed source"),
            ],
            clock=MockClock(),
        )
        base = MediaWikiPageRevision("Template:Item", 42, 1234, "t", "t", "ErenshorBot")

        with pytest.raises(MediaWikiEditConflictError, match="no-change"):
            client.safe_edit_page("Template:Item", "reviewed source", base)

    def test_edit_verifies_canonical_base_title_for_requested_alias(self) -> None:
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "token"}}},
                _revision_response("Example page"),
                {"edit": {"result": "Success", "oldrevid": 1234, "newrevid": 1235}},
                _revision_response("Example page", 1235, source="reviewed source", parent_id=1234),
            ],
            clock=MockClock(),
        )
        base = MediaWikiPageRevision("Example page", 42, 1234, "t", "t", "ErenshorBot")

        assert client.safe_edit_page("example_page", "reviewed source", base) == 1235
        post = next(request for request in api.requests if request.method == "POST")
        assert post.data["title"] == "example_page"

    @pytest.mark.parametrize("content_model", ["wikitext", "Scribunto", "sanitized-css"])
    def test_safe_edit_page_sends_conflict_hash_and_assertion_parameters(self, content_model: str) -> None:
        """Test safe edits include base revision, start timestamp, MD5, and assertion guard."""
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                _revision_response(),
                {"edit": {"result": "Success", "oldrevid": 1234, "newrevid": 1235}},
                _revision_response(
                    revision_id=1235, parent_id=1234, source="new template source", content_model=content_model
                ),
            ],
            clock=MockClock(),
        )
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
            user="ErenshorBot",
        )
        new_revision_id = client.safe_edit_page(
            title="Template:Item",
            content="new template source",
            base_revision=base_revision,
            summary="Deploy repo-owned template",
            assertion="bot",
            assert_user="ErenshorBot",
            content_model=content_model,
        )

        assert new_revision_id == 1235
        call_data = next(request.data for request in api.requests if request.method == "POST")
        assert call_data["action"] == "edit"
        assert call_data["title"] == "Template:Item"
        assert call_data["text"] == "new template source"
        assert call_data["summary"] == "Deploy repo-owned template"
        assert call_data["token"] == "test_csrf_token"
        assert call_data["baserevid"] == "1234"
        assert call_data["contentmodel"] == content_model
        assert call_data["starttimestamp"] == "2026-06-04T12:00:00Z"
        assert call_data["md5"] == hashlib.md5(b"new template source", usedforsecurity=False).hexdigest()
        assert call_data["assert"] == "bot"
        assert call_data["assertuser"] == "ErenshorBot"
        assert call_data["bot"] == "1"
        assert call_data["nocreate"] == "1"

    def test_safe_edit_page_refreshes_csrf_token_once_after_badtoken(self) -> None:
        """Test stale CSRF tokens are refreshed once without changing the base revision guard."""
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "stale_token"}}},
                _revision_response(),
                {"error": {"code": "badtoken", "info": "Invalid token"}},
                {"query": {"tokens": {"csrftoken": "fresh_token"}}},
                _revision_response(),
                {"edit": {"result": "Success", "oldrevid": 1234, "newrevid": 1235}},
                _revision_response(revision_id=1235, parent_id=1234, source="new template source"),
            ],
            clock=MockClock(),
        )
        base_revision = MediaWikiPageRevision(
            title="Template:Item",
            page_id=42,
            revision_id=1234,
            timestamp="2026-06-04T11:59:00Z",
            start_timestamp="2026-06-04T12:00:00Z",
            user="ErenshorBot",
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
                _revision_response(),
                {"error": {"code": "badtoken", "info": "Invalid token"}},
                {"query": {"tokens": {"csrftoken": "still_bad_token"}}},
                _revision_response(),
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
            user="ErenshorBot",
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
                _revision_response(),
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
            user="ErenshorBot",
        )
        with pytest.raises(MediaWikiEditConflictError, match="Edit conflict"):
            client.safe_edit_page(title="Template:Item", content="new template source", base_revision=base_revision)

    def test_safe_edit_page_surfaces_assertion_failure(self) -> None:
        """Test assertion failures are raised separately from generic edit failures."""
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                _revision_response(),
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
            user="ErenshorBot",
        )
        with pytest.raises(MediaWikiAssertionError, match="Not logged in as a bot"):
            client.safe_edit_page(title="Template:Item", content="new template source", base_revision=base_revision)

    def test_safe_edit_page_surfaces_permission_failure(self) -> None:
        """Test permission failures are raised separately from generic edit failures."""
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                _revision_response(),
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
            user="ErenshorBot",
        )
        with pytest.raises(MediaWikiPermissionError, match="Permission denied"):
            client.safe_edit_page(title="Template:Item", content="new template source", base_revision=base_revision)

    def test_safe_edit_page_returns_base_revision_on_no_change(self) -> None:
        """Test an identical-content edit (nochange) reports the existing revision, not a crash."""
        with _mediawiki_api_server(
            [
                {"query": {"tokens": {"csrftoken": "test_csrf_token"}}},
                _revision_response(page_id=7),
                {"edit": {"result": "Success", "pageid": 7, "title": "Template:Item", "nochange": ""}},
                _revision_response(page_id=7, source="identical source"),
            ]
        ) as (api_url, api):
            client = MediaWikiClient(api_url=api_url, transport=api.transport, clock=MockClock())
            base_revision = MediaWikiPageRevision(
                title="Template:Item",
                page_id=7,
                revision_id=1234,
                timestamp="2026-06-04T11:59:00Z",
                start_timestamp="2026-06-04T12:00:00Z",
                user="ErenshorBot",
            )

            revision_id = client.safe_edit_page(
                title="Template:Item",
                content="identical source",
                base_revision=base_revision,
            )

        assert revision_id == 1234


class TestMediaWikiClientTemplateSandbox:
    def test_parse_replaces_one_module_and_returns_render_dependencies(self) -> None:
        client, api = _mock_client(
            [
                {
                    "parse": {
                        "text": "<p>new</p>",
                        "templates": [{"title": "Template:Item", "exists": True}],
                        "categories": [{"category": "Items"}],
                    }
                }
            ],
            clock=MockClock(),
        )
        parsed = client.parse_wikitext(
            "Example",
            "{{Item}}",
            sandbox_title="Module:Erenshor/Item",
            sandbox_text="return {}",
            sandbox_content_model="Scribunto",
        )
        assert parsed.html == "<p>new</p>"
        assert parsed.templates[0].title == "Template:Item"
        assert parsed.categories[0].title == "Category:Items"
        [request] = api.requests
        assert request.data["prop"] == "text|templates|categories"
        assert request.data["templatesandboxtitle"] == "Module:Erenshor/Item"
        assert request.data["templatesandboxtext"] == "return {}"
        assert request.data["templatesandboxcontentmodel"] == "Scribunto"


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
                {"query": {"embeddedin": [{"pageid": 3, "ns": 10, "title": "Template:ItemTooltip"}]}},
            ],
            clock=MockClock(),
        )
        pages = client.get_embeddedin_pages("Template:Item", namespaces=(0, 10), assertion="bot")

        assert pages == ("Ember Longsword", "Abyssal Plate", "Template:ItemTooltip")
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
    """Test the limits installed after authentication."""

    def test_strictest_reported_bucket_paces_edits(self) -> None:
        clock = MockClock()
        client, api = _mock_client(
            [
                {"query": {"tokens": {"logintoken": "token"}}},
                {"login": {"result": "Success"}},
                {
                    "query": {
                        "userinfo": {
                            "name": "WoWBot",
                            "rights": ["edit", "purge"],
                            "ratelimits": {
                                "edit": {
                                    "user": {"hits": 90, "seconds": 60},
                                    "ip": {"hits": 100, "seconds": 60},
                                },
                                "purge": {"user": {"hits": 30, "seconds": 60}},
                            },
                        }
                    }
                },
                {"parse": {"text": {"*": "ok"}}},
                {"edit": {"result": "Success"}},
                {"edit": {"result": "Success"}},
            ],
            bot_username="WoWBot@Deploy",
            bot_password="secret",
            clock=clock,
        )
        client.login()
        client._request({"action": "parse"}, method="POST", data={"text": "test"})
        before = clock.time()
        client._request({"action": "edit"}, method="POST", data={"text": "first"})
        client._request({}, method="POST", data={"action": "edit", "text": "second"})
        assert clock.time() - before >= 60 / 90 * 1.1
        assert clock.time() - before < 0.734
        assert [request.data.get("action", request.query.get("action")) for request in api.requests[3:]] == [
            "parse",
            "edit",
            "edit",
        ]

    def test_noratelimit_right_skips_spacing(self) -> None:
        clock = MockClock()
        client, _ = _mock_client(
            [
                {"query": {"tokens": {"logintoken": "token"}}},
                {"login": {"result": "Success"}},
                {
                    "query": {
                        "userinfo": {
                            "name": "WoWBot",
                            "rights": ["edit", "noratelimit"],
                            "ratelimits": {"edit": {"user": {"hits": 90, "seconds": 60}}},
                        }
                    }
                },
                {"edit": {"result": "Success"}},
                {"edit": {"result": "Success"}},
            ],
            bot_username="WoWBot@Deploy",
            bot_password="secret",
            clock=clock,
        )
        client.login()
        before = clock.time()
        client._request({}, method="POST", data={"action": "edit"})
        client._request({}, method="POST", data={"action": "edit"})
        assert clock.time() == before


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

    _FAST_POLICY = MediaWikiRequestPolicy(base_backoff=1.0, jitter=0.0, max_retries=2)

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

    def test_user_creations_follow_continuation_and_keep_only_bot_articles(self) -> None:
        def contribution(title: str, revision: int) -> dict[str, Any]:
            return {"title": title, "ns": 0, "user": "WoWBot", "pageid": revision, "revid": revision, "new": ""}

        client, api = _mock_client(
            [
                {
                    "continue": {"uccontinue": "next", "continue": "-||"},
                    "query": {"usercontribs": [contribution("Old A", 1)]},
                },
                {"query": {"usercontribs": [contribution("Old B", 2), contribution("Old A", 1)]}},
            ],
            clock=MockClock(),
        )
        assert client.list_user_created_pages("WoWBot") == ("Old A", "Old B")
        assert api.requests[0].query["list"] == "usercontribs"
        assert api.requests[0].query["ucshow"] == "new"
        assert api.requests[0].query["ucnamespace"] == "0"
        assert api.requests[1].query["uccontinue"] == "next"

    def test_user_creations_reject_incomplete_result(self) -> None:
        client, _ = _mock_client([{"query": {"usercontribs": [{"title": "Old A", "ns": 0}]}}], clock=MockClock())
        with pytest.raises(MediaWikiAPIError, match="Incomplete user contributions"):
            client.list_user_created_pages("WoWBot")

    def test_title_statuses_reject_missing_result(self) -> None:
        client, _ = _mock_client([{"query": {"pages": {}}}], clock=MockClock())
        with pytest.raises(MediaWikiAPIError, match="page not returned"):
            client.get_title_statuses(["Old A"])

    def test_uploaded_files_follow_redirects_and_ignore_description_pages(self) -> None:
        client, api = _mock_client(
            [
                {
                    "query": {
                        "normalized": [{"from": "File:Lower_case.png", "to": "File:Lower case.png"}],
                        "redirects": [
                            {"from": "File:Lower case.png", "to": "File:Uploaded.png"},
                            {"from": "File:Dangling.png", "to": "File:Gone.png"},
                        ],
                        "pages": {
                            "1": {"pageid": 1, "title": "File:Uploaded.png", "imageinfo": [{"user": "Editor"}]},
                            "2": {"pageid": 2, "title": "File:Description only.png", "imagerepository": ""},
                            "-1": {"title": "File:Gone.png", "missing": ""},
                            "-2": {"title": "File:Missing.png", "missing": ""},
                        },
                    }
                }
            ],
            clock=MockClock(),
        )

        uploaded = client.get_uploaded_files(
            [
                "File:Uploaded.png",
                "File:Lower_case.png",
                "File:Description only.png",
                "File:Dangling.png",
                "File:Missing.png",
            ]
        )

        assert uploaded == {"File:Uploaded.png", "File:Lower_case.png"}
        assert api.requests[0].query["prop"] == "imageinfo"

    def test_file_uploads_name_the_final_file_its_uploader_and_hash(self) -> None:
        client, api = _mock_client(
            [
                {
                    "query": {
                        "redirects": [{"from": "File:Stance: Aggressive.png", "to": "File:Stance Aggressive.png"}],
                        "pages": {
                            "1": {
                                "pageid": 1,
                                "title": "File:Stance Aggressive.png",
                                "imageinfo": [{"user": "WoWBot", "sha1": "ab12"}],
                            },
                            "-1": {"title": "File:Faith.png", "missing": ""},
                        },
                    }
                }
            ],
            clock=MockClock(),
        )

        uploads = client.get_file_uploads(["File:Stance: Aggressive.png", "File:Faith.png"])

        assert uploads == {
            "File:Stance: Aggressive.png": MediaWikiFileUpload("File:Stance Aggressive.png", "WoWBot", "ab12")
        }
        assert api.requests[0].query["iiprop"] == "user|sha1"

    def test_files_by_sha1_list_every_title_with_that_image(self) -> None:
        client, api = _mock_client(
            [{"query": {"allimages": [{"title": "File:Vithean Chest.png"}, {"title": "File:Braxonian Chest.png"}]}}],
            clock=MockClock(),
        )

        titles = client.find_files_by_sha1("ab12")

        assert titles == ("File:Braxonian Chest.png", "File:Vithean Chest.png")
        assert (api.requests[0].query["list"], api.requests[0].query["aisha1"]) == ("allimages", "ab12")

    def test_upload_warnings_reach_the_caller_one_by_one(self, tmp_path: Path) -> None:
        image = tmp_path / "Faith.png"
        image.write_bytes(b"png")
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "token"}}},
                {"upload": {"result": "Warning", "warnings": {"exists": "Faith.png", "duplicate": ["Star.png"]}}},
            ],
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiUploadWarningError) as raised:
            client.upload_file(str(image), "Faith.png", "Upload a capture")

        assert raised.value.warnings == {"exists": "Faith.png", "duplicate": ["Star.png"]}
        assert "ignorewarnings" not in api.requests[-1].data

    def test_a_warned_upload_keeps_its_stash_key_and_confirming_publishes_it(self, tmp_path: Path) -> None:
        image = tmp_path / "Thorned Branch.png"
        image.write_bytes(b"png")
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "token"}}},
                {"upload": {"result": "Warning", "warnings": {"exists": "Thorned_Branch.png"}, "filekey": "k1.png"}},
                {"upload": {"result": "Success", "filename": "Thorned_Branch.png"}},
            ],
            clock=MockClock(),
        )

        with pytest.raises(MediaWikiUploadWarningError) as raised:
            client.upload_file(str(image), "Thorned Branch.png", "Icon update")
        client.confirm_upload(raised.value.filekey or "", "Thorned Branch.png", "Icon update")

        assert raised.value.filekey == "k1.png"
        confirmation = api.requests[-1].data
        assert (confirmation["filekey"], confirmation["ignorewarnings"], "file" in confirmation) == (
            "k1.png",
            "1",
            False,
        )

    def test_the_file_listing_follows_continuation_and_reads_hidden_uploaders(self) -> None:
        def entry(title: str, **extra: Any) -> dict[str, Any]:
            return {
                "title": title,
                "sha1": "ab12",
                "size": 1024,
                "width": 256,
                "height": 256,
                "timestamp": "2026-10-06T12:00:00Z",
                "url": f"https://erenshor.wiki.gg/images/{title[5:]}",
                **extra,
            }

        client, api = _mock_client(
            [
                {
                    "continue": {"aicontinue": "Faith.png", "continue": "-||"},
                    "query": {"allimages": [entry("File:Block.png", user="WoWBot", comment="Build 1")]},
                },
                {"query": {"allimages": [entry("File:Faith.png", userhidden="", comment="")]}},
            ],
            clock=MockClock(),
        )

        files = client.list_files()

        assert [(file.title, file.user, file.comment) for file in files] == [
            ("File:Block.png", "WoWBot", "Build 1"),
            ("File:Faith.png", None, ""),
        ]
        assert api.requests[1].query["aicontinue"] == "Faith.png"

    def test_the_file_listing_rejects_a_repeated_continuation(self) -> None:
        page = {"continue": {"aicontinue": "A.png", "continue": "-||"}, "query": {"allimages": []}}
        client, _ = _mock_client([page, page], clock=MockClock())

        with pytest.raises(MediaWikiAPIError, match="file listing response: repeated continuation"):
            client.list_files()

    def test_file_redirects_name_the_page_they_point_at_not_the_end_of_a_chain(self) -> None:
        client, api = _mock_client(
            [
                {
                    "query": {
                        "allpages": [
                            {"ns": 6, "title": "File:Stance: Aggressive.png"},
                            {"ns": 6, "title": "File:Stance Aggressive (old).png"},
                        ]
                    }
                },
                {
                    "query": {
                        "redirects": [
                            {"from": "File:Stance: Aggressive.png", "to": "File:Stance Aggressive (old).png"},
                            {"from": "File:Stance Aggressive (old).png", "to": "File:Stance Aggressive.png"},
                        ],
                        "pages": {"1": {"pageid": 1, "ns": 6, "title": "File:Stance Aggressive.png"}},
                    }
                },
                {
                    "query": {
                        "allpages": [
                            {"ns": 6, "title": "File:Stance Aggressive.png"},
                            {"ns": 6, "title": "File:Description only.png"},
                        ]
                    }
                },
            ],
            clock=MockClock(),
        )

        pages = client.list_file_pages()

        # MediaWiki shows a file through one redirect, so the first hop is what counts.
        assert pages.redirects == {
            "File:Stance: Aggressive.png": "File:Stance Aggressive (old).png",
            "File:Stance Aggressive (old).png": "File:Stance Aggressive.png",
        }
        assert pages.pages == {"File:Stance Aggressive.png", "File:Description only.png"}
        assert [api.requests[0].query["apfilterredir"], api.requests[2].query["apfilterredir"]] == [
            "redirects",
            "nonredirects",
        ]

    @pytest.mark.parametrize(
        ("uses", "used"),
        [
            ([{"pageid": 5, "ns": 6, "title": "File:Old name.png", "redirect": ""}], False),
            ([{"ns": 6, "title": "File:Old name.png", "redirect": "", "redirlinks": [{"title": "Faith"}]}], True),
            ([{"pageid": 7, "ns": 0, "title": "Faith"}], True),
        ],
    )
    def test_a_file_is_used_by_pages_but_not_by_a_bare_redirect(self, uses: list[dict[str, Any]], used: bool) -> None:
        client, _ = _mock_client([{"query": {"imageusage": uses}}], clock=MockClock())

        assert client.is_file_used("File:Faith.png") is used

    @pytest.mark.parametrize(
        ("call", "answer"),
        [
            ("delete_page", {"delete": {"title": "File:Copy.png", "reason": "Copy"}}),
            ("undelete_page", {"undelete": {"revisions": 0}}),
        ],
    )
    def test_a_deletion_or_restore_that_the_answer_does_not_confirm_fails(
        self, call: str, answer: dict[str, Any]
    ) -> None:
        client, api = _mock_client([{"query": {"tokens": {"csrftoken": "token"}}}, answer], clock=MockClock())

        with pytest.raises(MediaWikiAPIError, match=f"Unexpected {call.removesuffix('_page')} response"):
            getattr(client, call)("File:Copy.png", "Copy of File:Original.png")

        assert api.requests[-1].data["title"] == "File:Copy.png"

    def test_a_deletion_after_the_session_expired_logs_in_again_and_succeeds(self) -> None:
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "stale"}}},
                {"error": {"code": "assertuserfailed", "info": "You are no longer logged in."}},
                {"query": {"tokens": {"csrftoken": "fresh"}}},
                {"delete": {"title": "File:Copy.png", "reason": "Copy", "logid": 7}},
            ],
            clock=MockClock(),
        )
        logins: list[bool] = []
        client.login = lambda: logins.append(True)  # type: ignore[method-assign]

        client.delete_page("File:Copy.png", "Copy of File:Original.png")

        assert logins == [True]
        assert api.requests[1].data["assert"] == "user"
        assert api.requests[-1].data["token"] == "fresh"

    def test_a_move_sends_noredirect_only_without_a_redirect_and_fails_unless_the_answer_names_the_target(
        self,
    ) -> None:
        client, api = _mock_client(
            [
                {"query": {"tokens": {"csrftoken": "token"}}},
                {"move": {"from": "File:Faith.png", "to": "File:Faith render.png"}},
                {"move": {"from": "File:Faith render.png", "to": "File:Elsewhere.png"}},
            ],
            clock=MockClock(),
        )

        client.move_page("File:Faith.png", "File:Faith_render.png", "Rename")
        assert "noredirect" not in api.requests[-1].data
        with pytest.raises(MediaWikiAPIError, match="Unexpected move response"):
            client.move_page("File:Faith render.png", "File:Faith.png", "Revert", leave_redirect=False)
        assert api.requests[-1].data["noredirect"] == "1"

    def test_file_versions_come_newest_first_with_their_urls(self) -> None:
        version = {"sha1": "new", "user": "WoWBot", "comment": "Build 2", "timestamp": "2026-10-07T00:00:00Z"}
        older = {"sha1": "old", "user": "Ulor", "comment": "", "timestamp": "2026-01-01T00:00:00Z"}
        client, _ = _mock_client(
            [
                {
                    "query": {
                        "pages": {
                            "1": {
                                "title": "File:Block.png",
                                "imageinfo": [
                                    version | {"url": "https://example.test/Block.png"},
                                    older | {"url": "https://example.test/archive/Block.png"},
                                ],
                            }
                        }
                    }
                }
            ],
            clock=MockClock(),
        )

        versions = client.get_file_versions("File:Block.png")

        assert [(item.sha1, item.user, item.url) for item in versions] == [
            ("new", "WoWBot", "https://example.test/Block.png"),
            ("old", "Ulor", "https://example.test/archive/Block.png"),
        ]

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
