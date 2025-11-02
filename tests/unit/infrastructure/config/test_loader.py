"""Tests for configuration loader.

This module tests configuration loading from TOML files, including:
- Two-layer override system (base + local)
- Deep merge behavior
- Error handling (missing files, invalid syntax, validation errors)
"""

from pathlib import Path

import pytest

from erenshor.infrastructure.config.loader import (
    ConfigLoadError,
    _deep_merge,
    get_repo_root,
    load_config,
)
from erenshor.infrastructure.config.schema import Config


class TestDeepMerge:
    """Tests for _deep_merge() function."""

    def test_merge_empty_dicts(self):
        """Test merging two empty dictionaries."""
        result = _deep_merge({}, {})
        assert result == {}

    def test_merge_base_only(self):
        """Test merging when override is empty."""
        base = {"a": 1, "b": 2}
        override = {}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_merge_override_only(self):
        """Test merging when base is empty."""
        base = {}
        override = {"a": 1, "b": 2}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_merge_primitives_override_wins(self):
        """Test that override values replace base values for primitives."""
        base = {"a": 1, "b": "base", "c": True}
        override = {"a": 10, "b": "override", "c": False}
        result = _deep_merge(base, override)
        assert result == {"a": 10, "b": "override", "c": False}

    def test_merge_nested_dicts_recursively(self):
        """Test that nested dictionaries are merged recursively."""
        base = {
            "level1": {
                "level2": {
                    "a": 1,
                    "b": 2,
                },
                "c": 3,
            }
        }
        override = {
            "level1": {
                "level2": {
                    "a": 10,  # Override
                    # b is not overridden
                },
                "d": 4,  # New key
            }
        }
        result = _deep_merge(base, override)

        expected = {
            "level1": {
                "level2": {
                    "a": 10,  # Overridden
                    "b": 2,  # Preserved from base
                },
                "c": 3,  # Preserved from base
                "d": 4,  # Added from override
            }
        }
        assert result == expected

    def test_merge_lists_override_replaces(self):
        """Test that lists are replaced entirely, not merged."""
        base = {"items": [1, 2, 3]}
        override = {"items": [10, 20]}
        result = _deep_merge(base, override)
        assert result == {"items": [10, 20]}

    def test_merge_none_value_overrides(self):
        """Test that None in override is treated as a value (not ignored)."""
        base = {"a": "base_value"}
        override = {"a": None}
        result = _deep_merge(base, override)
        assert result == {"a": None}

    def test_merge_preserves_non_overridden_keys(self):
        """Test that keys only in base are preserved."""
        base = {"a": 1, "b": 2, "c": 3}
        override = {"b": 20}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 20, "c": 3}

    def test_merge_adds_new_keys_from_override(self):
        """Test that keys only in override are added."""
        base = {"a": 1}
        override = {"b": 2, "c": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_merge_type_mismatch_override_wins(self):
        """Test that when types don't match, override wins."""
        # Dict in base, primitive in override
        base = {"value": {"nested": "data"}}
        override = {"value": "string"}
        result = _deep_merge(base, override)
        assert result == {"value": "string"}

        # Primitive in base, dict in override
        base = {"value": 42}
        override = {"value": {"nested": "data"}}
        result = _deep_merge(base, override)
        assert result == {"value": {"nested": "data"}}

    def test_merge_does_not_modify_originals(self):
        """Test that merge creates new dict without modifying inputs."""
        base = {"a": 1, "b": {"x": 1}}
        override = {"b": {"y": 2}}

        base_copy = base.copy()
        override_copy = override.copy()

        result = _deep_merge(base, override)

        # Originals unchanged
        assert base == base_copy
        assert override == override_copy
        # Result is different
        assert result != base
        assert result != override

    def test_merge_complex_real_world_config(self):
        """Test merging a realistic configuration structure."""
        base = {
            "version": "0.3",
            "default_variant": "main",
            "global": {
                "unity": {
                    "version": "2021.3.45f2",
                    "path": "/base/unity/path",
                    "timeout": 3600,
                },
                "logging": {
                    "level": "info",
                },
            },
            "variants": {
                "main": {
                    "enabled": True,
                    "app_id": "2382520",
                }
            },
        }

        override = {
            "default_variant": "playtest",
            "global": {
                "unity": {
                    "path": "/override/unity/path",
                    "timeout": 7200,
                },
                "logging": {
                    "level": "debug",
                },
            },
            "variants": {
                "main": {
                    "enabled": False,
                },
                "playtest": {
                    "enabled": True,
                    "app_id": "3090030",
                },
            },
        }

        result = _deep_merge(base, override)

        # Top-level overrides
        assert result["default_variant"] == "playtest"
        assert result["version"] == "0.3"  # Preserved from base

        # Unity config: partial override
        assert result["global"]["unity"]["version"] == "2021.3.45f2"  # Preserved
        assert result["global"]["unity"]["path"] == "/override/unity/path"  # Overridden
        assert result["global"]["unity"]["timeout"] == 7200  # Overridden

        # Verify logging override
        assert result["global"]["logging"]["level"] == "debug"

        # Verify variants are merged correctly
        assert result["variants"]["main"]["enabled"] is False  # Overridden
        assert result["variants"]["main"]["app_id"] == "2382520"  # Preserved
        assert result["variants"]["playtest"]["enabled"] is True  # Added
        assert result["variants"]["playtest"]["app_id"] == "3090030"  # Added


class TestGetRepoRoot:
    """Tests for get_repo_root() function."""

    def test_get_repo_root_from_within_repo(self, tmp_path: Path, monkeypatch):
        """Test getting repo root when cwd is inside repository."""
        # Create fake repo structure
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        subdir = tmp_path / "src" / "erenshor"
        subdir.mkdir(parents=True)

        # Change to subdirectory
        monkeypatch.chdir(subdir)

        # Should find repo root by traversing upward
        repo_root = get_repo_root()
        assert repo_root == tmp_path

    def test_get_repo_root_from_repo_root(self, tmp_path: Path, monkeypatch):
        """Test getting repo root when cwd is already repo root."""
        # Create fake repo structure
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Change to repo root
        monkeypatch.chdir(tmp_path)

        repo_root = get_repo_root()
        assert repo_root == tmp_path

    def test_get_repo_root_fails_outside_repo(self, tmp_path: Path, monkeypatch):
        """Test that get_repo_root() fails when not in a git repository."""
        # No .git directory
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigLoadError) as exc_info:
            get_repo_root()

        assert "Could not find repository root" in str(exc_info.value)


