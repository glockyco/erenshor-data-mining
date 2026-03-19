"""WebSocket client for HotRepl eval protocol."""

from __future__ import annotations

import asyncio
import json
import time

import websockets
from loguru import logger

DEFAULT_URL = "ws://localhost:18590"
CLIENT_TIMEOUT_S = 30.0  # Hard ceiling on any single round-trip


class EvalError(Exception):
    """Raised when the server returns an eval_error response."""

    def __init__(self, message: str, error_kind: str, stack_trace: str | None = None):
        self.error_kind = error_kind
        self.stack_trace = stack_trace
        super().__init__(message)


class EvalConnectionError(Exception):
    """Raised when the client cannot reach the game."""


class EvalClient:
    """Async WebSocket client for HotRepl eval requests."""

    def __init__(self, url: str = DEFAULT_URL) -> None:
        self.url = url
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._counter = 0
        self.handshake: dict | None = None

    # -- lifecycle --

    async def connect(self) -> dict:
        """Open the WebSocket and consume the server handshake message."""
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(self.url),
                timeout=CLIENT_TIMEOUT_S,
            )
        except (OSError, ConnectionRefusedError) as exc:
            raise EvalConnectionError(
                "Game not running or HotRepl not loaded"
            ) from exc

        raw = await asyncio.wait_for(self._ws.recv(), timeout=CLIENT_TIMEOUT_S)
        self.handshake = json.loads(raw)
        logger.debug("HotRepl handshake: {}", self.handshake)
        return self.handshake

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    # -- commands --

    async def eval(self, code: str, timeout_ms: int = 10000) -> dict:
        """Send code for evaluation; returns the full response dict.

        Raises EvalError on eval_error responses and asyncio.TimeoutError
        if no response arrives within *timeout_ms* + a client-side margin.
        """
        msg_id = self._next_id()
        payload = {
            "type": "eval",
            "id": msg_id,
            "code": code,
            "timeout_ms": timeout_ms,
        }
        # Client-side timeout: server timeout + 2 s margin
        client_timeout = (timeout_ms / 1000) + 2.0
        return await self._request(payload, msg_id, timeout=client_timeout)

    async def reset(self) -> dict:
        """Reset the server-side REPL state."""
        msg_id = self._next_id()
        payload = {"type": "reset", "id": msg_id}
        return await self._request(payload, msg_id)

    async def ping(self) -> float:
        """Ping the server; returns round-trip time in milliseconds."""
        msg_id = self._next_id()
        payload = {"type": "ping", "id": msg_id}
        t0 = time.perf_counter()
        await self._request(payload, msg_id)
        return (time.perf_counter() - t0) * 1000

    async def cancel(self, eval_id: str) -> None:
        """Cancel a running eval by its id."""
        msg_id = self._next_id()
        payload = {"type": "cancel", "id": msg_id, "eval_id": eval_id}
        await self._request(payload, msg_id)

    # -- internals --

    def _next_id(self) -> str:
        self._counter += 1
        return f"cli-{self._counter}"

    async def _request(
        self, payload: dict, msg_id: str, *, timeout: float = CLIENT_TIMEOUT_S
    ) -> dict:
        """Send *payload* and wait for a response whose ``id`` matches *msg_id*."""
        assert self._ws is not None, "call connect() first"

        await self._ws.send(json.dumps(payload))
        logger.debug("-> {}", payload)

        # Consume messages until we get our id (server may send broadcasts).
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError(
                    f"Timed out waiting for response to {payload['type']}"
                )

            raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
            resp = json.loads(raw)
            logger.debug("<- {}", resp)

            if resp.get("id") == msg_id:
                if resp.get("type") == "eval_error":
                    raise EvalError(
                        message=resp.get("error", "unknown error"),
                        error_kind=resp.get("error_kind", "unknown"),
                        stack_trace=resp.get("stack_trace"),
                    )
                return resp

            # Not our message; keep waiting.
