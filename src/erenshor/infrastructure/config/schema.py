"""Configuration schema definitions using Pydantic models.

This module defines the complete configuration structure for the Erenshor
data mining pipeline. All configuration models use Pydantic for validation
and type safety.

The configuration supports:
- Global settings (paths, logging, behavior)
- Tool-specific settings (Steam, Unity, AssetRipper, Database)
- Service settings (MediaWiki, Google Sheets)
- Multiple game variants (main, playtest, demo) with variant-specific configs
"""

import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigModel(BaseModel):
    """Base for configuration sections. An unknown or removed key is an error."""

    model_config = ConfigDict(extra="forbid")


class PathsConfig(ConfigModel):
    """Global path configuration for project directories and files.

    All paths support variable expansion:
    - $REPO_ROOT: Repository root directory (auto-detected)
    - $HOME, ~: User's home directory
    """

    state: str = Field(
        default="$REPO_ROOT/.erenshor/state.json",
        description="Path to state file tracking pipeline execution status",
    )
    config_local: str = Field(
        default="$REPO_ROOT/.erenshor/config.local.toml",
        description="Path to local config overrides (gitignored)",
    )
    logs: str = Field(
        default="$REPO_ROOT/.erenshor/logs",
        description="Directory for global logs",
    )
    templates: str = Field(
        default="$REPO_ROOT/src/erenshor/application/wiki/generators/templates",
        description="Directory for Jinja2 wiki templates",
    )

    def resolved_state(self, repo_root: Path) -> Path:
        """Get resolved state file path."""
        from .paths import resolve_path

        return resolve_path(self.state, repo_root)

    def resolved_config_local(self, repo_root: Path) -> Path:
        """Get resolved local config file path."""
        from .paths import resolve_path

        return resolve_path(self.config_local, repo_root)

    def resolved_logs(self, repo_root: Path) -> Path:
        """Get resolved logs directory path."""
        from .paths import resolve_path

        return resolve_path(self.logs, repo_root)

    def resolved_templates(self, repo_root: Path) -> Path:
        """Get resolved templates directory path."""
        from .paths import resolve_path

        return resolve_path(self.templates, repo_root)


class UnityConfig(ConfigModel):
    """Unity Editor configuration for batch mode exports.

    Unity must match the exact version used by the game for asset compatibility.
    """

    version: str = Field(
        description="Unity Editor version (must match game's Unity version exactly). Set in config.toml.",
    )
    path: str = Field(
        description="Path to Unity executable. Set in config.toml, override in the local config.",
    )
    timeout: int = Field(
        default=3600,
        ge=60,
        le=7200,
        description="Maximum time in seconds for Unity batch exports (60s - 2h)",
    )

    def resolved_path(self, repo_root: Path, validate: bool = True) -> Path:
        """Get resolved Unity executable path.

        Args:
            repo_root: Repository root for path expansion.
            validate: If True, verify that Unity executable exists.

        Returns:
            Absolute path to Unity executable.

        Raises:
            PathResolutionError: If validation enabled and Unity not found.
        """
        from .paths import resolve_path

        return resolve_path(self.path, repo_root, validate=validate)


class AssetRipperConfig(ConfigModel):
    """AssetRipper configuration for extracting Unity projects from game files.

    AssetRipper converts compiled game assets back into editable Unity projects.
    A bare executable name is looked up on PATH, so the dev shell can supply the
    binary; a value containing a separator is treated as a filesystem path.
    """

    path: str = Field(
        default="AssetRipper",
        description="AssetRipper executable: bare name resolved on PATH, or an explicit path",
    )
    port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="Port for AssetRipper GUI/API (1024-65535)",
    )
    timeout: int = Field(
        default=3600,
        ge=60,
        le=7200,
        description="Maximum time in seconds for asset extraction (60s - 2h)",
    )

    def resolved_path(self, repo_root: Path, validate: bool = True) -> Path:
        """Get resolved AssetRipper executable path.

        A configured value without a path separator names an executable on PATH
        and is resolved there, which keeps environment-managed installations
        (nix dev shell, package manager) out of the tracked configuration.

        Args:
            repo_root: Repository root for path expansion.
            validate: If True, verify that AssetRipper executable exists.

        Returns:
            Absolute path to AssetRipper executable or directory.

        Raises:
            PathResolutionError: If validation enabled and AssetRipper not found.
        """
        from .paths import PathResolutionError, resolve_path

        if self.path and "/" not in self.path and "\\" not in self.path:
            found = shutil.which(self.path)
            if found is not None:
                return Path(found)
            if validate:
                raise PathResolutionError(
                    f"AssetRipper executable not found on PATH: {self.path}\n"
                    f"Enter the dev shell, or set [global.assetripper] path to an "
                    f"explicit location in .erenshor/config.local.toml."
                )
            return Path(self.path)

        return resolve_path(self.path, repo_root, validate=validate)


