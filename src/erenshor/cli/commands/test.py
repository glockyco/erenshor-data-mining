"""Commands for running the repository's Python test suites.

The unit command deliberately selects the unit directory by path.  It does
not use pytest markers: a marker can be missing, stale, or accidentally
applied to a test owned by another verification task.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

app = typer.Typer(
    name="test",
    help="Run tests and validation",
    no_args_is_help=True,
)

console = Console()

# This module is also loaded as a pytest plugin for the unit command.  Keeping
# the report protocol here means later leaf commands can reuse the same
# process boundary without scraping terminal output.
_PYTEST_PLUGIN = "erenshor.cli.commands.test"
_REPORT_OPTION = "--erenshor-report"


class _PytestState:
    """Mutable state shared by pytest's module-level hooks."""

    config: Any | None = None


_pytest_state = _PytestState()


# The following hooks intentionally avoid importing pytest.  pytest loads this
# module with ``-p`` in a subprocess, while the normal CLI must remain
# importable when the optional development test dependencies are absent.
def pytest_addoption(parser: Any) -> None:
    """Register the private JSON report option used by the CLI runner."""
    group = parser.getgroup("erenshor")
    group.addoption(
        _REPORT_OPTION,
        action="store",
        default=None,
        help="Write the Erenshor machine-readable test report to this path.",
    )


def pytest_configure(config: Any) -> None:
    """Initialize per-session counters for the machine-readable report."""
    _pytest_state.config = config
    config._erenshor_deselected_nodeids = set()
    config._erenshor_skipped_nodeids = set()
    config._erenshor_failed_nodeids = set()


def pytest_deselected(items: list[Any]) -> None:
    """Record every deselected item without relying on terminal summaries."""
    # pytest exposes the active config only through the session hook objects;
    # attach the set to each item during collection so this hook stays valid
    # for pytest versions that do not pass config explicitly.
    for item in items:
        config = item.config
        config._erenshor_deselected_nodeids.add(item.nodeid)


def pytest_collectreport(report: Any) -> None:
    """Record collection-time skips as skipped tests."""
    if _pytest_state.config is None:
        return
    if report.outcome == "skipped":
        _pytest_state.config._erenshor_skipped_nodeids.add(report.nodeid)


def pytest_runtest_logreport(report: Any) -> None:
    """Record skipped and failed tests from structured pytest reports."""
    if _pytest_state.config is None:
        return
    if report.outcome == "skipped" and not getattr(report, "wasxfail", False):
        _pytest_state.config._erenshor_skipped_nodeids.add(report.nodeid)
    elif report.failed:
        _pytest_state.config._erenshor_failed_nodeids.add(report.nodeid)


def pytest_sessionfinish(session: Any, exitstatus: Any) -> None:
    """Persist a stable JSON summary at the end of a pytest session."""
    report_path = session.config.getoption("erenshor_report", default=None)
    if not report_path:
        return

    payload = {
        "schema": 1,
        "collected": int(session.testscollected),
        "deselected": len(session.config._erenshor_deselected_nodeids),
        "skipped": len(session.config._erenshor_skipped_nodeids),
        "failed": len(session.config._erenshor_failed_nodeids),
        "exit_code": int(getattr(session, "exitstatus", exitstatus)),
    }
    if int(exitstatus) == 0 and (
        session.testscollected == 0
        or session.config._erenshor_deselected_nodeids
        or session.config._erenshor_skipped_nodeids
    ):
        session.exitstatus = 1
        payload["exit_code"] = 1
    Path(report_path).write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _pytest_command(arguments: list[str], report_path: Path | None = None) -> list[str]:
    """Build the subprocess command shared by current and future leaf tasks."""
    command = ["uv", "run", "pytest", *arguments]
    if report_path is not None:
        command.extend(["-p", _PYTEST_PLUGIN, _REPORT_OPTION, str(report_path)])
    return command


