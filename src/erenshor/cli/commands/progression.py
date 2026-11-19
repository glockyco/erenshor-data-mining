"""Inspect persisted requirements and their new-character playthrough order."""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

import typer

from erenshor.application.progression_wording import ProgressionSentences, ProgressionWordingError, condition_text
from erenshor.infrastructure.database.connection import DatabaseConnection, DatabaseConnectionError
from erenshor.infrastructure.database.repositories.progression import ProgressionRepository
from erenshor.infrastructure.database.repository import RepositoryError

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext
    from erenshor.domain.value_objects.progression import ProgressionNeed, ProgressionNode

_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")

app = typer.Typer(help="Inspect the clean database's progression requirements")


def _label(node: ProgressionNode) -> str:
    return f"{node.name} [{node.stable_key}]"


def _condition(need: ProgressionNeed) -> str:
    key = need.condition_key or ""
    try:
        return f"{condition_text(key)} [{key}]"
    except ProgressionWordingError as error:
        raise RepositoryError(str(error)) from error


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
    if need.required_level is not None:
        details.append(f"level {need.required_level}")
    if need.advisory:
        details.append("advisory")
    if need.unconfirmed:
        details.append("unconfirmed")
    return f"{need.relation} {text}" + (f" ({', '.join(details)})" if details else "")


def _show_node(repository: ProgressionRepository, node: ProgressionNode) -> None:
    nodes = {node.stable_key: node for node in repository.get_nodes()}
    writer = ProgressionSentences(
        nodes, {other: repository.get_ways(other) for other in nodes}, repository.display_names()
    )

    def show_ways(target: ProgressionNode, selected: set[str] | None = None) -> None:
        try:
            sentences = writer.sentences(target.stable_key)
        except ProgressionWordingError as error:
            raise RepositoryError(str(error)) from error
        for way, sentence in zip(repository.get_ways(target.stable_key), sentences, strict=True):
            if selected is not None and way.way_key not in selected:
                continue
            named = _PLACEHOLDER.sub(lambda match: nodes[match.group(1)].name, sentence)
            first = " (first)" if way.way_key == target.first_way_key else ""
            typer.echo(f"  {way.way_key}{first}: {named}")
            for need in way.needs:
                typer.echo("    " + _need(repository, need))
            if not way.needs:
                typer.echo("    no needs")

    typer.echo(_label(node))
    tier = "unreachable" if node.tier is None else str(node.tier)
    typer.echo(f"Kind {node.kind}. Tier {tier}. Build {repository.game_build_id}.")
    typer.echo("Playthrough order from new-character starts, not a save-state assessment.")
    key = node.stable_key
    typer.echo(f"Ways ({len(repository.get_ways(key))})")
    show_ways(node)
    if node.kind == "zone":
        door_keys = repository.zone_door_keys(key)
        if door_keys:
            typer.echo("Local doors")
            for door in door_keys:
                typer.echo(_label(nodes[door]))
                if repository.get_ways(door):
                    show_ways(nodes[door])
                else:
                    typer.echo("  no recorded way")
        exits = repository.gated_exit_ways(key)
        if exits:
            typer.echo("Gated exits")
            for destination, way_keys in exits.items():
                typer.echo(_label(nodes[destination]))
                show_ways(nodes[destination], way_keys)
    elif node.kind == "quest":
        deaths = repository.turn_in_deaths(key)
        if deaths:
            typer.echo("Turn-in deaths")
            for holder, variant in deaths:
                typer.echo(f"  {_label(nodes[holder])} (variant {variant})")
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
