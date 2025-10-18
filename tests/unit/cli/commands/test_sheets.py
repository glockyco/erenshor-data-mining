"""Unit tests for sheets CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# Patch the decorator BEFORE importing the command module
with patch("erenshor.cli.preconditions.require_preconditions") as mock_decorator:
    # Make it a passthrough decorator
    mock_decorator.side_effect = lambda *checks: lambda func: func
    from erenshor.cli.main import app

from erenshor.application.services.sheets_service import DeploymentResult, SheetMetadata

runner = CliRunner()


@pytest.fixture
def mock_cli_context():
    """Create mock CLI context."""
    context = MagicMock()
    context.config.variants = {
        "main": MagicMock(
            resolved_database=MagicMock(return_value="/path/to/database.sqlite"),
            google_sheets=MagicMock(spreadsheet_id="abc123"),
        )
    }
    context.config.global_.google_sheets = MagicMock(
        resolved_credentials_file=MagicMock(return_value="/path/to/credentials.json")
    )
    context.variant = "main"
    context.dry_run = False
    context.repo_root = MagicMock()
    return context


@pytest.fixture
def mock_sheet_metadata():
    """Create mock sheet metadata."""
    return [
        SheetMetadata(
            name="items",
            description="All items with stats",
            query_file=MagicMock(name="items.sql"),
            row_count=100,
        ),
        SheetMetadata(
            name="characters",
            description="All characters and enemies",
            query_file=MagicMock(name="characters.sql"),
            row_count=50,
        ),
    ]


@pytest.fixture
def mock_deployment_result():
    """Create mock deployment result."""
    return DeploymentResult(
        total_sheets=2,
        deployed=2,
        failed=0,
        total_rows=150,
        errors=[],
        duration_seconds=5.0,
    )


@pytest.fixture
def mock_deployment_result_with_failures():
    """Create mock deployment result with failures."""
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

    @patch("erenshor.cli.commands.sheets._create_sheets_service")
    def test_list_sheets_success(self, mock_create_service, mock_sheet_metadata):
        """Test successful sheet listing."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.list_sheets.return_value = mock_sheet_metadata
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["sheets", "list"])

        # Verify
        assert result.exit_code == 0
        assert "items" in result.stdout
        assert "characters" in result.stdout
        assert "Total: 2 sheet(s)" in result.stdout
        mock_service.list_sheets.assert_called_once()

    @patch("erenshor.cli.commands.sheets._create_sheets_service")
    def test_list_sheets_empty(self, mock_create_service):
        """Test listing when no sheets available."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.list_sheets.return_value = []
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["sheets", "list"])

        # Verify
        assert result.exit_code == 0
        assert "No sheets found" in result.stdout

    @patch("erenshor.cli.commands.sheets._create_sheets_service")
    def test_list_sheets_service_exception(self, mock_create_service):
        """Test listing when service raises exception."""
        # Setup mock service to raise exception
        mock_service = MagicMock()
        mock_service.list_sheets.side_effect = Exception("Service error")
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["sheets", "list"])

        # Verify
        assert result.exit_code == 1
        assert "Error listing sheets" in result.stdout


class TestSheetsDeployCommand:
    """Test sheets deploy command."""

    @patch("erenshor.cli.commands.sheets._create_sheets_service")
    def test_deploy_all_sheets_success(self, mock_create_service, mock_deployment_result):
        """Test successful deployment of all sheets."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.deploy.return_value = mock_deployment_result
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["sheets", "deploy", "--all-sheets"])

        # Verify
        assert result.exit_code == 0
        mock_service.deploy.assert_called_once_with(sheet_names=None, all_sheets=True, dry_run=False)

    @patch("erenshor.cli.commands.sheets._create_sheets_service")
    def test_deploy_specific_sheets_success(self, mock_create_service, mock_deployment_result):
        """Test successful deployment of specific sheets."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.deploy.return_value = mock_deployment_result
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["sheets", "deploy", "--sheets", "items", "--sheets", "characters"])

        # Verify
        assert result.exit_code == 0
        mock_service.deploy.assert_called_once_with(
            sheet_names=["items", "characters"], all_sheets=False, dry_run=False
        )

    @patch("erenshor.cli.commands.sheets._create_sheets_service")
    def test_deploy_dry_run(self, mock_create_service, mock_deployment_result):
        """Test deployment in dry-run mode."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.deploy.return_value = mock_deployment_result
        mock_create_service.return_value = mock_service

        # Run command with global --dry-run flag
        result = runner.invoke(app, ["--dry-run", "sheets", "deploy", "--all-sheets"])

        # Verify
        assert result.exit_code == 0
        mock_service.deploy.assert_called_once_with(sheet_names=None, all_sheets=True, dry_run=True)

    @patch("erenshor.cli.commands.sheets._create_sheets_service")
    def test_deploy_no_sheets_specified(self, mock_create_service):
        """Test deployment when no sheets are specified."""
        # Setup mock service (won't be called)
        mock_service = MagicMock()
        mock_create_service.return_value = mock_service

        # Run command without --sheets or --all-sheets
        result = runner.invoke(app, ["sheets", "deploy"])

        # Verify
        assert result.exit_code == 1
        assert "Must specify either --sheets or --all-sheets" in result.stdout
        mock_service.deploy.assert_not_called()

    @patch("erenshor.cli.commands.sheets._create_sheets_service")
    def test_deploy_with_failures(self, mock_create_service, mock_deployment_result_with_failures):
        """Test deployment that completes with failures."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.deploy.return_value = mock_deployment_result_with_failures
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["sheets", "deploy", "--all-sheets"])

        # Verify - should exit 1 with failures
        assert result.exit_code == 1
        mock_service.deploy.assert_called_once()

    @patch("erenshor.cli.commands.sheets._create_sheets_service")
    def test_deploy_service_exception(self, mock_create_service):
        """Test deployment when service raises exception."""
        # Setup mock service to raise exception
        mock_service = MagicMock()
        mock_service.deploy.side_effect = Exception("Service error")
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["sheets", "deploy", "--all-sheets"])

        # Verify
        assert result.exit_code == 1
        assert "Error during sheets deployment" in result.stdout

    @patch("erenshor.cli.commands.sheets._create_sheets_service")
    def test_deploy_missing_spreadsheet_id(self, mock_create_service):
        """Test deployment when spreadsheet_id is not configured."""
        # Setup mock service creation to raise ValueError
        mock_create_service.side_effect = ValueError("No spreadsheet_id configured")

        # Run command
        result = runner.invoke(app, ["sheets", "deploy", "--all-sheets"])

        # Verify
        assert result.exit_code == 1
        assert "Error during sheets deployment" in result.stdout
