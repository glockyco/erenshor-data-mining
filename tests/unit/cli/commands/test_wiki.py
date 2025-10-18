"""Unit tests for wiki CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# Patch the decorator BEFORE importing the command module
with patch("erenshor.cli.preconditions.require_preconditions") as mock_decorator:
    # Make it a passthrough decorator
    mock_decorator.side_effect = lambda *checks: lambda func: func
    from erenshor.cli.main import app

from erenshor.application.services.wiki_service import UpdateResult

runner = CliRunner()


@pytest.fixture
def mock_cli_context():
    """Create mock CLI context."""
    context = MagicMock()
    context.config.variants = {
        "main": MagicMock(
            resolved_database=MagicMock(return_value="/path/to/database.sqlite"),
            google_sheets=None,
        )
    }
    context.config.global_.mediawiki = MagicMock(
        api_url="https://wiki.example.com/api.php",
        username="bot",
        password="secret",
    )
    context.variant = "main"
    context.dry_run = False
    context.repo_root = MagicMock()
    return context


@pytest.fixture
def mock_update_result():
    """Create mock update result."""
    return UpdateResult(
        total=10,
        updated=10,
        skipped=0,
        failed=0,
        warnings=[],
        errors=[],
    )


@pytest.fixture
def mock_update_result_with_warnings():
    """Create mock update result with warnings."""
    return UpdateResult(
        total=10,
        updated=9,
        skipped=0,
        failed=0,
        warnings=["Manual edit preserved: Item:Iron Sword"],
        errors=[],
    )


@pytest.fixture
def mock_update_result_with_failures():
    """Create mock update result with failures."""
    return UpdateResult(
        total=10,
        updated=8,
        skipped=0,
        failed=2,
        warnings=[],
        errors=["Failed to update Item:Broken Sword", "Failed to update Item:Missing Item"],
    )


class TestWikiUpdateCommand:
    """Test wiki update command."""

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_update_items_success(self, mock_create_service, mock_update_result):
        """Test successful items update."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.update_item_pages.return_value = mock_update_result
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["wiki", "update", "--entity-type", "items"])

        # Verify
        assert result.exit_code == 0
        mock_service.update_item_pages.assert_called_once_with(dry_run=False, limit=None)

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_update_characters_success(self, mock_create_service, mock_update_result):
        """Test successful characters update."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.update_character_pages.return_value = mock_update_result
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["wiki", "update", "--entity-type", "characters"])

        # Verify
        assert result.exit_code == 0
        mock_service.update_character_pages.assert_called_once_with(dry_run=False, limit=None)

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_update_spells_success(self, mock_create_service, mock_update_result):
        """Test successful spells update."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.update_spell_pages.return_value = mock_update_result
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["wiki", "update", "--entity-type", "spells"])

        # Verify
        assert result.exit_code == 0
        mock_service.update_spell_pages.assert_called_once_with(dry_run=False, limit=None)

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_update_with_limit(self, mock_create_service, mock_update_result):
        """Test update with limit parameter."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.update_item_pages.return_value = mock_update_result
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["wiki", "update", "--entity-type", "items", "--limit", "5"])

        # Verify
        assert result.exit_code == 0
        mock_service.update_item_pages.assert_called_once_with(dry_run=False, limit=5)

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_update_dry_run(self, mock_create_service, mock_update_result):
        """Test update in dry-run mode."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.update_item_pages.return_value = mock_update_result
        mock_create_service.return_value = mock_service

        # Run command with global --dry-run flag
        result = runner.invoke(app, ["--dry-run", "wiki", "update", "--entity-type", "items"])

        # Verify
        assert result.exit_code == 0
        mock_service.update_item_pages.assert_called_once_with(dry_run=True, limit=None)

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_update_invalid_entity_type(self, mock_create_service):
        """Test update with invalid entity type."""
        # Setup mock service
        mock_service = MagicMock()
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["wiki", "update", "--entity-type", "invalid"])

        # Verify
        assert result.exit_code == 1
        assert "Invalid entity type" in result.stdout

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_update_with_warnings(self, mock_create_service, mock_update_result_with_warnings):
        """Test update that completes with warnings."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.update_item_pages.return_value = mock_update_result_with_warnings
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["wiki", "update", "--entity-type", "items"])

        # Verify - should exit 0 even with warnings
        assert result.exit_code == 0
        mock_service.update_item_pages.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_update_with_failures(self, mock_create_service, mock_update_result_with_failures):
        """Test update that completes with failures."""
        # Setup mock service
        mock_service = MagicMock()
        mock_service.update_item_pages.return_value = mock_update_result_with_failures
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["wiki", "update", "--entity-type", "items"])

        # Verify - should exit 1 with failures
        assert result.exit_code == 1
        mock_service.update_item_pages.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_update_service_exception(self, mock_create_service):
        """Test update when service raises exception."""
        # Setup mock service to raise exception
        mock_service = MagicMock()
        mock_service.update_item_pages.side_effect = Exception("Service error")
        mock_create_service.return_value = mock_service

        # Run command
        result = runner.invoke(app, ["wiki", "update", "--entity-type", "items"])

        # Verify
        assert result.exit_code == 1
        assert "Error during wiki update" in result.stdout
