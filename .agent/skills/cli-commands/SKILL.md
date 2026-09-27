---
name: cli-commands
description: Typer CLI conventions for this project — command groups, options, dry-run flags, and precondition checks. Use when adding or modifying a command or command group under src/erenshor/cli/commands/.
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

## Precondition coverage

Declare `@require_preconditions` on a command that writes files, changes a
database, publishes data, changes a game installation, or starts an external
process. Check the inputs that the command needs before any state changes.
Use a check in `cli/preconditions/checks/` and add a missing field to
`_build_check_context` when necessary. A check returns its real cause in
`PreconditionResult`. Remove the equivalent check from the command body so
one condition has one owner. Do not declare an empty precondition list.
For a command with an optional output, check the required inputs regardless
of whether the user chooses to write the output.

State-changing commands with declarations:

- `capture run`, `capture tile`
- `images process`, `images compare`, `images report --output`, `images upload`
- `extract compare-variants --output`, `extract changes --output`, `extract packages`, `extract rip`,
  `extract export`, `extract build`, `extract code-facts`, `extract ide-setup`
- `golden capture`
- `guide compile`, `guide export-mod`
- `maps dev`, `maps preview`, `maps check`, `maps build`, `maps deploy`,
  `maps thumbnails`
- `mod setup`, `mod dev-setup`, `mod build`, `mod activate`, `mod deploy`,
  `mod thunderstore`, `mod vault`, `mod launch`
- `sheets deploy`
- `wiki fetch`, `wiki generate-lua`, `wiki audit-links --output`,
  `wiki inventory-templates`, `wiki generate`, `wiki sync-interface`,
  `wiki deploy-interface`, `wiki rollback-interface`, `wiki deploy-repo-pages`,
  `wiki review-overrides --output`, `wiki refresh-embedded`,
  `wiki rollback-repo-pages`, `wiki deploy`
- `eval run` checks the code argument or source file before contacting the game.

The following commands deliberately have no declaration because they only
read and report state: `backup list`, `capture status`, `capture budget`,
`eval ping`, `eval complete`, `extract profile report`, `mod status`, and
`sheets list`. `extract compare-variants`, `extract changes`, `images report`,
`wiki audit-links`, and `wiki review-overrides` only read when no output
is requested, but retain declarations for their output mode.
`mod launch --inspect-pid` only reads, but shares the declaration with launch.

`eval reset` and `eval watch` change remote REPL state, but have no local
input dependency to check before connecting. The `test` commands run their
own task-graph preflight before starting subprocesses and must not repeat
those checks in the CLI decorator.

## Existing Commands

- `extract` - Download, rip, export pipeline
- `wiki` - Fetch, generate, deploy wiki pages
- `sheets` - Google Sheets deployment
- `maps` - Interactive maps dev/build/deploy
- `images` - Image processing and wiki upload
- `backup` - Backup management
- `mod` - Companion mod development (setup, build, deploy, launch)
