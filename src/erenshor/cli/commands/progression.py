"""Inspect persisted requirements and their new-character playthrough order."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import typer

from erenshor.infrastructure.database.connection import DatabaseConnection, DatabaseConnectionError
from erenshor.infrastructure.database.repositories.progression import ProgressionRepository
from erenshor.infrastructure.database.repository import RepositoryError

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext
    from erenshor.domain.value_objects.progression import ProgressionNeed, ProgressionNode

app = typer.Typer(help="Inspect the clean database's progression requirements")


def _label(node: ProgressionNode) -> str:
    return f"{node.name} [{node.stable_key}]"


def _condition(need: ProgressionNeed) -> str:
    key = need.condition_key or ""
    if need.relation == "event" and key.startswith("event:"):
        return f"scripted event [{key}]"
    descriptions = {
        "health_phase_timer": "vulnerability after a health-phase timer",
        "spawn_health_phase_timer": "vulnerability after a spawn health-phase timer",
        "combat_empty_wards": "vulnerability during combat with no wards",
    }
    for mechanism, description in descriptions.items():
        if need.relation == "condition" and key.startswith(f"release:{mechanism}:"):
            return f"{description} [{key}]"
    raise RepositoryError(f"Cannot word progression condition: {key!r}")


def _need(repository: ProgressionRepository, need: ProgressionNeed) -> str:
    if need.need_stable_key is None:
        text = _condition(need)
    else:
        target = repository.get_node(need.need_stable_key)
        if target is None:
            raise RepositoryError(f"Progression need resolves to no node: {need.need_stable_key}")
        text = _label(target)
    details = []
    if need.quantity is not None:
        details.append(f"quantity {need.quantity:g}")
    if need.slot is not None:
        details.append(f"slot {need.slot}")
    if need.keywords is not None:
        details.append(f"keywords {need.keywords!r}")
    if need.advisory:
        details.append("advisory")
    if need.unconfirmed:
        details.append("unconfirmed")
    return f"{need.relation} {text}" + (f" ({', '.join(details)})" if details else "")


def _show_node(repository: ProgressionRepository, node: ProgressionNode) -> None:
    typer.echo(_label(node))
    tier = "unreachable" if node.tier is None else str(node.tier)
    typer.echo(f"Kind {node.kind}. Tier {tier}. Build {repository.game_build_id}.")
    typer.echo("Playthrough order from new-character starts, not a save-state assessment.")
    ways = repository.get_ways(node.stable_key)
    typer.echo(f"Ways ({len(ways)})")
    for way in ways:
        typer.echo(f"  {way.way_key}" + (" (first)" if way.way_key == node.first_way_key else ""))
        for need in way.needs:
            typer.echo("    " + _need(repository, need))
        if not way.needs:
            typer.echo("    no needs")
    if node.tier is not None:
        typer.echo("First-way milestones")
        milestones = repository.first_way_milestones(node.stable_key)
        for milestone in milestones:
            typer.echo(f"  tier {milestone.tier}: {_label(milestone)}")
        if not milestones:
            typer.echo("  none")
        return
    typer.echo("No way reaches it from a start.")
    typer.echo("Unreachable needs")
    chain = repository.unreachable_chain(node.stable_key)
    for index, entry in enumerate(chain):
        typer.echo("  " * (index + 1) + _label(entry))
    if chain and not repository.get_ways(chain[-1].stable_key):
        typer.echo("  " * (len(chain) + 1) + "no recorded way")
    elif chain:
        typer.echo("  " * (len(chain) + 1) + "unreachable cycle")


def _show_gaps(repository: ProgressionRepository) -> None:
    gaps = repository.gaps()
    without_way = Counter(node.kind for node in gaps if not repository.get_ways(node.stable_key))
    without_tier = Counter(node.kind for node in gaps if node.tier is None)
    typer.echo(f"Gaps ({len(gaps)} nodes)")
    for label, counts in (("Without a way", without_way), ("Without a tier", without_tier)):
        text = ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items())) or "none"
        typer.echo(f"{label} ({sum(counts.values())}): {text}")
    for node in gaps:
        reasons = []
        if not repository.get_ways(node.stable_key):
            reasons.append("no way")
        if node.tier is None:
            reasons.append("no tier")
        typer.echo(f"  {_label(node)} ({', '.join(reasons)})")


@app.command("show")
def show(
    ctx: typer.Context,
    stable_key: str | None = typer.Argument(None, help="Exact progression stable key"),
    gaps: bool = typer.Option(False, "--gaps", help="List nodes without a way or a playthrough tier"),
) -> None:
    """Show a node's ways and first-way milestones, or list graph gaps."""
    if (stable_key is None) == (not gaps):
        raise typer.BadParameter("Provide one stable key or --gaps, not both.")
    cli_ctx: CLIContext = ctx.obj
    path = cli_ctx.config.variants[cli_ctx.variant].resolved_database(cli_ctx.repo_root)
    try:
        with DatabaseConnection(path, read_only=True) as database:
            repository = ProgressionRepository(database)
            if gaps:
                _show_gaps(repository)
            else:
                node = repository.get_node(str(stable_key))
                if node is None:
                    raise RepositoryError(f"Unknown progression node: {stable_key}")
                _show_node(repository, node)
    except (DatabaseConnectionError, RepositoryError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
