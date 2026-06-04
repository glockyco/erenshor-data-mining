"""Unit tests for wiki CLI commands."""

from pathlib import Path
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

    def test_generate_lua_dry_run_reports_output_without_writing(self):
        """Test dry-run reports Lua output paths without writing files."""
        result = runner.invoke(app, ["--dry-run", "wiki", "generate-lua"])

        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Items.lua" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Items" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Characters.lua" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/AbilityLinks.lua" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Quests.lua" in result.output
        assert "variants/main/wiki/lua/Erenshor/Data/Zones.lua" in result.output


class TestWikiInventoryTemplatesCommand:
    """Test wiki template inventory command."""

    def test_inventory_templates_writes_manifest_from_recorded_fixtures(self, tmp_path: Path):
        """Test template inventory writes ownership manifest from recorded API fixtures."""
        output_path = tmp_path / "ownership.yml"

        result = runner.invoke(
            app,
            [
                "wiki",
                "inventory-templates",
                "--fixture-dir",
                "tests/fixtures/wiki_inventory",
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0
        manifest = output_path.read_text(encoding="utf-8")
        assert "title: Template:Item" in manifest
        assert "ownership: repo_owned_template" in manifest
        assert "cutover_blocking: true" in manifest
        assert "Wrote template ownership manifest" in result.output


class TestWikiSyncInterfaceCommand:
    """Test wiki interface sync command."""

    def test_sync_interface_help_describes_live_interface_mirror(self):
        """Test sync-interface exposes the local preview bootstrap command."""
        result = runner.invoke(app, ["wiki", "sync-interface", "--help"])

        assert result.exit_code == 0
        assert "Sync live MediaWiki interface pages for local preview." in result.output
        assert "wiki-dev/interface" in result.output


class TestWikiDeployCommand:
    """Test wiki deploy command."""

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_success(self, mock_create_service, mock_operation_result):
        """Test successful deploy."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "deploy", "--legacy-article-deploy"])

        assert result.exit_code == 0
        mock_service.deploy_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_with_limit(self, mock_create_service, mock_operation_result):
        """Test deploy with limit parameter."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "deploy", "--legacy-article-deploy", "--limit", "5"])

        assert result.exit_code == 0
        mock_service.deploy_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_dry_run(self, mock_create_service, mock_operation_result):
        """Test deploy in dry-run mode."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["--dry-run", "wiki", "deploy", "--legacy-article-deploy"])

        assert result.exit_code == 0
        mock_service.deploy_all.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_deploy_with_failures(self, mock_create_service, mock_operation_result_with_failures):
        """Test deploy that completes with failures."""
        mock_service = MagicMock()
        mock_service.deploy_all.return_value = mock_operation_result_with_failures
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["wiki", "deploy", "--legacy-article-deploy"])

        # Should exit 1 with failures
        assert result.exit_code == 1
        mock_service.deploy_all.assert_called_once()


class TestWikiDeployRepoCommand:
    """Test repo-owned wiki deploy command."""

    @patch("erenshor.cli.commands.wiki.MediaWikiClient")
    @patch("erenshor.cli.commands.wiki.deploy_repo_pages")
    @patch("erenshor.cli.commands.wiki.build_repo_page_manifest")
    def test_deploy_repo_pages(self, mock_build_manifest, mock_deploy_repo_pages, mock_client_class):
        """Test repo-owned page deploy uses manifest and safe deploy service."""
        mock_manifest = MagicMock()
        mock_build_manifest.return_value = mock_manifest
        mock_result = MagicMock()
        mock_result.entries = [
            MagicMock(status="unchanged"),
            MagicMock(status="changed"),
        ]
        mock_deploy_repo_pages.return_value = mock_result

        result = runner.invoke(app, ["wiki", "deploy-repo-pages"])

        assert result.exit_code == 0
        assert "Changed: 1" in result.output
        mock_build_manifest.assert_called_once()
        mock_deploy_repo_pages.assert_called_once()
        mock_client_class.return_value.close.assert_called_once()

    @patch("erenshor.cli.commands.wiki._create_wiki_service")
    def test_legacy_deploy_requires_explicit_legacy_flag(self, mock_create_service):
        """Test legacy generated article deploy is guarded during Lua cutover."""
        result = runner.invoke(app, ["wiki", "deploy"])

        assert result.exit_code == 1
        assert "--legacy-article-deploy" in result.output
        mock_create_service.assert_not_called()
