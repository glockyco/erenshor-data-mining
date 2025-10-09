"""Integration tests for path resolution across the system."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from erenshor.application.services.mapping_service import MappingService
from erenshor.application.reporting import Reporter
from erenshor.domain.mapping import MappingFile, save_mapping_file
from erenshor.infrastructure.services import ZoneService
from erenshor.infrastructure.config.paths import PathResolver, get_path_resolver
from erenshor.infrastructure.config.settings import WikiSettings, load_settings


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create a mock project root with expected structure."""
    # Create project structure
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'\n")

    # Create package structure
    pkg = tmp_path / "src" / "erenshor"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").touch()

    # Create config directory
    config = pkg / "infrastructure" / "config"
    config.mkdir(parents=True)

    # Create zones.json
    zones_data = {"Zone1": "Display Zone 1", "Zone2": "Display Zone 2"}
    (config / "zones.json").write_text(json.dumps(zones_data))

    # Create data directories
    (tmp_path / "registry").mkdir()
    (tmp_path / "wiki_cache").mkdir()
    (tmp_path / "wiki_updated").mkdir()

    # Create mapping.json
    mapping = MappingFile(rules={})
    save_mapping_file(mapping, tmp_path / "mapping.json")

    # Create .env file
    (tmp_path / ".env").write_text("ERENSHOR_BOT_USERNAME=test\n")

    # Create database (just touch it)
    (tmp_path / "erenshor.sqlite").touch()

    return tmp_path


class TestPathResolutionIntegration:
    """Integration tests for path resolution."""

    def test_settings_uses_resolver(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that settings uses path resolver."""
        # Reset singleton and set root
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        # Set environment to use our mock root
        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))

        settings = load_settings()

        # All paths should be absolute and under project root
        assert settings.db_path.is_absolute()
        assert settings.cache_dir.is_absolute()
        assert settings.output_dir.is_absolute()
        assert settings.reports_dir.is_absolute()

        # Verify they point to the right places
        assert settings.db_path == mock_project_root / "erenshor.sqlite"
        assert settings.cache_dir == mock_project_root / "wiki_cache"
        assert settings.output_dir == mock_project_root / "wiki_updated"
        assert settings.reports_dir == mock_project_root / "out" / "reports"

    def test_from_subdirectory(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test running from project subdirectory."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        # Change to subdirectory
        subdir = mock_project_root / "src" / "erenshor"
        monkeypatch.chdir(subdir)

        resolver = get_path_resolver()
        assert resolver.root == mock_project_root
        assert resolver.mapping_file == mock_project_root / "mapping.json"

    def test_with_env_overrides(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test with environment variable overrides."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        # Set custom paths
        custom_registry = tmp_path / "custom_registry"
        custom_registry.mkdir()
        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))
        monkeypatch.setenv("ERENSHOR_REGISTRY_DIR", str(custom_registry))

        resolver = get_path_resolver()
        assert resolver.registry_dir == custom_registry

    def test_mapping_service_uses_resolver(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that MappingService uses PathResolver."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))

        service = MappingService.load()
        assert service.path == mock_project_root / "mapping.json"

    def test_zone_service_uses_resolver(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that ZoneService uses PathResolver."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))

        service = ZoneService.load()
        assert service.names == {"Zone1": "Display Zone 1", "Zone2": "Display Zone 2"}

    def test_reporter_uses_resolver(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that Reporter uses PathResolver."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))

        reporter = Reporter.open(command="test", args={})
        assert reporter.base_dir.parent == mock_project_root / "out" / "reports"
        reporter.finish()

    def test_custom_reports_dir(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test custom reports directory via env var."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        custom_reports = tmp_path / "custom_reports"
        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))
        monkeypatch.setenv("ERENSHOR_OUT_REPORTS_DIR", str(custom_reports))

        reporter = Reporter.open(command="test", args={})
        assert reporter.base_dir.parent == custom_reports
        reporter.finish()

    def test_settings_with_relative_override(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test settings with relative path override."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))

        # Create settings with relative path
        settings = WikiSettings(cache_dir=Path("custom_cache"))

        # Should be resolved relative to project root
        assert settings.cache_dir == mock_project_root / "custom_cache"

    def test_settings_with_absolute_override(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test settings with absolute path override."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))

        # Create settings with absolute path
        absolute_cache = tmp_path / "absolute_cache"
        settings = WikiSettings(cache_dir=absolute_cache)

        # Should use absolute path as-is
        assert settings.cache_dir == absolute_cache

    def test_env_file_resolution(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test .env file resolution."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))

        settings = load_settings()

        # Should have loaded bot username from .env
        assert settings.bot_username == "test"


class TestPathResolverConsistency:
    """Test that all services use paths consistently."""

    def test_all_services_use_same_root(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that all services resolve to the same project root."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))

        # Get paths from different sources
        resolver = get_path_resolver()
        settings = load_settings()
        mapping_service = MappingService.load()

        # All should reference the same root
        assert resolver.root == mock_project_root
        assert settings.db_path.parent == mock_project_root
        assert mapping_service.path.parent == mock_project_root

    def test_singleton_consistency(
        self, mock_project_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that singleton is used consistently."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(mock_project_root))

        # Multiple calls should return same instance
        resolver1 = get_path_resolver()
        resolver2 = get_path_resolver()
        resolver3 = get_path_resolver()

        assert resolver1 is resolver2
        assert resolver2 is resolver3
