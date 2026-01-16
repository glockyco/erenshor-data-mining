---
name: adding-cli-commands
description: Add new CLI commands to the erenshor tool. Use when creating new Typer commands, subcommands, or extending the command-line interface.
---

# Adding New CLI Commands

The CLI uses Typer. Commands live in `src/erenshor/cli/commands/`.

## Steps

1. **Create command file**: `src/erenshor/cli/commands/mycommand.py`

```python
import typer
from typing_extensions import Annotated

app = typer.Typer(help="My command group")


@app.command()
def action(
    variant: Annotated[str, typer.Option(help="Game variant")] = "main",
    dry_run: Annotated[bool, typer.Option(help="Preview only")] = False,
) -> None:
    """Perform my action."""
    typer.echo(f"Running on {variant}")
    if dry_run:
        typer.echo("Dry run - no changes made")
```

2. **Register in main.py**: `src/erenshor/cli/main.py`

```python
from erenshor.cli.commands import mycommand

app.add_typer(mycommand.app, name="mycommand")
```

3. **Test**: `uv run erenshor mycommand action --help`

## Common Patterns

**Variant option** (most commands need this):
```python
variant: Annotated[str, typer.Option(help="Game variant")] = "main"
```

**Using the database** (via repositories):
```python
from erenshor.cli.context import CLIContext
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.items import ItemRepository

@app.command()
def action(ctx: typer.Context) -> None:
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    db_path = variant_config.resolved_database(cli_ctx.repo_root)
    db_connection = DatabaseConnection(db_path, read_only=True)
    item_repo = ItemRepository(db_connection)
    # Use repository methods
```

**Precondition checks** (decorator pattern):
```python
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_valid

@app.command()
@require_preconditions(database_exists, database_valid)
def action(ctx: typer.Context) -> None:
    # Checks run automatically before command executes
    cli_ctx: CLIContext = ctx.obj
    # ... rest of command
```

## Existing Commands

- `extract` - Download, rip, export pipeline
- `wiki` - Fetch, generate, deploy wiki pages
- `sheets` - Google Sheets deployment
- `maps` - Interactive maps dev/build/deploy
- `images` - Image processing and wiki upload
- `backup` - Backup management
- `mod` - Companion mod development (setup, build, deploy, launch)
