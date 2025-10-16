"""Tests for path resolution.

This module tests path resolution with variable expansion:
- $REPO_ROOT expansion
- $HOME expansion
- ~ expansion
- Relative path resolution
- Absolute paths (unchanged)
- Path validation
"""

from pathlib import Path

import pytest

from erenshor.infrastructure.config.paths import (
    PathResolutionError,
    resolve_path,
)


class TestResolvePathBasic:
    """Basic path resolution tests."""

    def test_absolute_path_unchanged(self, tmp_path: Path):
        """Test that absolute paths are returned unchanged."""
        absolute = "/usr/local/bin/unity"
        result = resolve_path(absolute, tmp_path, validate=False)
        assert result == Path("/usr/local/bin/unity")
        assert result.is_absolute()

    def test_relative_path_resolved_to_repo_root(self, tmp_path: Path):
        """Test that relative paths are resolved relative to repo root."""
        result = resolve_path("variants/main/unity", tmp_path, validate=False)
        assert result == tmp_path / "variants/main/unity"
        assert result.is_absolute()

    def test_empty_path(self, tmp_path: Path):
        """Test handling of empty path string."""
        result = resolve_path("", tmp_path, validate=False)
        assert result == tmp_path
        assert result.is_absolute()

    def test_dot_current_directory(self, tmp_path: Path):
        """Test that '.' resolves to repo root."""
        result = resolve_path(".", tmp_path, validate=False)
        assert result == tmp_path
        assert result.is_absolute()

    def test_dot_dot_parent_directory(self, tmp_path: Path):
        """Test that '..' works correctly relative to repo root."""
        result = resolve_path("..", tmp_path, validate=False)
        # Path is resolved relative to repo root, so .. means parent
        # Path normalization may not actually resolve .. until the path exists
        assert result.is_absolute()
        assert ".." in str(result) or result == tmp_path.parent


class TestResolvePathRepoRoot:
    """Tests for $REPO_ROOT expansion."""

    def test_repo_root_at_start(self, tmp_path: Path):
        """Test $REPO_ROOT at start of path."""
        result = resolve_path("$REPO_ROOT/variants/main", tmp_path, validate=False)
        assert result == tmp_path / "variants/main"
        assert result.is_absolute()

    def test_repo_root_only(self, tmp_path: Path):
        """Test path that is just $REPO_ROOT."""
        result = resolve_path("$REPO_ROOT", tmp_path, validate=False)
        assert result == tmp_path
        assert result.is_absolute()

    def test_repo_root_with_trailing_slash(self, tmp_path: Path):
        """Test $REPO_ROOT with trailing slash."""
        result = resolve_path("$REPO_ROOT/", tmp_path, validate=False)
        assert result == tmp_path
        assert result.is_absolute()

    def test_repo_root_multiple_occurrences(self, tmp_path: Path):
        """Test that all occurrences of $REPO_ROOT are replaced."""
        # This is an edge case that shouldn't normally happen
        result = resolve_path("$REPO_ROOT/$REPO_ROOT/test", tmp_path, validate=False)
        # Both should be replaced - result will have tmp_path embedded in path
        assert result.is_absolute()
        # Path should contain the repo root path twice (nested)
        path_str = str(result)
        assert path_str.count(str(tmp_path.name)) >= 1

    def test_repo_root_case_sensitive(self, tmp_path: Path):
        """Test that $REPO_ROOT is case-sensitive."""
        # Lowercase should NOT be expanded
        result = resolve_path("$repo_root/test", tmp_path, validate=False)
        # Should be treated as relative path
        assert result == tmp_path / "$repo_root/test"


class TestResolvePathHome:
    """Tests for $HOME and ~ expansion."""

    def test_home_variable_expansion(self, tmp_path: Path):
        """Test $HOME expansion."""
        result = resolve_path("$HOME/.config/erenshor", tmp_path, validate=False)
        expected = Path.home() / ".config/erenshor"
        assert result == expected
        assert result.is_absolute()

    def test_home_variable_only(self, tmp_path: Path):
        """Test path that is just $HOME."""
        result = resolve_path("$HOME", tmp_path, validate=False)
        assert result == Path.home()
        assert result.is_absolute()

    def test_tilde_expansion(self, tmp_path: Path):
        """Test ~ expansion."""
        result = resolve_path("~/Documents/erenshor", tmp_path, validate=False)
        expected = Path.home() / "Documents/erenshor"
        assert result == expected
        assert result.is_absolute()

    def test_tilde_only(self, tmp_path: Path):
        """Test path that is just ~."""
        result = resolve_path("~", tmp_path, validate=False)
        assert result == Path.home()
        assert result.is_absolute()

    def test_tilde_with_trailing_slash(self, tmp_path: Path):
        """Test ~ with trailing slash."""
        result = resolve_path("~/", tmp_path, validate=False)
        assert result == Path.home()
        assert result.is_absolute()

    def test_home_and_repo_root_combined(self, tmp_path: Path):
        """Test path with both $HOME and $REPO_ROOT (edge case)."""
        # This shouldn't normally happen, but test the behavior
        result = resolve_path("$HOME/$REPO_ROOT/test", tmp_path, validate=False)
        # Both variables should be expanded
        assert result.is_absolute()
        # Path should start with home directory
        assert str(result).startswith(str(Path.home()))


