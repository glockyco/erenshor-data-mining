"""Canonical verification task commands.

The command owns the repository verification DAG and keeps each leaf's
preconditions, process boundary, and machine-readable result in one place.
Pytest is loaded as a plugin in its own process so collection policy is based on
pytest's structured hooks rather than terminal output.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, TypeGuard, cast

import typer
from rich.console import Console

from erenshor.application.mods.artifacts import format_artifact_issues, verify_static_mod_artifacts
from erenshor.cli.commands import maps
from erenshor.cli.commands.mod import _artifact_specs

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext


class _VariantWithMaps(Protocol):
    maps: object


app = typer.Typer(
    name="test",
    help="Run canonical verification tasks",
    no_args_is_help=False,
)

console = Console()

# This module is also loaded as a pytest plugin.  The plugin is deliberately
# dependency-free so importing the CLI does not require pytest itself.
_PYTEST_PLUGIN = "erenshor.cli.commands.test"
_REPORT_OPTION = "--erenshor-report"
_REPORT_SCHEMA = 1
_REPORT_DIRECTORY = Path("artifacts/test-reports")
_WIKI_BASE_URL = "http://localhost:8088"


@dataclass(frozen=True)
class _ContractNativeTestProject:
    name: str
    key: str
    project: Path


_CONTRACT_NATIVE_TEST_PROJECTS: tuple[_ContractNativeTestProject, ...] = (
    _ContractNativeTestProject(
        name="CodeFacts",
        key="codefacts",
        project=Path("src/tools/CodeFacts/tests/CodeFacts.Tests/CodeFacts.Tests.csproj"),
    ),
    _ContractNativeTestProject(
        name="ExportSurface",
        key="exportsurface",
        project=Path("src/tools/ExportSurface/tests/ExportSurface.Tests/ExportSurface.Tests.csproj"),
    ),
)


class TaskGraphError(ValueError):
    """Raised when a requested verification task cannot be expanded."""


# Ordered tuples are part of the public verification contract.  Do not turn
# these into sets: CI reports and execution order must be stable.
TASKS: Mapping[str, tuple[str, ...]] = {
    "unit": (),
    "contract": (),
    "data": (),
    "wiki": (),
    "maps": (),
    "mods": (),
    "ci": ("unit", "contract", "maps", "mods"),
    "release": ("ci", "data", "wiki"),
}
LEAF_TASKS = ("unit", "contract", "data", "wiki", "maps", "mods")
COMPOSITE_TASKS = ("ci", "release")


@dataclass(frozen=True)
class _Preflight:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class _CommandResult:
    argv: tuple[str, ...]
    cwd: Path
    exit_code: int
    duration_seconds: float


class _PrerequisiteJson(TypedDict):
    name: str
    status: str
    detail: str


class _PytestCounts(TypedDict, total=False):
    collected: int
    deselected: int
    skipped: int
    failed: int
    exit_code: int


class _CompletePytestCounts(TypedDict):
    collected: int
    deselected: int
    skipped: int
    failed: int
    exit_code: int


class _TrxReportedCounters(TypedDict, total=False):
    executed: int
    failed: int
    skipped: int
    notExecuted: int


class _TrxCounts(TypedDict, total=False):
    executed: int
    failed: int
    skipped: int
    not_executed: int


class _CompleteTrxCounts(TypedDict):
    executed: int
    failed: int
    skipped: int
    not_executed: int


@dataclass
class _LeafResult:
    task_id: str
    status: str
    exit_code: int
    duration_seconds: float
    prerequisites: list[_PrerequisiteJson]
    result_counts: Mapping[str, object]
    commands: list[dict[str, object]]
    diagnostics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _NativeTestResult:
    command: _CommandResult
    result_counts: Mapping[str, object]
    status: str
    exit_code: int
    diagnostics: dict[str, object]


class _PytestState:
    """Mutable state shared by pytest's module-level hooks."""

    config: Any | None = None


_pytest_state = _PytestState()


# ----------------------------- pytest plugin -----------------------------


def pytest_addoption(parser: Any) -> None:
    """Register the private JSON report option used by pytest runners."""
    group = parser.getgroup("erenshor")
    group.addoption(
        _REPORT_OPTION,
        action="store",
        default=None,
        help="Write the Erenshor machine-readable test report to this path.",
    )


def pytest_configure(config: Any) -> None:
    """Initialize per-session counters for the structured report."""
    _pytest_state.config = config
    config._erenshor_deselected_nodeids = set()
    config._erenshor_skipped_nodeids = set()
    config._erenshor_failed_nodeids = set()


def pytest_unconfigure(config: Any) -> None:
    """Release the process-local plugin state after pytest exits."""
    if _pytest_state.config is config:
        _pytest_state.config = None


def pytest_deselected(items: list[Any]) -> None:
    """Record every deselected item without scraping pytest output."""
    for item in items:
        item.config._erenshor_deselected_nodeids.add(item.nodeid)


def pytest_collectreport(report: Any) -> None:
    """Record collection-time skips as skipped tests."""
    config = _pytest_state.config
    if config is not None and report.outcome == "skipped":
        config._erenshor_skipped_nodeids.add(report.nodeid)


def pytest_runtest_logreport(report: Any) -> None:
    """Record skipped and failed tests from structured pytest reports."""
    config = _pytest_state.config
    if config is None:
        return
    if report.outcome == "skipped" and not getattr(report, "wasxfail", False):
        config._erenshor_skipped_nodeids.add(report.nodeid)
    elif report.failed:
        config._erenshor_failed_nodeids.add(report.nodeid)


