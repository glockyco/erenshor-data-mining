"""Eval commands for HotRepl C# evaluation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console

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



@app.command()
def complete(
    ctx: typer.Context,
    code: str = typer.Argument(..., help="Partial C# code to complete"),
    cursor_pos: int = typer.Option(-1, "--cursor", help="Cursor position (-1 = end)"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON response"),
) -> None:
    """Get autocomplete suggestions for partial C# code."""
    asyncio.run(_complete(code, cursor_pos=cursor_pos, json_output=json_output))


@app.command()
def watch(
    ctx: typer.Context,
    code: str = typer.Argument(..., help="C# expression to watch"),
    interval: int = typer.Option(60, "--interval", help="Eval interval in frames"),
    on_change: bool = typer.Option(False, "--on-change", help="Only print when value changes"),
    limit: int = typer.Option(0, "--limit", help="Max deliveries (0 = unlimited)"),
    timeout: int = typer.Option(10000, "--timeout", help="Per-eval timeout in ms"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Watch a C# expression, printing updates until Ctrl-C."""
    asyncio.run(_watch(
        code,
        interval_frames=interval,
        on_change=on_change,
        limit=limit,
        timeout_ms=timeout,
        json_output=json_output,
    ))

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
    except TimeoutError:
        console.print("[red]Timed out waiting for eval response.[/red]")
        raise typer.Exit(code=1) from None
    except EvalError as exc:
        if json_output:
            # Even errors get raw JSON when --json is used.
            error_payload = {
                "type": "eval_error",
                "error": str(exc),
                "error_kind": exc.error_kind,
                "stack_trace": exc.stack_trace,
            }
            print(json.dumps(error_payload))
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
        await client.reset()
    except EvalConnectionError as exc:
        console.print(f"[red]{exc}[/red]", highlight=False)
        raise typer.Exit(code=1) from None
    finally:
        await client.close()

    console.print("[green]REPL state reset.[/green]")



async def _complete(code: str, *, cursor_pos: int, json_output: bool) -> None:
    from erenshor.application.eval.client import EvalClient, EvalConnectionError

    client = EvalClient()
    try:
        await client.connect()
        completions = await client.complete(code, cursor_pos=cursor_pos)
    except EvalConnectionError as exc:
        console.print(f"[red]{exc}[/red]", highlight=False)
        raise typer.Exit(code=1) from None
    except TimeoutError:
        console.print("[red]Timed out waiting for completions.[/red]")
        raise typer.Exit(code=1) from None
    finally:
        await client.close()

    if json_output:
        print(json.dumps({"completions": completions}))
    elif completions:
        for c in completions:
            console.print(c, highlight=False)
    else:
        console.print("[dim]No completions.[/dim]")


async def _watch(
    code: str,
    *,
    interval_frames: int,
    on_change: bool,
    limit: int,
    timeout_ms: int,
    json_output: bool,
) -> None:
    from erenshor.application.eval.client import EvalClient, EvalConnectionError

    client = EvalClient()
    try:
        await client.connect()
        gen = client.subscribe(
            code,
            interval_frames=interval_frames,
            on_change=on_change,
            limit=limit,
            timeout_ms=timeout_ms,
        )
        async for resp in gen:
            if json_output:
                print(json.dumps(resp), flush=True)
            elif resp.get("type") == "subscribe_error":
                console.print(
                    f"[red]#{resp.get('seq', '?')} error: {resp.get('message', '?')}[/red]",
                    highlight=False,
                )
            else:
                value = resp.get("value", "")
                seq = resp.get("seq", "?")
                console.print(f"[dim]#{seq}[/dim] {value}", highlight=False)

            if resp.get("final", False):
                break
    except EvalConnectionError as exc:
        console.print(f"[red]{exc}[/red]", highlight=False)
        raise typer.Exit(code=1) from None
    except TimeoutError:
        console.print("[red]Timed out waiting for subscription data.[/red]")
        raise typer.Exit(code=1) from None
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")
    finally:
        await client.close()
