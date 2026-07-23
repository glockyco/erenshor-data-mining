"""Observable contracts for the Python test CLI command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from erenshor.cli import main
from erenshor.cli.commands import test
from erenshor.cli.context import CLIContext

runner = CliRunner()


def _context(tmp_path: Path) -> CLIContext:
    return CLIContext(
        config=SimpleNamespace(),
        variant="main",
        dry_run=False,
        repo_root=tmp_path,
    )


def _subprocess_with_report(
    payload: object | None,
    calls: list[dict[str, Any]],
    *,
    returncode: int = 0,
) -> Any:
    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, **kwargs})
        if payload is not None:
            report_option = args.index("--erenshor-report")
            report_path = Path(args[report_option + 1])
            report_path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=returncode)

    return fake_run


def test_unit_selects_unit_path_uses_repository_cwd_and_accepts_report(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        test.subprocess,
        "run",
        _subprocess_with_report(
            {"collected": 12, "deselected": 0, "skipped": 0, "failed": 0, "exit_code": 0},
            calls,
        ),
    )

    result = runner.invoke(test.app, ["unit"], obj=_context(tmp_path))

    assert result.exit_code == 0
    assert len(calls) == 1
    invocation = calls[0]
    assert invocation["cwd"] == tmp_path
    args = invocation["args"]
    assert args[:4] == ["uv", "run", "pytest", "tests/unit"]
    assert "-m" not in args
    assert args[args.index("-p") + 1] == "erenshor.cli.commands.test"
    assert args[args.index("--erenshor-report") + 1]


def test_unit_propagates_pytest_exit_code_exactly(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        test.subprocess,
        "run",
        _subprocess_with_report(None, calls, returncode=37),
    )

    result = runner.invoke(test.app, ["unit"], obj=_context(tmp_path))

    assert result.exit_code == 37
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"collected": 0, "deselected": 0, "skipped": 0, "exit_code": 0},
            "collected=0",
        ),
        (
            {"collected": 4, "deselected": 0, "skipped": 1, "exit_code": 0},
            "skipped=1",
        ),
        (
            {"collected": 4, "deselected": 2, "skipped": 0, "exit_code": 0},
            "deselected=2",
        ),
    ],
)
def test_unit_rejects_incomplete_collection_report(
    tmp_path: Path,
    monkeypatch: Any,
    payload: dict[str, int],
    message: str,
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        test.subprocess,
        "run",
        _subprocess_with_report(payload, calls),
    )

    result = runner.invoke(test.app, ["unit"], obj=_context(tmp_path))

    assert result.exit_code == 1
    assert message in result.output


@pytest.mark.parametrize("payload", [None, "not-json"])
def test_unit_rejects_missing_or_malformed_report(tmp_path: Path, monkeypatch: Any, payload: object | None) -> None:
    calls: list[dict[str, Any]] = []
    if payload == "not-json":

        def write_malformed_report(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append({"args": args, **kwargs})
            report_option = args.index("--erenshor-report")
            Path(args[report_option + 1]).write_text("{not-json", encoding="utf-8")
            return subprocess.CompletedProcess(args=args, returncode=0)

        monkeypatch.setattr(test.subprocess, "run", write_malformed_report)
    else:
        monkeypatch.setattr(
            test.subprocess,
            "run",
            _subprocess_with_report(None, calls),
        )

    result = runner.invoke(test.app, ["unit"], obj=_context(tmp_path))

    assert result.exit_code == 1
    if payload is None:
        assert "machine-readable report" in result.output
    else:
        assert "Unable to read the pytest report" in result.output


def test_all_tests_callback_preserves_integration_command_surface(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[tuple[CLIContext, list[str], bool]] = []

    def fake_run(
        cli_ctx: CLIContext,
        arguments: list[str],
        *,
        coverage: bool = False,
        require_complete: bool = False,
    ) -> None:
        calls.append((cli_ctx, arguments, coverage))
        assert require_complete is False

    monkeypatch.setattr(test, "_run_pytest", fake_run)
    callback_context = SimpleNamespace(invoked_subcommand=None, obj=_context(tmp_path))

    test.test_callback(callback_context, coverage=True)

    assert calls == [(_context(tmp_path), [], True)]


def test_root_registers_test_group_and_exposes_unit_help() -> None:
    root_help = runner.invoke(main.app, ["--help"])
    assert root_help.exit_code == 0
    assert "test" in root_help.output
    assert "Run tests and validation" in root_help.output

    result = runner.invoke(main.app, ["test", "--help"])

    assert result.exit_code == 0
    assert "unit" in result.output
    assert "coverage" in result.output
    assert "integration" in result.output


def test_root_routes_test_unit_to_registered_command(tmp_path: Path, monkeypatch: Any) -> None:
    config = SimpleNamespace(
        global_=SimpleNamespace(logging=SimpleNamespace(level="info")),
        variants={"main": object()},
    )
    monkeypatch.setattr(main, "load_config", lambda: config)
    monkeypatch.setattr(main, "get_repo_root", lambda: tmp_path)
    monkeypatch.setattr(main, "setup_logging", lambda *_args, **_kwargs: None)

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        test.subprocess,
        "run",
        _subprocess_with_report(
            {"collected": 2, "deselected": 0, "skipped": 0, "failed": 0, "exit_code": 0},
            calls,
        ),
    )

    result = runner.invoke(main.app, ["test", "unit"])

    assert result.exit_code == 0


def test_unknown_test_subcommand_fails() -> None:
    result = runner.invoke(test.app, ["unknown"])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_integration_routes_marker_uses_repository_cwd_and_propagates_exit_code(
    tmp_path: Path, monkeypatch: Any
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, **kwargs})
        return subprocess.CompletedProcess(args=args, returncode=23)

    monkeypatch.setattr(test.subprocess, "run", fake_run)

    result = runner.invoke(test.app, ["integration"], obj=_context(tmp_path))

    assert result.exit_code == 23
    assert calls == [
        {
            "args": ["uv", "run", "pytest", "-m", "integration"],
            "cwd": tmp_path,
            "check": False,
        }
    ]
