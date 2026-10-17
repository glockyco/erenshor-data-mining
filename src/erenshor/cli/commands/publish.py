"""Prepare and explicitly apply selected writes through existing publishers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from erenshor.application.publish.coordinator import (
    apply_publish,
    inspect_publish,
    preparation_outputs,
    prepare_publish,
    resume_publish,
    run_directory,
    status_publish,
)
from erenshor.application.publish.models import PublishError, load_selection
from erenshor.application.publish.reporting import review_summary, status_summary
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.publish import preparation_inputs, prepared_plan

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(help="Review, approve, and recover explicitly selected publication writes.", no_args_is_help=True)


def _print(value: Any) -> None:
    if isinstance(value, dict) and "operations" in value:
        value = review_summary(value) if "approval_digest" in value else status_summary(value)
    typer.echo(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _error(error: Exception) -> None:
    if hasattr(error, "review"):
        _print(error.review)
    typer.echo(f"Publication refused: {error}", err=True)
    raise typer.Exit(1) from error


@app.command()
@require_preconditions(preparation_inputs)
def prepare(
    ctx: typer.Context,
    selection: Annotated[
        Path,
        typer.Option(
            "--selection", help="Explicit selection TOML. See PublishSelection in application/publish/models.py."
        ),
    ],
    output: Annotated[Path, typer.Option("--output", help="New run directory under selected variant storage.")],
) -> None:
    """Freeze exact selected payloads and inspect remote bases without live writes."""
    cli_ctx: CLIContext = ctx.obj
    try:
        selected = load_selection(selection)
        destination = run_directory(cli_ctx, output)
        bounded = selected.model_dump(mode="json", exclude_none=True)
        _print(
            {
                "local_output": str(destination),
                "local_writes": preparation_outputs(cli_ctx, bounded, destination),
                "live_writes": False,
            }
        )
        if cli_ctx.dry_run:
            actions = ["Inspect selected remote bases through existing publishers"]
            if selected.wiki:
                actions.append("Generate selected wiki data and projected article bytes in isolated storage")
            if selected.maps:
                actions.append("Build selected maps locally and freeze complete deployable assets")
            if selected.sheets:
                actions.append("Format exact selected Sheets rows and inspect live table operations")
            actions.append("Write immutable plan and exact review sidecars")
            _print(
                {
                    "selection": bounded,
                    "actions": actions,
                    "durable_artifacts": False,
                    "approval": "Not requested during preparation",
                }
            )
            return
        prepare_publish(selected, cli_ctx, destination, selection_path=selection)
        _print(
            {
                **json.loads((destination / "review.json").read_text(encoding="utf-8")),
                "next": (
                    f"Read every referenced payload and diff, then run erenshor -V {cli_ctx.variant} "
                    f"--dry-run publish apply {destination / 'plan.json'}. "
                    "Human approval is a separate declaration after review."
                ),
            }
        )
    except (PublishError, ValueError, OSError, RuntimeError) as error:
        _error(error)


@app.command()
@require_preconditions(prepared_plan)
def apply(
    ctx: typer.Context,
    plan: Annotated[Path, typer.Argument(help="Prepared plan.json.")],
    approval: Annotated[
        str | None,
        typer.Option("--approval", help="Human approval declaration naming the exact reviewed sha256 digest."),
    ] = None,
) -> None:
    """Review the complete frozen write set by exact references, or apply after human approval."""
    cli_ctx: CLIContext = ctx.obj
    try:
        _print(apply_publish(plan, approval, cli_ctx))
    except (PublishError, ValueError, OSError, RuntimeError) as error:
        _error(error)


@app.command()
def status(ctx: typer.Context, plan: Annotated[Path, typer.Argument(help="Prepared plan.json.")]) -> None:
    """Read durable writes, failures, blocked work, and provider recovery limits."""
    cli_ctx: CLIContext = ctx.obj
    try:
        _print(status_publish(plan, cli_ctx))
    except (PublishError, ValueError, OSError, RuntimeError) as error:
        _error(error)


@app.command()
@require_preconditions(prepared_plan)
def resume(
    ctx: typer.Context,
    plan: Annotated[Path, typer.Argument(help="Prepared plan.json with execution history.")],
    approval: Annotated[
        str | None,
        typer.Option("--approval", help="Human approval declaration for the unchanged reviewed sha256 digest."),
    ] = None,
) -> None:
    """Reconcile completed receipts and explicitly continue only unchanged work."""
    cli_ctx: CLIContext = ctx.obj
    try:
        if cli_ctx.dry_run:
            _print(inspect_publish(plan, cli_ctx))
        else:
            _print(resume_publish(plan, approval, cli_ctx))
    except (PublishError, ValueError, OSError, RuntimeError) as error:
        _error(error)
