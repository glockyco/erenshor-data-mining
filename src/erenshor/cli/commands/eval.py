"""HotRepl v2 evaluation and typed control-plane commands."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import aclosing, asynccontextmanager
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console

from erenshor.application.eval.artifacts import ArtifactError, ArtifactPathResolver, resolve_wine_artifact_path
from erenshor.application.eval.client import EvalClient, EvalConnectionError, EvalError
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.eval import eval_source

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(name="eval", help="Evaluate C# and run HotRepl typed commands", no_args_is_help=True)
console = Console()
notification_console = Console(stderr=True)


class JournalKind(StrEnum):
    eval = "eval"
    command = "command"


@app.command()
@require_preconditions(eval_source)
def run(
    ctx: typer.Context,
    code: str | None = typer.Argument(None, help="C# code to evaluate"),
    file: Path | None = typer.Option(None, "--file", help="Read code from file"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON response"),
    timeout: int = typer.Option(10000, "--timeout", min=1, help="Server-side timeout in ms"),
) -> None:
    """Evaluate a C# expression or script in the running game."""
    if file:
        code = file.read_text()
    assert code is not None  # eval_source guarantees a code argument or file.
    asyncio.run(_run(code, json_output=json_output, timeout_ms=timeout))


@app.command()
def ping(ctx: typer.Context) -> None:
    """Check reachability via the v2 handshake and show connection latency."""
    asyncio.run(_ping())


@app.command()
def reset(ctx: typer.Context) -> None:
    """Reset the server-side REPL state."""
    asyncio.run(_reset())


@app.command()
def complete(
    ctx: typer.Context,
    code: str = typer.Argument(..., help="Partial C# code to complete"),
    cursor_pos: int = typer.Option(-1, "--cursor", min=-1, help="Cursor position (-1 = end)"),
    json_output: bool = typer.Option(False, "--json", help="Output completion JSON"),
) -> None:
    """Get autocomplete suggestions for partial C# code."""
    asyncio.run(_complete(code, cursor_pos=cursor_pos, json_output=json_output))


@app.command()
def watch(
    ctx: typer.Context,
    code: str = typer.Argument(..., help="C# expression to watch"),
    interval: int = typer.Option(60, "--interval", min=1, help="Eval interval in frames"),
    on_change: bool = typer.Option(False, "--on-change", help="Only print when value changes"),
    limit: int = typer.Option(0, "--limit", min=0, help="Max deliveries (0 = unlimited)"),
    timeout: int = typer.Option(10000, "--timeout", min=1, help="Per-eval timeout in ms"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON frames"),
) -> None:
    """Watch a C# expression until final, error or Ctrl-C."""
    try:
        asyncio.run(
            _watch(
                code,
                interval_frames=interval,
                on_change=on_change,
                limit=limit,
                timeout_ms=timeout,
                json_output=json_output,
            )
        )
    except KeyboardInterrupt:
        console.print("\nWatch stopped.", style="dim")


@app.command()
def commands(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON response"),
) -> None:
    """List the registered typed commands (sync and job)."""
    asyncio.run(_control("commands", json_output=json_output))


@app.command()
def describe(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Registered command name"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON response"),
) -> None:
    """Show a command's input, output, artifact and cancellation schemas."""
    asyncio.run(_control("describe", name=name, json_output=json_output))


@app.command()
def call(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Registered command name"),
    args: str = typer.Option("{}", "--args", help="Command arguments as a JSON object"),
    timeout: int = typer.Option(30000, "--timeout", min=1, help="Overall command/job deadline in ms"),
    artifact: str | None = typer.Option(None, "--artifact", help="Print a named artifact as verified UTF-8 text"),
    json_output: bool = typer.Option(False, "--json", help="Output raw terminal JSON response"),
) -> None:
    """Run a typed command, waiting for jobs and verifying returned artifacts."""
    try:
        parsed = json.loads(args)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid JSON: {exc}", param_hint="--args") from exc
    if not isinstance(parsed, dict):
        raise typer.BadParameter("Must be a JSON object", param_hint="--args")
    if artifact is not None and json_output:
        raise typer.BadParameter("--artifact and --json are mutually exclusive")
    try:
        asyncio.run(
            _call(
                name,
                parsed,
                timeout_ms=timeout,
                artifact=artifact,
                json_output=json_output,
                resolver=_artifact_resolver(ctx.obj),
            )
        )
    except KeyboardInterrupt:
        console.print("\nCommand interrupted; accepted job cancellation requested.", style="dim")
        raise typer.Exit(130) from None


