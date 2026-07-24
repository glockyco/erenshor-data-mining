"""Observable contracts for the canonical Python verification task CLI."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from threading import Barrier, Lock
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from erenshor.application.mods.artifacts import ArtifactIssue
from erenshor.cli.commands import test
from erenshor.cli.context import CLIContext

runner = CliRunner()


def _context(tmp_path: Path, *, configured_maps: bool = False) -> CLIContext:
    if configured_maps:
        maps = SimpleNamespace(source_dir=tmp_path / "maps", database_dir=tmp_path / "maps-db")
        variant = SimpleNamespace(maps=maps)
        config = SimpleNamespace(variants={"main": variant})
    else:
        config = SimpleNamespace()
    return CLIContext(config=config, variant="main", dry_run=False, repo_root=tmp_path)


def _passing_preflight() -> list[Any]:
    return [test._Preflight("ready", True, "ok")]


def _counts(
    *,
    collected: int = 3,
    skipped: int = 0,
    deselected: int = 0,
    failed: int = 0,
    exit_code: int = 0,
) -> dict[str, int]:
    return {
        "collected": collected,
        "skipped": skipped,
        "deselected": deselected,
        "failed": failed,
        "exit_code": exit_code,
    }


def _valid_pytest_report(**overrides: object) -> dict[str, object]:
    return {"schema": 1, **_counts(), **overrides}


def _leaf_result(task_id: str, *, status: str = "passed", exit_code: int = 0) -> Any:
    return test._LeafResult(
        task_id=task_id,
        status=status,
        exit_code=exit_code,
        duration_seconds=0.25,
        prerequisites=[{"name": "tool", "status": "passed", "detail": "/bin/tool"}],
        result_counts={"collected": 3, "skipped": 0, "deselected": 0, "failed": 0},
        commands=[
            {
                "argv": ["tool", "--check"],
                "cwd": "/repo",
                "exit_code": exit_code,
                "duration_seconds": 0.125,
            }
        ],
    )


def _assert_intermediate_report_path(path: Path, repo_root: Path, task_id: str) -> None:
    assert path.parent == repo_root / "artifacts/test-reports"
    assert path.name.startswith(f".pytest-{task_id}")
    assert path.suffix == ".json"


def _write_trx(argv: Sequence[str], outcomes: Sequence[str]) -> Path:
    logger = next(argument for argument in argv if argument.startswith("trx;LogFileName="))
    path = Path(logger.split("=", 1)[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    failed = sum(outcome.casefold() in {"failed", "error", "timeout", "aborted"} for outcome in outcomes)
    skipped = sum(outcome.casefold() in {"skipped", "ignored"} for outcome in outcomes)
    not_executed = sum(outcome.casefold() in {"notexecuted", "not executed"} for outcome in outcomes)
    counters = (
        f'<Counters executed="{len(outcomes)}" failed="{failed}" skipped="{skipped}" notExecuted="{not_executed}" />'
    )
    results = "".join(
        f'<UnitTestResult testId="{index}" outcome="{outcome}" />' for index, outcome in enumerate(outcomes)
    )
    path.write_text(
        f"<TestRun><ResultSummary>{counters}</ResultSummary><Results>{results}</Results></TestRun>",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("missing", ["schema", "collected", "deselected", "skipped", "failed", "exit_code"])
def test_pytest_report_requires_schema_and_all_counters(tmp_path: Path, missing: str) -> None:
    payload = _valid_pytest_report()
    payload.pop(missing)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    counts, error = test._read_pytest_report(path)

    assert counts == {}
    assert error is not None
    assert missing in error


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", 2),
        ("schema", True),
        ("collected", "3"),
        ("deselected", False),
        ("collected", -1),
        ("deselected", -1),
        ("skipped", -1),
        ("failed", -1),
        ("exit_code", -1),
    ],
)
def test_pytest_report_rejects_wrong_schema_and_nonnegative_integer_violations(
    tmp_path: Path, field: str, value: object
) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_valid_pytest_report(**{field: value})), encoding="utf-8")

    counts, error = test._read_pytest_report(path)

    assert counts == {}
    assert error is not None
    assert field in error


def test_pytest_report_accepts_extra_metadata_without_relaxing_required_schema(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_valid_pytest_report(worker="unit-worker")), encoding="utf-8")

    counts, error = test._read_pytest_report(path)

    assert error is None
    assert counts == _counts()


def test_task_catalog_has_exact_leaves_and_composites() -> None:
    assert test.LEAF_TASKS == ("unit", "contract", "data", "wiki", "maps", "mods")
    assert test.COMPOSITE_TASKS == ("ci", "release")
    assert test.TASKS == {
        "unit": (),
        "contract": (),
        "data": (),
        "wiki": (),
        "maps": (),
        "mods": (),
        "ci": ("unit", "contract", "maps", "mods"),
        "release": ("ci", "data", "wiki"),
    }


def test_task_expansion_is_ordered_and_suppresses_duplicate_leaves() -> None:
    assert test.expand_tasks("ci") == ["unit", "contract", "maps", "mods"]
    assert test.expand_tasks("release") == ["unit", "contract", "maps", "mods", "data", "wiki"]
    assert test.expand_tasks(["release", "ci", "unit", "wiki"]) == [
        "unit",
        "contract",
        "maps",
        "mods",
        "data",
        "wiki",
    ]


def test_task_expansion_rejects_unknown_ids_and_cycles(monkeypatch: Any) -> None:
    with pytest.raises(test.TaskGraphError, match="Unknown verification task: missing"):
        test.expand_tasks("missing")

    monkeypatch.setattr(test, "TASKS", {"first": ("second",), "second": ("first",)})
    with pytest.raises(test.TaskGraphError, match=r"cycle detected: first -> second -> first"):
        test.expand_tasks("first")


@pytest.mark.parametrize(
    ("arguments", "task_id"),
    [
        (["unit"], "unit"),
        (["contract"], "contract"),
        (["data"], "data"),
        (["wiki", "--warm"], "wiki"),
        (["maps"], "maps"),
        (["mods"], "mods"),
        (["ci"], "ci"),
        (["release"], "release"),
    ],
)
def test_all_typer_routes_dispatch_their_task_id(
    tmp_path: Path,
    monkeypatch: Any,
    arguments: list[str],
    task_id: str,
) -> None:
    calls: list[tuple[str, bool, bool]] = []

    def fake_run_task(
        _ctx: CLIContext,
        requested: str,
        *,
        coverage: bool = False,
        wiki_clean_parity: bool = False,
    ) -> None:
        calls.append((requested, coverage, wiki_clean_parity))

    monkeypatch.setattr(test, "_run_task", fake_run_task)
    result = runner.invoke(test.app, arguments, obj=_context(tmp_path))

    assert result.exit_code == 0
    assert calls == [(task_id, False, task_id == "release")]


def test_wiki_route_dispatches_clean_parity_and_requires_one_mode(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        test,
        "_run_task",
        lambda _ctx, requested, *, coverage=False, wiki_clean_parity=False: calls.append(
            (requested, wiki_clean_parity)
        ),
    )

    clean = runner.invoke(test.app, ["wiki", "--clean-parity"], obj=_context(tmp_path))
    missing = runner.invoke(test.app, ["wiki"], obj=_context(tmp_path))
    conflicting = runner.invoke(
        test.app,
        ["wiki", "--warm", "--clean-parity"],
        obj=_context(tmp_path),
    )

    assert clean.exit_code == 0
    assert calls == [("wiki", True)]
    assert missing.exit_code != 0
    assert "Choose exactly one" in missing.output
    assert conflicting.exit_code != 0
    assert "Choose exactly one" in conflicting.output


def test_bare_test_command_prints_help(tmp_path: Path) -> None:
    result = runner.invoke(test.app, [], obj=_context(tmp_path))

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert all(route in result.output for route in (*test.LEAF_TASKS, *test.COMPOSITE_TASKS))


def test_unit_route_preserves_explicit_coverage_option(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        test,
        "_run_task",
        lambda _ctx, requested, *, coverage=False: calls.append((requested, coverage)),
    )

    result = runner.invoke(test.app, ["unit", "--coverage"], obj=_context(tmp_path))

    assert result.exit_code == 0
    assert calls == [("unit", True)]


@pytest.mark.parametrize(
    ("task_id", "arguments"),
    [
        ("unit", ["tests/unit"]),
        ("data", ["tests/data"]),
    ],
)
def test_python_leaves_use_exact_pytest_path_argv_and_repository_cwd(
    tmp_path: Path, monkeypatch: Any, task_id: str, arguments: list[str]
) -> None:
    calls: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(test, "_read_pytest_report", lambda _path: (_counts(), None))
    monkeypatch.setitem(test._PREFLIGHTS, task_id, lambda _ctx: _passing_preflight())

    def fake_run_process(argv: list[str], cwd: Path) -> Any:
        calls.append((argv, cwd))
        return test._CommandResult(tuple(argv), cwd, 0, 0.125)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    result = test._run_leaf(_context(tmp_path), task_id)

    assert result.status == "passed"
    command = calls[0][0]
    assert command[: 3 + len(arguments)] == ["uv", "run", "pytest", *arguments]
    assert command[3 + len(arguments) : 6 + len(arguments)] == [
        "--quiet",
        "-p",
        "erenshor.cli.commands.test",
    ]
    report_path = Path(command[-1])
    _assert_intermediate_report_path(report_path, tmp_path, task_id)
    assert calls[0][1] == tmp_path


def test_contract_preflight_requires_both_native_projects(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(test, "_executable", lambda name: test._Preflight(name, True, "present"))

    checks = test._preflight_contract(_context(tmp_path))

    project_checks = [check for check in checks if "native test project" in check.name]
    assert [check.name for check in project_checks] == [
        "CodeFacts native test project",
        "ExportSurface native test project",
    ]
    assert [check.detail for check in project_checks] == [
        str(tmp_path / test._CONTRACT_NATIVE_TEST_PROJECTS[0].project),
        str(tmp_path / test._CONTRACT_NATIVE_TEST_PROJECTS[1].project),
    ]
    assert all(not check.ok for check in project_checks)

    for project in test._CONTRACT_NATIVE_TEST_PROJECTS:
        path = tmp_path / project.project
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    checks = test._preflight_contract(_context(tmp_path))
    assert all(check.ok for check in checks if "native test project" in check.name)


def test_contract_leaf_uses_exact_native_and_pytest_commands_and_namespaced_results(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(test, "_read_pytest_report", lambda _path: (_counts(), None))
    monkeypatch.setitem(test._PREFLIGHTS, "contract", lambda _ctx: _passing_preflight())
    calls: list[tuple[Sequence[str], Path]] = []

    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        calls.append((argv, cwd))
        if argv[0] == "dotnet":
            _write_trx(argv, ["Passed"])
        return test._CommandResult(tuple(argv), cwd, 0, 0.125)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    result = test._run_leaf(_context(tmp_path), "contract")

    assert result.status == "passed"
    assert len(calls) == 3
    native_projects = test._CONTRACT_NATIVE_TEST_PROJECTS
    for (native_command, native_cwd), project in zip(calls[:2], native_projects, strict=True):
        native_logger = native_command[-1]
        expected_project = tmp_path / project.project
        assert native_logger.startswith("trx;LogFileName=")
        assert list(native_command) == [
            "dotnet",
            "test",
            str(expected_project),
            "-c",
            "Release",
            "--logger",
            native_logger,
        ]
        assert native_cwd == tmp_path

    pytest_command, pytest_cwd = calls[2]
    pytest_report = pytest_command[-1]
    assert list(pytest_command) == [
        "uv",
        "run",
        "pytest",
        "tests/contract",
        "--quiet",
        "-p",
        "erenshor.cli.commands.test",
        "--erenshor-report",
        pytest_report,
    ]
    assert pytest_cwd == tmp_path
    _assert_intermediate_report_path(Path(pytest_report), tmp_path, "contract")
    assert result.result_counts == {
        "codefacts": {"executed": 1, "failed": 0, "skipped": 0, "not_executed": 0},
        "exportsurface": {"executed": 1, "failed": 0, "skipped": 0, "not_executed": 0},
        "pytest": _counts(),
    }
    assert list(result.diagnostics) == ["codefacts", "exportsurface", "pytest"]


@pytest.mark.parametrize(
    ("outcomes", "expected_status"),
    [
        (["Passed"], "passed"),
        ([], "failed"),
        (["Failed"], "failed"),
        (["Skipped"], "failed"),
        (["NotExecuted"], "failed"),
    ],
)
def test_contract_native_runner_validates_trx_counts(
    tmp_path: Path, monkeypatch: Any, outcomes: list[str], expected_status: str
) -> None:
    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        _write_trx(argv, outcomes)
        return test._CommandResult(tuple(argv), cwd, 0, 0.0)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    result = test._run_native_test_project(
        _context(tmp_path), test._CONTRACT_NATIVE_TEST_PROJECTS[0].project, name="CodeFacts"
    )

    assert result.status == expected_status
    assert result.exit_code == (0 if expected_status == "passed" else 1)
    if expected_status == "passed":
        assert result.result_counts["executed"] == 1
    else:
        assert result.status == "failed"


def test_contract_leaf_runs_every_native_project_and_pytest_after_native_failure(
    tmp_path: Path, monkeypatch: Any
) -> None:
    native_calls: list[str] = []
    pytest_calls: list[Sequence[str]] = []

    def fake_native(_ctx: CLIContext, _project: Path, *, name: str) -> test._NativeTestResult:
        native_calls.append(name)
        failed = name == "CodeFacts"
        return test._NativeTestResult(
            command=test._CommandResult(("dotnet", "test", name), tmp_path, 7 if failed else 0, 0.0),
            result_counts={"executed": 0 if failed else 1, "failed": 0, "skipped": 0, "not_executed": 0},
            status="failed" if failed else "passed",
            exit_code=7 if failed else 0,
            diagnostics={"validation": ["exit_code=7"]} if failed else {},
        )

    monkeypatch.setattr(test, "_run_native_test_project", fake_native)

    def fake_pytest(_ctx: CLIContext, _task_id: str, arguments: Sequence[str], **_kwargs: Any) -> Any:
        pytest_calls.append(arguments)
        return test._LeafResult(
            task_id="contract",
            status="passed",
            exit_code=0,
            duration_seconds=0.0,
            prerequisites=[],
            result_counts=_counts(),
            commands=[{"argv": ["uv", "run", "pytest", "tests/contract"], "cwd": str(tmp_path), "exit_code": 0}],
            diagnostics={},
        )

    monkeypatch.setattr(test, "_run_pytest_leaf", fake_pytest)
    result = test._run_contract_leaf(_context(tmp_path))

    assert result.status == "failed"
    assert result.exit_code == 7
    assert native_calls == ["CodeFacts", "ExportSurface"]
    assert pytest_calls == [["tests/contract"]]
    assert result.result_counts["codefacts"]["executed"] == 0
    assert result.result_counts["exportsurface"]["executed"] == 1
    assert result.result_counts["pytest"] == _counts()
    assert result.diagnostics["codefacts"] == {"validation": ["exit_code=7"]}
    assert result.diagnostics["exportsurface"] == {}
    assert result.diagnostics["pytest"] == {}


def test_contract_leaf_retains_native_reports_and_cleans_pytest_report(tmp_path: Path, monkeypatch: Any) -> None:
    report_paths: list[Path] = []
    monkeypatch.setattr(test, "_read_pytest_report", lambda _path: (_counts(), None))

    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        if argv[0] == "dotnet":
            logger = next(argument for argument in argv if "LogFileName=" in argument)
            path = Path(logger.split("=", 1)[1])
            _write_trx(argv, ["Passed"])
        else:
            path = Path(argv[-1])
        report_paths.append(path)
        return test._CommandResult(tuple(argv), cwd, 0, 0.0)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    result = test._run_contract_leaf(_context(tmp_path))

    assert result.status == "passed"
    assert len(report_paths) == 3
    assert len(set(report_paths)) == 3
    assert all(path.exists() for path in report_paths[:2])
    assert report_paths[0] == tmp_path / "artifacts/test-reports/native/contract/CodeFacts.trx"
    assert report_paths[1] == tmp_path / "artifacts/test-reports/native/contract/ExportSurface.trx"
    assert not report_paths[2].exists()


def test_pytest_intermediate_report_paths_are_unique_and_cleaned(tmp_path: Path, monkeypatch: Any) -> None:
    paths: list[Path] = []
    monkeypatch.setattr(test, "_read_pytest_report", lambda _path: (_counts(), None))

    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        paths.append(Path(argv[-1]))
        return test._CommandResult(tuple(argv), cwd, 0, 0.0)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    context = _context(tmp_path)
    test._run_pytest_leaf(context, "unit", ["tests/unit"])
    test._run_pytest_leaf(context, "unit", ["tests/unit"])

    assert len(paths) == 2
    assert paths[0] != paths[1]
    for path in paths:
        _assert_intermediate_report_path(path, tmp_path, "unit")
        assert not path.exists()


def test_maps_leaf_uses_exact_commands_and_configured_source_cwd(tmp_path: Path, monkeypatch: Any) -> None:
    source = tmp_path / "maps"
    monkeypatch.setitem(test._PREFLIGHTS, "maps", lambda _ctx: _passing_preflight())
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        calls.append((argv, cwd))
        return test._CommandResult(tuple(argv), cwd, 0, 0.125)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    result = test._run_leaf(_context(tmp_path, configured_maps=True), "maps")

    assert result.status == "passed"
    assert calls == [
        (("pnpm", "run", "lint"), source),
        (("pnpm", "run", "check"), source),
        (("pnpm", "run", "test"), source),
        (("node", "scripts/test-prerender.mjs"), source),
    ]


def test_wiki_leaf_uses_exact_setup_and_pytest_commands(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "wiki", lambda _ctx: _passing_preflight())
    monkeypatch.setattr(test, "_read_pytest_report", lambda _path: (_counts(), None))
    calls: list[tuple[Sequence[str], Path]] = []

    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        calls.append((argv, cwd))
        return test._CommandResult(tuple(argv), cwd, 0, 0.125)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    result = test._run_leaf(_context(tmp_path), "wiki")

    assert result.status == "passed"
    assert calls[:3] == [
        (
            (
                "uv",
                "run",
                "python",
                "wiki-dev/import_pages.py",
                "--base-url",
                "http://localhost:8088",
                "--root",
                str(tmp_path),
            ),
            tmp_path,
        ),
        (("uv", "run", "python", "wiki-dev/smoke_test.py", "--base-url", "http://localhost:8088"), tmp_path),
        (("uv", "run", "python", "wiki-dev/cargo_check.py", "--base-url", "http://localhost:8088"), tmp_path),
    ]
    pytest_command, pytest_cwd = calls[3]
    assert pytest_cwd == tmp_path
    assert pytest_command[:6] == [
        "uv",
        "run",
        "pytest",
        "tests/system/wiki",
        "--quiet",
        "-p",
    ]
    assert pytest_command[6] == "erenshor.cli.commands.test"
    assert pytest_command[7] == "--erenshor-report"
    _assert_intermediate_report_path(Path(pytest_command[8]), tmp_path, "wiki")


def test_wiki_clean_parity_leaf_uses_isolated_harness_command(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(test, "_preflight_wiki_clean", lambda _ctx: _passing_preflight())
    calls: list[tuple[Sequence[str], Path]] = []

    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        calls.append((argv, cwd))
        return test._CommandResult(tuple(argv), cwd, 0, 0.125)

    monkeypatch.setattr(test, "_run_process", fake_run_process)

    result = test._run_leaf(_context(tmp_path), "wiki", wiki_clean_parity=True)

    assert result.status == "passed"
    assert calls == [
        (
            (
                "uv",
                "run",
                "python",
                "wiki-dev/clean_parity.py",
                "--root",
                str(tmp_path),
                "--warm-base-url",
                "http://localhost:8088",
                "--report",
                str(tmp_path / "artifacts/test-reports/wiki-clean-parity.json"),
            ),
            tmp_path,
        )
    ]


def test_mods_leaf_uses_each_exact_native_project_argv_and_repository_cwd(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "mods", lambda _ctx: _passing_preflight())
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        _write_trx(argv, ["Passed"])
        calls.append((argv, cwd))
        return test._CommandResult(tuple(argv), cwd, 0, 0.125)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    result = test._run_leaf(_context(tmp_path), "mods")

    expected_projects = [
        (
            "lunaris",
            tmp_path / "src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj",
        ),
        (
            "bepinex",
            tmp_path
            / "src/mods/InteractiveMapCompanion/tests/InteractiveMapCompanion.Tests/"
            / "InteractiveMapCompanion.Tests.csproj",
        ),
        (
            "lunaris",
            tmp_path / "src/mods/Sprint/tests/Sprint.Tests/Sprint.Tests.csproj",
        ),
        (
            "lunaris",
            tmp_path / "src/mods/JusticeForF7/tests/JusticeForF7.Tests/JusticeForF7.Tests.csproj",
        ),
        (
            "bepinex",
            tmp_path / "src/mods/tests/LoaderAdapter.Tests/LoaderAdapter.Tests.csproj",
        ),
    ]
    assert result.status == "passed"
    assert len(calls) == len(expected_projects)
    trx_paths: list[Path] = []
    for (argv, cwd), (loader, project) in zip(calls, expected_projects, strict=True):
        assert cwd == tmp_path
        assert argv[:3] == ["dotnet", "test", str(project)]
        assert argv[3:5] == ["-c", "Release"]
        assert argv[5:7] == [f"-p:ModLoader={loader}", "-p:ModVersion=0.0.0-test"]
        logger = next(argument for argument in argv if argument.startswith("trx;LogFileName="))
        trx_paths.append(Path(logger.split("=", 1)[1]))
    assert len(trx_paths) == len(set(trx_paths))
    assert list(result.result_counts["projects"]) == [
        "AdventureGuide",
        "InteractiveMapCompanion",
        "Sprint",
        "JusticeForF7",
        "LoaderAdapters",
    ]


def test_mods_leaf_retains_each_native_report(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "mods", lambda _ctx: _passing_preflight())
    report_paths: list[Path] = []

    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        report_path = _write_trx(argv, ["Passed"])
        report_paths.append(report_path)
        return test._CommandResult(tuple(argv), cwd, 0, 0.0)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    result = test._run_leaf(_context(tmp_path), "mods")

    assert result.status == "passed"
    assert len(report_paths) == len(test._NATIVE_TEST_PROJECTS) == 5
    assert len(set(report_paths)) == len(report_paths)
    assert all(path.exists() for path in report_paths)
    assert report_paths[0] == tmp_path / "artifacts/test-reports/native/mods/AdventureGuide.trx"


@pytest.mark.parametrize(
    ("outcomes", "expected_status"),
    [
        (["Passed", "Passed"], "passed"),
        ([], "failed"),
        (["Failed"], "failed"),
        (["Skipped"], "failed"),
        (["NotExecuted"], "failed"),
    ],
)
def test_mods_parse_trx_inventory_and_outcomes(
    tmp_path: Path, monkeypatch: Any, outcomes: list[str], expected_status: str
) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "mods", lambda _ctx: _passing_preflight())

    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        _write_trx(argv, outcomes)
        return test._CommandResult(tuple(argv), cwd, 0, 0.0)

    monkeypatch.setattr(test, "_run_process", fake_run_process)

    result = test._run_leaf(_context(tmp_path), "mods")

    assert result.status == expected_status
    assert result.exit_code == (0 if expected_status == "passed" else 1)


def test_mods_preflight_requires_only_native_test_projects(tmp_path: Path, monkeypatch: Any) -> None:
    checked_paths: list[Path] = []
    monkeypatch.setattr(test, "_executable", lambda name: test._Preflight(name, True, "present"))
    monkeypatch.setattr(test, "_dotnet_sdk_10", lambda: test._Preflight("dotnet SDK 10", True, "10.0.0"))

    def fake_file(path: Path, label: str) -> test._Preflight:
        checked_paths.append(path)
        return test._Preflight(label, True, str(path))

    monkeypatch.setattr(test, "_file", fake_file)
    monkeypatch.setattr(test, "verify_static_mod_artifacts", lambda *_args: ())
    monkeypatch.setattr(test, "format_artifact_issues", lambda _issues: "")

    checks = test._preflight_mods(_context(tmp_path))

    assert all(project.required_ignored_references == () for project in test._NATIVE_TEST_PROJECTS)
    assert all(check.ok for check in checks)
    assert checks[-1].name == "static mod artifacts"
    assert checked_paths == [tmp_path / native_project.project for native_project in test._NATIVE_TEST_PROJECTS]


def test_static_artifact_failure_prevents_native_subprocesses(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(test, "_executable", lambda name: test._Preflight(name, True, "present"))
    monkeypatch.setattr(test, "_dotnet_sdk_10", lambda: test._Preflight("dotnet SDK 10", True, "10.0.0"))
    monkeypatch.setattr(test, "_file", lambda path, label: test._Preflight(label, True, str(path)))
    monkeypatch.setattr(
        test,
        "verify_static_mod_artifacts",
        lambda *_args: (ArtifactIssue("sprint", "catalog-project", "missing"),),
    )
    monkeypatch.setattr(test, "format_artifact_issues", lambda issues: "sprint [catalog-project]: missing")
    subprocess_calls: list[Any] = []
    monkeypatch.setattr(test.subprocess, "run", lambda *args, **kwargs: subprocess_calls.append((args, kwargs)))

    with pytest.raises(typer.Exit) as raised:
        test._run_task(_context(tmp_path), "mods")

    assert raised.value.exit_code == 1
    assert subprocess_calls == []


def test_preflight_failure_is_reported_and_prevents_subprocesses(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(
        test._PREFLIGHTS,
        "unit",
        lambda _ctx: [test._Preflight("uv", False, "uv is missing")],
    )
    subprocess_calls: list[Any] = []
    monkeypatch.setattr(test.subprocess, "run", lambda *args, **kwargs: subprocess_calls.append((args, kwargs)))

    with pytest.raises(typer.Exit) as raised:
        test._run_task(_context(tmp_path), "unit")

    assert raised.value.exit_code == 1
    assert subprocess_calls == []
    payload = json.loads((tmp_path / "artifacts/test-reports/unit.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["expanded_leaves"] == ["unit"]
    assert payload["leaves"][0]["status"] == "blocked"
    assert payload["leaves"][0]["prerequisites"] == [{"name": "uv", "status": "failed", "detail": "uv is missing"}]
    assert payload["leaves"][0]["diagnostics"]["commands"] == []


@pytest.mark.parametrize(
    "payload",
    [
        _counts(collected=0),
        _counts(skipped=1),
        _counts(deselected=1),
        _counts(failed=1),
    ],
)
def test_unit_rejects_zero_skipped_deselected_or_failed_pytest_results(
    tmp_path: Path, monkeypatch: Any, payload: dict[str, int]
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, **kwargs})
        report_path = Path(args[args.index("--erenshor-report") + 1])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(test.subprocess, "run", fake_run)
    monkeypatch.setitem(test._PREFLIGHTS, "unit", lambda _ctx: _passing_preflight())
    result = runner.invoke(test.app, ["unit"], obj=_context(tmp_path))

    assert result.exit_code == 1
    payload = json.loads((tmp_path / "artifacts/test-reports/unit.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["leaves"][0]["status"] == "failed"
    assert payload["leaves"][0]["exit_code"] == 1
    assert len(calls) == 1


@pytest.mark.parametrize("report_mode", ["missing", "malformed", "shape", "counter", "incomplete", "schema"])
def test_unit_rejects_missing_malformed_or_invalid_pytest_reports(
    tmp_path: Path, monkeypatch: Any, report_mode: str
) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "unit", lambda _ctx: _passing_preflight())

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        report_path = Path(args[args.index("--erenshor-report") + 1])
        if report_mode != "missing":
            report_path.parent.mkdir(parents=True, exist_ok=True)
            contents: object = (
                {
                    "shape": [1],
                }
                if report_mode == "shape"
                else {
                    "collected": "not-an-int",
                }
                if report_mode == "counter"
                else {
                    "schema": 1,
                    "collected": 3,
                }
                if report_mode == "incomplete"
                else {
                    **_counts(),
                    "schema": 999,
                }
                if report_mode == "schema"
                else "{not-json"
            )
            report_path.write_text(contents if isinstance(contents, str) else json.dumps(contents), encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(test.subprocess, "run", fake_run)
    result = runner.invoke(test.app, ["unit"], obj=_context(tmp_path))

    assert result.exit_code == 1
    payload = json.loads((tmp_path / "artifacts/test-reports/unit.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["leaves"][0]["status"] == "failed"
    assert payload["leaves"][0]["result_counts"] == {}
    assert payload["leaves"][0]["diagnostics"]["commands"]


def test_invalid_pytest_report_validation_is_persisted_in_leaf_diagnostics(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "unit", lambda _ctx: _passing_preflight())

    def fake_run_process(argv: Sequence[str], cwd: Path) -> Any:
        report_path = Path(argv[-1])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(_valid_pytest_report(schema=99)), encoding="utf-8")
        return test._CommandResult(tuple(argv), cwd, 0, 0.0)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    with pytest.raises(typer.Exit) as raised:
        test._run_task(_context(tmp_path), "unit")

    assert raised.value.exit_code == 1
    payload = json.loads((tmp_path / "artifacts/test-reports/unit.json").read_text(encoding="utf-8"))
    diagnostics = payload["leaves"][0]["diagnostics"]
    assert isinstance(diagnostics["report_validation"], list)
    assert "schema" in str(diagnostics["report_validation"])


def test_maps_preflight_checks_toolchain_and_fixture_without_database(tmp_path: Path, monkeypatch: Any) -> None:
    executable_calls: list[str] = []
    directory_calls: list[str] = []
    file_calls: list[str] = []
    monkeypatch.setattr(
        test,
        "_executable",
        lambda name: (executable_calls.append(name) or test._Preflight(f"executable:{name}", True, "/bin/tool")),
    )
    monkeypatch.setattr(
        test,
        "_directory",
        lambda _path, label: (directory_calls.append(label) or test._Preflight(label, True, "present")),
    )
    monkeypatch.setattr(
        test,
        "_file",
        lambda _path, label: (file_calls.append(label) or test._Preflight(label, True, "present")),
    )

    checks = test._preflight_maps(_context(tmp_path, configured_maps=True))

    assert all(check.ok for check in checks)
    assert executable_calls == ["pnpm", "node"]
    assert directory_calls == ["configured maps project", "maps node_modules"]
    assert file_calls == ["maps prerender smoke", "maps fixture schema"]


def test_wiki_preflight_monkeypatches_api_and_browser_boundaries(tmp_path: Path, monkeypatch: Any) -> None:
    api_calls: list[str] = []
    browser_calls: list[bool] = []
    monkeypatch.setattr(test, "_executable", lambda name: test._Preflight(name, True, "present"))
    monkeypatch.setattr(test, "_directory", lambda _path, label: test._Preflight(label, True, "present"))
    monkeypatch.setattr(test, "_file", lambda _path, label: test._Preflight(label, True, "present"))
    monkeypatch.setattr(
        test,
        "_wiki_api_reachable",
        lambda base_url=test._WIKI_BASE_URL: (api_calls.append(base_url) or (True, "loopback")),
    )
    monkeypatch.setattr(
        test,
        "_playwright_chromium_available",
        lambda: (browser_calls.append(True) or (True, "browser")),
    )

    checks = test._preflight_wiki(_context(tmp_path))

    assert all(check.ok for check in checks)
    assert api_calls == ["http://localhost:8088"]
    assert browser_calls == [True]


def test_keyboard_interrupt_persists_exit_130_report_and_propagates(tmp_path: Path, monkeypatch: Any) -> None:
    def interrupt(_ctx: CLIContext, _task_id: str, **_kwargs: Any) -> Any:
        raise KeyboardInterrupt

    monkeypatch.setattr(test, "_run_leaf", interrupt)

    with pytest.raises(KeyboardInterrupt):
        test._run_task(_context(tmp_path), "unit")

    payload = json.loads((tmp_path / "artifacts/test-reports/unit.json").read_text(encoding="utf-8"))
    assert payload["status"] == "interrupted"
    assert payload["exit_code"] == 130
    assert payload["requested_task_id"] == "unit"
    assert payload["expanded_leaves"] == ["unit"]
    assert payload["interrupted"] is True
    assert payload["error"] == "KeyboardInterrupt"


def test_runner_exception_is_recorded_in_failed_report(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(test, "_run_leaf", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(typer.Exit) as raised:
        test._run_task(_context(tmp_path), "unit")

    assert raised.value.exit_code == 1
    payload = json.loads((tmp_path / "artifacts/test-reports/unit.json").read_text(encoding="utf-8"))
    leaf = payload["leaves"][0]
    assert leaf["status"] == "failed"
    assert leaf["prerequisites"] == []
    assert leaf["diagnostics"]["commands"] == [{"error": "boom"}]


def test_subprocess_launch_oserror_is_reported_without_fake_exit_code(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "unit", lambda _ctx: _passing_preflight())

    def fail_to_launch(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("uv executable could not be launched")

    monkeypatch.setattr(test.subprocess, "run", fail_to_launch)

    with pytest.raises(typer.Exit) as raised:
        test._run_task(_context(tmp_path), "unit")

    assert raised.value.exit_code == 1
    payload = json.loads((tmp_path / "artifacts/test-reports/unit.json").read_text(encoding="utf-8"))
    leaf = payload["leaves"][0]
    assert leaf["status"] == "failed"
    assert leaf["exit_code"] == 1
    assert leaf["diagnostics"]["commands"] == [{"error": "uv executable could not be launched"}]
    assert leaf["diagnostics"]["commands"][0].get("exit_code") != 127


def test_preflight_exception_is_recorded_without_running_subprocess(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "unit", lambda _ctx: (_ for _ in ()).throw(RuntimeError("preflight boom")))
    subprocess_calls: list[Any] = []
    monkeypatch.setattr(test.subprocess, "run", lambda *args, **kwargs: subprocess_calls.append((args, kwargs)))

    with pytest.raises(typer.Exit):
        test._run_task(_context(tmp_path), "unit")

    assert subprocess_calls == []
    payload = json.loads((tmp_path / "artifacts/test-reports/unit.json").read_text(encoding="utf-8"))
    assert payload["leaves"][0]["diagnostics"]["commands"] == [{"error": "preflight boom"}]


def test_nonzero_runner_outcome_writes_failed_report_with_diagnostics(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "unit", lambda _ctx: _passing_preflight())
    monkeypatch.setattr(test.time, "monotonic", lambda: 10.0)

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        report_path = Path(args[args.index("--erenshor-report") + 1])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(_valid_pytest_report()), encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=23)

    monkeypatch.setattr(test.subprocess, "run", fake_run)
    with pytest.raises(typer.Exit) as raised:
        test._run_task(_context(tmp_path), "unit")

    assert raised.value.exit_code == 23

    payload = json.loads((tmp_path / "artifacts/test-reports/unit.json").read_text(encoding="utf-8"))
    assert payload["schema"] == 1
    assert payload["requested_task_id"] == "unit"
    assert payload["expanded_leaves"] == ["unit"]
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 23
    leaf = payload["leaves"][0]
    assert leaf["result_counts"] == _counts()
    assert leaf["diagnostics"]["commands"][0]["exit_code"] == 23
    assert leaf["duration_seconds"] >= 0
    assert payload["duration_seconds"] >= 0


def test_success_report_contains_schema_identity_prerequisites_counts_diagnostics_and_duration(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(test.time, "monotonic", lambda: 42.0)
    monkeypatch.setattr(test, "_run_leaf", lambda _ctx, task_id, **_kwargs: _leaf_result(task_id))

    test._run_task(_context(tmp_path), "ci")

    payload = json.loads((tmp_path / "artifacts/test-reports/ci.json").read_text(encoding="utf-8"))
    assert payload["schema"] == 1
    assert payload["requested_task"] == "ci"
    assert payload["requested_task_id"] == "ci"
    assert payload["expanded_leaves"] == ["unit", "contract", "maps", "mods"]
    assert payload["status"] == "passed"
    assert payload["exit_code"] == 0
    assert payload["duration_seconds"] >= 0
    assert [leaf["task_id"] for leaf in payload["leaves"]] == payload["expanded_leaves"]
    for leaf in payload["leaves"]:
        assert leaf["prerequisites"] == [{"name": "tool", "status": "passed", "detail": "/bin/tool"}]
        assert leaf["result_counts"]["collected"] == 3
        assert leaf["diagnostics"]["commands"][0]["argv"] == ["tool", "--check"]
        assert leaf["duration_seconds"] >= 0


def test_report_write_is_atomic_and_deterministic(tmp_path: Path, monkeypatch: Any) -> None:
    payload = test._report_payload("unit", ["unit"], [_leaf_result("unit")], 0.5)
    replacements: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def record_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(test.os, "replace", record_replace)
    destination = test._write_report(tmp_path, "unit", payload)
    first = destination.read_bytes()
    test._write_report(tmp_path, "unit", payload)
    second = destination.read_bytes()

    assert destination == tmp_path / "artifacts/test-reports/unit.json"
    assert first == second
    assert len(replacements) == 2
    assert all(source.parent == destination.parent for source, destination in replacements)
    assert all(source.name.startswith(".unit.json.") and source.suffix == ".tmp" for source, _ in replacements)


def test_composite_invokes_each_expanded_leaf_once_then_release_actions(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[tuple[str, bool]] = []
    command_calls: list[tuple[str, ...]] = []
    barrier = Barrier(6)
    call_lock = Lock()

    def fake_leaf(_ctx: CLIContext, task_id: str, **kwargs: Any) -> test._LeafResult:
        barrier.wait(timeout=5)
        with call_lock:
            calls.append((task_id, kwargs.get("wiki_clean_parity", False)))
        return _leaf_result(task_id)

    def fake_process(argv: Sequence[str], cwd: Path) -> test._CommandResult:
        command_calls.append(tuple(argv))
        return test._CommandResult(tuple(argv), cwd, 0, 0.0)

    monkeypatch.setattr(test, "_run_leaf", fake_leaf)
    monkeypatch.setattr(test, "_run_process", fake_process)

    test._run_task(_context(tmp_path), "release", wiki_clean_parity=True)

    expected_leaves = ["unit", "contract", "maps", "mods", "data", "wiki"]
    assert sorted(task_id for task_id, _clean in calls) == sorted(expected_leaves)
    assert ("wiki", True) in calls
    assert command_calls == list(test._RELEASE_COMMANDS)
    payload = json.loads((tmp_path / "artifacts/test-reports/release.json").read_text(encoding="utf-8"))
    assert [leaf["task_id"] for leaf in payload["leaves"]] == expected_leaves
    assert len(expected_leaves) == len(set(expected_leaves)) == 6
    assert payload["release_actions"]["status"] == "passed"
    assert payload["release_actions"]["result_counts"] == {"commands": 3, "completed_commands": 3}


def test_release_actions_are_blocked_when_a_leaf_fails(tmp_path: Path, monkeypatch: Any) -> None:
    command_calls: list[Sequence[str]] = []

    def fake_leaf(_ctx: CLIContext, task_id: str, **_kwargs: Any) -> test._LeafResult:
        result = _leaf_result(task_id)
        if task_id == "data":
            result.status = "failed"
            result.exit_code = 1
        return result

    monkeypatch.setattr(test, "_run_leaf", fake_leaf)
    monkeypatch.setattr(test, "_run_process", lambda argv, _cwd: command_calls.append(argv))

    with pytest.raises(typer.Exit):
        test._run_task(_context(tmp_path), "release", wiki_clean_parity=True)

    assert command_calls == []
    payload = json.loads((tmp_path / "artifacts/test-reports/release.json").read_text(encoding="utf-8"))
    assert payload["release_actions"]["status"] == "blocked"
    assert payload["release_actions"]["diagnostics"]["reason"].startswith("release actions require")


def test_explicit_unit_coverage_uses_one_xml_report(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "unit", lambda _ctx: _passing_preflight())
    monkeypatch.setattr(test, "_read_pytest_report", lambda _path: (_counts(), None))
    calls: list[list[str]] = []

    def fake_run_process(argv: list[str], _cwd: Path) -> Any:
        calls.append(argv)
        return test._CommandResult(tuple(argv), tmp_path, 0, 0.0)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    result = test._run_leaf(_context(tmp_path), "unit", coverage=True)

    assert result.status == "passed"
    assert calls[0].count("--cov=src/erenshor") == 1
    assert calls[0].count("--cov-report=xml") == 1
    assert calls[0].count("--cov-branch") == 1
    assert "--cov-report=term-missing" not in calls[0]


def test_focused_unit_command_stays_on_unit_tree(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(test._PREFLIGHTS, "unit", lambda _ctx: _passing_preflight())
    monkeypatch.setattr(test, "_read_pytest_report", lambda _path: (_counts(collected=12), None))
    calls: list[list[str]] = []

    def fake_run_process(argv: list[str], _cwd: Path) -> Any:
        calls.append(argv)
        return test._CommandResult(tuple(argv), tmp_path, 0, 0.0)

    monkeypatch.setattr(test, "_run_process", fake_run_process)
    result = test._run_leaf(_context(tmp_path), "unit")

    assert result.status == "passed"
    assert calls[0][3] == "tests/unit"
    assert "--quiet" in calls[0]
    assert "--cov" not in calls[0]


__all__ = []
