"""Consumer contracts exercised against an in-process v2 WebSocket server."""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import aclosing
from pathlib import Path
from typing import Any

import pytest
from tests.fixtures.hotrepl import ERROR, HANDSHAKE, frame, hotrepl

from erenshor.application.eval.artifacts import Artifact, ArtifactError, resolve_wine_artifact_path
from erenshor.application.eval.client import EvalClient, EvalConnectionError, EvalError


def test_native_results_completion_reset_catalog_and_journal() -> None:
    def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
        responses = {
            "eval": frame(request, "eval_result", hasValue=True, value={"items": [1, False, None]}, durationMs=1),
            "complete": frame(request, "complete_result", completions=["position"], durationMs=1),
            "reset": frame(request, "reset_result", success=True),
            "commands_list": frame(request, "commands_list_result", commands=[{"name": "unity.app.info"}]),
            "command_describe": frame(request, "command_describe_result", descriptor={"name": "unity.app.info"}),
            "journal_query": frame(request, "journal_query_result", entries=[{"kind": "eval", "success": True}]),
        }
        return [responses[request["type"]]]

    async def scenario() -> None:
        async with hotrepl(respond) as server:
            client = EvalClient(server.url)
            try:
                handshake = await client.connect()
                assert handshake == HANDSHAKE == client.handshake
                assert (await client.eval("Items()", timeout_ms=123))["value"] == {"items": [1, False, None]}
                assert await client.complete("Camera.main.") == ["position"]
                assert await client.complete("Camera.main.", 3) == ["position"]
                assert (await client.reset())["success"]
                assert (await client.commands())["commands"][0]["name"] == "unity.app.info"
                assert (await client.describe("unity.app.info"))["descriptor"]["name"] == "unity.app.info"
                assert (await client.journal(kind="eval", limit=7))["entries"][0]["success"]
            finally:
                await client.close()
            assert server.requests[0]["timeoutMs"] == 123
            assert "timeout_ms" not in server.requests[0]
            assert "cursor" not in server.requests[1] and "cursorPos" not in server.requests[1]
            assert server.requests[2]["cursor"] == 3
            assert server.requests[-1]["kind"] == "eval" and server.requests[-1]["limit"] == 7

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["eval", "subscribe", "command_call", "commands_list", "job_status"])
def test_all_error_envelopes_reach_consumers(operation: str) -> None:
    def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
        if request["type"] == "cancel":
            return []
        types = {"eval": "eval_error", "subscribe": "subscribe_error", "command_call": "command_result"}
        fields: dict[str, Any] = {"error": ERROR}
        if operation == "subscribe":
            fields.update(seq=1, final=True)
        if operation == "command_call":
            fields.update(status="failed", artifacts={}, durationMs=1)
        return [frame(request, types.get(operation, "error"), **fields)]

    async def scenario() -> None:
        async with hotrepl(respond) as server:
            client = EvalClient(server.url)
            await client.connect()
            try:
                with pytest.raises(EvalError) as error:
                    if operation == "eval":
                        await client.eval("bad")
                    elif operation == "subscribe":
                        async for _ in client.subscribe("bad"):
                            pytest.fail("An error must not be returned as a value")
                    elif operation == "command_call":
                        await client.call("bad", {})
                    elif operation == "commands_list":
                        await client.commands()
                    else:
                        await client.job_status("missing")
                assert str(error.value) == "validation_failed/badArgument: Invalid scene [Missing]"
                assert error.value.envelope == ERROR
                assert error.value.retryable is False
                assert error.value.details == {"path": "/scene"}
                assert "unknown error" not in str(error.value)
            finally:
                await client.close()

    asyncio.run(scenario())


def test_truncation_and_subscription_final_are_not_lost() -> None:
    def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
        fields = {"hasValue": True, "value": None, "truncated": True, "truncatedBytes": 250112, "durationMs": 1}
        if request["type"] == "eval":
            return [frame(request, "eval_result", **fields)]
        return [
            frame(request, "subscribe_result", seq=1, final=False, **fields),
            frame(request, "subscribe_result", seq=2, final=True, hasValue=True, value=False, durationMs=1),
        ]

    async def scenario() -> None:
        async with hotrepl(respond) as server:
            client = EvalClient(server.url)
            await client.connect()
            try:
                result = await client.eval("large")
                assert result["value"] is None and result["truncated"] and result["truncatedBytes"] == 250112
                ticks = [tick async for tick in client.subscribe("large", interval_frames=12, on_change=True, limit=2)]
                assert ticks[0]["truncatedBytes"] == 250112
                assert ticks[1]["value"] is False and ticks[1]["final"] is True
            finally:
                await client.close()
            assert [request["type"] for request in server.requests] == ["eval", "subscribe"]
            assert server.requests[1]["intervalFrames"] == 12 and server.requests[1]["onChange"] is True

    asyncio.run(scenario())


