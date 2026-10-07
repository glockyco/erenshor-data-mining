"""Async client for the HotRepl v2 control plane."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import suppress
from typing import Any, cast

import websockets
from websockets.exceptions import WebSocketException

from .artifacts import Artifact, ArtifactPathResolver

DEFAULT_URL = "ws://localhost:18590"
CLIENT_TIMEOUT_S = 30.0


class EvalError(Exception):
    """A v2 error envelope, retaining the original response for JSON consumers."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.envelope: dict[str, Any] = response["error"]
        self.kind: str = self.envelope["kind"]
        self.code: str = self.envelope["code"]
        self.message: str = self.envelope["message"]
        self.retryable: bool = self.envelope["retryable"]
        self.details: Any = self.envelope.get("details")
        super().__init__(f"{self.kind}/{self.code}: {self.message}")


class EvalConnectionError(Exception):
    """The connection is unavailable or does not speak protocol v2."""


class EvalClient:
    """Multiplex requests and subscriptions on one v2 connection.

    Notifications are retained in ``notifications`` and optionally delivered to
    ``on_notification``. Catalogs/descriptors are not cached, so assembly reloads
    cannot leave callers with stale command schemas.
    """

    def __init__(
        self,
        url: str = DEFAULT_URL,
        *,
        resolve_artifact_path: ArtifactPathResolver | None = None,
        on_notification: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.url = url
        self.resolve_artifact_path = resolve_artifact_path
        self.on_notification = on_notification
        self.handshake: dict[str, Any] | None = None
        self.handshake_ms = 0.0
        self.notifications: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._ws: websockets.ClientConnection | None = None
        self._reader: asyncio.Task[None] | None = None
        self._pending: dict[str, asyncio.Queue[dict[str, Any] | Exception]] = {}
        self._failure: Exception | None = None
        self._counter = 0

    async def connect(self) -> dict[str, Any]:
        """Connect and validate the initial handshake; retain all capabilities."""
        await self.close()
        self._failure = None
        self.handshake = None
        started = time.perf_counter()
        try:
            self._ws = await asyncio.wait_for(websockets.connect(self.url), CLIENT_TIMEOUT_S)
            raw = await asyncio.wait_for(self._ws.recv(), CLIENT_TIMEOUT_S)
            handshake = json.loads(raw)
            if not isinstance(handshake, dict) or handshake.get("type") != "handshake":
                raise EvalConnectionError("HotRepl did not send a handshake")
            if handshake.get("protocolVersion") != 2:
                raise EvalConnectionError(
                    f"HotRepl protocol version {handshake.get('protocolVersion')!r} is unsupported; expected 2"
                )
            self.handshake = handshake
            self.handshake_ms = (time.perf_counter() - started) * 1000
            self._reader = asyncio.create_task(self._read_messages())
            return handshake
        except (OSError, WebSocketException, TimeoutError, ValueError) as exc:
            await self.close()
            raise EvalConnectionError(f"Cannot connect to HotRepl: {exc}") from exc
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        if self._reader is not None:
            self._reader.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader
            self._reader = None

    async def ping(self) -> float:
        """Measure connection plus handshake latency; v2 has no ping message."""
        await self.connect()
        return self.handshake_ms

    async def eval(self, code: str, timeout_ms: int = 10000) -> dict[str, Any]:
        return await self._request(
            "eval", {"code": code, "timeoutMs": timeout_ms}, {"eval_result"}, timeout=timeout_ms / 1000 + 2
        )

    async def reset(self) -> dict[str, Any]:
        response = await self._request("reset", {}, {"reset_result"})
        if not response["success"]:
            raise EvalConnectionError("HotRepl reset_result reported success=false")
        return response

    async def cancel(self, target_id: str) -> None:
        await self._send({"type": "cancel", "id": self._next_id(), "targetId": target_id})

    async def complete(self, code: str, cursor_pos: int = -1) -> list[str]:
        fields: dict[str, Any] = {"code": code}
        if cursor_pos >= 0:
            fields["cursor"] = cursor_pos
        response = await self._request("complete", fields, {"complete_result"})
        return cast("list[str]", response["completions"])

    async def subscribe(
        self,
        code: str,
        *,
        interval_frames: int = 1,
        on_change: bool = False,
        limit: int = 0,
        timeout_ms: int = 10000,
    ) -> AsyncGenerator[dict[str, Any]]:
        msg_id = self._next_id()
        queue: asyncio.Queue[dict[str, Any] | Exception] = asyncio.Queue()
        self._pending[msg_id] = queue
        final = False
        try:
            await self._send(
                {
                    "type": "subscribe",
                    "id": msg_id,
                    "code": code,
                    "intervalFrames": interval_frames,
                    "onChange": on_change,
                    "limit": limit,
                    "timeoutMs": timeout_ms,
                }
            )
            while not final:
                response = await self._receive(queue, CLIENT_TIMEOUT_S)
                final = response.get("final", False)
                self._check_error(response)
                self._expect(response, {"subscribe_result"})
                yield response
        finally:
            self._pending.pop(msg_id, None)
            if not final and self._ws is not None and self._failure is None:
                await self.cancel(msg_id)

    async def commands(self) -> dict[str, Any]:
        return await self._request("commands_list", {}, {"commands_list_result"})

    async def describe(self, name: str) -> dict[str, Any]:
        return await self._request("command_describe", {"name": name}, {"command_describe_result"})

    async def journal(self, *, kind: str | None = None, limit: int = 20) -> dict[str, Any]:
        fields: dict[str, Any] = {"limit": limit}
        if kind is not None:
            fields["kind"] = kind
        return await self._request("journal_query", fields, {"journal_query_result"})

    async def job_status(self, job_id: str, *, timeout: float = CLIENT_TIMEOUT_S) -> dict[str, Any]:
        return await self._request(
            "job_status", {"jobId": job_id}, {"job_status_result", "job_result"}, timeout=timeout
        )

    async def job_cancel(self, job_id: str) -> dict[str, Any]:
        return await self._request("job_cancel", {"jobId": job_id}, {"job_cancel_result"})

    async def call(
        self, name: str, args: dict[str, Any], *, timeout_ms: int = 30000, poll_interval: float = 0.25
    ) -> dict[str, Any]:
        """Run sync or job commands; cancel accepted jobs on timeout/Ctrl-C.

        ``timeout_ms`` is an overall client deadline as well as the command's
        server timeout. Terminal artifact references are verified before return.
        """
        deadline = time.monotonic() + timeout_ms / 1000
        response = await self._request(
            "command_call",
            {"name": name, "args": args, "timeoutMs": timeout_ms},
            {"command_result", "job_accepted"},
            timeout=timeout_ms / 1000 + 2,
        )
        if response["type"] == "job_accepted":
            job_id = response["jobId"]
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError(f"Timed out waiting for job {job_id}")
                    response = await self.job_status(job_id, timeout=min(CLIENT_TIMEOUT_S, remaining))
                    if response["type"] == "job_result":
                        break
                    await asyncio.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
            except (asyncio.CancelledError, KeyboardInterrupt, TimeoutError):
                await asyncio.shield(self.job_cancel(job_id))
                raise
        for reference in response["artifacts"].values():
            self.artifact(reference).verify()
        return response

    def artifact(self, reference: dict[str, Any]) -> Artifact:
        return Artifact(reference, self.resolve_artifact_path)

    def _next_id(self) -> str:
        self._counter += 1
        return f"cli-{self._counter}"

    async def _send(self, payload: dict[str, Any]) -> None:
        if self._failure is not None:
            raise self._failure
        if self._ws is None:
            raise EvalConnectionError("Connect to HotRepl before sending requests")
        try:
            await self._ws.send(json.dumps(payload))
        except WebSocketException as exc:
            raise EvalConnectionError(f"HotRepl disconnected: {exc}") from exc

    async def _request(
        self, message_type: str, fields: dict[str, Any], expected: set[str], *, timeout: float = CLIENT_TIMEOUT_S
    ) -> dict[str, Any]:
        msg_id = self._next_id()
        queue: asyncio.Queue[dict[str, Any] | Exception] = asyncio.Queue()
        self._pending[msg_id] = queue
        try:
            await self._send({"type": message_type, "id": msg_id, **fields})
            response = await self._receive(queue, timeout)
            self._check_error(response)
            self._expect(response, expected)
            return response
        except (asyncio.CancelledError, TimeoutError):
            if message_type == "eval" and self._ws is not None and self._failure is None:
                await self.cancel(msg_id)
            raise
        finally:
            self._pending.pop(msg_id, None)

    @staticmethod
    async def _receive(queue: asyncio.Queue[dict[str, Any] | Exception], timeout: float) -> dict[str, Any]:
        response = await asyncio.wait_for(queue.get(), timeout)
        if isinstance(response, Exception):
            raise response
        return response

    @staticmethod
    def _check_error(response: dict[str, Any]) -> None:
        if "error" in response:
            raise EvalError(response)
        if response.get("status") == "failed":
            raise EvalConnectionError(f"Malformed {response['type']}: failed without a v2 error envelope")

    @staticmethod
    def _expect(response: dict[str, Any], expected: set[str]) -> None:
        if response.get("type") not in expected:
            raise EvalConnectionError(
                f"Unexpected HotRepl response {response.get('type')!r}; expected {sorted(expected)}"
            )

    async def _read_messages(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                response = json.loads(raw)
                message_type = response.get("type")
                if message_type in {"session_evicted", "assembly_reload"}:
                    self.notifications.put_nowait(response)
                    if self.on_notification is not None:
                        self.on_notification(response)
                    if message_type == "session_evicted":
                        by = response.get("by", {}).get("clientName")
                        suffix = f" (by {by})" if by else ""
                        raise EvalConnectionError(f"HotRepl session evicted: {response['reason']}{suffix}")
                elif response.get("id") in self._pending:
                    self._pending[response["id"]].put_nowait(response)
                elif message_type == "error" and "id" not in response:
                    raise EvalError(response)
            raise EvalConnectionError("HotRepl connection closed")
        except (WebSocketException, ValueError, EvalConnectionError, EvalError) as exc:
            self._failure = exc if isinstance(exc, (EvalConnectionError, EvalError)) else EvalConnectionError(str(exc))
            for queue in self._pending.values():
                queue.put_nowait(self._failure)
