"""Adventure Guide compiled guide commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(help="Adventure Guide compiled guide commands")


@app.command()
def compile(
    ctx: typer.Context,
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for guide.json (default: quest_guides/guide.json)",
    ),
    overrides: Path = typer.Option(
        None,
        "--overrides",
        help="Path to graph_overrides.toml (default: quest_guides/graph_overrides.toml)",
    ),
) -> None:
    """Compile entity graph to JSON guide format.

    Reads the processed SQLite database, builds the entity graph,
    compiles it into the dense indexed format consumed by the
    AdventureGuide mod, and writes guide.json.
    """
    cli_ctx: CLIContext = ctx.obj

    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    db_path = variant_config.resolved_database(cli_ctx.repo_root)

    if not db_path.exists():
        typer.echo(f"Error: Database not found: {db_path}", err=True)
        raise typer.Exit(1)

    guides_dir = cli_ctx.repo_root / "quest_guides"
    if output is None:
        output = guides_dir / "guide.json"
    if overrides is None:
        overrides = guides_dir / "graph_overrides.toml"

    from erenshor.application.guide.compiler import compile_graph
    from erenshor.application.guide.generator import generate as gen_graph
    from erenshor.application.guide.json_writer import serialize

    typer.echo(f"Reading entity data from {db_path}")
    graph = gen_graph(db_path, overrides if overrides.exists() else None)
    typer.echo(f"Built graph: {graph.node_count} nodes, {graph.edge_count} edges")

    compiled = compile_graph(graph)
    text = serialize(compiled)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    typer.echo(
        f"Wrote {output} ({len(text.encode('utf-8')):,} bytes, "
        f"{len(compiled.quest_node_ids)} quests, "
        f"{len(compiled.item_node_ids)} items)"
    )