class TestResolvePathValidation:
    """Tests for path validation."""

    def test_validation_disabled_allows_nonexistent_path(self, tmp_path: Path):
        """Test that validation can be disabled."""
        result = resolve_path("$REPO_ROOT/nonexistent/path", tmp_path, validate=False)
        assert result == tmp_path / "nonexistent/path"
        # No error even though path doesn't exist

    def test_validation_fails_for_nonexistent_path(self, tmp_path: Path):
        """Test that validation raises error for nonexistent paths."""
        with pytest.raises(PathResolutionError) as exc_info:
            resolve_path("$REPO_ROOT/nonexistent/path", tmp_path, validate=True)

        error_msg = str(exc_info.value)
        assert "Path does not exist" in error_msg
        assert "nonexistent/path" in error_msg

    def test_validation_succeeds_for_existing_file(self, tmp_path: Path):
        """Test that validation succeeds for existing file."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = resolve_path("$REPO_ROOT/test.txt", tmp_path, validate=True)
        assert result == test_file
        assert result.exists()

    def test_validation_succeeds_for_existing_directory(self, tmp_path: Path):
        """Test that validation succeeds for existing directory."""
        # Create a test directory
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        result = resolve_path("$REPO_ROOT/test_dir", tmp_path, validate=True)
        assert result == test_dir
        assert result.exists()
        assert result.is_dir()

    def test_validation_error_includes_original_path(self, tmp_path: Path):
        """Test that validation error includes both original and resolved paths."""
        original = "$REPO_ROOT/config/missing.toml"

        with pytest.raises(PathResolutionError) as exc_info:
            resolve_path(original, tmp_path, validate=True)

        error_msg = str(exc_info.value)
        assert "Original path: $REPO_ROOT/config/missing.toml" in error_msg
        assert "Path does not exist" in error_msg


class TestResolvePathEdgeCases:
    """Edge case tests for path resolution."""

    def test_path_with_spaces(self, tmp_path: Path):
        """Test path with spaces in directory name."""
        result = resolve_path("$REPO_ROOT/path with spaces/file.txt", tmp_path, validate=False)
        assert result == tmp_path / "path with spaces/file.txt"

    def test_path_with_special_characters(self, tmp_path: Path):
        """Test path with special characters."""
        result = resolve_path("$REPO_ROOT/path-with_special.chars/file@123.txt", tmp_path, validate=False)
        assert result == tmp_path / "path-with_special.chars/file@123.txt"

    def test_windows_style_path(self, tmp_path: Path):
        """Test Windows-style path with backslashes."""
        # Path objects normalize backslashes on Windows
        result = resolve_path("$REPO_ROOT\\variants\\main\\unity", tmp_path, validate=False)
        # Result will use platform-appropriate separator
        assert "variants" in str(result)
        assert "main" in str(result)
        assert "unity" in str(result)

    def test_path_with_double_slashes(self, tmp_path: Path):
        """Test path with consecutive slashes."""
        result = resolve_path("$REPO_ROOT//variants//main", tmp_path, validate=False)
        # Path normalization should handle this
        assert "variants" in str(result)
        assert "main" in str(result)

    def test_path_with_unicode(self, tmp_path: Path):
        """Test path with unicode characters."""
        result = resolve_path("$REPO_ROOT/café/naïve/file.txt", tmp_path, validate=False)
        assert result == tmp_path / "café/naïve/file.txt"

    def test_symlink_resolution(self, tmp_path: Path):
        """Test that symlinks are not resolved (we want the symlink path)."""
        # Create a directory and a symlink to it
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()

        symlink_dir = tmp_path / "symlink_dir"
        symlink_dir.symlink_to(real_dir)

        # Resolve path to symlink
        result = resolve_path("$REPO_ROOT/symlink_dir", tmp_path, validate=False)

        # Should return the symlink path, not the real path
        assert result == symlink_dir
        # Note: Path.resolve() would follow symlinks, but we don't use it


class TestResolvePathRealWorld:
    """Real-world usage scenarios."""

    def test_config_file_paths(self, tmp_path: Path):
        """Test typical config file path patterns."""
        paths = [
            "$REPO_ROOT/config.toml",
            "$REPO_ROOT/.erenshor/config.local.toml",
            "$HOME/.config/erenshor/credentials.json",
            "~/Documents/Erenshor/backups",
        ]

        for path in paths:
            result = resolve_path(path, tmp_path, validate=False)
            assert result.is_absolute()

    def test_variant_directory_paths(self, tmp_path: Path):
        """Test variant directory path patterns."""
        variant_paths = {
            "unity_project": "$REPO_ROOT/variants/main/unity",
            "game_files": "$REPO_ROOT/variants/main/game",
            "database": "$REPO_ROOT/variants/main/erenshor-main.sqlite",
            "logs": "$REPO_ROOT/variants/main/logs",
            "backups": "$REPO_ROOT/variants/main/backups",
        }

        for _name, path in variant_paths.items():
            result = resolve_path(path, tmp_path, validate=False)
            assert result.is_absolute()
            assert "variants/main" in str(result)

    def test_external_tool_paths(self, tmp_path: Path):
        """Test external tool path patterns."""
        tool_paths = [
            "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app",
            "$HOME/Projects/AssetRipper/AssetRipper.GUI.Free",
            "/usr/local/bin/steamcmd",
        ]

        for path in tool_paths:
            result = resolve_path(path, tmp_path, validate=False)
            assert result.is_absolute()

    def test_all_expansion_types_in_one_session(self, tmp_path: Path):
        """Test multiple path expansion types in sequence."""
        # Create test structure
        (tmp_path / "variants/main").mkdir(parents=True)
        test_file = tmp_path / "test.txt"
        test_file.touch()

        # Test all expansion types work correctly
        paths = [
            ("$REPO_ROOT/test.txt", tmp_path / "test.txt"),
            ("$REPO_ROOT/variants/main", tmp_path / "variants/main"),
            ("variants/main", tmp_path / "variants/main"),
            ("$HOME", Path.home()),
            ("~", Path.home()),
        ]

        for input_path, expected in paths:
            result = resolve_path(input_path, tmp_path, validate=False)
            assert result == expected

    def test_mixed_path_separators(self, tmp_path: Path):
        """Test handling mixed forward/backward slashes (Windows compat)."""
        # Should handle gracefully regardless of platform
        result = resolve_path("$REPO_ROOT/variants\\main/unity", tmp_path, validate=False)
        assert result.is_absolute()
        assert "variants" in str(result)

    def test_nested_repo_root_expansion(self, tmp_path: Path):
        """Test deeply nested path with $REPO_ROOT."""
        result = resolve_path("$REPO_ROOT/src/erenshor/infrastructure/config/schema.py", tmp_path, validate=False)
        expected = tmp_path / "src/erenshor/infrastructure/config/schema.py"
        assert result == expected

    def test_validation_with_relative_path(self, tmp_path: Path):
        """Test validation works with relative paths."""
        # Create test file
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Relative path with validation
        result = resolve_path("test_dir", tmp_path, validate=True)
        assert result == test_dir
        assert result.exists()

    def test_validation_with_home_expansion(self):
        """Test validation with $HOME expansion (user's home should exist)."""
        # User's home directory should always exist
        result = resolve_path("$HOME", Path.cwd(), validate=True)
        assert result == Path.home()
        assert result.exists()

    def test_multiple_paths_same_repo_root(self, tmp_path: Path):
        """Test resolving multiple paths with same repo_root (typical usage)."""
        # Simulate loading multiple config paths
        paths = {
            "state": "$REPO_ROOT/.erenshor/state.json",
            "logs": "$REPO_ROOT/.erenshor/logs",
            "database": "$REPO_ROOT/variants/main/erenshor.sqlite",
        }

        resolved = {}
        for name, path in paths.items():
            resolved[name] = resolve_path(path, tmp_path, validate=False)

        # All should share same repo root
        for result in resolved.values():
            assert str(result).startswith(str(tmp_path))
            assert result.is_absolute()
