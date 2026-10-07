from __future__ import annotations

import httpx
import pytest

from erenshor.infrastructure.time import MockClock
from erenshor.infrastructure.wiki.rate_limit import (
    MediaWikiRequestor,
    MediaWikiRequestPolicy,
    MediaWikiRetryableRequestError,
    MediaWikiUnretryableRequestError,
    RateLimit,
)


class FakeHttpClient:
    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self._responses = responses
        self.requests: list[tuple[str, dict[str, str], dict[str, str] | None]] = []
        self.times: list[float] = []
        self.clock: MockClock | None = None

    def get(self, url: str, *, params: dict[str, str] | None = None) -> httpx.Response:
        if self.clock is not None:
            self.times.append(self.clock.time())
        self.requests.append(("GET", params or {}, None))
        return self._pop_response()

    def post(self, url: str, *, params: dict[str, str], data: dict[str, str] | None = None) -> httpx.Response:
        self.requests.append(("POST", params, data))
        if self.clock is not None:
            self.times.append(self.clock.time())
        return self._pop_response()

    def close(self) -> None:
        pass

    def _pop_response(self) -> httpx.Response:
        if not self._responses:
            raise AssertionError("unexpected HTTP request")
        answer = self._responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


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
    active_clock = clock if clock is not None else MockClock()
    client.clock = active_clock
    return MediaWikiRequestor(
        api_url="https://erenshor.wiki.gg/api.php",
        http_client=client,
        clock=active_clock,
        policy=MediaWikiRequestPolicy(max_retries=3, jitter=0.0),
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


def test_a_download_asks_for_the_exact_url_with_its_cache_busting_query() -> None:
    # The query names the file's current SHA-1 prefix; without it the file
    # server's cache may answer with an earlier version of the file.
    urls: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, content=b"image-bytes", headers={"Content-Type": "image/png"})

    requestor = MediaWikiRequestor(
        api_url="https://erenshor.wiki.gg/api.php", transport=httpx.MockTransport(answer), clock=MockClock()
    )

    result = requestor.download("https://erenshor.wiki.gg/images/Shadow_of_Brax.png?59f0b7")

    assert (result.status_code, result.content_type, result.content) == (200, "image/png", b"image-bytes")
    assert urls == ["https://erenshor.wiki.gg/images/Shadow_of_Brax.png?59f0b7"]


def _image_response(status_code: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=b"image-bytes" if status_code == 200 else b"<html>busy</html>",
        headers=headers,
        request=httpx.Request("GET", "https://erenshor.wiki.gg/images/logo.png"),
    )


def test_a_download_waits_out_an_overloaded_file_server() -> None:
    clock = MockClock()
    client = FakeHttpClient([_image_response(503), _image_response(429, {"Retry-After": "30"}), _image_response(200)])
    requestor = make_requestor(client, clock)

    result = requestor.download("https://erenshor.wiki.gg/images/logo.png")

    assert result.content == b"image-bytes"
    assert [later - earlier for earlier, later in zip(client.times, client.times[1:], strict=False)] == [5.0, 30.0]


def test_a_download_returns_the_last_answer_when_the_server_stays_unavailable() -> None:
    client = FakeHttpClient([_image_response(503) for _ in range(4)])
    requestor = make_requestor(client)

    assert requestor.download("https://erenshor.wiki.gg/images/logo.png").status_code == 503
    assert len(client.requests) == 4


def test_a_download_does_not_retry_a_missing_file() -> None:
    client = FakeHttpClient([_image_response(404)])
    requestor = make_requestor(client)

    assert requestor.download("https://erenshor.wiki.gg/images/logo.png").status_code == 404


def test_a_dropped_connection_repeats_a_read() -> None:
    client = FakeHttpClient([httpx.ReadError("Connection reset by peer"), response()])
    requestor = make_requestor(client)

    assert requestor.post({"action": "parse"}, data={"action": "parse", "text": "x"}) == {"query": {}}
    assert len(client.requests) == 2


def test_a_dropped_connection_does_not_repeat_a_write() -> None:
    client = FakeHttpClient([httpx.ReadError("Connection reset by peer"), response()])
    requestor = make_requestor(client)

    with pytest.raises(httpx.ReadError):
        requestor.post({"action": "edit"}, data={"action": "edit", "text": "x"})
    assert len(client.requests) == 1


@pytest.mark.parametrize(("action", "attempts"), [("query", 2), ("edit", 1)])
def test_a_gateway_error_repeats_a_read_but_not_a_write(action: str, attempts: int) -> None:
    client = FakeHttpClient([response(502, json={}), response()])
    requestor = make_requestor(client)

    try:
        result = requestor.post({"action": action}, data={"action": action})
    except MediaWikiUnretryableRequestError:
        result = None

    assert len(client.requests) == attempts
    assert result == ({"query": {}} if action == "query" else None)


def test_a_download_repeats_after_a_dropped_connection() -> None:
    client = FakeHttpClient([httpx.ReadError("Connection reset by peer"), _image_response(200)])
    requestor = make_requestor(client)

    assert requestor.download("https://erenshor.wiki.gg/images/logo.png").content == b"image-bytes"


def test_omits_maxlag_for_interactive_requests() -> None:
    client = FakeHttpClient([response()])
    requestor = make_requestor(client)

    requestor.get({"action": "query"}, noninteractive=False)

    assert client.requests[0][1] == {"action": "query", "format": "json", "formatversion": "2"}


def test_edits_use_reported_action_spacing_without_delaying_other_actions() -> None:
    clock = MockClock()
    client = FakeHttpClient([response() for _ in range(6)])
    requestor = make_requestor(client, clock)
    requestor.set_rate_limits({"edit": RateLimit(90, 60), "purge": RateLimit(30, 60)})

    requestor.post({}, data={"action": "edit"})
    requestor.get({"action": "query"})
    requestor.get({"action": "query"})
    requestor.post({}, data={"action": "parse"})
    requestor.post({"action": "purge"})
    requestor.post({}, data={"action": "edit"})

    assert client.times[0:5] == [client.times[0]] * 5
    assert client.times[5] - client.times[0] >= 60 / 90 * 1.1
    assert client.times[5] - client.times[0] < 0.734


def test_unlimited_account_actions_never_wait() -> None:
    clock = MockClock()
    client = FakeHttpClient([response(), response()])
    requestor = make_requestor(client, clock)
    requestor.set_rate_limits({})

    requestor.post({}, data={"action": "edit"})
    requestor.post({}, data={"action": "edit"})

    assert client.times[1] == client.times[0]


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
            response(json={"edit": {"result": "Success"}}),
        ]
    )
    requestor = make_requestor(client, clock)
    requestor.set_rate_limits({"edit": RateLimit(90, 60)})

    result = requestor.post({}, data={"action": "edit"})

    assert result == {"edit": {"result": "Success"}}
    assert len(client.requests) == 2
    assert client.times[1] - client.times[0] >= 5


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
