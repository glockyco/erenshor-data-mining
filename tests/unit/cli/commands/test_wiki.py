"""Unit tests for wiki CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# Patch the decorator BEFORE importing the command module
with patch("erenshor.cli.preconditions.require_preconditions") as mock_decorator:
    # Make it a passthrough decorator
    mock_decorator.side_effect = lambda *checks: lambda func: func
    from erenshor.cli.main import app

from erenshor.application.wiki.services.page import OperationResult

runner = CliRunner()


@pytest.fixture
def mock_operation_result():
    """Create mock operation result."""
    return OperationResult(
        total=10,
        succeeded=10,
        skipped=0,
        failed=0,
        warnings=[],
        errors=[],
    )


@pytest.fixture
def mock_operation_result_with_warnings():
    """Create mock operation result with warnings."""
    return OperationResult(
        total=10,
        succeeded=9,
        skipped=0,
        failed=0,
        warnings=["Manual edit preserved: Item:Iron Sword"],
        errors=[],
    )


@pytest.fixture
def mock_operation_result_with_failures():
    """Create mock operation result with failures."""
    return OperationResult(
        total=10,
        succeeded=8,
        skipped=0,
        failed=2,
        warnings=[],
        errors=["Failed to update Item:Broken Sword", "Failed to update Item:Missing Item"],
    )


class TestWikiFetchCommand:
    """Test wiki fetch command."""

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_fetch_success(self, mock_create_service, mock_operation_result):
        """Test successful fetch."""
        mock_service = MagicMock()
        mock_service.fetch_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "fetch"])

        assert result.exit_code == 0
        mock_service.fetch_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_fetch_with_limit(self, mock_create_service, mock_operation_result):
        """Test fetch with limit parameter."""
        mock_service = MagicMock()
        mock_service.fetch_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "fetch", "--limit", "5"])

        assert result.exit_code == 0
        mock_service.fetch_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_fetch_with_force(self, mock_create_service, mock_operation_result):
        """Test fetch with force flag."""
        mock_service = MagicMock()
        mock_service.fetch_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "fetch", "--force"])

        assert result.exit_code == 0
        mock_service.fetch_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_fetch_dry_run(self, mock_create_service, mock_operation_result):
        """Test fetch in dry-run mode."""
        mock_service = MagicMock()
        mock_service.fetch_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["--dry-run", "wiki", "fetch"])

        assert result.exit_code == 0
        mock_service.fetch_all.assert_called_once()


class TestWikiGenerateCommand:
    """Test wiki generate command."""

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_generate_success(self, mock_create_service, mock_operation_result):
        """Test successful generate."""
        mock_service = MagicMock()
        mock_service.generate_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "generate"])

        assert result.exit_code == 0
        mock_service.generate_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_generate_with_limit(self, mock_create_service, mock_operation_result):
        """Test generate with limit parameter."""
        mock_service = MagicMock()
        mock_service.generate_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "generate", "--limit", "5"])

        assert result.exit_code == 0
        mock_service.generate_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_generate_dry_run(self, mock_create_service, mock_operation_result):
        """Test generate in dry-run mode."""
        mock_service = MagicMock()
        mock_service.generate_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["--dry-run", "wiki", "generate"])

        assert result.exit_code == 0
        mock_service.generate_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_generate_with_warnings(self, mock_create_service, mock_operation_result_with_warnings):
        """Test generate that completes with warnings."""
        mock_service = MagicMock()
        mock_service.generate_all.return_value = mock_operation_result_with_warnings
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "generate"])

        # Should exit 0 even with warnings
        assert result.exit_code == 0
        mock_service.generate_all.assert_called_once()


class TestWikiDeployCommand:
    """Test wiki deploy command."""

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_success(self, mock_create_service, mock_operation_result):
        """Test successful deploy."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "deploy"])

        assert result.exit_code == 0
        mock_service.deploy_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_with_limit(self, mock_create_service, mock_operation_result):
        """Test deploy with limit parameter."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "deploy", "--limit", "5"])

        assert result.exit_code == 0
        mock_service.deploy_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_dry_run(self, mock_create_service, mock_operation_result):
        """Test deploy in dry-run mode."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["--dry-run", "wiki", "deploy"])

        assert result.exit_code == 0
        mock_service.deploy_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_with_failures(self, mock_create_service, mock_operation_result_with_failures):
        """Test deploy that completes with failures."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result_with_failures
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "deploy"])

        # Should exit 1 with failures
        assert result.exit_code == 1
        mock_service.deploy_all.assert_called_once()
