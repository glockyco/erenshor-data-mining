"""Quest guide generation CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext
app = typer.Typer(help="Quest guide generation and curation")


@app.command()
def generate(
    ctx: typer.Context,
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for merged quest-guide.json (default: quest_guides/quest-guide.json)",
    ),
    report: bool = typer.Option(
        True,
        help="Generate curation report",
    ),
    manual_dir: Path = typer.Option(
        None,
        "--manual-dir",
        help="Directory with manual override JSON files (default: quest_guides/manual/)",
    ),
) -> None:
    """Generate quest guide JSON from database.

    Reads the processed SQLite database, builds structured quest guide
    entries with auto-generated steps, merges with manual curation layer,
    and writes the final quest-guide.json.
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
        output = guides_dir / "quest-guide.json"
    if manual_dir is None:
        manual_dir = guides_dir / "manual"

    # Generate
    from erenshor.application.guide.generator import generate as gen_guides

    typer.echo(f"Reading quest data from {db_path}")
    auto_guides = gen_guides(db_path)
    typer.echo(f"Generated {len(auto_guides)} quest guide entries")

    # Merge
    from erenshor.application.guide.merge import generate_curation_report, merge_guides

    merged = merge_guides(auto_guides, manual_dir)

    # Write output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    typer.echo(f"Wrote {output} ({len(merged)} quests)")

    # Curation report
    if report:
        report_path = output.parent / "CURATION_REPORT.md"
        report_text = generate_curation_report(merged)
        report_path.write_text(report_text, encoding="utf-8")
        typer.echo(f"Wrote curation report: {report_path}")

        # Print summary to console
        lines = report_text.split("\n")
        for line in lines:
            if line.startswith("- **"):
                typer.echo(f"  {line}")
