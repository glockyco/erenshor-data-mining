"""Selected publication inputs are checked before local preparation writes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from erenshor.application.publish.models import load_selection
from erenshor.cli.preconditions.base import PreconditionCheck, PreconditionResult
from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid
from erenshor.cli.preconditions.checks.inputs import program_available, required_path
from erenshor.cli.preconditions.checks.maps import cloudflare_auth_configured, no_static_database_files
from erenshor.cli.preconditions.checks.wiki import wiki_endpoint


def preparation_inputs(context: dict[str, Any]) -> PreconditionResult:
    """Validate selected owners before creating any run artifact."""
    from erenshor.application.publish.coordinator import run_directory

    try:
        selection = load_selection(Path(context["selection"]))
        run_dir = run_directory(context["cli_ctx"], Path(context["output"]))
        if run_dir.exists():
            raise ValueError(f"Choose a new output directory: {run_dir}")
        checks: list[PreconditionCheck] = [database_exists, database_valid, database_has_items]
        if selection.wiki:
            checks.append(wiki_endpoint)
        if selection.maps and selection.maps.targets:
            checks.extend(
                [
                    no_static_database_files,
                    program_available("pnpm"),
                    program_available("node"),
                    required_path("maps_source_dir", kind="directory"),
                    required_path("maps_source_dir", "node_modules", kind="directory"),
                    cloudflare_auth_configured,
                ]
            )
        failures = [str(result) for check in checks if not (result := check(context)).passed]
        if failures:
            return PreconditionResult(
                False, "preparation_inputs", "Selected publication inputs are unavailable", "\n".join(failures)
            )
        return PreconditionResult(True, "preparation_inputs", "Selected publication inputs are available")
    except (ValueError, OSError) as error:
        return PreconditionResult(False, "preparation_inputs", str(error))


def prepared_plan(context: dict[str, Any]) -> PreconditionResult:
    """Read and validate the immutable plan before opening an execution lock."""
    from erenshor.application.publish.coordinator import load_plan, run_directory

    try:
        path = Path(context["plan"])
        cli_ctx = context["cli_ctx"]
        load_plan(path, cli_ctx)
        run_directory(cli_ctx, path.parent)
        return PreconditionResult(True, "prepared_plan", "Prepared plan is available for guarded inspection")
    except (ValueError, OSError) as error:
        return PreconditionResult(False, "prepared_plan", str(error))
