from __future__ import annotations

import httpx
import pytest

from erenshor.infrastructure.time import MockClock
from erenshor.infrastructure.wiki.rate_limit import (
    MediaWikiRequestor,
    MediaWikiRequestPolicy,
    MediaWikiRetryableRequestError,
    MediaWikiUnretryableRequestError,
)


class FakeHttpClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses
        self.requests: list[tuple[str, dict[str, str], dict[str, str] | None]] = []

    def get(self, url: str, *, params: dict[str, str]) -> httpx.Response:
        self.requests.append(("GET", params, None))
        return self._pop_response()

    def post(self, url: str, *, params: dict[str, str], data: dict[str, str] | None = None) -> httpx.Response:
        self.requests.append(("POST", params, data))
        return self._pop_response()

    def close(self) -> None:
        pass

    def _pop_response(self) -> httpx.Response:
        if not self._responses:
            raise AssertionError("unexpected HTTP request")
        return self._responses.pop(0)


def response(
    status_code: int = 200,
    *,
    json: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=json if json is not None else {"query": {}},
        headers=headers,
        request=httpx.Request("GET", "https://erenshor.wiki.gg/api.php"),
    )


def make_requestor(client: FakeHttpClient, clock: MockClock | None = None) -> MediaWikiRequestor:
    return MediaWikiRequestor(
        api_url="https://erenshor.wiki.gg/api.php",
        http_client=client,
        clock=clock or MockClock(),
        policy=MediaWikiRequestPolicy(read_delay=1.0, write_delay=2.0, max_retries=3, jitter=0.0),
    )


def test_adds_json_format_and_maxlag_to_noninteractive_requests() -> None:
    client = FakeHttpClient([response()])
    requestor = make_requestor(client)

    requestor.get({"action": "query"})

    assert client.requests == [
        (
            "GET",
            {"action": "query", "format": "json", "formatversion": "2", "maxlag": "5"},
            None,
        )
    ]


def test_download_uses_the_owned_http_session() -> None:
    image_response = httpx.Response(
        200,
        content=b"image-bytes",
        headers={"Content-Type": "image/png"},
        request=httpx.Request("GET", "https://erenshor.wiki.gg/images/logo.png"),
    )
    client = FakeHttpClient([image_response])
    requestor = make_requestor(client)

    result = requestor.download("https://erenshor.wiki.gg/images/logo.png")

    assert result.status_code == 200
    assert result.content_type == "image/png"
    assert result.content == b"image-bytes"
    assert client.requests == [("GET", {}, None)]


def test_omits_maxlag_for_interactive_requests() -> None:
    client = FakeHttpClient([response()])
    requestor = make_requestor(client)

    requestor.get({"action": "query"}, noninteractive=False)

    assert client.requests[0][1] == {"action": "query", "format": "json", "formatversion": "2"}


def test_serializes_requests_with_read_delay() -> None:
    clock = MockClock()
    client = FakeHttpClient([response(), response()])
    requestor = make_requestor(client, clock)

    start = clock.time()
    requestor.get({"action": "query"})
    requestor.get({"action": "query"})

    assert clock.time() - start >= 1.0


def test_retries_http_429_after_retry_after_header() -> None:
    clock = MockClock()
    client = FakeHttpClient(
        [
            response(429, json={"error": "too many"}, headers={"Retry-After": "7"}),
            response(json={"query": {"ok": True}}),
        ]
    )
    requestor = make_requestor(client, clock)

    result = requestor.get({"action": "query"})

    assert result == {"query": {"ok": True}}
    assert len(client.requests) == 2
    assert clock.time() >= 7


def test_retries_api_maxlag_error_with_retry_after_header() -> None:
    clock = MockClock()
    client = FakeHttpClient(
        [
            response(json={"error": {"code": "maxlag", "info": "Waiting", "lag": 9}}, headers={"Retry-After": "11"}),
            response(json={"query": {"ok": True}}),
        ]
    )
    requestor = make_requestor(client, clock)

    result = requestor.get({"action": "query"})

    assert result == {"query": {"ok": True}}
    assert len(client.requests) == 2
    assert clock.time() >= 11


def test_retries_api_ratelimited_error_with_exponential_backoff() -> None:
    clock = MockClock()
    client = FakeHttpClient(
        [
            response(json={"error": {"code": "ratelimited", "info": "Wait"}}),
            response(json={"query": {"ok": True}}),
        ]
    )
    requestor = make_requestor(client, clock)

    result = requestor.get({"action": "query"})

    assert result == {"query": {"ok": True}}
    assert len(client.requests) == 2
    assert clock.time() >= 5


def test_does_not_retry_503_without_retry_signal() -> None:
    client = FakeHttpClient([response(503, json={"error": "backend timeout"})])
    requestor = make_requestor(client)

    with pytest.raises(MediaWikiUnretryableRequestError, match="HTTP 503"):
        requestor.get({"action": "query"})

    assert len(client.requests) == 1


def test_fails_after_bounded_retries() -> None:
    client = FakeHttpClient(
        [
            response(429, json={"error": "too many"}, headers={"Retry-After": "1"}),
            response(429, json={"error": "too many"}, headers={"Retry-After": "1"}),
            response(429, json={"error": "too many"}, headers={"Retry-After": "1"}),
            response(429, json={"error": "too many"}, headers={"Retry-After": "1"}),
        ]
    )
    requestor = make_requestor(client)

    with pytest.raises(MediaWikiRetryableRequestError, match="exhausted retries"):
        requestor.get({"action": "query"})

    assert len(client.requests) == 4