def _run_pytest(
    cli_ctx: CLIContext,
    arguments: list[str],
    *,
    coverage: bool = False,
    require_complete: bool = False,
) -> None:
    """Run pytest and optionally enforce a complete, non-skipped collection.

    ``require_complete`` is intentionally a policy switch rather than a
    separate runner.  Future leaf commands can use the same machine-readable
    reporting seam while applying their own collection policy.
    """
    if coverage:
        arguments = [*arguments, "--cov", "--cov-report=term-missing"]

    with tempfile.TemporaryDirectory(prefix="erenshor-pytest-") as report_dir:
        report_path = Path(report_dir) / "report.json" if require_complete else None
        result = subprocess.run(
            _pytest_command(arguments, report_path),
            cwd=cli_ctx.repo_root,
            check=False,
        )

        if result.returncode != 0:
            raise typer.Exit(result.returncode)
        if not require_complete:
            return

        if report_path is None or not report_path.is_file():
            console.print("[red]Pytest did not produce its machine-readable report.[/red]")
            raise typer.Exit(1)

        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            console.print(f"[red]Unable to read the pytest report: {error}[/red]")
            raise typer.Exit(1) from error

        if not isinstance(report, dict):
            console.print("[red]The pytest report has an invalid JSON shape.[/red]")
            raise typer.Exit(1)

        try:
            collected = int(report.get("collected", 0))
            skipped = int(report.get("skipped", 0))
            deselected = int(report.get("deselected", 0))
            exit_code = int(report.get("exit_code", 1))
        except (TypeError, ValueError) as error:
            console.print(f"[red]The pytest report has invalid counters: {error}[/red]")
            raise typer.Exit(1) from error

        violations: dict[str, int] = {}
        if collected == 0:
            violations["collected"] = collected
        if skipped > 0:
            violations["skipped"] = skipped
        if deselected > 0:
            violations["deselected"] = deselected
        if violations or exit_code != 0:
            details = ", ".join(f"{name}={value}" for name, value in violations.items())
            if exit_code != 0:
                details = f"{details}, exit_code={exit_code}" if details else f"exit_code={exit_code}"
            console.print(f"[red]Unit test verification failed ({details}).[/red]")
            raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def test_callback(
    ctx: typer.Context,
    coverage: bool = typer.Option(
        False,
        "--coverage",
        help="Generate coverage report",
    ),
) -> None:
    """Run all tests.

    Executes the complete test suite. Optionally generates a coverage report.
    Purpose-specific leaf commands provide stricter environment and collection
    guarantees.
    """
    if ctx.invoked_subcommand is None:
        cli_ctx: CLIContext = ctx.obj
        console.print()
        console.print("[bold cyan]Running all tests...[/bold cyan]")
        console.print()
        _run_pytest(cli_ctx, [], coverage=coverage)


@app.command("integration")
def test_integration(
    ctx: typer.Context,
    coverage: bool = typer.Option(
        False,
        "--coverage",
        help="Generate coverage report",
    ),
) -> None:
    """Run integration tests selected by the integration pytest marker."""
    cli_ctx: CLIContext = ctx.obj
    console.print()
    console.print("[bold cyan]Running integration tests...[/bold cyan]")
    console.print()
    _run_pytest(cli_ctx, ["-m", "integration"], coverage=coverage)


@app.command("unit")
def test_unit(
    ctx: typer.Context,
    coverage: bool = typer.Option(
        False,
        "--coverage",
        help="Generate coverage report",
    ),
) -> None:
    """Run unit tests from the tests/unit directory.

    The command fails if pytest collects no tests, skips a test, or deselects
    an item.  This protects the command from silently passing after marker or
    collection configuration changes.
    """
    cli_ctx: CLIContext = ctx.obj
    console.print()
    console.print("[bold cyan]Running unit tests...[/bold cyan]")
    console.print()
    _run_pytest(cli_ctx, ["tests/unit"], coverage=coverage, require_complete=True)


__all__ = ["app"]
