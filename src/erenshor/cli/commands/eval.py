"""Eval commands for HotRepl C# evaluation."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from loguru import logger
from rich.console import Console

if TYPE_CHECKING:
    from ..context import CLIContext

app = typer.Typer(
    name="eval",
    help="Evaluate C# code via HotRepl",
    no_args_is_help=True,
)

console = Console()


@app.command()
def run(
    ctx: typer.Context,
    code: str | None = typer.Argument(None, help="C# code to evaluate"),
    file: Path | None = typer.Option(None, "--file", help="Read code from file"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON response"),
    timeout: int = typer.Option(10000, "--timeout", help="Server-side timeout in ms"),
) -> None:
    """Evaluate a C# expression or script in the running game."""
    if code and file:
        console.print("[red]Provide either code argument or --file, not both.[/red]")
        raise typer.Exit(code=1)
    if not code and not file:
        console.print("[red]Provide a code argument or --file.[/red]")
        raise typer.Exit(code=1)

    if file:
        if not file.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(code=1)
        code = file.read_text()

    asyncio.run(_run(code, json_output=json_output, timeout_ms=timeout))  # type: ignore[arg-type]


@app.command()
def ping(ctx: typer.Context) -> None:
    """Ping the HotRepl server and show round-trip latency."""
    asyncio.run(_ping())


@app.command()
def reset(ctx: typer.Context) -> None:
    """Reset the server-side REPL state."""
    asyncio.run(_reset())


# -- async implementations --


async def _run(code: str, *, json_output: bool, timeout_ms: int) -> None:
    from erenshor.application.eval.client import (
        EvalClient,
        EvalConnectionError,
        EvalError,
    )

    client = EvalClient()
    try:
        await client.connect()
        resp = await client.eval(code, timeout_ms=timeout_ms)
    except EvalConnectionError as exc:
        console.print(f"[red]{exc}[/red]", highlight=False)
        raise typer.Exit(code=1) from None
    except asyncio.TimeoutError:
        console.print("[red]Timed out waiting for eval response.[/red]")
        raise typer.Exit(code=1) from None
    except EvalError as exc:
        if json_output:
            # Even errors get raw JSON when --json is used.
            print(json.dumps({"type": "eval_error", "error": str(exc), "error_kind": exc.error_kind, "stack_trace": exc.stack_trace}))
        else:
            console.print(f"[red]{exc}[/red]", highlight=False)
            if exc.stack_trace:
                console.print(exc.stack_trace, style="dim")
        raise typer.Exit(code=1) from None
    finally:
        await client.close()

    if json_output:
        print(json.dumps(resp))
    else:
        value = resp.get("result", resp.get("value", ""))
        console.print(str(value), highlight=False)


async def _ping() -> None:
    from erenshor.application.eval.client import EvalClient, EvalConnectionError

    client = EvalClient()
    try:
        await client.connect()
        ms = await client.ping()
    except EvalConnectionError as exc:
        console.print(f"[red]{exc}[/red]", highlight=False)
        raise typer.Exit(code=1) from None
    finally:
        await client.close()

    console.print(f"[green]Pong[/green] {ms:.1f} ms")


async def _reset() -> None:
    from erenshor.application.eval.client import EvalClient, EvalConnectionError

    client = EvalClient()
    try:
        await client.connect()
        resp = await client.reset()
    except EvalConnectionError as exc:
        console.print(f"[red]{exc}[/red]", highlight=False)
        raise typer.Exit(code=1) from None
    finally:
        await client.close()

    console.print("[green]REPL state reset.[/green]")
