"""Shared MediaWiki API request policy and retry handling."""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol, cast

import httpx

from erenshor.infrastructure.time import Clock, RealClock

JsonObject = dict[str, Any]

# The answers of a file server that a download retries.
_TRANSIENT_DOWNLOAD_STATUSES = frozenset({429, 502, 503, 504})

# The API actions that only read, which a dropped connection can safely repeat.
_READ_ACTIONS = frozenset({"query", "parse", "expandtemplates", "compare", "opensearch", "cargoquery"})


class MediaWikiRequestError(RuntimeError):
    """Base error for MediaWiki request policy failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        info: str | None = None,
        attempts: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.info = info
        self.attempts = attempts


class MediaWikiRetryableRequestError(MediaWikiRequestError):
    """Raised when retryable MediaWiki failures exhaust bounded retries."""


class MediaWikiUnretryableRequestError(MediaWikiRequestError):
    """Raised when a MediaWiki request fails in a way that should not be retried."""


@dataclass(frozen=True, slots=True)
class RateLimit:
    """Maximum action requests allowed within a period."""

    hits: int
    seconds: int

    def __post_init__(self) -> None:
        if self.hits <= 0 or self.seconds <= 0:
            raise ValueError("Rate-limit hits and seconds must be positive")


@dataclass(frozen=True)
class MediaWikiDownload:
    """Binary response downloaded through the shared MediaWiki session."""

    status_code: int
    content_type: str
    content: bytes


@dataclass(frozen=True)
class MediaWikiRequestPolicy:
    """Retry settings for non-interactive MediaWiki jobs."""

    user_agent: str = "ErenshorWikiBot/0.4 (https://erenshor.wiki.gg) httpx"
    maxlag: int = 5
    max_retries: int = 6
    base_backoff: float = 5.0
    max_backoff: float = 120.0
    jitter: float = 0.25


class _ResponseLike(Protocol):
    status_code: int
    headers: Mapping[str, str]
    text: str
    content: bytes

    def json(self) -> JsonObject: ...


class _ClientLike(Protocol):
    def get(self, url: str, *, params: dict[str, str] | None = None) -> _ResponseLike: ...

    def post(self, url: str, *, params: dict[str, str], data: dict[str, str] | None = None) -> _ResponseLike: ...

    def close(self) -> None: ...


class _MultipartClientLike(Protocol):
    def post(
        self,
        url: str,
        *,
        params: dict[str, str],
        data: dict[str, Any] | None = None,
        files: Mapping[str, Any],
    ) -> _ResponseLike: ...


class MediaWikiRequestor:
    """Small MediaWiki Action API requester with shared bot etiquette."""

    def __init__(
        self,
        *,
        api_url: str,
        policy: MediaWikiRequestPolicy | None = None,
        http_client: _ClientLike | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
        user_agent: str | None = None,
        formatversion: str | None = "2",
        clock: Clock | None = None,
    ) -> None:
        if http_client is not None and transport is not None:
            raise ValueError("transport and http_client are mutually exclusive")
        self.api_url = api_url
        self.policy = policy or MediaWikiRequestPolicy()
        self.clock = clock or RealClock()
        self._rate_limits: dict[str, RateLimit] = {}
        self._last_action_time: dict[str, float] = {}
        self._lock = Lock()
        self._formatversion = formatversion
        self._http_client: _ClientLike
        if http_client is None:
            self._http_client = cast(
                "_ClientLike",
                httpx.Client(
                    timeout=timeout,
                    headers={"User-Agent": user_agent or self.policy.user_agent},
                    transport=transport,
                ),
            )
            self._owns_http_client = True
        else:
            self._http_client = http_client
            self._owns_http_client = False
        self._closed = False

    def set_rate_limits(self, limits: Mapping[str, RateLimit]) -> None:
        """Install the account's current per-action limits."""
        with self._lock:
            self._rate_limits = dict(limits)
            self._last_action_time.clear()

    def close(self) -> None:
        """Close the owned HTTP client exactly once."""
        if self._owns_http_client and not self._closed:
            self._http_client.close()
        self._closed = True

    def get(
        self,
        params: Mapping[str, str],
        *,
        noninteractive: bool = True,
    ) -> JsonObject:
        """Run a GET request under the shared MediaWiki policy."""
        return self._request("GET", params=params, data=None, noninteractive=noninteractive)

    def post(
        self,
        params: Mapping[str, str],
        *,
        data: Mapping[str, str] | None = None,
        noninteractive: bool = True,
    ) -> JsonObject:
        """Run a POST request under the shared MediaWiki policy."""
        request_data = dict(data) if data is not None else None
        return self._request("POST", params=params, data=request_data, noninteractive=noninteractive)

    def post_files(
        self,
        params: Mapping[str, str],
        *,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any],
        noninteractive: bool = True,
    ) -> JsonObject:
        """Run a multipart POST request under the shared MediaWiki policy."""
        request_data = dict(data) if data is not None else None
        return self._request(
            "POST",
            params=params,
            data=request_data,
            files=files,
            noninteractive=noninteractive,
        )

    def download(self, url: str) -> MediaWikiDownload:
        """Download bytes through the owned HTTP session.

        A file server answers overload with 429 or a bare 502, 503, or 504, so
        a download retries those with the policy's backoff, or after the
        ``Retry-After`` that the server names, and a dropped connection with
        the backoff. The last answer is returned.
        """
        with self._lock:
            for attempt in range(self.policy.max_retries + 1):
                try:
                    # The URL's query carries the file's SHA-1 prefix, which
                    # makes the file server's cache serve the current version.
                    response = self._http_client.get(url)
                except httpx.TransportError:
                    if attempt == self.policy.max_retries:
                        raise
                    self.clock.sleep(_backoff_delay(attempt, self.policy))
                    continue
                if response.status_code not in _TRANSIENT_DOWNLOAD_STATUSES or attempt == self.policy.max_retries:
                    break
                self.clock.sleep(_retry_after_or_backoff(response.headers, attempt, self.policy))
        return MediaWikiDownload(
            status_code=response.status_code,
            content_type=response.headers.get("content-type", ""),
            content=response.content,
        )

    def _request(
        self,
        method: str,
        *,
        params: Mapping[str, str],
        data: dict[str, Any] | None,
        files: Mapping[str, Any] | None = None,
        noninteractive: bool,
    ) -> JsonObject:
        request_params = self._params(params, noninteractive=noninteractive)
        with self._lock:
            return self._send_with_retries(method, request_params, data, files)

    def _send_with_retries(
        self,
        method: str,
        request_params: dict[str, str],
        data: dict[str, Any] | None,
        files: Mapping[str, Any] | None,
    ) -> JsonObject:
        action = data.get("action", request_params.get("action")) if data is not None else request_params.get("action")
        file_positions = _capture_file_positions(files)
        for attempt in range(self.policy.max_retries + 1):
            _restore_file_positions(file_positions)
            self._pace(action)
            try:
                response = self._send(method, request_params, data, files)
            except httpx.TransportError:
                # A dropped connection loses no write only for a request that
                # writes nothing, so only reads are sent again.
                if action not in _READ_ACTIONS or attempt == self.policy.max_retries:
                    raise
                self.clock.sleep(_backoff_delay(attempt, self.policy))
                continue
            retry_delay = self._retry_delay(response, attempt)
            if retry_delay is not None:
                if attempt == self.policy.max_retries:
                    raise MediaWikiRetryableRequestError(
                        "MediaWiki request exhausted retries",
                        status_code=response.status_code,
                        attempts=attempt + 1,
                    )
                self.clock.sleep(retry_delay)
                continue
            try:
                payload = response.json()
                json_error: Exception | None = None
            except Exception as error:
                # A transient response may carry its retry signal outside JSON.
                # Preserve that retry before surfacing a parse or HTTP failure.
                payload = {}
                json_error = error
            api_retry_delay = self._api_retry_delay(payload, response, attempt)
            if api_retry_delay is not None:
                if attempt == self.policy.max_retries:
                    raise MediaWikiRetryableRequestError(
                        "MediaWiki API request exhausted retries", attempts=attempt + 1
                    )
                self.clock.sleep(api_retry_delay)
                continue
            if 500 <= response.status_code < 600:
                raise MediaWikiUnretryableRequestError(
                    f"HTTP {response.status_code} from MediaWiki API", status_code=response.status_code
                )
            if response.status_code >= 400:
                raise MediaWikiUnretryableRequestError(
                    f"HTTP {response.status_code} from MediaWiki API", status_code=response.status_code
                )
            if "error" in payload:
                error_payload = cast("dict[str, object]", payload["error"])
                code = str(error_payload.get("code", "unknown"))
                info = str(error_payload.get("info", "unknown MediaWiki API error"))
                raise MediaWikiUnretryableRequestError(f"MediaWiki API error ({code}): {info}", code=code, info=info)
            if json_error is not None:
                raise json_error
            return payload
        raise AssertionError("unreachable")

    def _send(
        self,
        method: str,
        params: dict[str, str],
        data: dict[str, Any] | None,
        files: Mapping[str, Any] | None = None,
    ) -> _ResponseLike:
        if method == "GET":
            return self._http_client.get(self.api_url, params=params)
        if files is None:
            return self._http_client.post(self.api_url, params=params, data=data)
        return cast("_MultipartClientLike", self._http_client).post(self.api_url, params=params, data=data, files=files)

    def _params(self, params: Mapping[str, str], *, noninteractive: bool) -> dict[str, str]:
        request_params = dict(params)
        request_params.setdefault("format", "json")
        if self._formatversion is not None:
            request_params.setdefault("formatversion", self._formatversion)
        if noninteractive:
            request_params.setdefault("maxlag", str(self.policy.maxlag))
        return request_params

    def _pace(self, action: str | None) -> None:
        if action is None or (limit := self._rate_limits.get(action)) is None:
            return
        now = self.clock.time()
        last = self._last_action_time.get(action)
        if last is not None:
            interval = limit.seconds / limit.hits * 1.1
            if now - last < interval:
                self.clock.sleep(interval - (now - last))
                now = self.clock.time()
        self._last_action_time[action] = now

    def _retry_delay(self, response: _ResponseLike, attempt: int) -> float | None:
        return retry_delay_for(
            status_code=response.status_code,
            headers=response.headers,
            payload={},
            text=response.text,
            attempt=attempt,
            policy=self.policy,
        )

    def _api_retry_delay(self, payload: JsonObject, response: _ResponseLike, attempt: int) -> float | None:
        return retry_delay_for(
            status_code=200,
            headers=response.headers,
            payload=payload,
            text=response.text,
            attempt=attempt,
            policy=self.policy,
        )