class DatabaseConfig(ConfigModel):
    """Database configuration and validation settings.

    SQLite databases store extracted game data in normalized tables.
    """

    enable_validation: bool = Field(
        default=True,
        description="Enable database schema validation after exports",
    )


class MediaWikiConfig(ConfigModel):
    """MediaWiki API configuration for wiki synchronization.

    Supports fetching wiki templates and uploading generated pages.
    Bot credentials are loaded from config.toml or .erenshor/config.local.toml.
    Interface-admin credentials are a separate account and must be stored only
    in .erenshor/config.local.toml. Store all sensitive credentials in
    config.local.toml only (gitignored).
    """

    api_url: str = Field(
        default="https://erenshor.wiki.gg/api.php",
        description="MediaWiki API endpoint URL",
    )
    max_page_bytes: int = Field(
        default=4194304,
        ge=1,
        description="Maximum UTF-8 bytes in a wiki data module",
    )
    upload_batch_size: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum pages to upload in one batch",
    )
    upload_edit_summary: str = Field(
        default="Automated wiki update",
        description="Default edit summary for wiki page updates",
    )
    upload_minor_edit: bool = Field(
        default=True,
        description="Mark uploads as minor edits",
    )
    bot_username: str = Field(
        default="",
        description="MediaWiki bot username from Special:BotPasswords (set in .erenshor/config.local.toml)",
    )
    bot_password: str = Field(
        default="",
        description="MediaWiki bot password from Special:BotPasswords (set in .erenshor/config.local.toml)",
    )
    interface_username: str = Field(
        default="",
        description=(
            "Dedicated MediaWiki interface-admin username (set only in "
            ".erenshor/config.local.toml; never use bot_username as a fallback)"
        ),
    )
    interface_password: str = Field(
        default="",
        description=(
            "Dedicated MediaWiki interface-admin password (set only in "
            ".erenshor/config.local.toml; never use bot_password as a fallback)"
        ),
    )
    administrator_username: str = Field(
        default="",
        description=(
            "Bot password username of an administrator with the delete and file-move grants, which "
            "images publish moves and deletes files with (set only in .erenshor/config.local.toml)"
        ),
    )
    administrator_password: str = Field(
        default="",
        description=(
            "Bot password of an administrator with the delete and file-move grants, which images "
            "publish moves and deletes files with (set only in .erenshor/config.local.toml)"
        ),
    )


class GoogleSheetsConfig(ConfigModel):
    """Google Sheets API configuration for spreadsheet deployment.

    Uses Google Service Account credentials for API access.
    Service account must have Editor permissions on target spreadsheets.
    """

    credentials_file: str = Field(
        default="$HOME/.config/erenshor/google-credentials.json",
        description="Path to Google Service Account credentials JSON file",
    )
    batch_size: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Number of rows to upload per batch request",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts for failed operations",
    )
    retry_delay: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Delay in seconds between retry attempts",
    )

    def resolved_credentials_file(self, repo_root: Path, validate: bool = True) -> Path:
        """Get resolved credentials file path.

        Args:
            repo_root: Repository root for path expansion.
            validate: If True, verify that credentials file exists.

        Returns:
            Absolute path to Google credentials JSON file.

        Raises:
            PathResolutionError: If validation enabled and credentials not found.
        """
        from .paths import resolve_path

        return resolve_path(self.credentials_file, repo_root, validate=validate)


class BehaviorConfig(ConfigModel):
    """Global behavior settings for pipeline operations.

    These settings control retry logic, timeouts, and other behavioral aspects
    of the pipeline that aren't specific to individual tools.
    """

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Default maximum retry attempts for operations",
    )
    retry_delay: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Default delay in seconds between retry attempts",
    )


class BepInExDevToolsConfig(ConfigModel):
    """Download URLs for BepInEx development tools.

    Used by `erenshor mod dev-setup` to install ScriptEngine (hot reload)
    and ConfigurationManager (in-game config editing).
    Values configured in config.toml under [global.bepinex_dev_tools].
    """

    script_engine_url: str = Field(description="ScriptEngine download URL (BepInEx.Debug release)")
    config_manager_url: str = Field(description="ConfigurationManager download URL (BepInEx5 release)")


