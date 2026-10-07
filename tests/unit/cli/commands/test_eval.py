"""Exercise the Typer surface over the real v2 WebSocket client."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from tests.fixtures.hotrepl import ERROR, HANDSHAKE, frame, hotrepl
from typer.testing import CliRunner

from erenshor.application.eval.client import EvalClient
from erenshor.cli.commands import eval as eval_command
from erenshor.infrastructure.steam import installation

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext


def _use_server(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    class LoopbackClient(EvalClient):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(url, **kwargs)

    monkeypatch.setattr(eval_command, "EvalClient", LoopbackClient)


@pytest.mark.parametrize("command", ["run", "watch", "call", "reset", "complete", "commands", "describe", "journal"])
@pytest.mark.parametrize("json_output", [False, True])
def test_cli_renders_v2_errors(
    command: str,
    json_output: bool,
    cli_context: CLIContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
        types = {"eval": "eval_error", "subscribe": "subscribe_error", "command_call": "command_result"}
        fields: dict[str, Any] = {"error": ERROR}
        if request["type"] == "command_call":
            fields.update(status="failed", artifacts={}, durationMs=1)
        elif request["type"] == "subscribe":
            fields.update(seq=1, final=True)
        return [frame(request, types.get(request["type"], "error"), **fields)]

    async def scenario() -> None:
        async with hotrepl(respond) as server:
            _use_server(monkeypatch, server.url)
            arguments = [command]
            if command in {"run", "watch", "call", "complete", "describe"}:
                arguments.append("bad")
            if json_output and command != "reset":
                arguments.append("--json")
            result = await asyncio.to_thread(CliRunner().invoke, eval_command.app, arguments, obj=cli_context)
            assert result.exit_code == 1, result.output
            if json_output and command != "reset":
                assert json.loads(result.stdout)["error"] == ERROR
            else:
                assert "validation_failed/badArgument: Invalid scene [Missing]" in result.output
            assert "unknown error" not in result.output.lower()

    asyncio.run(scenario())


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_truncated_values(
    json_output: bool,
    cli_context: CLIContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
            return [
                frame(
                    request,
                    "eval_result",
                    hasValue=True,
                    value=None,
                    truncated=True,
                    truncatedBytes=250112,
                    durationMs=1,
                )
            ]

        async with hotrepl(respond) as server:
            _use_server(monkeypatch, server.url)
            result = await asyncio.to_thread(
                CliRunner().invoke,
                eval_command.app,
                ["run", "large", *(["--json"] if json_output else [])],
                obj=cli_context,
            )
            assert result.exit_code == 0, result.output
            if json_output:
                assert json.loads(result.stdout)["truncatedBytes"] == 250112
            else:
                assert "<truncated: 250112 bytes>" in result.output

    asyncio.run(scenario())


def test_ping_shows_host_and_evaluator(cli_context: CLIContext, monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        async with hotrepl(lambda _: pytest.fail("No ping wire message")) as server:
            _use_server(monkeypatch, server.url)
            result = await asyncio.to_thread(CliRunner().invoke, eval_command.app, ["ping"], obj=cli_context)
            assert result.exit_code == 0, result.output
            assert "Pong" in result.output and "ms" in result.output
            assert "BepInEx test / Mono.CSharp" in result.output
            assert server.requests == []

    asyncio.run(scenario())


def test_commands_describe_call_and_journal_surface(
    cli_context: CLIContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = {
        "name": "unity.app.info",
        "majorVersion": 1,
        "kind": "sync",
        "mutatesState": False,
        "inputSchema": {},
        "outputSchema": {},
        "artifactsSchema": {},
    }

    def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
        responses = {
            "commands_list": frame(request, "commands_list_result", commands=[descriptor]),
            "command_describe": frame(request, "command_describe_result", descriptor=descriptor),
            "command_call": frame(
                request,
                "command_result",
                status="ok",
                output={"scene": "test"},
                artifacts={},
                durationMs=1,
            ),
            "journal_query": frame(
                request,
                "journal_query_result",
                entries=[{"kind": "command", "name": "unity.app.info"}],
            ),
        }
        return [responses[request["type"]]]

    async def scenario() -> None:
        async with hotrepl(respond) as server:
            _use_server(monkeypatch, server.url)
            for arguments, field in [
                (["commands", "--json"], "commands"),
                (["describe", "unity.app.info", "--json"], "descriptor"),
                (["call", "unity.app.info", "--args", '{"scene":"test"}', "--json"], "output"),
                (["journal", "--kind", "command", "--limit", "3", "--json"], "entries"),
            ]:
                result = await asyncio.to_thread(CliRunner().invoke, eval_command.app, arguments, obj=cli_context)
                assert result.exit_code == 0, result.output
                assert field in json.loads(result.stdout)
            assert server.requests[2]["args"] == {"scene": "test"}
            assert server.requests[3]["kind"] == "command" and server.requests[3]["limit"] == 3

    asyncio.run(scenario())


@pytest.mark.parametrize("arguments", [["--args", "[]"], ["--args", "{"], ["--artifact", "data", "--json"]])
def test_call_invalid_options_do_not_connect(
    arguments: list[str],
    cli_context: CLIContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        async with hotrepl(lambda _: pytest.fail("Invalid input must fail before side effects")) as server:
            _use_server(monkeypatch, server.url)
            result = await asyncio.to_thread(
                CliRunner().invoke,
                eval_command.app,
                ["call", "export", *arguments],
                obj=cli_context,
            )
            assert result.exit_code == 2
            assert server.requests == []

    asyncio.run(scenario())


def test_call_prints_verified_wine_artifact_from_selected_bottle(
    tmp_path: Path,
    cli_context: CLIContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = b'{"count":2}'
    bottle = tmp_path / "Playtest"
    local = bottle / "drive_c/users/crossover/HotRepl/data.json"
    local.parent.mkdir(parents=True)
    local.write_bytes(data)
    reference = {
        "uri": "file:///C:/users/crossover/HotRepl/data.json",
        "path": r"C:\users\crossover\HotRepl\data.json",
        "sha256": hashlib.sha256(data).hexdigest(),
        "byteSize": len(data),
        "finalized": True,
        "contentType": "application/json",
    }
    selected: list[tuple[str, str]] = []

    def find(variant: str, app_id: str) -> installation.GameInstallation:
        selected.append((variant, app_id))
        return installation.GameInstallation(bottle / "game", bottle / "manifest", bottle.name)

    monkeypatch.setattr(installation, "CROSSOVER_BOTTLES_ROOT", tmp_path)
    monkeypatch.setattr(installation, "find_game_installation", find)

    async def scenario() -> None:
        def respond(request: dict[str, Any]) -> list[dict[str, Any]]:
            return [
                frame(
                    request,
                    "command_result",
                    status="ok",
                    output={},
                    artifacts={"data": reference},
                    durationMs=1,
                )
            ]

        async with hotrepl(respond) as server:
            _use_server(monkeypatch, server.url)
            result = await asyncio.to_thread(
                CliRunner().invoke,
                eval_command.app,
                ["call", "export", "--artifact", "data"],
                obj=cli_context,
            )
            assert result.exit_code == 0, result.output
            assert '{"count":2}' in result.output
            assert selected and all(pair == (cli_context.variant, "0") for pair in selected)

    asyncio.run(scenario())


def test_cli_refuses_v1_server(cli_context: CLIContext, monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        async with hotrepl(lambda _: [], handshake={**HANDSHAKE, "protocolVersion": 1}) as server:
            _use_server(monkeypatch, server.url)
            result = await asyncio.to_thread(CliRunner().invoke, eval_command.app, ["ping"], obj=cli_context)
            assert result.exit_code == 1
            assert "expected 2" in result.output

    asyncio.run(scenario())