def pytest_sessionfinish(session: Any, exitstatus: Any) -> None:
    """Persist the pytest collection and result counters as JSON."""
    report_path = session.config.getoption("erenshor_report", default=None)
    if not report_path:
        return

    payload = {
        "schema": _REPORT_SCHEMA,
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

    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


# ------------------------------- graph -----------------------------------


def expand_tasks(requested: str | Iterable[str]) -> list[str]:
    """Expand task IDs depth-first, preserving declaration order once each.

    Unknown IDs and cycles are errors instead of silently shrinking a gate.
    Accepting an iterable is useful for callers composing several requested
    tasks while the CLI itself exposes one requested ID per invocation.
    """
    ids = [requested] if isinstance(requested, str) else list(requested)
    expanded: list[str] = []
    visited: set[str] = set()
    visiting: list[str] = []

    def visit(task_id: str) -> None:
        if task_id not in TASKS:
            raise TaskGraphError(f"Unknown verification task: {task_id}")
        if task_id in visiting:
            cycle = " -> ".join([*visiting, task_id])
            raise TaskGraphError(f"Verification task cycle detected: {cycle}")
        if task_id in visited:
            return

        visiting.append(task_id)
        for child in TASKS[task_id]:
            visit(child)
        visiting.pop()
        visited.add(task_id)
        if task_id in LEAF_TASKS:
            expanded.append(task_id)

    for task_id in ids:
        visit(task_id)
    return expanded


# --------------------------- path/config helpers --------------------------


def _path_value(value: object, repo_root: Path) -> Path:
    """Resolve a configured path while supporting lightweight test contexts."""
    raw = str(value).replace("$REPO_ROOT", str(repo_root)).replace("${REPO_ROOT}", str(repo_root))
    path = Path(raw).expanduser()
    return path if path.is_absolute() else repo_root / path


def _configured_path(config: object, method_name: str, field_name: str, repo_root: Path) -> Path:
    method = getattr(config, method_name, None)
    if callable(method):
        return Path(method(repo_root))
    return _path_value(getattr(config, field_name), repo_root)


def _variant(cli_ctx: CLIContext, name: str | None = None) -> object:
    variant_name = name or cli_ctx.variant
    config = getattr(cli_ctx, "config", None)
    variants = getattr(config, "variants", None)
    if not isinstance(variants, Mapping) or variant_name not in variants:
        raise KeyError(f"Configured variant is missing: {variant_name}")
    return variants[variant_name]


def _main_data_paths(cli_ctx: CLIContext) -> tuple[Path, Path, Path]:
    main = _variant(cli_ctx, "main")
    root = cli_ctx.repo_root
    clean = _configured_path(main, "resolved_database", "database", root)
    raw = _configured_path(main, "resolved_database_raw", "database_raw", root)
    game = _configured_path(main, "resolved_game_files", "game_files", root)
    assembly = game / "Erenshor_Data" / "Managed" / "Assembly-CSharp.dll"
    return clean, raw, assembly


def _maps_paths(cli_ctx: CLIContext) -> tuple[Path, Path]:
    variant = cast("_VariantWithMaps", _variant(cli_ctx))
    maps = variant.maps
    root = cli_ctx.repo_root
    source = _configured_path(maps, "resolved_source_dir", "source_dir", root)
    return source, source / "node_modules"


# ------------------------------ preflights --------------------------------


def _executable(name: str) -> _Preflight:
    path = shutil.which(name)
    return _Preflight(name=f"executable:{name}", ok=path is not None, detail=path or f"{name} is not on PATH")


def _directory(path: Path, label: str) -> _Preflight:
    return _Preflight(name=label, ok=path.is_dir(), detail=str(path))


def _file(path: Path, label: str) -> _Preflight:
    return _Preflight(name=label, ok=path.is_file(), detail=str(path))


def _preflight_unit(cli_ctx: CLIContext) -> list[_Preflight]:
    return [_executable("uv"), _directory(cli_ctx.repo_root / "tests/unit", "tests/unit")]


def _preflight_contract(cli_ctx: CLIContext) -> list[_Preflight]:
    checks = [
        _executable("uv"),
        _executable("dotnet"),
        _directory(cli_ctx.repo_root / "tests/contract", "tests/contract"),
    ]
    checks.extend(
        _file(cli_ctx.repo_root / project.project, f"{project.name} native test project")
        for project in _CONTRACT_NATIVE_TEST_PROJECTS
    )
    return checks


def _preflight_data(cli_ctx: CLIContext) -> list[_Preflight]:
    checks = [_executable("uv"), _executable("dotnet"), _directory(cli_ctx.repo_root / "tests/data", "tests/data")]
    try:
        clean, raw, assembly = _main_data_paths(cli_ctx)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        checks.append(_Preflight("main-data-configuration", False, str(error)))
    else:
        checks.extend(
            [
                _file(clean, "main clean database"),
                _file(raw, "main raw database"),
                _file(assembly, "shipped main Assembly-CSharp.dll"),
            ]
        )
    return checks


def _wiki_api_reachable(base_url: str = _WIKI_BASE_URL) -> tuple[bool, str]:
    endpoint = f"{base_url.rstrip('/')}/api.php?action=query&meta=siteinfo&format=json"
    request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            if not 200 <= int(status) < 300:
                return False, f"MediaWiki API returned HTTP {status}"
            response.read(1)
    except (OSError, urllib.error.URLError, ValueError) as error:
        return False, f"MediaWiki API is unreachable at {base_url}: {error}"
    return True, endpoint


def _playwright_chromium_available() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except Exception as error:  # Playwright uses several backend exception types.
        return False, f"Playwright Chromium is unavailable: {error}"
    return True, "Playwright Chromium launched"


def _preflight_wiki(cli_ctx: CLIContext) -> list[_Preflight]:
    root = cli_ctx.repo_root
    checks = [
        _executable("uv"),
        _executable("docker"),
        _directory(root / "wiki-dev", "wiki-dev"),
        _file(root / "wiki-dev/import_pages.py", "wiki-dev/import_pages.py"),
        _file(root / "wiki-dev/smoke_test.py", "wiki-dev/smoke_test.py"),
        _file(root / "wiki-dev/cargo_check.py", "wiki-dev/cargo_check.py"),
        _directory(root / "tests/system/wiki", "tests/system/wiki"),
    ]
    reachable, detail = _wiki_api_reachable()
    checks.append(_Preflight("local MediaWiki API", reachable, detail))
    playwright_ok, detail = _playwright_chromium_available()
    checks.append(_Preflight("Playwright Chromium", playwright_ok, detail))
    return checks


def _preflight_wiki_clean(cli_ctx: CLIContext) -> list[_Preflight]:
    root = cli_ctx.repo_root
    return [
        *_preflight_wiki(cli_ctx),
        _executable("curl"),
        _file(root / "wiki-dev/acceptance.py", "wiki-dev/acceptance.py"),
        _file(root / "wiki-dev/clean_parity.py", "wiki-dev/clean_parity.py"),
        _file(root / "wiki-dev/bootstrap.sh", "wiki-dev/bootstrap.sh"),
        _file(root / "wiki-dev/compose.yml", "wiki-dev/compose.yml"),
    ]


def _preflight_maps(cli_ctx: CLIContext) -> list[_Preflight]:
    checks = [_executable("pnpm"), _executable("node")]
    try:
        source, node_modules = _maps_paths(cli_ctx)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        checks.append(_Preflight("maps configuration", False, str(error)))
    else:
        checks.extend(
            [
                _directory(source, "configured maps project"),
                _directory(node_modules, "maps node_modules"),
                _file(source / "scripts/test-prerender.mjs", "maps prerender smoke"),
                _file(source / "tests/fixtures/map-database.sql", "maps fixture schema"),
            ]
        )
    return checks


@dataclass(frozen=True)
class _NativeTestProject:
    name: str
    project: Path
    default_loader: str
    required_ignored_references: tuple[Path, ...]


_NATIVE_TEST_PROJECTS: tuple[_NativeTestProject, ...] = (
    _NativeTestProject(
        name="AdventureGuide",
        project=Path("src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj"),
        default_loader="lunaris",
        required_ignored_references=(),
    ),
    _NativeTestProject(
        name="InteractiveMapCompanion",
        project=Path(
            "src/mods/InteractiveMapCompanion/tests/InteractiveMapCompanion.Tests/InteractiveMapCompanion.Tests.csproj"
        ),
        default_loader="bepinex",
        required_ignored_references=(),
    ),
    _NativeTestProject(
        name="Sprint",
        project=Path("src/mods/Sprint/tests/Sprint.Tests/Sprint.Tests.csproj"),
        default_loader="lunaris",
        required_ignored_references=(),
    ),
    _NativeTestProject(
        name="JusticeForF7",
        project=Path("src/mods/JusticeForF7/tests/JusticeForF7.Tests/JusticeForF7.Tests.csproj"),
        default_loader="lunaris",
        required_ignored_references=(),
    ),
    _NativeTestProject(
        name="LoaderAdapters",
        project=Path("src/mods/tests/LoaderAdapter.Tests/LoaderAdapter.Tests.csproj"),
        default_loader="bepinex",
        required_ignored_references=(),
    ),
)


def _dotnet_sdk_10() -> _Preflight:
    """Require an installed .NET 10 SDK, not merely a dotnet executable."""
    if shutil.which("dotnet") is None:
        return _Preflight("dotnet SDK 10", False, "dotnet is not on PATH")
    try:
        completed = subprocess.run(
            ["dotnet", "--list-sdks"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        return _Preflight("dotnet SDK 10", False, f"Unable to query dotnet SDKs: {error}")
    if completed.returncode != 0:
        return _Preflight(
            "dotnet SDK 10",
            False,
            f"dotnet --list-sdks exited with {completed.returncode}: {getattr(completed, 'stderr', '') or ''}".strip(),
        )
    stdout = getattr(completed, "stdout", "") or ""
    for line in str(stdout).splitlines():
        version = line.strip().split(maxsplit=1)[0] if line.strip() else ""
        if re.fullmatch(r"10\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
            return _Preflight("dotnet SDK 10", True, version)
    return _Preflight("dotnet SDK 10", False, "No .NET 10 SDK is installed")


def _preflight_mods(cli_ctx: CLIContext) -> list[_Preflight]:
    root = cli_ctx.repo_root
    checks = [_executable("dotnet"), _dotnet_sdk_10()]
    if not _NATIVE_TEST_PROJECTS:
        checks.append(_Preflight("native test project inventory", False, "No native test projects are configured"))
    else:
        for native_project in _NATIVE_TEST_PROJECTS:
            project = root / native_project.project
            project_check = _file(project, f"{native_project.name} native test project")
            checks.append(project_check)
            if not project_check.ok:
                continue
            checks.extend(
                _file(root / reference, f"{native_project.name} required reference {reference.name}")
                for reference in native_project.required_ignored_references
            )
    artifact_issues = verify_static_mod_artifacts(root, _artifact_specs())
    artifact_detail = format_artifact_issues(artifact_issues)
    checks.append(
        _Preflight(
            "static mod artifacts",
            not artifact_issues,
            artifact_detail or "All static mod artifact checks passed",
        )
    )
    return checks


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


_PREFLIGHTS = {
    "unit": _preflight_unit,
    "contract": _preflight_contract,
    "data": _preflight_data,
    "wiki": _preflight_wiki,
    "maps": _preflight_maps,
    "mods": _preflight_mods,
}


# ------------------------------- execution --------------------------------


def _duration(start: float) -> float:
    return round(max(0.0, time.monotonic() - start), 6)


def _run_process(argv: Sequence[str], cwd: Path) -> _CommandResult:
    start = time.monotonic()
    command = tuple(str(part) for part in argv)
    completed = subprocess.run(list(command), cwd=cwd, check=False)
    exit_code = int(completed.returncode)
    return _CommandResult(command, cwd, exit_code, _duration(start))


def _command_json(result: _CommandResult) -> dict[str, object]:
    return {
        "argv": list(result.argv),
        "cwd": str(result.cwd),
        "exit_code": result.exit_code,
        "duration_seconds": result.duration_seconds,
    }


def _pytest_command(arguments: Sequence[str], report_path: Path | None = None) -> list[str]:
    """Build the subprocess command for a pytest leaf."""
    command = ["uv", "run", "pytest", *arguments]
    if report_path is not None:
        command.extend(["-p", _PYTEST_PLUGIN, _REPORT_OPTION, str(report_path)])
    return command


def _is_nonnegative_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _required_nonnegative_int(payload: Mapping[str, object], key: str) -> int | str:
    if key not in payload:
        return f"The pytest report is missing required counter: {key}"
    value = payload[key]
    if not _is_nonnegative_int(value):
        return f"The pytest report has an invalid nonnegative integer counter: {key}"
    return value


def _pytest_report_counts(payload: object) -> tuple[_PytestCounts, str | None]:
    if not isinstance(payload, dict):
        return {}, "The pytest report has an invalid JSON shape"

    schema = payload.get("schema")
    if isinstance(schema, bool) or not isinstance(schema, int) or schema != _REPORT_SCHEMA:
        return {}, f"The pytest report has unsupported schema {schema!r}; expected {_REPORT_SCHEMA}"

    counters = ("collected", "deselected", "skipped", "failed", "exit_code")
    values: dict[str, int] = {}
    for key in counters:
        value = _required_nonnegative_int(payload, key)
        if isinstance(value, str):
            return {}, value
        values[key] = value
    counts: _PytestCounts = {
        "collected": values["collected"],
        "deselected": values["deselected"],
        "skipped": values["skipped"],
        "failed": values["failed"],
        "exit_code": values["exit_code"],
    }
    return counts, None


def _complete_pytest_counts(counts: _PytestCounts) -> _CompletePytestCounts:
    values: dict[str, int] = {}
    for key in ("collected", "deselected", "skipped", "failed", "exit_code"):
        value = counts.get(key)
        if not _is_nonnegative_int(value):
            raise ValueError(f"The pytest report has an incomplete counter: {key}")
        values[key] = value
    return {
        "collected": values["collected"],
        "deselected": values["deselected"],
        "skipped": values["skipped"],
        "failed": values["failed"],
        "exit_code": values["exit_code"],
    }


def _read_pytest_report(path: Path) -> tuple[_PytestCounts, str | None]:
    if not path.is_file():
        return {}, "Pytest did not produce its machine-readable report"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as read_error:
        return {}, f"Unable to read the pytest report: {read_error}"
    return _pytest_report_counts(payload)


def _temporary_report_path(directory: Path, *, prefix: str, suffix: str) -> Path:
    """Reserve a unique report pathname without leaving a placeholder file."""
    file_descriptor, filename = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    path = Path(filename)
    try:
        os.close(file_descriptor)
    except BaseException:
        with suppress(OSError):
            path.unlink(missing_ok=True)
        raise
    with suppress(OSError):
        path.unlink()
    return path


def _optional_trx_counter(raw: str | None, name: str) -> int | str | None:
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return f"The dotnet test TRX report has an invalid counter: {name}"
    if value < 0:
        return f"The dotnet test TRX report has a negative counter: {name}"
    return value


def _trx_counters(counter_element: ET.Element | None) -> tuple[_TrxReportedCounters, str | None]:
    if counter_element is None:
        return {}, None

    executed = _optional_trx_counter(counter_element.attrib.get("executed"), "executed")
    if isinstance(executed, str):
        return {}, executed
    failed = _optional_trx_counter(counter_element.attrib.get("failed"), "failed")
    if isinstance(failed, str):
        return {}, failed
    skipped = _optional_trx_counter(counter_element.attrib.get("skipped"), "skipped")
    if isinstance(skipped, str):
        return {}, skipped
    not_executed = _optional_trx_counter(counter_element.attrib.get("notExecuted"), "notExecuted")
    if isinstance(not_executed, str):
        return {}, not_executed

    counters: _TrxReportedCounters = {}
    if executed is not None:
        counters["executed"] = executed
    if failed is not None:
        counters["failed"] = failed
    if skipped is not None:
        counters["skipped"] = skipped
    if not_executed is not None:
        counters["notExecuted"] = not_executed
    return counters, None


def _read_trx_report(path: Path) -> tuple[_TrxCounts, str | None]:
    """Read one dotnet test TRX result and normalize its outcome counters."""
    if not path.is_file():
        return {}, "dotnet test did not produce its machine-readable TRX report"
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as parse_error:
        return {}, f"Unable to read the dotnet test TRX report: {parse_error}"

    counter_element = next(
        (element for element in root.iter() if _xml_local_name(element.tag) == "Counters"),
        None,
    )

    outcome_executed = 0
    outcome_failed = 0
    outcome_skipped = 0
    outcome_not_executed = 0
    structured_results = 0
    for element in root.iter():
        if _xml_local_name(element.tag) != "UnitTestResult":
            continue
        structured_results += 1
        outcome = element.attrib.get("outcome", "").strip().casefold()
        if outcome in {"failed", "error", "timeout", "aborted", "passed"}:
            outcome_executed += 1
            if outcome != "passed":
                outcome_failed += 1
        elif outcome in {"skipped", "ignored"}:
            outcome_skipped += 1
        elif outcome in {"notexecuted", "not executed"}:
            outcome_not_executed += 1
        else:
            outcome_not_executed += 1

    reported, counter_error = _trx_counters(counter_element)
    if counter_error:
        return {}, counter_error

    counts: _TrxCounts = {
        "executed": outcome_executed if structured_results else 0,
        "failed": max(reported.get("failed", 0), outcome_failed),
        "skipped": max(reported.get("skipped", 0), outcome_skipped),
        "not_executed": max(reported.get("notExecuted", 0), outcome_not_executed),
    }
    return counts, None


def _complete_trx_counts(counts: _TrxCounts) -> _CompleteTrxCounts:
    values: dict[str, int] = {}
    for key in ("executed", "failed", "skipped", "not_executed"):
        value = counts.get(key)
        if not _is_nonnegative_int(value):
            raise ValueError(f"The dotnet test TRX report has an incomplete counter: {key}")
        values[key] = value
    return {
        "executed": values["executed"],
        "failed": values["failed"],
        "skipped": values["skipped"],
        "not_executed": values["not_executed"],
    }


def _run_pytest_leaf(
    cli_ctx: CLIContext,
    task_id: str,
    arguments: Sequence[str],
    *,
    coverage: bool = False,
) -> _LeafResult:
    start = time.monotonic()
    command_arguments = list(arguments)
    if coverage:
        command_arguments.extend(["--cov", "--cov-report=term-missing"])

    report_directory = cli_ctx.repo_root / _REPORT_DIRECTORY
    report_directory.mkdir(parents=True, exist_ok=True)
    report_path = _temporary_report_path(
        report_directory,
        prefix=f".pytest-{task_id}-",
        suffix=".json",
    )
    try:
        result = _run_process(_pytest_command(command_arguments, report_path), cli_ctx.repo_root)
        counts, report_error = _read_pytest_report(report_path)
    finally:
        with suppress(OSError):
            report_path.unlink(missing_ok=True)

    violations: list[str] = []
    diagnostics: dict[str, object] = {}
    complete_counts: _CompletePytestCounts | None = None
    if report_error:
        violations.append(report_error)
        diagnostics["report_validation"] = [report_error]
    else:
        complete_counts = _complete_pytest_counts(counts)
        if complete_counts["collected"] == 0:
            violations.append("collected=0")
        if complete_counts["skipped"] > 0:
            violations.append(f"skipped={complete_counts['skipped']}")
        if complete_counts["deselected"] > 0:
            violations.append(f"deselected={complete_counts['deselected']}")
        if complete_counts["failed"] > 0:
            violations.append(f"failed={complete_counts['failed']}")
        if complete_counts["exit_code"] != 0:
            violations.append(f"exit_code={complete_counts['exit_code']}")
    if result.exit_code != 0 and not any(item.startswith("exit_code=") for item in violations):
        violations.append(f"exit_code={result.exit_code}")

    status = "passed" if not violations else "failed"
    if violations and not report_error:
        diagnostics["validation"] = violations
    return _LeafResult(
        task_id=task_id,
        status=status,
        exit_code=0 if status == "passed" else (result.exit_code or 1),
        duration_seconds=_duration(start),
        prerequisites=[],
        result_counts=complete_counts if complete_counts is not None else counts,
        commands=[_command_json(result)],
        diagnostics=diagnostics,
    )


def _run_native_test_project(cli_ctx: CLIContext, project: Path, *, name: str) -> _NativeTestResult:
    """Run one native test project and validate its temporary TRX report."""
    report_directory = cli_ctx.repo_root / _REPORT_DIRECTORY
    report_directory.mkdir(parents=True, exist_ok=True)
    report_path = _temporary_report_path(
        report_directory,
        prefix=f".dotnet-{re.sub(r'[^A-Za-z0-9_.-]+', '_', name)}-",
        suffix=".trx",
    )
    project_path = project if project.is_absolute() else cli_ctx.repo_root / project
    command = [
        "dotnet",
        "test",
        str(project_path),
        "-c",
        "Release",
        "--logger",
        f"trx;LogFileName={report_path}",
    ]
    try:
        command_result = _run_process(command, cli_ctx.repo_root)
        parsed_counts, report_error = _read_trx_report(report_path)
    finally:
        with suppress(OSError):
            report_path.unlink(missing_ok=True)

    violations: list[str] = []
    diagnostics: dict[str, object] = {}
    complete_counts: _CompleteTrxCounts | None = None
    if report_error:
        violations.append(report_error)
        diagnostics["report_validation"] = [report_error]
    else:
        try:
            complete_counts = _complete_trx_counts(parsed_counts)
        except ValueError as validation_error:
            report_error = str(validation_error)
            violations.append(report_error)
            diagnostics["report_validation"] = [report_error]
        else:
            if complete_counts["executed"] <= 0:
                violations.append(f"executed={complete_counts['executed']}")
            if complete_counts["failed"] > 0:
                violations.append(f"failed={complete_counts['failed']}")
            if complete_counts["skipped"] > 0:
                violations.append(f"skipped={complete_counts['skipped']}")
            if complete_counts["not_executed"] > 0:
                violations.append(f"not_executed={complete_counts['not_executed']}")
    if command_result.exit_code != 0:
        violations.append(f"exit_code={command_result.exit_code}")

    status = "passed" if not violations else "failed"
    if violations and not report_error:
        diagnostics["validation"] = violations
    return _NativeTestResult(
        command=command_result,
        result_counts=complete_counts if complete_counts is not None else parsed_counts,
        status=status,
        exit_code=0 if status == "passed" else (command_result.exit_code or 1),
        diagnostics=diagnostics,
    )


def _run_contract_leaf(cli_ctx: CLIContext) -> _LeafResult:
    """Run each native contract project and the Python contract tests exactly once."""
    start = time.monotonic()
    native_results = [
        (
            project,
            _run_native_test_project(cli_ctx, project.project, name=project.name),
        )
        for project in _CONTRACT_NATIVE_TEST_PROJECTS
    ]
    pytest_result = _run_pytest_leaf(cli_ctx, "contract", ["tests/contract"])
    all_results = [result for _, result in native_results]
    failed_native_result = next(
        (result for result in all_results if result.exit_code != 0),
        None,
    )
    exit_code = failed_native_result.exit_code if failed_native_result is not None else pytest_result.exit_code
    result_counts: dict[str, object] = {project.key: result.result_counts for project, result in native_results}
    result_counts["pytest"] = pytest_result.result_counts
    diagnostics: dict[str, object] = {project.key: result.diagnostics for project, result in native_results}
    diagnostics["pytest"] = pytest_result.diagnostics
    return _LeafResult(
        task_id="contract",
        status="passed" if exit_code == 0 else "failed",
        exit_code=exit_code,
        duration_seconds=_duration(start),
        prerequisites=[],
        result_counts=result_counts,
        commands=[
            *(_command_json(result.command) for _, result in native_results),
            *pytest_result.commands,
        ],
        diagnostics=diagnostics,
    )


def _run_mods_leaf(cli_ctx: CLIContext) -> _LeafResult:
    """Run every native project and validate its structured TRX result."""
    start = time.monotonic()
    if not _NATIVE_TEST_PROJECTS:
        return _LeafResult(
            task_id="mods",
            status="failed",
            exit_code=1,
            duration_seconds=_duration(start),
            prerequisites=[],
            result_counts={},
            commands=[],
            diagnostics={"validation": ["native test project inventory is empty"]},
        )

    report_directory = cli_ctx.repo_root / _REPORT_DIRECTORY
    report_directory.mkdir(parents=True, exist_ok=True)
    command_results: list[_CommandResult] = []
    project_counts: dict[str, _CompleteTrxCounts] = {}
    violations: list[str] = []
    report_validation: list[str] = []
    for native_project in _NATIVE_TEST_PROJECTS:
        name = native_project.name
        project = cli_ctx.repo_root / native_project.project
        report_path = _temporary_report_path(
            report_directory,
            prefix=f".dotnet-{re.sub(r'[^A-Za-z0-9_.-]+', '_', name)}-",
            suffix=".trx",
        )
        command = [
            "dotnet",
            "test",
            str(project),
            f"-p:ModLoader={native_project.default_loader}",
            "-p:ModVersion=0.0.0-test",
            "--logger",
            f"trx;LogFileName={report_path}",
        ]
        try:
            command_result = _run_process(command, cli_ctx.repo_root)
            command_results.append(command_result)
            parsed_counts, report_error = _read_trx_report(report_path)
        finally:
            with suppress(OSError):
                report_path.unlink(missing_ok=True)

        if report_error:
            report_validation.append(f"{name}: {report_error}")
            violations.append(f"{name}: {report_error}")
            continue

        project_counts[name] = _complete_trx_counts(parsed_counts)
        counts = project_counts[name]
        executed = counts["executed"]
        failed = counts["failed"]
        skipped = counts["skipped"]
        not_executed = counts["not_executed"]
        if executed <= 0:
            violations.append(f"{name}: executed={executed}")
        if failed > 0:
            violations.append(f"{name}: failed={failed}")
        if skipped > 0:
            violations.append(f"{name}: skipped={skipped}")
        if not_executed > 0:
            violations.append(f"{name}: not_executed={not_executed}")
        if command_result.exit_code != 0:
            violations.append(f"{name}: exit_code={command_result.exit_code}")

    aggregate: _CompleteTrxCounts = {
        "executed": sum(counts["executed"] for counts in project_counts.values()),
        "failed": sum(counts["failed"] for counts in project_counts.values()),
        "skipped": sum(counts["skipped"] for counts in project_counts.values()),
        "not_executed": sum(counts["not_executed"] for counts in project_counts.values()),
    }
    result_counts = {**aggregate, "projects": project_counts}
    if not project_counts:
        violations.append("no native project produced a valid TRX result")
    diagnostics: dict[str, object] = {}
    if report_validation:
        diagnostics["report_validation"] = report_validation
    if violations:
        diagnostics["validation"] = violations
    process_failure = next((item for item in command_results if item.exit_code != 0), None)
    exit_code = process_failure.exit_code if process_failure is not None else (1 if violations else 0)
    status = "passed" if not violations else "failed"
    return _LeafResult(
        task_id="mods",
        status=status,
        exit_code=exit_code,
        duration_seconds=_duration(start),
        prerequisites=[],
        result_counts=result_counts,
        commands=[_command_json(item) for item in command_results],
        diagnostics=diagnostics,
    )


def _run_leaf_commands(
    cli_ctx: CLIContext,
    task_id: str,
    commands: Sequence[Sequence[str]],
    *,
    cwd: Path | None = None,
    continue_on_failure: bool = False,
) -> _LeafResult:
    start = time.monotonic()
    results: list[_CommandResult] = []
    command_cwd = cwd or cli_ctx.repo_root
    for command in commands:
        result = _run_process(command, command_cwd)
        results.append(result)
        if result.exit_code != 0 and not continue_on_failure:
            break
    failed = next((result for result in results if result.exit_code != 0), None)
    return _LeafResult(
        task_id=task_id,
        status="passed" if failed is None and len(results) == len(commands) else "failed",
        exit_code=0 if failed is None and len(results) == len(commands) else (failed.exit_code if failed else 1),
        duration_seconds=_duration(start),
        prerequisites=[],
        result_counts={"commands": len(commands), "completed_commands": len(results)},
        commands=[_command_json(result) for result in results],
    )


def _run_wiki_leaf(cli_ctx: CLIContext) -> _LeafResult:
    """Import and smoke the local wiki, then enforce structured pytest counts."""
    start = time.monotonic()
    base = _WIKI_BASE_URL
    setup_commands = (
        ("uv", "run", "python", "wiki-dev/import_pages.py", "--base-url", base, "--root", str(cli_ctx.repo_root)),
        ("uv", "run", "python", "wiki-dev/smoke_test.py", "--base-url", base),
        ("uv", "run", "python", "wiki-dev/cargo_check.py", "--base-url", base),
    )
    setup_results: list[_CommandResult] = []
    for command in setup_commands:
        result = _run_process(command, cli_ctx.repo_root)
        setup_results.append(result)
        if result.exit_code != 0:
            break

    if len(setup_results) != len(setup_commands) or any(item.exit_code != 0 for item in setup_results):
        failed = next(item for item in setup_results if item.exit_code != 0)
        return _LeafResult(
            task_id="wiki",
            status="failed",
            exit_code=failed.exit_code,
            duration_seconds=_duration(start),
            prerequisites=[],
            result_counts={"commands": 4, "completed_commands": len(setup_results)},
            commands=[_command_json(item) for item in setup_results],
        )

    pytest_result = _run_pytest_leaf(cli_ctx, "wiki", ["tests/system/wiki"])
    return _LeafResult(
        task_id="wiki",
        status=pytest_result.status,
        exit_code=pytest_result.exit_code,
        duration_seconds=_duration(start),
        prerequisites=[],
        result_counts={**pytest_result.result_counts, "commands": 4, "completed_commands": 4},
        commands=[
            *[_command_json(item) for item in setup_results],
            *pytest_result.commands,
        ],
        diagnostics=pytest_result.diagnostics,
    )


def _run_wiki_clean_parity_leaf(cli_ctx: CLIContext) -> _LeafResult:
    """Compare an isolated clean stack with the warm developer wiki."""
    detail_report = cli_ctx.repo_root / _REPORT_DIRECTORY / "wiki-clean-parity.json"
    return _run_leaf_commands(
        cli_ctx,
        "wiki",
        (
            (
                "uv",
                "run",
                "python",
                "wiki-dev/clean_parity.py",
                "--root",
                str(cli_ctx.repo_root),
                "--warm-base-url",
                _WIKI_BASE_URL,
                "--report",
                str(detail_report),
            ),
        ),
    )


def _run_leaf(
    cli_ctx: CLIContext,
    task_id: str,
    *,
    coverage: bool = False,
    wiki_clean_parity: bool = False,
) -> _LeafResult:
    start = time.monotonic()
    preflight_fn = _preflight_wiki_clean if task_id == "wiki" and wiki_clean_parity else _PREFLIGHTS[task_id]
    preflight = preflight_fn(cli_ctx)
    prerequisite_json: list[_PrerequisiteJson] = [
        {"name": item.name, "status": "passed" if item.ok else "failed", "detail": item.detail} for item in preflight
    ]
    if not all(item.ok for item in preflight):
        return _LeafResult(
            task_id=task_id,
            status="blocked",
            exit_code=1,
            duration_seconds=_duration(start),
            prerequisites=prerequisite_json,
            result_counts={},
            commands=[],
        )

    if task_id == "unit":
        result = _run_pytest_leaf(cli_ctx, task_id, ["tests/unit"], coverage=coverage)
    elif task_id == "contract":
        result = _run_contract_leaf(cli_ctx)
    elif task_id == "data":
        result = _run_pytest_leaf(cli_ctx, task_id, ["tests/data"])
    elif task_id == "wiki":
        result = _run_wiki_clean_parity_leaf(cli_ctx) if wiki_clean_parity else _run_wiki_leaf(cli_ctx)
    elif task_id == "maps":
        source, _ = _maps_paths(cli_ctx)
        commands = (*maps.CHECK_COMMANDS, maps.PRERENDER_SMOKE_COMMAND)
        result = _run_leaf_commands(cli_ctx, task_id, commands, cwd=source)
    elif task_id == "mods":
        result = _run_mods_leaf(cli_ctx)
    else:  # pragma: no cover - guarded by expand_tasks and _PREFLIGHTS
        raise TaskGraphError(f"No runner for verification task: {task_id}")

    result.prerequisites = prerequisite_json
    result.duration_seconds = _duration(start)
    return result


# ------------------------------- reporting --------------------------------


def _report_path(repo_root: Path, requested: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", requested).strip("._") or "task"
    return repo_root / _REPORT_DIRECTORY / f"{safe}.json"


def _write_report(repo_root: Path, requested: str, payload: Mapping[str, object]) -> Path:
    destination = _report_path(repo_root, requested)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(encoded)
        temporary_path = Path(temporary.name)
    temporary_path.replace(destination)
    return destination


def _report_payload(
    requested: str,
    expanded: list[str],
    results: list[_LeafResult],
    duration: float,
) -> dict[str, object]:
    failed = next((item for item in results if item.exit_code != 0), None)
    return {
        "schema": _REPORT_SCHEMA,
        "requested_task": requested,
        "requested_task_id": requested,
        "expanded_leaves": expanded,
        "status": "passed" if failed is None else "failed",
        "exit_code": 0 if failed is None else failed.exit_code,
        "duration_seconds": round(duration, 6),
        "leaves": [
            {
                "task_id": item.task_id,
                "status": item.status,
                "exit_code": item.exit_code,
                "duration_seconds": item.duration_seconds,
                "prerequisites": item.prerequisites,
                "result_counts": item.result_counts,
                "diagnostics": {**item.diagnostics, "commands": item.commands},
            }
            for item in results
        ],
    }


def _report_exit_code(payload: Mapping[str, object]) -> int:
    value = payload.get("exit_code", 1)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("Verification report exit_code must be an integer")
    return value


def _run_task(
    cli_ctx: CLIContext,
    requested: str,
    *,
    coverage: bool = False,
    wiki_clean_parity: bool = False,
) -> None:
    start = time.monotonic()
    expanded: list[str] = []
    results: list[_LeafResult] = []
    try:
        expanded = expand_tasks(requested)
        for task_id in expanded:
            leaf_start = time.monotonic()
            try:
                result = _run_leaf(
                    cli_ctx,
                    task_id,
                    coverage=coverage and task_id == "unit",
                    wiki_clean_parity=wiki_clean_parity and task_id == "wiki",
                )
            except KeyboardInterrupt:
                results.append(
                    _LeafResult(
                        task_id=task_id,
                        status="interrupted",
                        exit_code=130,
                        duration_seconds=_duration(leaf_start),
                        prerequisites=[],
                        result_counts={},
                        commands=[],
                        diagnostics={"error": "KeyboardInterrupt"},
                    )
                )
                raise
            except Exception as leaf_error:
                result = _LeafResult(
                    task_id=task_id,
                    status="failed",
                    exit_code=1,
                    duration_seconds=_duration(leaf_start),
                    prerequisites=[],
                    result_counts={},
                    commands=[{"error": str(leaf_error)}],
                )
            results.append(result)
    except KeyboardInterrupt:
        payload = _report_payload(requested, expanded, results, _duration(start))
        payload.update(
            {
                "status": "interrupted",
                "exit_code": 130,
                "interrupted": True,
                "error": "KeyboardInterrupt",
            }
        )
        try:
            report_path = _write_report(cli_ctx.repo_root, requested, payload)
        except OSError as interrupted_report_error:
            console.print(f"[red]Unable to write interrupted test report: {interrupted_report_error}[/red]")
        else:
            console.print(f"Verification report: {report_path}")
        raise
    except Exception as task_error:
        payload = {
            "schema": _REPORT_SCHEMA,
            "requested_task": requested,
            "requested_task_id": requested,
            "expanded_leaves": expanded,
            "status": "failed",
            "exit_code": 1,
            "duration_seconds": _duration(start),
            "leaves": [],
            "error": str(task_error),
        }
    else:
        payload = _report_payload(requested, expanded, results, _duration(start))

    try:
        report_path = _write_report(cli_ctx.repo_root, requested, payload)
    except OSError as report_write_error:
        console.print(f"[red]Unable to write test report: {report_write_error}[/red]")
        raise typer.Exit(1) from report_write_error

    console.print(f"Verification report: {report_path}")
    exit_code = _report_exit_code(payload)
    if exit_code:
        raise typer.Exit(exit_code)


# -------------------------------- commands --------------------------------


@app.callback(invoke_without_command=True)
def test_callback(ctx: typer.Context) -> None:
    """Run one leaf task or a canonical composite task."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("unit")
def test_unit(
    ctx: typer.Context,
    coverage: bool = typer.Option(False, "--coverage", help="Generate explicit coverage output"),
) -> None:
    """Run hermetic Python unit tests."""
    _run_task(ctx.obj, "unit", coverage=coverage)


@app.command("contract")
def test_contract(ctx: typer.Context) -> None:
    """Run Python and tool contract tests."""
    _run_task(ctx.obj, "contract")


@app.command("data")
def test_data(ctx: typer.Context) -> None:
    """Run main-variant data and shipped-code tests."""
    _run_task(ctx.obj, "data")


@app.command("wiki")
def test_wiki(
    ctx: typer.Context,
    warm: bool = typer.Option(False, "--warm", help="Verify the existing warm developer wiki"),
    clean_parity: bool = typer.Option(
        False,
        "--clean-parity",
        help="Compare an isolated clean wiki with the warm developer wiki",
    ),
) -> None:
    """Run one explicit local MediaWiki verification mode."""
    if warm == clean_parity:
        raise typer.BadParameter("Choose exactly one of --warm or --clean-parity")
    _run_task(ctx.obj, "wiki", wiki_clean_parity=clean_parity)


@app.command("maps")
def test_maps(ctx: typer.Context) -> None:
    """Run maps lint, Svelte checks, and Vitest without a production build."""
    _run_task(ctx.obj, "maps")


@app.command("mods")
def test_mods(ctx: typer.Context) -> None:
    """Run the maintained native mod test projects explicitly."""
    _run_task(ctx.obj, "mods")


@app.command("ci")
def test_ci(ctx: typer.Context) -> None:
    """Run the disjoint CI verification leaves."""
    _run_task(ctx.obj, "ci")


@app.command("release")
def test_release(ctx: typer.Context) -> None:
    """Run CI plus the main data and local wiki leaves."""
    _run_task(ctx.obj, "release")


__all__ = [
    "COMPOSITE_TASKS",
    "LEAF_TASKS",
    "TASKS",
    "TaskGraphError",
    "app",
    "expand_tasks",
]