class LoggingConfig(ConfigModel):
    """Logging configuration for the pipeline.

    Controls log level and format for both Bash CLI and Python services.
    """

    level: Literal["debug", "info", "warn", "error"] = Field(
        default="info",
        description="Log level: debug (verbose), info (normal), warn (important), error (critical only)",
    )


class ModsConfig(ConfigModel):
    """Configuration for companion mod builds."""

    lunaris_lib_dir: str = Field(
        default="",
        description=(
            "Directory with the Lunaris compile libraries (ImGui.NET.dll, "
            "Newtonsoft.Json.dll, 0Harmony.dll, ...) extracted from LunarisLibs.zip. "
            "Overridden by the ERENSHOR_LUNARIS_LIB_DIR environment variable. Set in "
            ".erenshor/config.local.toml to point at your extracted copy, or leave it "
            "empty to auto-fetch LunarisLibs.zip into .erenshor/cache."
        ),
    )

    lunaris_libs_url: str = Field(
        default="https://github.com/MizukiBelhi/Lunaris/releases/download/Libs/LunarisLibs.zip",
        description=(
            "URL of the LunarisLibs.zip archive (ImGui.NET, Newtonsoft.Json, "
            "0Harmony, ...). Auto-fetched and cached under .erenshor/cache when "
            "lunaris_lib_dir is empty and ERENSHOR_LUNARIS_LIB_DIR is unset."
        ),
    )

    def resolved_lunaris_lib_dir(self, repo_root: Path, validate: bool = False) -> Path:
        """Resolve the Lunaris build library directory to an absolute path."""
        from .paths import resolve_path

        return resolve_path(self.lunaris_lib_dir, repo_root, validate=validate)


class GlobalConfig(ConfigModel):
    """Global configuration settings shared across all variants.

    Contains tool configurations, service settings, and behavioral options
    that apply to the entire pipeline.
    """

    paths: PathsConfig = Field(
        default_factory=PathsConfig,
        description="Global path configuration",
    )
    unity: UnityConfig = Field(
        description="Unity Editor configuration",
    )
    assetripper: AssetRipperConfig = Field(
        default_factory=AssetRipperConfig,
        description="AssetRipper configuration",
    )
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="Database configuration",
    )
    mediawiki: MediaWikiConfig = Field(
        default_factory=MediaWikiConfig,
        description="MediaWiki API configuration",
    )
    google_sheets: GoogleSheetsConfig = Field(
        default_factory=GoogleSheetsConfig,
        description="Google Sheets API configuration",
    )
    behavior: BehaviorConfig = Field(
        default_factory=BehaviorConfig,
        description="Global behavior settings",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration",
    )
    bepinex_dev_tools: BepInExDevToolsConfig | None = Field(
        default=None,
        description="BepInEx development tool download URLs (configure in config.toml)",
    )
    mods: ModsConfig = Field(
        default_factory=ModsConfig,
        description="Companion mod build configuration",
    )


class VariantGoogleSheetsConfig(ConfigModel):
    """Variant-specific Google Sheets configuration.

    Each game variant can deploy to a different spreadsheet.
    """

    spreadsheet_id: str = Field(
        default="",
        description="Google Sheets spreadsheet ID (from spreadsheet URL)",
    )


class MapsConfig(ConfigModel):
    """Configuration for the interactive maps web application.

    The maps project is a SvelteKit application that displays game data
    in an interactive map interface. Its build reads the variant's clean
    database and deploys to Cloudflare Workers.
    """

    source_dir: str = Field(
        default="$REPO_ROOT/src/maps",
        description="Path to maps source directory (SvelteKit project root)",
    )
    data_dir: str = Field(
        default="$REPO_ROOT/src/maps/static/data",
        description="Path to maps static/data directory for exported data files",
    )
    build_dir: str = Field(
        default="$REPO_ROOT/src/maps/build",
        description="Path to maps build output directory",
    )
    base_url: str = Field(
        default="https://erenshor.compendiums.org",
        description="Public base URL of the deployed maps website",
    )

    def resolved_source_dir(self, repo_root: Path) -> Path:
        """Get resolved maps source directory path."""
        from .paths import resolve_path

        return resolve_path(self.source_dir, repo_root)

    def resolved_data_dir(self, repo_root: Path) -> Path:
        """Get resolved maps data directory path."""
        from .paths import resolve_path

        return resolve_path(self.data_dir, repo_root)

    def resolved_build_dir(self, repo_root: Path) -> Path:
        """Get resolved maps build directory path."""
        from .paths import resolve_path

        return resolve_path(self.build_dir, repo_root)


