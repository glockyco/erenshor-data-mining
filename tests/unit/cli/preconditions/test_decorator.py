"""Tests for precondition decorator."""

from pathlib import Path
from unittest.mock import Mock

import pytest
import typer

from erenshor.cli.context import CLIContext
from erenshor.cli.preconditions.base import PreconditionResult
from erenshor.cli.preconditions.decorator import require_preconditions
from erenshor.infrastructure.config.schema import (
    Config,
    GlobalConfig,
    LoggingConfig,
    MediaWikiConfig,
    PathsConfig,
    UnityConfig,
    VariantConfig,
)


@pytest.fixture
def minimal_config(tmp_path: Path) -> Config:
    """Create a minimal valid configuration for testing."""
    return Config(
        version="0.3",
        default_variant="main",
        global_=GlobalConfig(
            unity=UnityConfig(
                version="2021.3.45f2",
                path="/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app",
                timeout=3600,
            ),
            logging=LoggingConfig(level="info"),
            paths=PathsConfig(
                logs=".erenshor/logs",
                state=".erenshor/state.json",
            ),
            mediawiki=MediaWikiConfig(
                api_url="https://wiki.example.com/api.php",
                bot_username="TestBot",
            ),
        ),
        variants={
            "main": VariantConfig(
                enabled=True,
                name="Main Game",
                app_id="2382520",
                unity_project="variants/main/unity",
                editor_scripts="src/Assets/Editor",
                database_raw="variants/main/erenshor-main-raw.sqlite",
                database="variants/main/erenshor-main.sqlite",
                logs="variants/main/logs",
                backups="variants/main/backups",
                images_output="variants/main/images",
                wiki="variants/main/wiki",
            ),
        },
    )


@pytest.fixture
def cli_context(minimal_config: Config, tmp_path: Path) -> CLIContext:
    """Create CLI context for testing."""
    return CLIContext(
        config=minimal_config,
        variant="main",
        dry_run=False,
        repo_root=tmp_path,
    )


def test_decorator_with_passing_checks(cli_context: CLIContext):
    """Test decorator with all checks passing."""

    def always_pass(context: dict) -> PreconditionResult:
        return PreconditionResult(
            passed=True,
            check_name="always_pass",
            message="Check passed",
        )

    @require_preconditions(always_pass)
    def test_command(ctx: typer.Context):
        return "success"

    # Create typer context with CLIContext
    mock_ctx = Mock(spec=typer.Context)
    mock_ctx.obj = cli_context

    # Call should succeed
    result = test_command(mock_ctx)
    assert result == "success"


def test_decorator_with_failing_check(cli_context: CLIContext):
    """Test decorator aborts when check fails."""

    def always_fail(context: dict) -> PreconditionResult:
        return PreconditionResult(
            passed=False,
            check_name="always_fail",
            message="Check failed",
            detail="Something went wrong",
        )

    @require_preconditions(always_fail)
    def test_command(ctx: typer.Context):
        return "success"

    mock_ctx = Mock(spec=typer.Context)
    mock_ctx.obj = cli_context

    # Call should raise Exit
    with pytest.raises(typer.Exit) as exc_info:
        test_command(mock_ctx)

    assert exc_info.value.exit_code == 1


def test_decorator_with_mixed_checks(cli_context: CLIContext):
    """Test decorator shows all results when some fail."""

    def check_pass(context: dict) -> PreconditionResult:
        return PreconditionResult(
            passed=True,
            check_name="check_pass",
            message="This passed",
        )

    def check_fail(context: dict) -> PreconditionResult:
        return PreconditionResult(
            passed=False,
            check_name="check_fail",
            message="This failed",
        )

    @require_preconditions(check_pass, check_fail)
    def test_command(ctx: typer.Context):
        return "success"

    mock_ctx = Mock(spec=typer.Context)
    mock_ctx.obj = cli_context

    # Should fail and show both results
    with pytest.raises(typer.Exit) as exc_info:
        test_command(mock_ctx)

    assert exc_info.value.exit_code == 1


def test_decorator_runs_all_checks_before_failing(cli_context: CLIContext):
    """Test that all checks run even if first one fails."""
    check1_called = False
    check2_called = False

    def check1(context: dict) -> PreconditionResult:
        nonlocal check1_called
        check1_called = True
        return PreconditionResult(
            passed=False,
            check_name="check1",
            message="Check 1 failed",
        )

    def check2(context: dict) -> PreconditionResult:
        nonlocal check2_called
        check2_called = True
        return PreconditionResult(
            passed=False,
            check_name="check2",
            message="Check 2 failed",
        )

    @require_preconditions(check1, check2)
    def test_command(ctx: typer.Context):
        return "success"

    mock_ctx = Mock(spec=typer.Context)
    mock_ctx.obj = cli_context

    with pytest.raises(typer.Exit):
        test_command(mock_ctx)

    # Both checks should have been called
    assert check1_called is True
    assert check2_called is True


def test_decorator_handles_check_exception(cli_context: CLIContext):
    """Test decorator handles exceptions raised by checks."""

    def check_raises(context: dict) -> PreconditionResult:
        raise ValueError("Something went wrong")

    @require_preconditions(check_raises)
    def test_command(ctx: typer.Context):
        return "success"

    mock_ctx = Mock(spec=typer.Context)
    mock_ctx.obj = cli_context

    # Should catch exception and convert to failure
    with pytest.raises(typer.Exit) as exc_info:
        test_command(mock_ctx)

    assert exc_info.value.exit_code == 1


def test_decorator_with_no_checks(cli_context: CLIContext):
    """Test decorator with no checks (should just run command)."""

    @require_preconditions()
    def test_command(ctx: typer.Context):
        return "success"

    mock_ctx = Mock(spec=typer.Context)
    mock_ctx.obj = cli_context

    result = test_command(mock_ctx)
    assert result == "success"


def test_decorator_rejects_missing_context():
    """Test decorator fails when no ctx parameter is provided."""

    def check_variant(context: dict) -> PreconditionResult:
        variant = context.get("variant", "unknown")
        return PreconditionResult(
            passed=True,
            check_name="check_variant",
            message=f"Variant: {variant}",
        )

    @require_preconditions(check_variant)
    def test_command(variant="test"):
        return f"Ran with {variant}"

    # Call without ctx parameter should raise error
    with pytest.raises(RuntimeError) as exc_info:
        test_command(variant="test")

    assert "Command missing ctx parameter" in str(exc_info.value)
