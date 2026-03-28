"""Entity graph generation CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(help="Entity graph generation for the Adventure Guide mod")


@app.command()
def generate(
    ctx: typer.Context,
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for entity-graph.json (default: quest_guides/entity-graph.json)",
    ),
    overrides: Path = typer.Option(
        None,
        "--overrides",
        help="Path to graph_overrides.toml (default: quest_guides/graph_overrides.toml)",
    ),
) -> None:
    """Generate entity graph JSON from database.

    Reads the processed SQLite database, builds the entity graph with
    all nodes and edges, merges manual overrides, and writes the
    serialized graph for the Adventure Guide mod.
    """
    cli_ctx: CLIContext = ctx.obj

    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    db_path = variant_config.resolved_database(cli_ctx.repo_root)

    if not db_path.exists():
        typer.echo(f"Error: Database not found: {db_path}", err=True)
        raise typer.Exit(1)

    # Resolve paths
    guides_dir = cli_ctx.repo_root / "quest_guides"
    if output is None:
        output = guides_dir / "entity-graph.json"
    if overrides is None:
        overrides = guides_dir / "graph_overrides.toml"

    # Generate
    from erenshor.application.guide.generator import generate as gen_graph
    from erenshor.application.guide.serializer import graph_to_json

    typer.echo(f"Reading entity data from {db_path}")
    graph = gen_graph(db_path, overrides if overrides.exists() else None)
    typer.echo(f"Built graph: {graph.node_count} nodes, {graph.edge_count} edges")

    graph_to_json(graph, output)
    typer.echo(f"Wrote {output}")
