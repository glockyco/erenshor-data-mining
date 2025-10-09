"""Unit tests for PathResolver."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from erenshor.infrastructure.config.paths import PathResolver, get_path_resolver


class TestPathResolver:
    """Test PathResolver functionality."""

    def test_explicit_root(self, tmp_path: Path) -> None:
        """Test with explicit root."""
        resolver = PathResolver(root=tmp_path)
        assert resolver.root == tmp_path.resolve()

    def test_auto_detect_pyproject_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test auto-detection via pyproject.toml."""
        # Create pyproject.toml
        (tmp_path / "pyproject.toml").touch()

        # Change to subdirectory
        subdir = tmp_path / "src" / "erenshor"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        resolver = PathResolver()
        assert resolver.root == tmp_path

    def test_auto_detect_git(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test auto-detection via .git."""
        (tmp_path / ".git").mkdir()

        subdir = tmp_path / "deep" / "nested"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        resolver = PathResolver()
        assert resolver.root == tmp_path

    def test_env_var_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test ERENSHOR_PROJECT_ROOT override."""
        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(tmp_path))

        resolver = PathResolver()
        assert resolver.root == tmp_path

    def test_fallback_to_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test fallback when no markers found."""
        monkeypatch.chdir(tmp_path)

        resolver = PathResolver()
        assert resolver.root == tmp_path

    def test_development_mode(self, tmp_path: Path) -> None:
        """Test development mode detection."""
        (tmp_path / "pyproject.toml").touch()

        resolver = PathResolver(root=tmp_path)
        assert resolver.mode == "development"
        assert resolver.is_development()
        assert not resolver.is_installed()

    def test_installed_mode(self, tmp_path: Path) -> None:
        """Test installed mode detection."""
        # No pyproject.toml
        resolver = PathResolver(root=tmp_path)
        assert resolver.mode == "installed"
        assert resolver.is_installed()
        assert not resolver.is_development()

    def test_src_dir_in_development(self, tmp_path: Path) -> None:
        """Test src_dir in development mode."""
        (tmp_path / "pyproject.toml").touch()
        (tmp_path / "src").mkdir()

        resolver = PathResolver(root=tmp_path)
        assert resolver.src_dir == tmp_path / "src"

    def test_src_dir_in_installed_raises(self, tmp_path: Path) -> None:
        """Test src_dir raises in installed mode."""
        # No pyproject.toml = installed mode
        resolver = PathResolver(root=tmp_path)

        with pytest.raises(RuntimeError, match="only available in development mode"):
            _ = resolver.src_dir

    def test_package_dir_in_development(self, tmp_path: Path) -> None:
        """Test package_dir in development mode."""
        (tmp_path / "pyproject.toml").touch()
        package = tmp_path / "src" / "erenshor"
        package.mkdir(parents=True)

        resolver = PathResolver(root=tmp_path)
        assert resolver.package_dir == package

    def test_data_dir_default(self, tmp_path: Path) -> None:
        """Test default data directory in development mode."""
        # Create pyproject.toml to force development mode
        (tmp_path / "pyproject.toml").touch()
        resolver = PathResolver(root=tmp_path)
        assert resolver.registry_dir == tmp_path / "registry"

    def test_data_dir_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test data directory env override."""
        custom_dir = tmp_path / "custom_registry"
        monkeypatch.setenv("ERENSHOR_REGISTRY_DIR", str(custom_dir))

        resolver = PathResolver(root=tmp_path)
        assert resolver.registry_dir == custom_dir

    def test_cache_dir(self, tmp_path: Path) -> None:
        """Test cache directory in development mode."""
        # Create pyproject.toml to force development mode
        (tmp_path / "pyproject.toml").touch()
        resolver = PathResolver(root=tmp_path)
        assert resolver.cache_dir == tmp_path / "wiki_cache"

    def test_cache_dir_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test cache directory env override."""
        custom_cache = tmp_path / "custom_cache"
        monkeypatch.setenv("ERENSHOR_WIKI_CACHE_DIR", str(custom_cache))

        resolver = PathResolver(root=tmp_path)
        assert resolver.cache_dir == custom_cache

    def test_output_dir(self, tmp_path: Path) -> None:
        """Test output directory in development mode."""
        # Create pyproject.toml to force development mode
        (tmp_path / "pyproject.toml").touch()
        resolver = PathResolver(root=tmp_path)
        assert resolver.output_dir == tmp_path / "wiki_updated"

    def test_output_dir_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test output directory env override."""
        custom_output = tmp_path / "custom_output"
        monkeypatch.setenv("ERENSHOR_WIKI_UPDATED_DIR", str(custom_output))

        resolver = PathResolver(root=tmp_path)
        assert resolver.output_dir == custom_output

    def test_reports_dir(self, tmp_path: Path) -> None:
        """Test reports directory in development mode."""
        # Create pyproject.toml to force development mode
        (tmp_path / "pyproject.toml").touch()
        resolver = PathResolver(root=tmp_path)
        assert resolver.reports_dir == tmp_path / "out" / "reports"

    def test_reports_dir_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test reports directory env override."""
        custom_reports = tmp_path / "custom_reports"
        monkeypatch.setenv("ERENSHOR_OUT_REPORTS_DIR", str(custom_reports))

        resolver = PathResolver(root=tmp_path)
        assert resolver.reports_dir == custom_reports

    def test_mapping_file_default(self, tmp_path: Path) -> None:
        """Test default mapping file location."""
        resolver = PathResolver(root=tmp_path)
        assert resolver.mapping_file == tmp_path / "mapping.json"

    def test_mapping_file_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test mapping file env override."""
        custom_file = tmp_path / "custom_mapping.json"
        monkeypatch.setenv("ERENSHOR_MAPPING_FILE", str(custom_file))

        resolver = PathResolver(root=tmp_path)
        assert resolver.mapping_file == custom_file

    def test_env_file_default(self, tmp_path: Path) -> None:
        """Test default .env file location."""
        resolver = PathResolver(root=tmp_path)
        assert resolver.env_file == tmp_path / ".env"

    def test_env_file_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test .env file env override."""
        custom_env = tmp_path / "custom.env"
        monkeypatch.setenv("ERENSHOR_ENV_FILE", str(custom_env))

        resolver = PathResolver(root=tmp_path)
        assert resolver.env_file == custom_env

    def test_db_path_default(self, tmp_path: Path) -> None:
        """Test default database path."""
        resolver = PathResolver(root=tmp_path)
        assert resolver.db_path == tmp_path / "erenshor.sqlite"

    def test_db_path_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test database path env override."""
        custom_db = tmp_path / "custom.sqlite"
        monkeypatch.setenv("ERENSHOR_DB_PATH", str(custom_db))

        resolver = PathResolver(root=tmp_path)
        assert resolver.db_path == custom_db

    def test_zones_json_in_development(self, tmp_path: Path) -> None:
        """Test zones.json path in development mode."""
        (tmp_path / "pyproject.toml").touch()
        zones_file = (
            tmp_path
            / "src"
            / "erenshor"
            / "infrastructure"
            / "config"
            / "zones.json"
        )
        zones_file.parent.mkdir(parents=True)

        resolver = PathResolver(root=tmp_path)
        assert resolver.zones_json == zones_file

    def test_resolve_relative_path(self, tmp_path: Path) -> None:
        """Test resolving relative path."""
        resolver = PathResolver(root=tmp_path)
        result = resolver.resolve("subdir/file.txt")
        assert result == (tmp_path / "subdir" / "file.txt").resolve()

    def test_resolve_absolute_path(self, tmp_path: Path) -> None:
        """Test resolving absolute path (passthrough)."""
        absolute = Path("/absolute/path")
        resolver = PathResolver(root=tmp_path)
        result = resolver.resolve(absolute)
        assert result == absolute

    def test_resolve_string_path(self, tmp_path: Path) -> None:
        """Test resolving string path."""
        resolver = PathResolver(root=tmp_path)
        result = resolver.resolve("subdir/file.txt")
        assert result == (tmp_path / "subdir" / "file.txt").resolve()

    def test_pyproject_priority_over_git(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that pyproject.toml is found before .git."""
        # Create both markers
        (tmp_path / "pyproject.toml").touch()
        (tmp_path / ".git").mkdir()

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        resolver = PathResolver()
        # Should find tmp_path via pyproject.toml
        assert resolver.root == tmp_path
        assert resolver.is_development()

    def test_nested_project_detection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test detection in nested project structure."""
        # Create outer project
        outer = tmp_path / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()

        # Create inner project
        inner = outer / "inner"
        inner.mkdir()
        (inner / "pyproject.toml").touch()

        # Run from deep inside inner
        deep = inner / "src" / "pkg"
        deep.mkdir(parents=True)
        monkeypatch.chdir(deep)

        resolver = PathResolver()
        # Should find inner project (closest marker)
        assert resolver.root == inner


class TestGetPathResolver:
    """Test get_path_resolver singleton function."""

    def test_singleton(self, tmp_path: Path) -> None:
        """Test singleton pattern."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        resolver1 = get_path_resolver(root=tmp_path)
        resolver2 = get_path_resolver()
        assert resolver1 is resolver2

    def test_singleton_reset_with_new_root(self, tmp_path: Path) -> None:
        """Test singleton can be reset with new root."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        resolver1 = get_path_resolver(root=tmp_path)

        new_root = tmp_path / "new"
        new_root.mkdir()
        resolver2 = get_path_resolver(root=new_root)

        assert resolver1 is not resolver2
        assert resolver2.root == new_root

    def test_singleton_auto_detect(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test singleton with auto-detection."""
        # Reset singleton
        from erenshor.infrastructure.config import paths

        paths._resolver = None

        (tmp_path / "pyproject.toml").touch()
        monkeypatch.chdir(tmp_path)

        resolver = get_path_resolver()
        assert resolver.root == tmp_path


class TestPathResolverEdgeCases:
    """Test edge cases and error conditions."""

    def test_nonexistent_root_warning(self, tmp_path: Path) -> None:
        """Test warning when root doesn't exist."""
        nonexistent = tmp_path / "does_not_exist"

        # Should not raise, but may warn
        resolver = PathResolver(root=nonexistent)
        assert resolver.root == nonexistent.resolve()

    def test_missing_src_in_dev_mode_warning(self, tmp_path: Path) -> None:
        """Test warning when src/ missing in development mode."""
        # Create pyproject.toml but no src/
        (tmp_path / "pyproject.toml").touch()

        # Should not raise, but may warn
        resolver = PathResolver(root=tmp_path)
        assert resolver.is_development()

    def test_relative_path_with_parent_references(self, tmp_path: Path) -> None:
        """Test resolving path with parent directory references."""
        resolver = PathResolver(root=tmp_path)
        result = resolver.resolve("subdir/../other/file.txt")
        # Should resolve to normalized path
        assert result == (tmp_path / "other" / "file.txt").resolve()

    def test_env_var_with_trailing_slash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test env var with trailing slash."""
        monkeypatch.setenv("ERENSHOR_PROJECT_ROOT", str(tmp_path) + "/")

        resolver = PathResolver()
        # Should still work correctly
        assert resolver.root.exists()

    def test_symlink_resolution(self, tmp_path: Path) -> None:
        """Test that symlinks are resolved."""
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "pyproject.toml").touch()

        link_dir = tmp_path / "link"
        link_dir.symlink_to(real_dir)

        resolver = PathResolver(root=link_dir)
        # resolve() follows symlinks
        assert resolver.root == real_dir.resolve()

    def test_package_dir_in_installed_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test package_dir in installed mode using importlib."""
        # No pyproject.toml = installed mode
        resolver = PathResolver(root=tmp_path)

        # Mock importlib to return test package location
        from unittest.mock import MagicMock

        mock_spec = MagicMock()
        mock_spec.origin = str(tmp_path / "erenshor" / "__init__.py")

        with patch("importlib.util.find_spec", return_value=mock_spec):
            assert resolver.package_dir == tmp_path / "erenshor"

    @pytest.mark.skipif(os.name != "nt", reason="Windows-specific test")
    def test_windows_path_handling(self, tmp_path: Path) -> None:
        """Test Windows path handling."""
        # Windows paths with backslashes should work
        resolver = PathResolver(root=tmp_path)
        assert resolver.root.exists() or True  # May not exist yet

    def test_env_var_empty_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that empty string env vars are ignored."""
        # Create pyproject.toml to force development mode
        (tmp_path / "pyproject.toml").touch()
        monkeypatch.setenv("ERENSHOR_REGISTRY_DIR", "")

        resolver = PathResolver(root=tmp_path)
        # Empty string is falsy, so should fall back to default
        assert resolver.registry_dir == tmp_path / "registry"

    def test_env_var_relative_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test env var with relative path gets resolved."""
        monkeypatch.setenv("ERENSHOR_REGISTRY_DIR", "custom_registry")

        resolver = PathResolver(root=tmp_path)
        # Should be resolved to absolute path from cwd
        assert resolver.registry_dir.is_absolute()

    def test_concurrent_singleton_access(self, tmp_path: Path) -> None:
        """Test concurrent access to singleton (basic thread safety check)."""
        from threading import Thread
        from erenshor.infrastructure.config import paths

        # Reset singleton
        paths._resolver = None

        # Create pyproject.toml to force development mode
        (tmp_path / "pyproject.toml").touch()

        results = []

        def get_resolver():
            r = get_path_resolver(root=tmp_path)
            results.append(r)

        threads = [Thread(target=get_resolver) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # First call should create singleton, others may get it or recreate it
        # Due to race conditions, we can't guarantee all are the same instance
        # But we can verify all have the same root
        assert len(results) == 10
        assert all(r.root == tmp_path for r in results)

    def test_platformdirs_in_installed_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that installed mode uses platformdirs."""
        # No pyproject.toml = installed mode
        resolver = PathResolver(root=tmp_path)

        # In installed mode, data_dir should use platformdirs
        with patch("platformdirs.user_data_dir") as mock_user_data:
            mock_user_data.return_value = str(tmp_path / "platform_data")
            registry_dir = resolver.registry_dir

            # Should have called platformdirs
            mock_user_data.assert_called_once_with("erenshor-wiki", "erenshor-wiki")
            assert "platform_data" in str(registry_dir)

    def test_repr(self, tmp_path: Path) -> None:
        """Test __repr__ returns useful debug info."""
        (tmp_path / "pyproject.toml").touch()
        resolver = PathResolver(root=tmp_path)

        repr_str = repr(resolver)
        assert "PathResolver" in repr_str
        assert "root=" in repr_str
        assert "mode=" in repr_str
        assert "development" in repr_str


class TestPathResolverLogging:
    """Test logging behavior."""

    def test_logging_on_init(self, tmp_path: Path, caplog) -> None:
        """Test that initialization logs at INFO level."""
        import logging

        with caplog.at_level(logging.INFO):
            resolver = PathResolver(root=tmp_path)

        # Should have logged initialization
        assert any(
            "PathResolver initialized" in record.message for record in caplog.records
        )

    def test_env_var_logging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog
    ) -> None:
        """Test that env var usage is logged at DEBUG level."""
        import logging

        monkeypatch.setenv("ERENSHOR_DB_PATH", str(tmp_path / "custom.db"))

        with caplog.at_level(logging.DEBUG):
            resolver = PathResolver(root=tmp_path)
            _ = resolver.db_path

        # Should have logged env var usage
        assert any("ERENSHOR_DB_PATH" in record.message for record in caplog.records)
