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

from typing import Literal

from pydantic import BaseModel, Field


class PathsConfig(BaseModel):
    """Global path configuration for project directories and files.

    All paths support environment variable expansion:
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


class SteamConfig(BaseModel):
    """Steam and SteamCMD configuration.

    SteamCMD is used to download game files from Steam. Credentials
    are loaded from environment variables or local config for security.
    """

    username: str = Field(
        default="",
        description="Steam username (set via ERENSHOR_STEAM_USERNAME or config.local.toml)",
    )
    platform: Literal["windows", "macos", "linux"] = Field(
        default="windows",
        description="Platform version to download (force Windows for cross-platform compatibility)",
    )


class UnityConfig(BaseModel):
    """Unity Editor configuration for batch mode exports.

    Unity must match the exact version used by the game for asset compatibility.
    """

    version: str = Field(
        default="2021.3.45f2",
        description="Unity Editor version (must match game's Unity version exactly)",
    )
    path: str = Field(
        default="/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity",
        description="Path to Unity executable",
    )
    timeout: int = Field(
        default=3600,
        ge=60,
        le=7200,
        description="Maximum time in seconds for Unity batch exports (60s - 2h)",
    )


class AssetRipperConfig(BaseModel):
    """AssetRipper configuration for extracting Unity projects from game files.

    AssetRipper converts compiled game assets back into editable Unity projects.
    """

    path: str = Field(
        default="$HOME/Projects/AssetRipper/AssetRipper.GUI.Free",
        description="Path to AssetRipper executable or directory",
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


class DatabaseConfig(BaseModel):
    """Database configuration and validation settings.

    SQLite databases store extracted game data in normalized tables.
    """

    enable_validation: bool = Field(
        default=True,
        description="Enable database schema validation after exports",
    )


class MediaWikiConfig(BaseModel):
    """MediaWiki API configuration for wiki synchronization.

    Supports fetching wiki templates and uploading generated pages.
    Bot credentials are loaded from environment variables for security.
    """

    api_url: str = Field(
        default="https://erenshor.wiki.gg/api.php",
        description="MediaWiki API endpoint URL",
    )
    api_batch_size: int = Field(
        default=25,
        ge=1,
        le=50,
        description="Number of pages to fetch per API request (1-50)",
    )
    api_delay: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="Delay in seconds between API requests to avoid rate limiting",
    )
    upload_batch_size: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum pages to upload in one batch",
    )
    upload_delay: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="Delay in seconds between uploads to avoid rate limiting",
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
        description="MediaWiki bot username from Special:BotPasswords (set via env or config.local.toml)",
    )
    bot_password: str = Field(
        default="",
        description="MediaWiki bot password from Special:BotPasswords (set via env or config.local.toml)",
    )


class GoogleSheetsConfig(BaseModel):
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


class BehaviorConfig(BaseModel):
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


class LoggingConfig(BaseModel):
    """Logging configuration for the pipeline.

    Controls log level and format for both Bash CLI and Python services.
    """

    level: Literal["debug", "info", "warn", "error"] = Field(
        default="info",
        description="Log level: debug (verbose), info (normal), warn (important), error (critical only)",
    )


class GlobalConfig(BaseModel):
    """Global configuration settings shared across all variants.

    Contains tool configurations, service settings, and behavioral options
    that apply to the entire pipeline.
    """

    paths: PathsConfig = Field(
        default_factory=PathsConfig,
        description="Global path configuration",
    )
    steam: SteamConfig = Field(
        default_factory=SteamConfig,
        description="Steam and SteamCMD configuration",
    )
    unity: UnityConfig = Field(
        default_factory=UnityConfig,
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


class VariantGoogleSheetsConfig(BaseModel):
    """Variant-specific Google Sheets configuration.

    Each game variant can deploy to a different spreadsheet.
    """

    spreadsheet_id: str = Field(
        default="",
        description="Google Sheets spreadsheet ID (from spreadsheet URL)",
    )


class VariantConfig(BaseModel):
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
        description="Steam App ID for game download",
    )
    unity_project: str = Field(
        description="Path to Unity project directory (created by AssetRipper)",
    )
    editor_scripts: str = Field(
        description="Path to custom Unity Editor scripts (symlinked into project)",
    )
    game_files: str = Field(
        description="Path to downloaded game files from Steam",
    )
    database: str = Field(
        description="Path to SQLite database for this variant",
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
    google_sheets: VariantGoogleSheetsConfig = Field(
        default_factory=VariantGoogleSheetsConfig,
        description="Google Sheets configuration for this variant",
    )


class Config(BaseModel):
    """Root configuration model for the Erenshor data mining pipeline.

    This is the top-level configuration object that contains all settings
    for the pipeline. It supports multiple game variants with variant-specific
    overrides while sharing global settings.

    Configuration loading priority:
    1. Environment variables (ERENSHOR_* prefix)
    2. config.local.toml (gitignored, for local overrides)
    3. config.toml (project defaults)
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
        default_factory=GlobalConfig,
        description="Global configuration shared across all variants",
    )
    variants: dict[str, VariantConfig] = Field(
        default_factory=dict,
        description="Game variant configurations (main, playtest, demo, etc.)",
    )

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True  # Allow using both 'global_' and 'global'
