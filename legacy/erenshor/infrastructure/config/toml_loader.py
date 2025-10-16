"""TOML configuration loader for unified config.toml.

This module provides utilities to load configuration from the unified config.toml
file, with support for:
- Path expansion ($REPO_ROOT, $HOME, ~)
- Variant-specific configuration
- Merging with config.local.toml
- Environment variable overrides

The configuration file is shared between Bash CLI and Python services.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Optional

__all__ = ["TomlConfigLoader", "load_config"]


class TomlConfigLoader:
    """Load and parse unified config.toml with proper precedence."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        """Initialize TOML config loader.

        Args:
            repo_root: Explicit repository root. If None, auto-detects.
        """
        self._repo_root = repo_root or self._detect_repo_root()
        self._config_data: dict[str, Any] = {}

    @staticmethod
    def _detect_repo_root() -> Path:
        """Auto-detect repository root.

        Search order:
        1. REPO_ROOT environment variable
        2. Current directory and parents for config.toml
        3. Current directory and parents for .git
        4. Fallback to current directory

        Returns:
            Path to repository root
        """
        # Check env var first
        env_root = os.environ.get("REPO_ROOT")
        if env_root:
            return Path(env_root).resolve()

        # Search for marker files
        marker_files = ("config.toml", ".git")
        current = Path.cwd().resolve()

        for parent in [current] + list(current.parents):
            for marker in marker_files:
                if (parent / marker).exists():
                    return parent

        # Fallback to cwd
        return current

    def _expand_path(self, value: str) -> str:
        """Expand path variables in configuration values.

        Supports:
        - $REPO_ROOT: Repository root directory
        - $HOME: User home directory
        - ~: User home directory

        Args:
            value: Configuration value potentially containing path variables

        Returns:
            Expanded value
        """
        if not isinstance(value, str):
            return value

        # Save original env
        original_repo_root = os.environ.get("REPO_ROOT")

        # Temporarily set REPO_ROOT for expansion
        os.environ["REPO_ROOT"] = str(self._repo_root)

        # Expand environment variables
        expanded = os.path.expandvars(value)

        # Restore original env
        if original_repo_root is not None:
            os.environ["REPO_ROOT"] = original_repo_root
        elif "REPO_ROOT" in os.environ:
            del os.environ["REPO_ROOT"]

        # Expand tilde
        if expanded.startswith("~"):
            expanded = os.path.expanduser(expanded)

        return expanded

    def _expand_paths_recursive(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively expand paths in configuration dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            Dictionary with expanded paths
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self._expand_paths_recursive(value)
            elif isinstance(value, str):
                result[key] = self._expand_path(value)
            else:
                result[key] = value
        return result

    def _deep_merge(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary (takes precedence)

        Returns:
            Merged dictionary
        """
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def load(self) -> dict[str, Any]:
        """Load configuration from TOML files with proper precedence.

        Loading order (later overrides earlier):
        1. config.toml (project defaults)
        2. .erenshor/config.local.toml (local overrides)

        Environment variables are handled separately by pydantic-settings.

        Returns:
            Merged configuration dictionary
        """
        config = {}

        # Load main config.toml
        config_file = self._repo_root / "config.toml"
        if config_file.exists():
            with open(config_file, "rb") as f:
                config = tomllib.load(f)

        # Load local overrides
        local_config_file = self._repo_root / ".erenshor" / "config.local.toml"
        if local_config_file.exists():
            with open(local_config_file, "rb") as f:
                local_config = tomllib.load(f)
                config = self._deep_merge(config, local_config)

        # Expand paths
        config = self._expand_paths_recursive(config)

        self._config_data = config
        return config

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated key.

        Args:
            key: Dot-separated key (e.g., "global.mediawiki.api_url")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if not self._config_data:
            self.load()

        parts = key.split(".")
        value = self._config_data

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    def get_variant_config(self, variant: str) -> dict[str, Any]:
        """Get configuration for specific variant.

        Args:
            variant: Variant name (e.g., "main", "playtest")

        Returns:
            Variant configuration dictionary
        """
        if not self._config_data:
            self.load()

        return self._config_data.get("variants", {}).get(variant, {})

    def get_global_config(self, section: Optional[str] = None) -> dict[str, Any]:
        """Get global configuration or specific global section.

        Args:
            section: Optional section name (e.g., "mediawiki", "google_sheets")

        Returns:
            Global configuration dictionary
        """
        if not self._config_data:
            self.load()

        global_config = self._config_data.get("global", {})

        if section:
            return global_config.get(section, {})

        return global_config

    @property
    def repo_root(self) -> Path:
        """Get repository root directory."""
        return self._repo_root

    @property
    def version(self) -> str:
        """Get configuration version."""
        if not self._config_data:
            self.load()
        return self._config_data.get("version", "unknown")

    @property
    def default_variant(self) -> str:
        """Get default variant name."""
        if not self._config_data:
            self.load()
        return self._config_data.get("default_variant", "main")


def load_config(repo_root: Optional[Path] = None) -> TomlConfigLoader:
    """Load configuration from unified config.toml.

    Args:
        repo_root: Optional explicit repository root

    Returns:
        TomlConfigLoader instance
    """
    loader = TomlConfigLoader(repo_root)
    loader.load()
    return loader
