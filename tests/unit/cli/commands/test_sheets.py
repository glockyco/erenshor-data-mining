"""Unit tests for sheets CLI commands."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from erenshor.application.sheets.service import DeploymentResult, SheetMetadata
from erenshor.cli.commands import sheets

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

runner = CliRunner()


@dataclass
class _DeployRequest:
    sheet_names: list[str] | None
    all_sheets: bool
    dry_run: bool


@dataclass
class _FakeSheetsService:
    """The double for the Google Sheets collaborator: records what each deploy asked for."""

    sheets: list[SheetMetadata] = field(default_factory=list)
    deployment: DeploymentResult | None = None
    list_error: Exception | None = None
    deploy_error: Exception | None = None
    deploy_requests: list[_DeployRequest] = field(default_factory=list)

    def list_sheets(self) -> list[SheetMetadata]:
        if self.list_error is not None:
            raise self.list_error
        return self.sheets

    def deploy(self, sheet_names: list[str] | None, all_sheets: bool, dry_run: bool) -> DeploymentResult:
        self.deploy_requests.append(_DeployRequest(sheet_names, all_sheets, dry_run))
        if self.deploy_error is not None:
            raise self.deploy_error
        assert self.deployment is not None
        return self.deployment


def _use(monkeypatch: pytest.MonkeyPatch, service: _FakeSheetsService) -> None:
    """Route the command's composition function to this fake through its own override parameter.

    Typer's CLI boundary has no seam for a test to pass a keyword argument
    into a command it invokes, so this still monkeypatches the module-level
    name; the difference from `@patch` is that the replacement calls the real
    `_create_sheets_service` with the fake through `service`, instead of
    discarding the function and its contract entirely.
    """
    create = sheets._create_sheets_service
    monkeypatch.setattr(sheets, "_create_sheets_service", lambda cli_ctx: create(cli_ctx, service=service))


@pytest.fixture
def two_sheets() -> list[SheetMetadata]:
    from pathlib import Path

    return [
        SheetMetadata(name="items", description="All items with stats", query_file=Path("items.sql"), row_count=100),
        SheetMetadata(
            name="characters", description="All characters and enemies", query_file=Path("characters.sql"), row_count=50
        ),
    ]


@pytest.fixture
def clean_deployment() -> DeploymentResult:
    return DeploymentResult(total_sheets=2, deployed=2, failed=0, total_rows=150, errors=[], duration_seconds=5.0)


@pytest.fixture
def failed_deployment() -> DeploymentResult:
    return DeploymentResult(
        total_sheets=2,
        deployed=1,
        failed=1,
        total_rows=100,
        errors=["Failed to deploy sheet 'characters'"],
        duration_seconds=3.0,
    )


class TestSheetsListCommand:
    """Test sheets list command."""

    def test_list_sheets_success(
        self, monkeypatch: pytest.MonkeyPatch, two_sheets: list[SheetMetadata], cli_context: CLIContext
    ):
        """Test successful sheet listing."""
        _use(monkeypatch, _FakeSheetsService(sheets=two_sheets))

        result = runner.invoke(sheets.app, ["list"], obj=cli_context)

        assert result.exit_code == 0
        assert "items" in result.stdout
        assert "characters" in result.stdout
        assert "Total: 2 sheet(s)" in result.stdout

    def test_list_sheets_empty(self, monkeypatch: pytest.MonkeyPatch, cli_context: CLIContext):
        """Test listing when no sheets available."""
        _use(monkeypatch, _FakeSheetsService(sheets=[]))

        result = runner.invoke(sheets.app, ["list"], obj=cli_context)

        assert result.exit_code == 0
        assert "No sheets found" in result.stdout

    def test_list_sheets_service_exception(self, monkeypatch: pytest.MonkeyPatch, cli_context: CLIContext):
        """Test listing when service raises exception."""
        _use(monkeypatch, _FakeSheetsService(list_error=Exception("Service error")))

        result = runner.invoke(sheets.app, ["list"], obj=cli_context)

        assert result.exit_code == 1
        assert "Error listing sheets" in result.stdout


class TestSheetsDeployCommand:
    """Test sheets deploy command."""

    def test_deploy_all_sheets_success(
        self, monkeypatch: pytest.MonkeyPatch, clean_deployment: DeploymentResult, cli_context: CLIContext
    ):
        """Test successful deployment of all sheets."""
        service = _FakeSheetsService(deployment=clean_deployment)
        _use(monkeypatch, service)

        result = runner.invoke(sheets.app, ["deploy", "--all-sheets"], obj=cli_context)

        assert result.exit_code == 0
        assert service.deploy_requests == [_DeployRequest(sheet_names=None, all_sheets=True, dry_run=False)]

    def test_deploy_specific_sheets_success(
        self, monkeypatch: pytest.MonkeyPatch, clean_deployment: DeploymentResult, cli_context: CLIContext
    ):
        """Test successful deployment of specific sheets."""
        service = _FakeSheetsService(deployment=clean_deployment)
        _use(monkeypatch, service)

        result = runner.invoke(
            sheets.app,
            ["deploy", "--sheets", "items", "--sheets", "characters"],
            obj=cli_context,
        )

        assert result.exit_code == 0
        assert service.deploy_requests == [
            _DeployRequest(sheet_names=["items", "characters"], all_sheets=False, dry_run=False)
        ]

    def test_deploy_dry_run(
        self, monkeypatch: pytest.MonkeyPatch, clean_deployment: DeploymentResult, cli_context: CLIContext
    ):
        """Test deployment in dry-run mode."""
        service = _FakeSheetsService(deployment=clean_deployment)
        _use(monkeypatch, service)

        result = runner.invoke(
            sheets.app,
            ["deploy", "--all-sheets"],
            obj=replace(cli_context, dry_run=True),
        )

        assert result.exit_code == 0
        assert "Dry-run: True" in result.stdout
        assert service.deploy_requests == [_DeployRequest(sheet_names=None, all_sheets=True, dry_run=True)]

    def test_deploy_no_sheets_specified(self, monkeypatch: pytest.MonkeyPatch, cli_context: CLIContext):
        """Test deployment when no sheets are specified."""
        service = _FakeSheetsService()
        _use(monkeypatch, service)

        result = runner.invoke(sheets.app, ["deploy"], obj=cli_context)

        assert result.exit_code == 1
        assert "Must specify either --sheets or --all-sheets" in result.stdout
        assert service.deploy_requests == []

    def test_deploy_with_failures(
        self, monkeypatch: pytest.MonkeyPatch, failed_deployment: DeploymentResult, cli_context: CLIContext
    ):
        """Test deployment that completes with failures."""
        _use(monkeypatch, _FakeSheetsService(deployment=failed_deployment))

        result = runner.invoke(sheets.app, ["deploy", "--all-sheets"], obj=cli_context)

        assert result.exit_code == 1

    def test_deploy_service_exception(self, monkeypatch: pytest.MonkeyPatch, cli_context: CLIContext):
        """Test deployment when service raises exception."""
        _use(monkeypatch, _FakeSheetsService(deploy_error=Exception("Service error")))

        result = runner.invoke(sheets.app, ["deploy", "--all-sheets"], obj=cli_context)

        assert result.exit_code == 1
        assert "Error during sheets deployment" in result.stdout

    def test_deploy_missing_spreadsheet_id(self, monkeypatch: pytest.MonkeyPatch, cli_context: CLIContext):
        """Test deployment when spreadsheet_id is not configured."""

        def _raise(cli_ctx: CLIContext) -> sheets.SheetsService:
            raise ValueError("No spreadsheet_id configured")

        monkeypatch.setattr(sheets, "_create_sheets_service", _raise)

        result = runner.invoke(sheets.app, ["deploy", "--all-sheets"], obj=cli_context)

        assert result.exit_code == 1
        assert "Error during sheets deployment" in result.stdout
