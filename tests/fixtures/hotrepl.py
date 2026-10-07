"""In-process v2 server fixture using real WebSocket frames."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.server import ServerConnection, serve

HANDSHAKE: dict[str, Any] = {
    "type": "handshake",
    "protocolVersion": 2,
    "host": {"name": "BepInEx", "version": "test", "platform": "Unity Mono"},
    "evaluator": {
        "name": "Mono.CSharp",
        "languageVersion": "7.x",
        "persistentState": True,
        "supportsCompletion": True,
        "cancellation": "hardAbort",
    },
    "availableEvaluators": ["Mono.CSharp"],
    "defaultUsings": ["System"],
    "helpers": [],
    "control": {"supported": True, "commandsListChanged": False, "schemaValidation": True},
    "limits": {
        "maxMessageBytes": 4194304,
        "maxQueuedCommands": 32,
        "maxResultLength": 102400,
        "maxEnumerableElements": 100,
        "defaultEvalTimeoutMs": 10000,
        "maxJobConcurrency": 1,
    },
    "enforces": [
        "maxMessageBytes",
        "maxQueuedCommands",
        "maxResultLength",
        "maxEnumerableElements",
        "maxJobConcurrency",
    ],
}
ERROR: dict[str, Any] = {
    "kind": "validation_failed",
    "code": "badArgument",
    "message": "Invalid scene [Missing]",
    "retryable": False,
    "details": {"path": "/scene"},
}
Response = Callable[[dict[str, Any]], list[dict[str, Any]]]


@dataclass
class FakeHotRepl:
    url: str
    requests: list[dict[str, Any]] = field(default_factory=list)


@asynccontextmanager
async def hotrepl(response: Response, *, handshake: dict[str, Any] | None = None) -> AsyncIterator[FakeHotRepl]:
    requests: list[dict[str, Any]] = []

    async def handle(connection: ServerConnection) -> None:
        await connection.send(json.dumps(HANDSHAKE if handshake is None else handshake))
        async for raw in connection:
            request = json.loads(raw)
            requests.append(request)
            for frame in response(request):
                await connection.send(json.dumps(frame))

    async with serve(handle, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        yield FakeHotRepl(f"ws://127.0.0.1:{port}", requests)


def frame(request: dict[str, Any], message_type: str, **fields: Any) -> dict[str, Any]:
    return {"type": message_type, "id": request["id"], **fields}