class TestLoadConfig:
    """Tests for load_config() function."""

    def test_load_base_config_only(self, tmp_path: Path, monkeypatch):
        """Test loading configuration with only base config.toml."""
        # Create fake repo with .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Copy base config fixture
        fixture_path = Path(__file__).parent / "../../../fixtures/config/base_config.toml"
        base_config_path = tmp_path / "config.toml"
        base_config_path.write_text(fixture_path.read_text())

        # Change to repo directory
        monkeypatch.chdir(tmp_path)

        # Load config
        config = load_config()

        # Verify basic structure
        assert isinstance(config, Config)
        assert config.version == "0.3"
        assert config.default_variant == "main"
        assert config.global_.unity.version == "2021.3.45f2"
        assert config.global_.logging.level == "info"
        assert "main" in config.variants

    def test_load_with_local_override(self, tmp_path: Path, monkeypatch):
        """Test loading configuration with local override."""
        # Create fake repo with .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Copy base config fixture
        fixture_path = Path(__file__).parent / "../../../fixtures/config/base_config.toml"
        base_config_path = tmp_path / "config.toml"
        base_config_path.write_text(fixture_path.read_text())

        # Create .erenshor directory and copy override config
        erenshor_dir = tmp_path / ".erenshor"
        erenshor_dir.mkdir()
        override_fixture = Path(__file__).parent / "../../../fixtures/config/override_config.toml"
        local_config_path = erenshor_dir / "config.local.toml"
        local_config_path.write_text(override_fixture.read_text())

        # Change to repo directory
        monkeypatch.chdir(tmp_path)

        # Load config
        config = load_config()

        # Verify overrides were applied
        assert config.default_variant == "playtest"  # Overridden
        assert config.version == "0.3"  # Preserved from base

        # Unity config: partial override
        assert config.global_.unity.version == "2021.3.45f2"  # Preserved
        assert config.global_.unity.path == "/custom/unity/path/Unity.app"  # Overridden
        assert config.global_.unity.timeout == 7200  # Overridden

        # Verify logging override
        assert config.global_.logging.level == "debug"

        # MediaWiki: partial override
        assert config.global_.mediawiki.api_batch_size == 50  # Overridden
        assert config.global_.mediawiki.bot_username == "override_bot"  # Overridden
        assert config.global_.mediawiki.api_delay == 1.0  # Preserved from base

        # Variants: main disabled, playtest added
        assert config.variants["main"].enabled is False  # Overridden
        assert config.variants["main"].google_sheets.spreadsheet_id == "override-spreadsheet-id"  # Overridden
        assert "playtest" in config.variants
        assert config.variants["playtest"].name == "Playtest Branch"

    def test_load_missing_base_config_fails(self, tmp_path: Path, monkeypatch):
        """Test that loading fails if config.toml is missing."""
        # Create fake repo with .git but no config.toml
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigLoadError) as exc_info:
            load_config()

        error_msg = str(exc_info.value)
        assert "Base configuration file not found" in error_msg
        assert "config.toml" in error_msg

    def test_load_invalid_toml_syntax_in_base(self, tmp_path: Path, monkeypatch):
        """Test that loading fails with invalid TOML syntax in base config."""
        # Create fake repo with .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Copy invalid syntax fixture
        fixture_path = Path(__file__).parent / "../../../fixtures/config/invalid_syntax.toml"
        base_config_path = tmp_path / "config.toml"
        base_config_path.write_text(fixture_path.read_text())

        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigLoadError) as exc_info:
            load_config()

        error_msg = str(exc_info.value)
        assert "Invalid TOML syntax" in error_msg
        assert "config.toml" in error_msg

    def test_load_invalid_toml_syntax_in_local(self, tmp_path: Path, monkeypatch):
        """Test that loading fails with invalid TOML syntax in local config."""
        # Create fake repo with .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Copy valid base config
        base_fixture = Path(__file__).parent / "../../../fixtures/config/base_config.toml"
        base_config_path = tmp_path / "config.toml"
        base_config_path.write_text(base_fixture.read_text())

        # Create .erenshor directory and copy invalid syntax fixture
        erenshor_dir = tmp_path / ".erenshor"
        erenshor_dir.mkdir()
        invalid_fixture = Path(__file__).parent / "../../../fixtures/config/invalid_syntax.toml"
        local_config_path = erenshor_dir / "config.local.toml"
        local_config_path.write_text(invalid_fixture.read_text())

        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigLoadError) as exc_info:
            load_config()

        error_msg = str(exc_info.value)
        assert "Invalid TOML syntax" in error_msg
        assert "config.local.toml" in error_msg

    def test_load_validation_error(self, tmp_path: Path, monkeypatch):
        """Test that loading fails when configuration values fail validation."""
        # Create fake repo with .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Copy invalid values fixture
        fixture_path = Path(__file__).parent / "../../../fixtures/config/invalid_values.toml"
        base_config_path = tmp_path / "config.toml"
        base_config_path.write_text(fixture_path.read_text())

        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigLoadError) as exc_info:
            load_config()

        error_msg = str(exc_info.value)
        assert "Configuration validation failed" in error_msg
        # Should mention the validation errors
        assert "timeout" in error_msg or "port" in error_msg or "level" in error_msg

    def test_load_missing_local_config_is_optional(self, tmp_path: Path, monkeypatch):
        """Test that missing config.local.toml is optional and doesn't fail."""
        # Create fake repo with .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Copy base config fixture only (no local config)
        fixture_path = Path(__file__).parent / "../../../fixtures/config/base_config.toml"
        base_config_path = tmp_path / "config.toml"
        base_config_path.write_text(fixture_path.read_text())

        monkeypatch.chdir(tmp_path)

        # Should load successfully without local config
        config = load_config()
        assert isinstance(config, Config)
        assert config.default_variant == "main"  # Base value

    def test_load_from_subdirectory(self, tmp_path: Path, monkeypatch):
        """Test loading config from subdirectory within repository."""
        # Create fake repo with .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Copy base config fixture
        fixture_path = Path(__file__).parent / "../../../fixtures/config/base_config.toml"
        base_config_path = tmp_path / "config.toml"
        base_config_path.write_text(fixture_path.read_text())

        # Create subdirectory and change to it
        subdir = tmp_path / "src" / "erenshor" / "cli"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        # Should still find and load config from repo root
        config = load_config()
        assert isinstance(config, Config)
        assert config.default_variant == "main"

    def test_load_config_not_in_repo_fails(self, tmp_path: Path, monkeypatch):
        """Test that loading fails when not in a git repository."""
        # No .git directory
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigLoadError) as exc_info:
            load_config()

        error_msg = str(exc_info.value)
        assert "Failed to find repository root" in error_msg or "Could not find repository root" in error_msg

    def test_deep_merge_preserves_base_nested_values(self, tmp_path: Path, monkeypatch):
        """Test that deep merge preserves nested values not in override."""
        # Create fake repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create base config with deeply nested structure
        base_config = tmp_path / "config.toml"
        base_config.write_text("""
version = "0.3"
default_variant = "main"

[global.unity]
version = "2021.3.45f2"
path = "/base/unity/path"
timeout = 3600

[global.logging]
level = "info"

[variants.main]
enabled = true
name = "Main Game"
app_id = "2382520"
unity_project = "/path/to/unity"
editor_scripts = "/path/to/scripts"
game_files = "/path/to/game"
database = "/path/to/db.sqlite"
logs = "/path/to/logs"
backups = "/path/to/backups"
wiki = "/path/to/wiki"

[variants.main.google_sheets]
spreadsheet_id = "base-spreadsheet-id"
""")

        # Create .erenshor directory and local config that overrides only some nested values
        erenshor_dir = tmp_path / ".erenshor"
        erenshor_dir.mkdir()
        local_config = erenshor_dir / "config.local.toml"
        local_config.write_text("""
[global.unity]
timeout = 7200

[variants.main]
enabled = false
""")

        monkeypatch.chdir(tmp_path)
        config = load_config()

        # Verify that non-overridden nested values are preserved
        assert config.global_.unity.version == "2021.3.45f2"  # Preserved
        assert config.global_.unity.path == "/base/unity/path"  # Preserved
        assert config.global_.unity.timeout == 7200  # Overridden

        assert config.variants["main"].enabled is False  # Overridden
        assert config.variants["main"].name == "Main Game"  # Preserved
        assert config.variants["main"].app_id == "2382520"  # Preserved
        assert config.variants["main"].google_sheets.spreadsheet_id == "base-spreadsheet-id"  # Preserved