def test_stopping_subscription_sends_v2_cancel() -> None:
    def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
        if request["type"] == "subscribe":
            return [frame(request, "subscribe_result", seq=1, final=False, hasValue=True, value=1, durationMs=1)]
        return []

    async def scenario() -> None:
        async with hotrepl(respond) as server:
            client = EvalClient(server.url)
            await client.connect()
            try:
                async with aclosing(client.subscribe("counter")) as subscription:
                    assert (await anext(subscription))["value"] == 1
            finally:
                await client.close()
            subscription_request, cancel = server.requests
            assert cancel["type"] == "cancel"
            assert cancel["targetId"] == subscription_request["id"]
            assert cancel["id"] != subscription_request["id"]
            assert set(cancel) == {"type", "id", "targetId"}

    asyncio.run(scenario())


@pytest.mark.parametrize("stop", ["timeout", "interrupt"])
def test_job_cancellation_on_deadline_and_task_interrupt(stop: str) -> None:
    async def scenario() -> None:
        polled = asyncio.Event()

        def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
            if request["type"] == "command_call":
                return [frame(request, "job_accepted", jobId="job-1", state="running")]
            if request["type"] == "job_status":
                polled.set()
                return [frame(request, "job_status_result", jobId="job-1", state="running", progress={"count": 1})]
            return [frame(request, "job_cancel_result", jobId="job-1", accepted=True, state="running")]

        async with hotrepl(respond) as server:
            client = EvalClient(server.url)
            await client.connect()
            try:
                task = asyncio.create_task(client.call("export", {}, timeout_ms=50 if stop == "timeout" else 10000))
                await polled.wait()
                if stop == "interrupt":
                    task.cancel()
                with pytest.raises(TimeoutError if stop == "timeout" else asyncio.CancelledError):
                    await task
            finally:
                await client.close()
            assert server.requests[-1]["type"] == "job_cancel"
            assert server.requests[-1]["jobId"] == "job-1"
            assert all(request["type"] != "cancel" for request in server.requests)

    asyncio.run(scenario())


@pytest.mark.parametrize("failed", [False, True])
def test_job_polls_running_until_terminal_result(failed: bool) -> None:
    polls = 0

    def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
        nonlocal polls
        if request["type"] == "command_call":
            return [frame(request, "job_accepted", jobId="job-1", state="running")]
        polls += 1
        if polls == 1:
            return [frame(request, "job_status_result", jobId="job-1", state="running", progress=0.5)]
        fields: dict[str, Any] = {
            "jobId": "job-1",
            "state": "failed" if failed else "done",
            "status": "failed" if failed else "ok",
            "artifacts": {},
            "durationMs": 2,
        }
        fields.update({"error": ERROR} if failed else {"output": {"count": 4}})
        return [frame(request, "job_result", **fields)]

    async def scenario() -> None:
        async with hotrepl(respond) as server:
            client = EvalClient(server.url)
            await client.connect()
            try:
                if failed:
                    with pytest.raises(EvalError, match="validation_failed/badArgument"):
                        await client.call("export", {}, poll_interval=0)
                else:
                    result = await client.call("export", {}, poll_interval=0)
                    assert result["output"] == {"count": 4} and result["state"] == "done"
            finally:
                await client.close()
            assert [r["type"] for r in server.requests] == ["command_call", "job_status", "job_status"]
            assert server.requests[1]["jobId"] == "job-1"

    asyncio.run(scenario())


@pytest.mark.parametrize("mismatch", ["sha256", "byteSize", "finalized", None])
def test_command_artifacts_verified_before_return(tmp_path: Path, mismatch: str | None) -> None:
    data = b'{"count":2,"items":[1,2]}'
    path = tmp_path / "data.json"
    path.write_bytes(data)
    reference: dict[str, Any] = {
        "uri": path.as_uri(),
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "byteSize": len(data),
        "contentType": "application/json",
        "finalized": True,
    }
    if mismatch == "sha256":
        reference[mismatch] = "0" * 64
    elif mismatch == "byteSize":
        reference[mismatch] = 999
    elif mismatch == "finalized":
        reference[mismatch] = False

    async def scenario() -> None:
        def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
            return [
                frame(
                    request,
                    "command_result",
                    status="ok",
                    output={"count": 2},
                    artifacts={"data": reference},
                    durationMs=1,
                )
            ]

        async with hotrepl(respond) as server:
            client = EvalClient(server.url)
            await client.connect()
            try:
                if mismatch is not None:
                    with pytest.raises(ArtifactError):
                        await client.call("export", {})
                    with pytest.raises(ArtifactError):
                        client.artifact(reference).json()
                else:
                    result = await client.call("export", {})
                    assert client.artifact(result["artifacts"]["data"]).json() == {"count": 2, "items": [1, 2]}
            finally:
                await client.close()

    asyncio.run(scenario())


