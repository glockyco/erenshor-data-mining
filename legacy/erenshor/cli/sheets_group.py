"""Google Sheets deployment CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from erenshor.application.services.sheets_deploy_service import (
    SheetsDeployService,
)
from erenshor.infrastructure.config.toml_loader import load_config
from erenshor.infrastructure.database.repositories import get_engine
from erenshor.infrastructure.publishers.sheets import GoogleSheetsPublisher

__all__ = ["app"]


app = typer.Typer(help="Google Sheets deployment")


@app.command("deploy")
def deploy(
    variant: str = typer.Option("main", help="Variant to deploy (main/playtest/demo)"),
    sheets: list[str] = typer.Option(
        None,
        "--sheet",
        help="Specific sheets to deploy (can be used multiple times)",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without uploading"),
    credentials: Path | None = typer.Option(
        None, "--credentials", help="Path to Google credentials JSON file"
    ),
) -> None:
    """Deploy sheets to Google Sheets.

    Examples:
        # Deploy all sheets for main variant
        erenshor-wiki sheets deploy

        # Deploy specific sheets
        erenshor-wiki sheets deploy --sheet items --sheet characters

        # Dry run (preview without uploading)
        erenshor-wiki sheets deploy --dry-run

        # Deploy playtest variant
        erenshor-wiki sheets deploy --variant playtest
    """
    console = Console()

    # Load configuration
    config = load_config()

    # Get variant configuration
    variant_config = config.get_variant_config(variant)
    if not variant_config:
        console.print(f"[red]Error: Variant '{variant}' not found in config.toml[/red]")
        console.print("\n[yellow]Available variants:[/yellow] main, playtest, demo")
        raise typer.Exit(1)

    # Check if variant is enabled
    if not variant_config.get("enabled", False):
        console.print(
            f"[yellow]Warning: Variant '{variant}' is disabled in config.toml[/yellow]"
        )
        console.print(
            "Enable it by setting [bold]variants.{variant}.enabled = true[/bold] in config.toml or config.local.toml"
        )
        raise typer.Exit(1)

    # Get database path
    db_path = Path(variant_config.get("database", ""))
    if not db_path or str(db_path) == "" or not db_path.exists():
        console.print(
            f"[red]Error: Database not found for variant '{variant}': {db_path}[/red]"
        )
        console.print("\n[yellow]Run the export pipeline first:[/yellow]")
        console.print(f"  erenshor export --variant {variant}")
        raise typer.Exit(1)

    # Get Google Sheets configuration
    google_sheets_config = variant_config.get("google_sheets", {})
    spreadsheet_id = google_sheets_config.get("spreadsheet_id")

    if not spreadsheet_id:
        console.print(
            f"[red]Error: No Google Sheets spreadsheet_id configured for variant '{variant}'[/red]"
        )
        console.print("\n[yellow]Add spreadsheet_id to config.toml:[/yellow]")
        console.print(f"  [variants.{variant}.google_sheets]")
        console.print('  spreadsheet_id = "your_spreadsheet_id_here"')
        raise typer.Exit(1)

    # Get credentials file path
    if credentials is None:
        global_config = config.get_global_config("google_sheets")
        credentials_path_str = global_config.get("credentials_file", "")
        if not credentials_path_str:
            console.print(
                "[red]Error: No Google Sheets credentials file configured[/red]"
            )
            console.print(
                "\n[yellow]Add credentials_file to config.toml or use --credentials flag[/yellow]"
            )
            console.print("  [global.google_sheets]")
            console.print(
                '  credentials_file = "$HOME/.config/erenshor/google-credentials.json"'
            )
            raise typer.Exit(1)

        # Expand path
        credentials_path_str = credentials_path_str.replace("$HOME", str(Path.home()))
        credentials = Path(credentials_path_str)

    if not credentials.exists():
        console.print(f"[red]Error: Credentials file not found: {credentials}[/red]")
        console.print("\n[yellow]Get credentials from Google Cloud Console:[/yellow]")
        console.print("  1. Go to https://console.cloud.google.com/")
        console.print("  2. Create a service account with Google Sheets API access")
        console.print("  3. Download JSON credentials file")
        console.print(f"  4. Save to: {credentials}")
        raise typer.Exit(1)

    # Initialize components
    engine = get_engine(db_path)
    queries_dir = (
        Path(__file__).parent.parent
        / "application"
        / "formatters"
        / "sheets"
        / "queries"
    )

    try:
        publisher = GoogleSheetsPublisher(credentials)
    except Exception as e:
        console.print(f"[red]Error initializing Google Sheets publisher: {e}[/red]")
        raise typer.Exit(1)

    service = SheetsDeployService(
        engine=engine,
        queries_dir=queries_dir,
        publisher=publisher,
    )

    # Test connection first
    console.print("[dim]Testing Google Sheets API connection...[/dim]")
    try:
        service.test_connection()
    except Exception as e:
        console.print(f"[red]Error: Failed to connect to Google Sheets API: {e}[/red]")
        console.print("\n[yellow]Check:[/yellow]")
        console.print("  - Credentials file is valid")
        console.print("  - Service account has access to the spreadsheet")
        console.print("  - Google Sheets API is enabled in Google Cloud Console")
        raise typer.Exit(1)
    console.print("[green]✓[/green] Connected to Google Sheets API\n")

    # Determine which sheets to deploy
    if sheets:
        sheet_names = sheets
    else:
        sheet_names = service.get_available_sheets()

    # Validate sheet names
    available_sheets = service.get_available_sheets()
    invalid_sheets = [s for s in sheet_names if s not in available_sheets]
    if invalid_sheets:
        console.print(
            f"[red]Error: Invalid sheet names: {', '.join(invalid_sheets)}[/red]"
        )
        console.print(
            f"\n[yellow]Available sheets:[/yellow] {', '.join(available_sheets)}"
        )
        raise typer.Exit(1)

    # Show deployment info
    console.print("[bold cyan]Google Sheets Deployment[/bold cyan]")
    console.print(f"Variant:       [yellow]{variant}[/yellow]")
    console.print(f"Database:      [dim]{db_path}[/dim]")
    console.print(f"Spreadsheet:   [dim]{spreadsheet_id}[/dim]")
    console.print(f"Sheets:        {', '.join(sheet_names)}")
    console.print(f"Dry run:       [yellow]{dry_run}[/yellow]")
    console.print()

    # Deploy with progress bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
        task_id = progress.add_task(
            f"Deploying {len(sheet_names)} sheets", total=len(sheet_names)
        )

        def progress_callback(sheet_name: str, idx: int, total: int) -> None:
            progress.update(
                task_id,
                advance=1,
                description=f"Deploying: {sheet_name} ({idx}/{total})",
            )

        result = service.deploy_all(
            spreadsheet_id=spreadsheet_id,
            sheet_names=sheet_names,
            dry_run=dry_run,
            progress_callback=progress_callback,
        )

    # Display results
    _display_deployment_summary(result, dry_run, console)

    # Exit with error code if any failures
    if not result.success:
        raise typer.Exit(1)


@app.command("list")
def list_sheets() -> None:
    """List all available sheet queries.

    Shows all .sql query files in the queries directory.
    """
    console = Console()

    # Get queries directory
    queries_dir = (
        Path(__file__).parent.parent
        / "application"
        / "formatters"
        / "sheets"
        / "queries"
    )

    if not queries_dir.exists():
        console.print(f"[red]Error: Queries directory not found: {queries_dir}[/red]")
        raise typer.Exit(1)

    # Get all SQL files
    sql_files = sorted(queries_dir.glob("*.sql"))

    if not sql_files:
        console.print(f"[yellow]No query files found in {queries_dir}[/yellow]")
        raise typer.Exit(0)

    # Display table
    table = Table(title=f"Available Sheets ({len(sql_files)} total)")
    table.add_column("Sheet Name", style="cyan", no_wrap=True)
    table.add_column("Query File", style="dim")

    for sql_file in sql_files:
        sheet_name = sql_file.stem
        table.add_row(sheet_name, sql_file.name)

    console.print(table)
    console.print(f"\n[dim]Query directory: {queries_dir}[/dim]")


@app.command("validate")
def validate(
    variant: str = typer.Option("main", help="Variant to validate"),
) -> None:
    """Validate Google Sheets configuration.

    Checks:
    - Credentials file exists and is valid
    - Spreadsheet ID is configured
    - API connection works
    - Service account has access to spreadsheet
    """
    console = Console()

    # Load configuration
    config = load_config()

    console.print("[bold cyan]Google Sheets Configuration Validation[/bold cyan]\n")

    # Check variant configuration
    variant_config = config.get_variant_config(variant)
    if not variant_config:
        console.print(f"[red]✗[/red] Variant '{variant}' not found in config.toml")
        console.print("[yellow]Available variants:[/yellow] main, playtest, demo")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Variant '{variant}' found in config.toml")

    # Check if variant is enabled
    if not variant_config.get("enabled", False):
        console.print(f"[yellow]⚠[/yellow] Variant '{variant}' is disabled")
    else:
        console.print(f"[green]✓[/green] Variant '{variant}' is enabled")

    # Check spreadsheet ID
    google_sheets_config = variant_config.get("google_sheets", {})
    spreadsheet_id = google_sheets_config.get("spreadsheet_id")

    if not spreadsheet_id:
        console.print("[red]✗[/red] No spreadsheet_id configured")
        console.print("\n[yellow]Add to config.toml:[/yellow]")
        console.print(f"  [variants.{variant}.google_sheets]")
        console.print('  spreadsheet_id = "your_spreadsheet_id_here"')
        raise typer.Exit(1)

    console.print(
        f"[green]✓[/green] Spreadsheet ID configured: [dim]{spreadsheet_id}[/dim]"
    )

    # Check credentials file
    global_config = config.get_global_config("google_sheets")
    credentials_path_str = global_config.get("credentials_file", "")

    if not credentials_path_str:
        console.print("[red]✗[/red] No credentials_file configured")
        console.print("\n[yellow]Add to config.toml:[/yellow]")
        console.print("  [global.google_sheets]")
        console.print(
            '  credentials_file = "$HOME/.config/erenshor/google-credentials.json"'
        )
        raise typer.Exit(1)

    # Expand path
    credentials_path_str = credentials_path_str.replace("$HOME", str(Path.home()))
    credentials = Path(credentials_path_str)

    if not credentials.exists():
        console.print(f"[red]✗[/red] Credentials file not found: {credentials}")
        console.print("\n[yellow]Get credentials from Google Cloud Console:[/yellow]")
        console.print("  1. Go to https://console.cloud.google.com/")
        console.print("  2. Create a service account with Google Sheets API access")
        console.print("  3. Download JSON credentials file")
        console.print(f"  4. Save to: {credentials}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Credentials file exists: [dim]{credentials}[/dim]")

    # Test API connection
    console.print("\n[dim]Testing Google Sheets API connection...[/dim]")

    try:
        publisher = GoogleSheetsPublisher(credentials)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to initialize publisher: {e}")
        raise typer.Exit(1)

    console.print("[green]✓[/green] Publisher initialized successfully")

    try:
        publisher.test_connection()
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to connect to Google Sheets API: {e}")
        console.print("\n[yellow]Check:[/yellow]")
        console.print("  - Credentials file is valid JSON")
        console.print("  - Service account exists in Google Cloud Console")
        console.print("  - Google Sheets API is enabled")
        raise typer.Exit(1)

    console.print("[green]✓[/green] Connected to Google Sheets API")

    # Try to access the spreadsheet
    console.print("\n[dim]Testing spreadsheet access...[/dim]")

    try:
        # Test by attempting to get spreadsheet metadata
        from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

        service = publisher.service
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        title = spreadsheet.get("properties", {}).get("title", "Unknown")

        console.print(
            f"[green]✓[/green] Read access granted to spreadsheet: [bold]{title}[/bold]"
        )

        # Test write permissions by attempting a harmless batchUpdate
        # This will fail if we only have Viewer access
        console.print("[dim]Testing write permissions...[/dim]")

        try:
            # Try to perform a harmless batchUpdate that doesn't change anything
            # This requires Editor permissions
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": []
                },  # Empty request - does nothing but requires Editor
            ).execute()

            console.print(
                "[green]✓[/green] Write access confirmed (Editor permissions)"
            )

        except HttpError as e:
            if e.status_code == 403:
                console.print(
                    "[red]✗[/red] No write access to spreadsheet (Viewer permissions only)"
                )
                console.print("\n[yellow]Fix:[/yellow]")
                console.print("  1. Open the spreadsheet in Google Sheets")
                console.print(f"     {spreadsheet_id}")
                console.print("  2. Click 'Share' button")
                console.print(
                    "  3. Find the service account email in your credentials file:"
                )
                console.print(f"     [dim]grep client_email {credentials}[/dim]")
                console.print("  4. If the service account is already shared:")
                console.print("     - Click the dropdown next to their email")
                console.print("     - Change from 'Viewer' to 'Editor'")
                console.print("  5. If not shared yet:")
                console.print("     - Add service account email")
                console.print("     - Grant 'Editor' permissions (not 'Viewer')")
                raise typer.Exit(1)

    except HttpError as e:
        if e.status_code == 404:
            console.print(f"[red]✗[/red] Spreadsheet not found: {spreadsheet_id}")
            console.print("\n[yellow]Check:[/yellow]")
            console.print("  - Spreadsheet ID is correct")
            console.print("  - Spreadsheet exists")
        elif e.status_code == 403:
            console.print(
                f"[red]✗[/red] Access denied to spreadsheet: {spreadsheet_id}"
            )
            console.print("\n[yellow]Fix:[/yellow]")
            console.print("  1. Open the spreadsheet in Google Sheets")
            console.print("  2. Click 'Share' button")
            console.print("  3. Add service account email with Editor permissions")
            console.print("     (Find email in credentials JSON: 'client_email' field)")
        else:
            console.print(f"[red]✗[/red] Error accessing spreadsheet: {e}")

        raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        raise typer.Exit(1)

    # All checks passed
    console.print("\n[bold green]✓ All validation checks passed![/bold green]")
    console.print("\n[dim]Ready to deploy sheets with:[/dim]")
    console.print(f"  erenshor-wiki sheets deploy --variant {variant}")


def _display_deployment_summary(
    result: Any,
    dry_run: bool,
    console: Console,
) -> None:
    """Display rich summary table after deployment.

    Args:
        result: DeploymentResult instance
        dry_run: Whether this was a dry run
        console: Rich console for output
    """
    # Summary table
    table = Table(title="Deployment Complete" if not dry_run else "Dry Run Complete")
    table.add_column("Metric")
    table.add_column("Value", style="cyan")

    table.add_row("Total Sheets", str(result.total_sheets))

    success_pct = (
        result.successful_sheets / result.total_sheets * 100
        if result.total_sheets > 0
        else 0
    )
    table.add_row(
        "Successful",
        f"[green]{result.successful_sheets} ({success_pct:.1f}%)[/green]",
    )

    failed_pct = (
        result.failed_sheets / result.total_sheets * 100
        if result.total_sheets > 0
        else 0
    )
    table.add_row(
        "Failed",
        f"[red]{result.failed_sheets} ({failed_pct:.1f}%)[/red]",
    )

    console.print()
    console.print(table)

    # Detailed results
    if result.deployments:
        console.print("\n[bold]Sheet Details:[/bold]")
        details_table = Table(show_header=True, box=None)
        details_table.add_column("Sheet", style="cyan")
        details_table.add_column("Rows", justify="right")
        details_table.add_column("Status")

        for deployment in result.deployments:
            status = (
                "[green]✓ Success[/green]"
                if deployment.success
                else f"[red]✗ {deployment.error}[/red]"
            )
            details_table.add_row(
                deployment.sheet_name,
                str(deployment.row_count),
                status,
            )

        console.print(details_table)

    # Spreadsheet link
    if not dry_run:
        console.print(
            f"\n[dim]View spreadsheet: https://docs.google.com/spreadsheets/d/{result.spreadsheet_id}/edit[/dim]"
        )
