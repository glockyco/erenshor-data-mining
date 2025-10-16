"""Configuration schema and loading for Erenshor data mining pipeline.

This module provides Pydantic models for configuration management.
Configuration can be loaded from TOML files with variable expansion
($REPO_ROOT, $HOME, ~) and local overrides.
"""

from erenshor.infrastructure.config.loader import ConfigLoadError, get_repo_root, load_config
from erenshor.infrastructure.config.paths import PathResolutionError, resolve_path
from erenshor.infrastructure.config.schema import (
    AssetRipperConfig,
    BehaviorConfig,
    Config,
    DatabaseConfig,
    GlobalConfig,
    GoogleSheetsConfig,
    LoggingConfig,
    MediaWikiConfig,
    PathsConfig,
    SteamConfig,
    UnityConfig,
    VariantConfig,
    VariantGoogleSheetsConfig,
)

__all__ = [
    "AssetRipperConfig",
    "BehaviorConfig",
    "Config",
    "ConfigLoadError",
    "DatabaseConfig",
    "GlobalConfig",
    "GoogleSheetsConfig",
    "LoggingConfig",
    "MediaWikiConfig",
    "PathResolutionError",
    "PathsConfig",
    "SteamConfig",
    "UnityConfig",
    "VariantConfig",
    "VariantGoogleSheetsConfig",
    "get_repo_root",
    "load_config",
    "resolve_path",
]
