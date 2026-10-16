"""Adventure Guide data commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_valid
from erenshor.cli.preconditions.checks.inputs import option_path

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(help="Adventure Guide data commands")


@app.command("export-mod")
@require_preconditions(database_exists, database_valid, option_path("overrides"))
def export_mod(
    ctx: typer.Context,
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for quest-guide.json (default: quest_guides/quest-guide.json)",
    ),
    overrides: Path = typer.Option(
        None,
        "--overrides",
        help="Path to graph_overrides.toml (default: quest_guides/graph_overrides.toml)",
    ),
) -> None:
    """Export the quest data that the Adventure Guide mod embeds.

    Reads the processed SQLite database, builds the entity graph, compiles it
    once, and writes quest-guide.json.
    """
    cli_ctx: CLIContext = ctx.obj

    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    db_path = variant_config.resolved_database(cli_ctx.repo_root)

    guides_dir = cli_ctx.repo_root / "quest_guides"
    if output is None:
        output = guides_dir / "quest-guide.json"
    if overrides is None:
        overrides = guides_dir / "graph_overrides.toml"

    from erenshor.application.guide.compiler import compile_graph
    from erenshor.application.guide.generator import generate as gen_graph
    from erenshor.application.guide.graph_builder import excluded_quest_db_names
    from erenshor.application.guide.mod_writer import serialize_mod_guide

    typer.echo(f"Reading entity data from {db_path}")
    graph = gen_graph(db_path, overrides if overrides.exists() else None)
    typer.echo(f"Built graph: {graph.node_count} nodes, {graph.edge_count} edges")

    compiled = compile_graph(graph)
    text = serialize_mod_guide(graph, compiled, excluded_quest_db_names(db_path))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    typer.echo(f"Wrote {output} ({len(text.encode('utf-8')):,} bytes, {len(compiled.quest_node_ids)} quests)")