class VariantConfig(ConfigModel):
    """Configuration for a single game variant.

    Game variants represent different versions (main, playtest, demo) with
    separate downloads, Unity projects, databases, and deployment targets.
    """

    enabled: bool = Field(
        default=True,
        description="Enable this variant for pipeline operations",
    )
    name: str = Field(
        description="Human-readable name for this variant",
    )
    description: str = Field(
        default="",
        description="Description of what this variant represents",
    )
    app_id: str = Field(
        description="Steam App ID. Discovery finds the installation by this ID in the CrossOver Steam bottle.",
    )
    unity_project: str = Field(
        description="Path to Unity project directory (created by AssetRipper)",
    )
    editor_scripts: str = Field(
        description="Path to custom Unity Editor scripts (symlinked into project)",
    )
    database_raw: str = Field(
        description="Path to raw SQLite database written directly by Unity export",
    )
    database: str = Field(
        description="Path to clean SQLite database produced by the Python processor",
    )
    logs: str = Field(
        description="Directory for variant-specific logs",
    )
    backups: str = Field(
        description="Directory for database backups",
    )
    images_output: str = Field(
        default="",
        description="Directory for processed game images",
    )
    wiki: str = Field(
        description="Directory for wiki working files (fetched and generated pages)",
    )
    google_sheets: VariantGoogleSheetsConfig = Field(
        default_factory=VariantGoogleSheetsConfig,
        description="Google Sheets configuration for this variant",
    )
    maps: MapsConfig = Field(
        default_factory=MapsConfig,
        description="Interactive maps web application configuration",
    )

    def resolved_unity_project(self, repo_root: Path) -> Path:
        """Get resolved Unity project directory path."""
        from .paths import resolve_path

        return resolve_path(self.unity_project, repo_root)

    def resolved_editor_scripts(self, repo_root: Path) -> Path:
        """Get resolved Editor scripts directory path."""
        from .paths import resolve_path

        return resolve_path(self.editor_scripts, repo_root)

    def resolved_profiles(self, repo_root: Path) -> Path:
        """Get resolved extraction profile directory path."""
        return self.resolved_database(repo_root).parent / "profiles"

    def resolved_database_raw(self, repo_root: Path) -> Path:
        """Get resolved raw database file path (Unity export target)."""
        from .paths import resolve_path

        return resolve_path(self.database_raw, repo_root)

    def resolved_database(self, repo_root: Path) -> Path:
        """Get resolved clean database file path (Python processor output)."""
        from .paths import resolve_path

        return resolve_path(self.database, repo_root)

    def resolved_logs(self, repo_root: Path) -> Path:
        """Get resolved logs directory path."""
        from .paths import resolve_path

        return resolve_path(self.logs, repo_root)

    def resolved_backups(self, repo_root: Path) -> Path:
        """Get resolved backups directory path."""
        from .paths import resolve_path

        return resolve_path(self.backups, repo_root)

    def resolved_images_output(self, repo_root: Path) -> Path:
        """Get resolved images output directory path."""
        from .paths import resolve_path

        return resolve_path(self.images_output, repo_root)

    def resolved_wiki(self, repo_root: Path) -> Path:
        """Get resolved wiki working directory path."""
        from .paths import resolve_path

        return resolve_path(self.wiki, repo_root)


class Config(ConfigModel):
    """Root configuration model for the Erenshor data mining pipeline.

    This is the top-level configuration object that contains all settings
    for the pipeline. It supports multiple game variants with variant-specific
    overrides while sharing global settings.

    Two-layer configuration system:
    1. config.toml (project defaults, tracked in git)
    2. .erenshor/config.local.toml (user overrides, gitignored)

    NO environment variables are used. All configuration comes from TOML files.
    """

    version: str = Field(
        default="0.3",
        description="Configuration schema version",
    )
    default_variant: str = Field(
        default="main",
        description="Default variant when --variant flag is not specified",
    )
    global_: GlobalConfig = Field(
        alias="global",
        description="Global configuration shared across all variants",
    )
    variants: dict[str, VariantConfig] = Field(
        default_factory=dict,
        description="Game variant configurations (main, playtest, demo, etc.)",
    )

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True  # Allow using both 'global_' and 'global'
