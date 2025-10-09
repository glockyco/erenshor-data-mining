"""CLI entrypoint."""

from __future__ import annotations

import typer

from .commands.check_paths import check_paths
from .commands.update import app as update_app
from .db_group import app as db_app
from .mapping_group import app as mapping_app
from .sheets_group import app as sheets_app
from .wiki_group import app as wiki_app

__all__ = ["main"]


app = typer.Typer(help="Erenshor Wiki CLI")
app.add_typer(db_app, name="db")
app.add_typer(mapping_app, name="mapping")
app.add_typer(sheets_app, name="sheets")
app.add_typer(wiki_app, name="wiki")
app.add_typer(update_app, name="update")
app.command("check-paths")(check_paths)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