def _capture_file_positions(files: Mapping[str, Any] | None) -> list[tuple[Any, int]]:
    if files is None:
        return []
    positions: list[tuple[Any, int]] = []
    for value in files.values():
        stream = value[1] if isinstance(value, tuple) and len(value) > 1 else value
        try:
            positions.append((stream, stream.tell()))
        except (AttributeError, OSError):
            continue
    return positions


def _restore_file_positions(positions: list[tuple[Any, int]]) -> None:
    for stream, position in positions:
        try:
            stream.seek(position)
        except (AttributeError, OSError):
            continue


def retry_delay_for(
    *,
    status_code: int,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    text: str,
    attempt: int,
    policy: MediaWikiRequestPolicy,
) -> float | None:
    """Return the bounded wait before retrying a MediaWiki response, or None.
    Honors transport rate limiting (HTTP 429, lagging 503) and Action API
    soft failures (``maxlag``, ``ratelimited``) per MediaWiki bot etiquette.
    Returns None when the response is not retryable.
    """
    if status_code == 429:
        return _retry_after_or_backoff(headers, attempt, policy)
    if status_code == 503 and _has_retry_signal(headers, text):
        return _retry_after_or_backoff(headers, attempt, policy)
    error = payload.get("error")
    if isinstance(error, dict):
        code = str(error.get("code", ""))
        if code == "maxlag":
            return _retry_after_or_lag(headers, error, attempt, policy)
        if code == "ratelimited":
            return _retry_after_or_backoff(headers, attempt, policy)
    return None


def _retry_after_or_lag(
    headers: Mapping[str, str], error: Mapping[object, object], attempt: int, policy: MediaWikiRequestPolicy
) -> float:
    retry_after = _retry_after_header(headers)
    if retry_after is not None:
        return retry_after
    lag = error.get("lag")
    if isinstance(lag, int | float):
        return max(5.0, float(lag))
    return _backoff_delay(attempt, policy)


def _retry_after_or_backoff(headers: Mapping[str, str], attempt: int, policy: MediaWikiRequestPolicy) -> float:
    retry_after = _retry_after_header(headers)
    if retry_after is not None:
        return retry_after
    return _backoff_delay(attempt, policy)


def _backoff_delay(attempt: int, policy: MediaWikiRequestPolicy) -> float:
    delay = float(min(policy.max_backoff, policy.base_backoff * (2**attempt)))
    if policy.jitter <= 0:
        return delay
    return delay + float(random.uniform(0, policy.jitter))


def _retry_after_header(headers: Mapping[str, str]) -> float | None:
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _has_retry_signal(headers: Mapping[str, str], text: str) -> bool:
    if headers.get("Retry-After") is not None:
        return True
    if headers.get("X-Database-Lag") is not None:
        return True
    return "Waiting for" in text