@app.command()
def journal(
    ctx: typer.Context,
    kind: JournalKind | None = typer.Option(None, "--kind", help="Filter eval or command entries"),
    limit: int = typer.Option(20, "--limit", min=1, help="Maximum recent entries"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON response"),
) -> None:
    """Query recent eval and command journal entries."""
    asyncio.run(_control("journal", kind=kind, limit=limit, json_output=json_output))


def _artifact_resolver(cli_ctx: CLIContext) -> ArtifactPathResolver:
    def resolve(reference: dict[str, Any]) -> Path | None:
        path = reference.get("path")
        if path is None or not path.lower().startswith("c:"):
            return None
        from erenshor.infrastructure.steam.installation import CROSSOVER_BOTTLES_ROOT, find_game_installation

        variant = cli_ctx.config.variants[cli_ctx.variant]
        installation = find_game_installation(cli_ctx.variant, variant.app_id)
        return resolve_wine_artifact_path(path, CROSSOVER_BOTTLES_ROOT / installation.bottle)

    return resolve


def _notification(response: dict[str, Any]) -> None:
    if response["type"] == "assembly_reload":
        notification_console.print(response["message"], style="yellow", markup=False, highlight=False)


@asynccontextmanager
async def _session(
    *, json_output: bool = False, resolver: ArtifactPathResolver | None = None, connect: bool = True
) -> AsyncIterator[EvalClient]:
    client = EvalClient(resolve_artifact_path=resolver, on_notification=_notification)
    try:
        if connect:
            await client.connect()
        yield client
    except EvalError as exc:
        if json_output:
            print(json.dumps(exc.response))
        else:
            console.print(str(exc), style="red", markup=False, highlight=False)
        raise typer.Exit(1) from None
    except (EvalConnectionError, TimeoutError, ArtifactError, OSError, UnicodeError) as exc:
        message = str(exc) or "Timed out waiting for HotRepl response."
        console.print(message, style="red", markup=False, highlight=False)
        raise typer.Exit(1) from None
    finally:
        await client.close()


def _value(response: dict[str, Any]) -> str:
    if response.get("truncated"):
        return f"<truncated: {response.get('truncatedBytes', '?')} bytes>"
    return str(response.get("value", "")) if response.get("hasValue") else ""


async def _run(code: str, *, json_output: bool, timeout_ms: int) -> None:
    async with _session(json_output=json_output) as client:
        response = await client.eval(code, timeout_ms=timeout_ms)
    if json_output:
        print(json.dumps(response))
    else:
        console.print(_value(response), markup=False, highlight=False)


async def _ping() -> None:
    async with _session(connect=False) as client:
        milliseconds = await client.ping()
        assert client.handshake is not None
        host = client.handshake["host"]
        evaluator = client.handshake["evaluator"]
    console.print(
        f"Pong {milliseconds:.1f} ms — {host['name']} {host['version']} / {evaluator['name']}",
        style="green",
        markup=False,
        highlight=False,
    )


async def _reset() -> None:
    async with _session() as client:
        await client.reset()
    console.print("REPL state reset.", style="green")


async def _complete(code: str, *, cursor_pos: int, json_output: bool) -> None:
    async with _session(json_output=json_output) as client:
        completions = await client.complete(code, cursor_pos=cursor_pos)
    if json_output:
        print(json.dumps({"completions": completions}))
    elif completions:
        for completion in completions:
            console.print(completion, markup=False, highlight=False)
    else:
        console.print("No completions.", style="dim")


async def _watch(
    code: str, *, interval_frames: int, on_change: bool, limit: int, timeout_ms: int, json_output: bool
) -> None:
    async with (
        _session(json_output=json_output) as client,
        aclosing(
            client.subscribe(
                code,
                interval_frames=interval_frames,
                on_change=on_change,
                limit=limit,
                timeout_ms=timeout_ms,
            )
        ) as subscription,
    ):
        async for response in subscription:
            if json_output:
                print(json.dumps(response), flush=True)
            else:
                console.print(f"#{response['seq']} {_value(response)}", markup=False, highlight=False)


async def _control(action: str, *, name: str = "", kind: str | None = None, limit: int = 20, json_output: bool) -> None:
    async with _session(json_output=json_output) as client:
        if action == "commands":
            response = await client.commands()
        elif action == "describe":
            response = await client.describe(name)
        else:
            response = await client.journal(kind=kind, limit=limit)
    if json_output:
        print(json.dumps(response))
    elif action == "commands":
        for command in response["commands"]:
            mutation = "mutates state" if command["mutatesState"] else "read-only"
            console.print(
                f"{command['name']} v{command['majorVersion']} ({command['kind']}, {mutation})",
                markup=False,
                highlight=False,
            )
    else:
        console.print_json(json.dumps(response["descriptor"] if action == "describe" else response["entries"]))


async def _call(
    name: str,
    args: dict[str, Any],
    *,
    timeout_ms: int,
    artifact: str | None,
    json_output: bool,
    resolver: ArtifactPathResolver | None,
) -> None:
    async with _session(json_output=json_output, resolver=resolver) as client:
        response = await client.call(name, args, timeout_ms=timeout_ms)
        if artifact is not None:
            if artifact not in response["artifacts"]:
                raise ArtifactError(f"Command did not return artifact {artifact!r}")
            console.print(client.artifact(response["artifacts"][artifact]).text(), markup=False, highlight=False)
        elif json_output:
            print(json.dumps(response))
        else:
            console.print_json(json.dumps({"output": response.get("output"), "artifacts": response["artifacts"]}))
