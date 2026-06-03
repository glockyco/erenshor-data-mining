"""Shared MediaWiki API request policy and retry handling."""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, cast

import httpx

from erenshor.infrastructure.time import Clock, RealClock

JsonObject = dict[str, Any]


class MediaWikiRequestError(RuntimeError):
    """Base error for MediaWiki request policy failures."""


class MediaWikiRetryableRequestError(MediaWikiRequestError):
    """Raised when retryable MediaWiki failures exhaust bounded retries."""


class MediaWikiUnretryableRequestError(MediaWikiRequestError):
    """Raised when a MediaWiki request fails in a way that should not be retried."""


class RequestKind(StrEnum):
    """Request pacing class."""

    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class MediaWikiRequestPolicy:
    """Rate-limit and retry settings for non-interactive MediaWiki jobs."""

    user_agent: str = "ErenshorWikiBot/0.4 (https://erenshor.wiki.gg) httpx"
    maxlag: int = 5
    read_delay: float = 1.0
    write_delay: float = 1.0
    max_retries: int = 6
    base_backoff: float = 5.0
    max_backoff: float = 120.0
    jitter: float = 0.25


class _ResponseLike(Protocol):
    status_code: int
    headers: Mapping[str, str]
    text: str

    def json(self) -> JsonObject: ...


class _ClientLike(Protocol):
    def get(self, url: str, *, params: dict[str, str]) -> _ResponseLike: ...

    def post(self, url: str, *, params: dict[str, str], data: dict[str, str] | None = None) -> _ResponseLike: ...

    def close(self) -> None: ...


class MediaWikiRequestor:
    """Small MediaWiki Action API requester with shared bot etiquette."""

    def __init__(
        self,
        *,
        api_url: str,
        policy: MediaWikiRequestPolicy | None = None,
        http_client: _ClientLike | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.api_url = api_url
        self.policy = policy or MediaWikiRequestPolicy()
        self.clock = clock or RealClock()
        self._last_request_time: float | None = None
        self._http_client: _ClientLike
        if http_client is None:
            self._http_client = cast(
                "_ClientLike",
                httpx.Client(timeout=30, headers={"User-Agent": self.policy.user_agent}),
            )
            self._owns_http_client = True
        else:
            self._http_client = http_client
            self._owns_http_client = False

    def close(self) -> None:
        """Close the owned HTTP client."""
        if self._owns_http_client:
            self._http_client.close()

    def get(
        self,
        params: Mapping[str, str],
        *,
        kind: RequestKind = RequestKind.READ,
        noninteractive: bool = True,
    ) -> JsonObject:
        """Run a GET request under the shared MediaWiki policy."""
        return self._request("GET", params=params, data=None, kind=kind, noninteractive=noninteractive)

    def post(
        self,
        params: Mapping[str, str],
        *,
        data: Mapping[str, str] | None = None,
        kind: RequestKind = RequestKind.WRITE,
        noninteractive: bool = True,
    ) -> JsonObject:
        """Run a POST request under the shared MediaWiki policy."""
        request_data = dict(data) if data is not None else None
        return self._request("POST", params=params, data=request_data, kind=kind, noninteractive=noninteractive)

    def _request(
        self,
        method: str,
        *,
        params: Mapping[str, str],
        data: dict[str, str] | None,
        kind: RequestKind,
        noninteractive: bool,
    ) -> JsonObject:
        request_params = self._params(params, noninteractive=noninteractive)
        for attempt in range(self.policy.max_retries + 1):
            self._pace(kind)
            response = self._send(method, request_params, data)
            retry_delay = self._retry_delay(response, attempt)
            if retry_delay is not None:
                if attempt == self.policy.max_retries:
                    raise MediaWikiRetryableRequestError("MediaWiki request exhausted retries")
                self.clock.sleep(retry_delay)
                continue
            if 500 <= response.status_code < 600:
                raise MediaWikiUnretryableRequestError(f"HTTP {response.status_code} from MediaWiki API")
            if response.status_code >= 400:
                raise MediaWikiUnretryableRequestError(f"HTTP {response.status_code} from MediaWiki API")
            payload = response.json()
            api_retry_delay = self._api_retry_delay(payload, response, attempt)
            if api_retry_delay is not None:
                if attempt == self.policy.max_retries:
                    raise MediaWikiRetryableRequestError("MediaWiki API request exhausted retries")
                self.clock.sleep(api_retry_delay)
                continue
            if "error" in payload:
                error = cast("dict[str, object]", payload["error"])
                code = str(error.get("code", "unknown"))
                info = str(error.get("info", "unknown MediaWiki API error"))
                raise MediaWikiUnretryableRequestError(f"MediaWiki API error ({code}): {info}")
            return payload
        raise AssertionError("unreachable")

    def _send(self, method: str, params: dict[str, str], data: dict[str, str] | None) -> _ResponseLike:
        if method == "GET":
            return self._http_client.get(self.api_url, params=params)
        return self._http_client.post(self.api_url, params=params, data=data)

    def _params(self, params: Mapping[str, str], *, noninteractive: bool) -> dict[str, str]:
        request_params = dict(params)
        request_params.setdefault("format", "json")
        request_params.setdefault("formatversion", "2")
        if noninteractive:
            request_params.setdefault("maxlag", str(self.policy.maxlag))
        return request_params

    def _pace(self, kind: RequestKind) -> None:
        delay = self.policy.write_delay if kind is RequestKind.WRITE else self.policy.read_delay
        if delay <= 0:
            return
        now = self.clock.time()
        if self._last_request_time is not None:
            elapsed = now - self._last_request_time
            if elapsed < delay:
                self.clock.sleep(delay - elapsed)
        self._last_request_time = self.clock.time()

    def _retry_delay(self, response: _ResponseLike, attempt: int) -> float | None:
        if response.status_code == 429:
            return self._retry_after_or_backoff(response, attempt)
        if response.status_code == 503 and _has_retry_signal(response):
            return self._retry_after_or_backoff(response, attempt)
        return None

    def _api_retry_delay(self, payload: JsonObject, response: _ResponseLike, attempt: int) -> float | None:
        error = payload.get("error")
        if not isinstance(error, dict):
            return None
        code = str(error.get("code", ""))
        if code == "maxlag":
            return self._retry_after_or_lag(response, error, attempt)
        if code == "ratelimited":
            return self._retry_after_or_backoff(response, attempt)
        return None

    def _retry_after_or_lag(self, response: _ResponseLike, error: Mapping[object, object], attempt: int) -> float:
        retry_after = _retry_after(response)
        if retry_after is not None:
            return retry_after
        lag = error.get("lag")
        if isinstance(lag, int | float):
            return max(5.0, float(lag))
        return self._backoff(attempt)

    def _retry_after_or_backoff(self, response: _ResponseLike, attempt: int) -> float:
        retry_after = _retry_after(response)
        if retry_after is not None:
            return retry_after
        return self._backoff(attempt)

    def _backoff(self, attempt: int) -> float:
        delay = float(min(self.policy.max_backoff, self.policy.base_backoff * (2**attempt)))
        if self.policy.jitter <= 0:
            return delay
        return delay + float(random.uniform(0, self.policy.jitter))


def _retry_after(response: _ResponseLike) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _has_retry_signal(response: _ResponseLike) -> bool:
    if response.headers.get("Retry-After") is not None:
        return True
    if response.headers.get("X-Database-Lag") is not None:
        return True
    return "Waiting for" in response.text
