"""Modern configuration system using pydantic-settings.

Supports multiple configuration sources with clear precedence:
1. CLI flags (highest priority - rare overrides)
2. Environment variables (ERENSHOR_* prefix)
3. .env file (gitignored, for local secrets)
4. config.toml (unified Bash + Python configuration)
5. Sensible defaults (lowest - work out-of-the-box)

The configuration is shared with Bash CLI via config.toml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from erenshor.infrastructure.config.paths import get_path_resolver
from erenshor.infrastructure.config.toml_loader import load_config

__all__ = ["WikiSettings", "load_settings"]


class WikiSettings(BaseSettings):
    """Central configuration for erenshor-wiki with type-safe validation."""

    # Database
    db_path: Path = Field(
        default=Path(""),  # Will be set in model_post_init
        description="Path to erenshor.sqlite database file",
    )

    # Directories
    cache_dir: Path = Field(
        default=Path(""),  # Will be set in model_post_init
        description="Directory for cached wiki pages",
    )
    output_dir: Path = Field(
        default=Path(""),  # Will be set in model_post_init
        description="Directory for generated wiki pages",
    )
    reports_dir: Path = Field(
        default=Path(""),  # Will be set in model_post_init
        description="Directory for operation reports",
    )

    # API (fetch)
    api_url: str = Field(
        default="https://erenshor.wiki.gg/api.php",
        description="MediaWiki API endpoint URL",
    )
    api_batch_size: int = Field(
        default=25,
        ge=1,
        le=50,
        description="Number of pages to fetch per API request",
    )
    api_delay: float = Field(
        default=1.0,
        ge=0.0,
        description="Delay in seconds between API requests",
    )

    # Upload
    upload_batch_size: int = Field(
        default=10,
        ge=1,
        description="Maximum pages to upload in one batch",
    )
    upload_delay: float = Field(
        default=1.0,
        ge=0.0,
        description="Delay in seconds between uploads",
    )
    upload_edit_summary: str = Field(
        default="Automated wiki update",
        description="Default edit summary for uploads",
    )
    upload_minor_edit: bool = Field(
        default=True,
        description="Mark uploads as minor edits by default",
    )

    # Bot credentials (required for upload, loaded from env vars or .env)
    bot_username: Optional[str] = Field(
        default=None,
        description="MediaWiki bot username (from Special:BotPasswords)",
    )
    bot_password: Optional[str] = Field(
        default=None,
        description="MediaWiki bot password (from Special:BotPasswords)",
    )

    model_config = SettingsConfigDict(
        env_prefix="ERENSHOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("db_path", "cache_dir", "output_dir", "reports_dir", mode="before")
    @classmethod
    def resolve_path(cls, v: str | Path) -> Path:
        """Resolve paths using PathResolver.

        Empty Path("") values will be set to defaults in model_post_init.
        """
        if isinstance(v, str):
            v = Path(v)

        # Empty path means use default (will be set in model_post_init)
        if str(v) == "" or str(v) == ".":
            return v

        if v.is_absolute():
            return v

        # Use PathResolver for relative paths
        resolver = get_path_resolver()
        return resolver.resolve(v)

    def model_post_init(self, __context: Any) -> None:
        """Set defaults using PathResolver after initialization."""
        resolver = get_path_resolver()

        # Set defaults if not provided (empty string or ".")
        if str(self.db_path) == "" or str(self.db_path) == ".":
            self.db_path = resolver.db_path
        if str(self.cache_dir) == "" or str(self.cache_dir) == ".":
            self.cache_dir = resolver.cache_dir
        if str(self.output_dir) == "" or str(self.output_dir) == ".":
            self.output_dir = resolver.output_dir
        if str(self.reports_dir) == "" or str(self.reports_dir) == ".":
            self.reports_dir = resolver.reports_dir


def load_settings() -> WikiSettings:
    """Load configuration from all sources with proper precedence.

    Wiki commands always use the main variant.

    Priority order (highest to lowest):
    1. CLI flags (passed directly to commands)
    2. Environment variables (ERENSHOR_*)
    3. .env file (gitignored)
    4. config.toml (unified Bash + Python configuration)
    5. Defaults defined in WikiSettings
    """
    # Use PathResolver to find .env file (always use main variant for wiki)
    resolver = get_path_resolver(variant="main")
    env_file = resolver.env_file

    # Load TOML configuration
    toml_config = load_config(resolver.root)

    # Update model config with resolved env_file path
    if env_file.exists():
        WikiSettings.model_config["env_file"] = str(env_file)
    else:
        # Don't try to load .env if it doesn't exist
        WikiSettings.model_config["env_file"] = None

    # Get MediaWiki configuration from TOML
    mediawiki_config = toml_config.get_global_config("mediawiki")
    google_sheets_config = toml_config.get_global_config("google_sheets")
    paths_config = toml_config.get_global_config("paths")

    # Set Field defaults from TOML (pydantic will use these if env vars not set)
    # This ensures environment variables have higher priority than TOML config
    field_mappings = [
        ("api_url", "api_url"),
        ("api_batch_size", "api_batch_size"),
        ("api_delay", "api_delay"),
        ("upload_batch_size", "upload_batch_size"),
        ("upload_delay", "upload_delay"),
        ("upload_edit_summary", "upload_edit_summary"),
        ("upload_minor_edit", "upload_minor_edit"),
        ("bot_username", "bot_username"),
        ("bot_password", "bot_password"),
    ]

    for field_name, toml_key in field_mappings:
        toml_value = mediawiki_config.get(toml_key)
        if toml_value is not None and toml_value != "":
            WikiSettings.model_fields[field_name].default = toml_value

    # Create settings instance - pydantic will read env vars first, then use Field defaults
    settings = WikiSettings()

    return settings