def test_wine_paths_open_real_bottle_artifacts(tmp_path: Path) -> None:
    bottle = tmp_path / "Steam"
    wine = r"C:\users\crossover\AppData\Local\HotRepl\artifacts\job-1\data.json"
    local = bottle / "drive_c/users/crossover/AppData/Local/HotRepl/artifacts/job-1/data.json"
    local.parent.mkdir(parents=True)
    local.write_bytes(b"[1,2]")
    reference = {
        "uri": "file:///C:/users/crossover/data.json",
        "path": wine,
        "sha256": hashlib.sha256(b"[1,2]").hexdigest(),
        "byteSize": 5,
        "finalized": True,
    }
    artifact = Artifact(reference, lambda ref: resolve_wine_artifact_path(ref["path"], bottle))
    assert artifact.verify() == local
    assert artifact.json() == [1, 2]
    assert resolve_wine_artifact_path("Z:" + str(local).replace("/", "\\"), bottle) == local
    with pytest.raises(ArtifactError, match="resolver"):
        Artifact(reference).bytes()


@pytest.mark.parametrize("version", [1, 3, None])
def test_protocol_mismatch_refused(version: int | None) -> None:
    async def scenario() -> None:
        async with hotrepl(lambda _: [], handshake={**HANDSHAKE, "protocolVersion": version}) as server:
            client = EvalClient(server.url)
            with pytest.raises(EvalConnectionError, match="expected 2"):
                await client.connect()
            assert client.handshake is None and server.requests == []

    asyncio.run(scenario())


def test_ping_uses_only_the_handshake() -> None:
    async def scenario() -> None:
        async with hotrepl(lambda _: pytest.fail("v2 ping must not send a message")) as server:
            client = EvalClient(server.url)
            try:
                assert await client.ping() > 0
                assert client.handshake == HANDSHAKE
            finally:
                await client.close()
            assert server.requests == []

    asyncio.run(scenario())


def test_reload_notification_and_eviction_are_not_dropped() -> None:
    reload = {"type": "assembly_reload", "assembly": "Plugin.dll", "message": "Reloaded"}
    eviction = {"type": "session_evicted", "reason": "displaced", "by": {"clientName": "SDK"}}

    async def scenario() -> None:
        seen: list[dict[str, Any]] = []
        async with hotrepl(lambda _: [reload, eviction]) as server:
            client = EvalClient(server.url, on_notification=seen.append)
            await client.connect()
            try:
                with pytest.raises(EvalConnectionError, match=r"displaced.*SDK"):
                    await client.eval("1")
                assert seen == [reload, eviction]
                assert await client.notifications.get() == reload
                assert await client.notifications.get() == eviction
                with pytest.raises(EvalConnectionError, match="evicted"):
                    await client.commands()
            finally:
                await client.close()

    asyncio.run(scenario())


def test_cancelled_eval_sends_target_id() -> None:
    async def scenario() -> None:
        received = asyncio.Event()

        def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
            received.set()
            return []

        async with hotrepl(respond) as server:
            client = EvalClient(server.url)
            await client.connect()
            try:
                task = asyncio.create_task(client.eval("Slow()"))
                await received.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            finally:
                await client.close()
            assert server.requests[1]["targetId"] == server.requests[0]["id"]
            assert server.requests[1]["id"] != server.requests[0]["id"]

    asyncio.run(scenario())


def test_reset_failure_is_not_reported_as_success() -> None:
    async def scenario() -> None:
        async with hotrepl(lambda request: [frame(request, "reset_result", success=False)]) as server:
            client = EvalClient(server.url)
            await client.connect()
            try:
                with pytest.raises(EvalConnectionError, match="success=false"):
                    await client.reset()
            finally:
                await client.close()

    asyncio.run(scenario())


def test_connection_level_error_envelope_fails_pending_request() -> None:
    async def scenario() -> None:
        async with hotrepl(lambda _: [{"type": "error", "error": ERROR}]) as server:
            client = EvalClient(server.url)
            await client.connect()
            try:
                with pytest.raises(EvalError, match="validation_failed/badArgument"):
                    await client.commands()
            finally:
                await client.close()

    asyncio.run(scenario())


def test_multiplexed_requests_keep_their_responses() -> None:
    waiting: list[dict[str, Any]] = []

    def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
        waiting.append(request)
        if len(waiting) < 2:
            return []
        return [
            frame(request, "eval_result", hasValue=True, value=request["code"], durationMs=1)
            for request in reversed(waiting)
        ]

    async def scenario() -> None:
        async with hotrepl(respond) as server:
            client = EvalClient(server.url)
            await client.connect()
            try:
                first, second = await asyncio.gather(client.eval("one"), client.eval("two"))
                assert first["value"] == "one"
                assert second["value"] == "two"
            finally:
                await client.close()

    asyncio.run(scenario())
