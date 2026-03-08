"""Tests for configuration schema models.

This module tests Pydantic model validation, defaults, and constraints
for all configuration models defined in schema.py.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from erenshor.infrastructure.config.schema import (
    AssetRipperConfig,
    BehaviorConfig,
    Config,
    DatabaseConfig,
    GlobalConfig,
    GoogleSheetsConfig,
    LoggingConfig,
    MapsConfig,
    MediaWikiConfig,
    PathsConfig,
    SteamConfig,
    UnityConfig,
    VariantConfig,
    VariantGoogleSheetsConfig,
)


class TestPathsConfig:
    """Tests for PathsConfig model."""

    def test_default_values(self):
        """Test that PathsConfig has correct default values."""
        config = PathsConfig()
        assert config.state == "$REPO_ROOT/.erenshor/state.json"
        assert config.config_local == "$REPO_ROOT/.erenshor/config.local.toml"
        assert config.logs == "$REPO_ROOT/.erenshor/logs"

    def test_custom_values(self):
        """Test creating PathsConfig with custom values."""
        config = PathsConfig(
            state="/custom/state.json",
            config_local="/custom/config.toml",
            logs="/custom/logs",
        )
        assert config.state == "/custom/state.json"
        assert config.config_local == "/custom/config.toml"
        assert config.logs == "/custom/logs"

    def test_resolved_state(self, tmp_path: Path):
        """Test resolved_state() method."""
        config = PathsConfig(state="$REPO_ROOT/.erenshor/state.json")
        resolved = config.resolved_state(tmp_path)
        assert resolved == tmp_path / ".erenshor/state.json"
        assert resolved.is_absolute()

    def test_resolved_config_local(self, tmp_path: Path):
        """Test resolved_config_local() method."""
        config = PathsConfig(config_local="$REPO_ROOT/.erenshor/config.local.toml")
        resolved = config.resolved_config_local(tmp_path)
        assert resolved == tmp_path / ".erenshor/config.local.toml"
        assert resolved.is_absolute()

    def test_resolved_logs(self, tmp_path: Path):
        """Test resolved_logs() method."""
        config = PathsConfig(logs="$REPO_ROOT/.erenshor/logs")
        resolved = config.resolved_logs(tmp_path)
        assert resolved == tmp_path / ".erenshor/logs"
        assert resolved.is_absolute()


class TestSteamConfig:
    """Tests for SteamConfig model."""

    def test_default_values(self):
        """Test that SteamConfig has correct default values."""
        config = SteamConfig()
        assert config.username == ""
        assert config.platform == "windows"

    def test_valid_platforms(self):
        """Test that valid platform values are accepted."""
        for platform in ["windows", "macos", "linux"]:
            config = SteamConfig(platform=platform)
            assert config.platform == platform

    def test_invalid_platform_rejected(self):
        """Test that invalid platform values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SteamConfig(platform="invalid")

        errors = exc_info.value.errors()
        assert any("platform" in str(e["loc"]) for e in errors)

    def test_custom_username(self):
        """Test setting custom Steam username."""
        config = SteamConfig(username="test_user")
        assert config.username == "test_user"


class TestUnityConfig:
    """Tests for UnityConfig model."""

    def test_default_values(self):
        """Test that UnityConfig has correct default values."""
        config = UnityConfig()
        assert config.version == "2021.3.45f2"
        assert "/Unity" in config.path
        assert config.timeout == 3600

    def test_timeout_constraints(self):
        """Test that timeout respects min/max constraints."""
        # Valid values
        UnityConfig(timeout=60)  # Min
        UnityConfig(timeout=3600)  # Default
        UnityConfig(timeout=7200)  # Max

        # Too low
        with pytest.raises(ValidationError):
            UnityConfig(timeout=59)

        # Too high
        with pytest.raises(ValidationError):
            UnityConfig(timeout=7201)

    def test_custom_path(self):
        """Test setting custom Unity path."""
        custom_path = "/custom/unity/Unity.app"
        config = UnityConfig(path=custom_path)
        assert config.path == custom_path

    def test_resolved_path(self, tmp_path: Path):
        """Test resolved_path() method without validation."""
        config = UnityConfig(path="$REPO_ROOT/Unity.app")
        resolved = config.resolved_path(tmp_path, validate=False)
        assert resolved == tmp_path / "Unity.app"
        assert resolved.is_absolute()

    def test_resolved_path_with_validation_fails_if_not_exists(self, tmp_path: Path):
        """Test resolved_path() with validation raises error if path doesn't exist."""
        from erenshor.infrastructure.config.paths import PathResolutionError

        config = UnityConfig(path="$REPO_ROOT/nonexistent/Unity.app")
        with pytest.raises(PathResolutionError):
            config.resolved_path(tmp_path, validate=True)

    def test_resolved_path_with_validation_succeeds_if_exists(self, tmp_path: Path):
        """Test resolved_path() with validation succeeds if path exists."""
        unity_path = tmp_path / "Unity.app"
        unity_path.touch()

        config = UnityConfig(path=str(unity_path))
        resolved = config.resolved_path(tmp_path, validate=True)
        assert resolved == unity_path


class TestAssetRipperConfig:
    """Tests for AssetRipperConfig model."""

    def test_default_values(self):
        """Test that AssetRipperConfig has correct default values."""
        config = AssetRipperConfig()
        assert config.path == ""  # No default path - must be configured
        assert config.port == 8080
        assert config.timeout == 3600

    def test_port_constraints(self):
        """Test that port respects min/max constraints."""
        # Valid values
        AssetRipperConfig(port=1024)  # Min
        AssetRipperConfig(port=8080)  # Default
        AssetRipperConfig(port=65535)  # Max

        # Too low
        with pytest.raises(ValidationError):
            AssetRipperConfig(port=1023)

        # Too high
        with pytest.raises(ValidationError):
            AssetRipperConfig(port=65536)

    def test_timeout_constraints(self):
        """Test that timeout respects min/max constraints."""
        # Valid values
        AssetRipperConfig(timeout=60)  # Min
        AssetRipperConfig(timeout=3600)  # Default
        AssetRipperConfig(timeout=7200)  # Max

        # Too low
        with pytest.raises(ValidationError):
            AssetRipperConfig(timeout=59)

        # Too high
        with pytest.raises(ValidationError):
            AssetRipperConfig(timeout=7201)

    def test_resolved_path(self, tmp_path: Path):
        """Test resolved_path() method."""
        config = AssetRipperConfig(path="$REPO_ROOT/AssetRipper")
        resolved = config.resolved_path(tmp_path, validate=False)
        assert resolved == tmp_path / "AssetRipper"
        assert resolved.is_absolute()


class TestDatabaseConfig:
    """Tests for DatabaseConfig model."""

    def test_default_values(self):
        """Test that DatabaseConfig has correct default values."""
        config = DatabaseConfig()
        assert config.enable_validation is True

    def test_disable_validation(self):
        """Test disabling validation."""
        config = DatabaseConfig(enable_validation=False)
        assert config.enable_validation is False


class TestMediaWikiConfig:
    """Tests for MediaWikiConfig model."""

    def test_default_values(self):
        """Test that MediaWikiConfig has correct default values."""
        config = MediaWikiConfig()
        assert "erenshor.wiki.gg" in config.api_url
        assert config.api_batch_size == 25
        assert config.api_delay == 1.0
        assert config.upload_batch_size == 10
        assert config.upload_delay == 1.0
        assert config.upload_edit_summary == "Automated wiki update"
        assert config.upload_minor_edit is True
        assert config.bot_username == ""
        assert config.bot_password == ""

    def test_batch_size_constraints(self):
        """Test that batch sizes respect min/max constraints."""
        # Valid values
        MediaWikiConfig(api_batch_size=1)  # Min
        MediaWikiConfig(api_batch_size=50)  # Max
        MediaWikiConfig(upload_batch_size=1)  # Min
        MediaWikiConfig(upload_batch_size=50)  # Max

        # Too low
        with pytest.raises(ValidationError):
            MediaWikiConfig(api_batch_size=0)

        # Too high
        with pytest.raises(ValidationError):
            MediaWikiConfig(api_batch_size=51)

    def test_delay_constraints(self):
        """Test that delays respect min/max constraints."""
        # Valid values
        MediaWikiConfig(api_delay=0.0)  # Min
        MediaWikiConfig(api_delay=10.0)  # Max
        MediaWikiConfig(upload_delay=0.0)  # Min
        MediaWikiConfig(upload_delay=10.0)  # Max

        # Too low
        with pytest.raises(ValidationError):
            MediaWikiConfig(api_delay=-0.1)

        # Too high
        with pytest.raises(ValidationError):
            MediaWikiConfig(upload_delay=10.1)

    def test_custom_credentials(self):
        """Test setting bot credentials."""
        config = MediaWikiConfig(
            bot_username="test_bot",
            bot_password="secret123",
        )
        assert config.bot_username == "test_bot"
        assert config.bot_password == "secret123"


class TestGoogleSheetsConfig:
    """Tests for GoogleSheetsConfig model."""

    def test_default_values(self):
        """Test that GoogleSheetsConfig has correct default values."""
        config = GoogleSheetsConfig()
        assert "$HOME" in config.credentials_file
        assert config.batch_size == 1000
        assert config.max_retries == 3
        assert config.retry_delay == 5

    def test_batch_size_constraints(self):
        """Test that batch_size respects min/max constraints."""
        # Valid values
        GoogleSheetsConfig(batch_size=1)  # Min
        GoogleSheetsConfig(batch_size=1000)  # Default
        GoogleSheetsConfig(batch_size=10000)  # Max

        # Too low
        with pytest.raises(ValidationError):
            GoogleSheetsConfig(batch_size=0)

        # Too high
        with pytest.raises(ValidationError):
            GoogleSheetsConfig(batch_size=10001)

    def test_retry_constraints(self):
        """Test that retry settings respect min/max constraints."""
        # Valid values
        GoogleSheetsConfig(max_retries=0)  # Min
        GoogleSheetsConfig(max_retries=10)  # Max
        GoogleSheetsConfig(retry_delay=1)  # Min
        GoogleSheetsConfig(retry_delay=60)  # Max

        # Too low
        with pytest.raises(ValidationError):
            GoogleSheetsConfig(max_retries=-1)

        # Too high
        with pytest.raises(ValidationError):
            GoogleSheetsConfig(retry_delay=61)

    def test_resolved_credentials_file(self, tmp_path: Path):
        """Test resolved_credentials_file() method."""
        config = GoogleSheetsConfig(credentials_file="$REPO_ROOT/credentials.json")
        resolved = config.resolved_credentials_file(tmp_path, validate=False)
        assert resolved == tmp_path / "credentials.json"
        assert resolved.is_absolute()


class TestBehaviorConfig:
    """Tests for BehaviorConfig model."""

    def test_default_values(self):
        """Test that BehaviorConfig has correct default values."""
        config = BehaviorConfig()
        assert config.max_retries == 3
        assert config.retry_delay == 30

    def test_retry_constraints(self):
        """Test that retry settings respect min/max constraints."""
        # Valid values
        BehaviorConfig(max_retries=0)  # Min
        BehaviorConfig(max_retries=10)  # Max
        BehaviorConfig(retry_delay=1)  # Min
        BehaviorConfig(retry_delay=300)  # Max

        # Too low
        with pytest.raises(ValidationError):
            BehaviorConfig(max_retries=-1)

        # Too high
        with pytest.raises(ValidationError):
            BehaviorConfig(retry_delay=301)


class TestLoggingConfig:
    """Tests for LoggingConfig model."""

    def test_default_value(self):
        """Test that LoggingConfig has correct default value."""
        config = LoggingConfig()
        assert config.level == "info"

    def test_valid_levels(self):
        """Test that all valid log levels are accepted."""
        for level in ["debug", "info", "warn", "error"]:
            config = LoggingConfig(level=level)
            assert config.level == level

    def test_invalid_level_rejected(self):
        """Test that invalid log levels are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LoggingConfig(level="invalid")

        errors = exc_info.value.errors()
        assert any("level" in str(e["loc"]) for e in errors)


class TestGlobalConfig:
    """Tests for GlobalConfig model."""

    def test_default_factory_creates_nested_configs(self):
        """Test that default_factory creates all nested configuration objects."""
        config = GlobalConfig()

        # Check that all nested configs are created
        assert isinstance(config.paths, PathsConfig)
        assert isinstance(config.steam, SteamConfig)
        assert isinstance(config.unity, UnityConfig)
        assert isinstance(config.assetripper, AssetRipperConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.mediawiki, MediaWikiConfig)
        assert isinstance(config.google_sheets, GoogleSheetsConfig)
        assert isinstance(config.behavior, BehaviorConfig)
        assert isinstance(config.logging, LoggingConfig)

    def test_custom_nested_values(self):
        """Test creating GlobalConfig with custom nested values."""
        config = GlobalConfig(
            unity=UnityConfig(timeout=7200),
            logging=LoggingConfig(level="debug"),
        )
        assert config.unity.timeout == 7200
        assert config.logging.level == "debug"

    def test_partial_override_preserves_defaults(self):
        """Test that overriding one field doesn't affect other defaults."""
        config = GlobalConfig(
            unity=UnityConfig(timeout=7200)  # Override just timeout
        )
        # Unity timeout is overridden
        assert config.unity.timeout == 7200
        # But other Unity fields keep defaults
        assert config.unity.version == "2021.3.45f2"
        # Other top-level configs keep their defaults
        assert config.logging.level == "info"


class TestVariantGoogleSheetsConfig:
    """Tests for VariantGoogleSheetsConfig model."""

    def test_default_empty_spreadsheet_id(self):
        """Test that spreadsheet_id defaults to empty string."""
        config = VariantGoogleSheetsConfig()
        assert config.spreadsheet_id == ""

    def test_custom_spreadsheet_id(self):
        """Test setting custom spreadsheet ID."""
        config = VariantGoogleSheetsConfig(spreadsheet_id="1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E")
        assert config.spreadsheet_id == "1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E"


class TestMapsConfig:
    """Tests for MapsConfig model."""

    def test_default_values(self):
        """Test that MapsConfig has correct default values."""
        config = MapsConfig()
        assert config.source_dir == "$REPO_ROOT/src/maps"
        assert config.data_dir == "$REPO_ROOT/src/maps/static/data"
        assert config.database_dir == "$REPO_ROOT/src/maps/static/db"
        assert config.build_dir == "$REPO_ROOT/src/maps/build"
        assert config.deploy_target == "erenshor-maps"

    def test_custom_values(self):
        """Test creating MapsConfig with custom values."""
        config = MapsConfig(
            source_dir="/custom/maps",
            data_dir="/custom/data",
            database_dir="/custom/db",
            build_dir="/custom/build",
            deploy_target="custom-project",
        )
        assert config.source_dir == "/custom/maps"
        assert config.data_dir == "/custom/data"
        assert config.database_dir == "/custom/db"
        assert config.build_dir == "/custom/build"
        assert config.deploy_target == "custom-project"

    def test_resolved_source_dir(self, tmp_path: Path):
        """Test resolved_source_dir() method."""
        config = MapsConfig(source_dir="$REPO_ROOT/src/maps")
        resolved = config.resolved_source_dir(tmp_path)
        assert resolved == tmp_path / "src/maps"
        assert resolved.is_absolute()

    def test_resolved_data_dir(self, tmp_path: Path):
        """Test resolved_data_dir() method."""
        config = MapsConfig(data_dir="$REPO_ROOT/src/maps/static/data")
        resolved = config.resolved_data_dir(tmp_path)
        assert resolved == tmp_path / "src/maps/static/data"
        assert resolved.is_absolute()

    def test_resolved_database_dir(self, tmp_path: Path):
        """Test resolved_database_dir() method."""
        config = MapsConfig(database_dir="$REPO_ROOT/src/maps/static/db")
        resolved = config.resolved_database_dir(tmp_path)
        assert resolved == tmp_path / "src/maps/static/db"
        assert resolved.is_absolute()

    def test_resolved_build_dir(self, tmp_path: Path):
        """Test resolved_build_dir() method."""
        config = MapsConfig(build_dir="$REPO_ROOT/src/maps/build")
        resolved = config.resolved_build_dir(tmp_path)
        assert resolved == tmp_path / "src/maps/build"
        assert resolved.is_absolute()


class TestVariantConfig:
    """Tests for VariantConfig model."""

    def test_required_fields(self):
        """Test that required fields must be provided."""
        # Missing required fields should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            VariantConfig()

        errors = exc_info.value.errors()
        required_fields = {
            "name",
            "app_id",
            "unity_project",
            "editor_scripts",
            "game_files",
            "database_raw",
            "database",
            "logs",
            "backups",
            "wiki",
        }

        error_fields = {str(e["loc"][0]) for e in errors}
        # All required fields should be in errors
        assert required_fields.issubset(error_fields)

    def test_valid_variant_config(self):
        """Test creating valid VariantConfig with all required fields."""
        config = VariantConfig(
            name="Main Game",
            app_id="2382520",
            unity_project="$REPO_ROOT/variants/main/unity",
            editor_scripts="$REPO_ROOT/src/Assets/Editor",
            game_files="$REPO_ROOT/variants/main/game",
            database_raw="$REPO_ROOT/variants/main/erenshor-raw.sqlite",
            database="$REPO_ROOT/variants/main/erenshor.sqlite",
            logs="$REPO_ROOT/variants/main/logs",
            backups="$REPO_ROOT/variants/main/backups",
            wiki="$REPO_ROOT/variants/main/wiki",
        )

        assert config.enabled is True  # Default
        assert config.description == ""  # Default
        assert config.images_output == ""  # Default
        assert config.name == "Main Game"
        assert config.app_id == "2382520"

    def test_disabled_variant(self):
        """Test creating disabled variant."""
        config = VariantConfig(
            enabled=False,
            name="Disabled Variant",
            app_id="12345",
            unity_project="/path/to/unity",
            editor_scripts="/path/to/scripts",
            game_files="/path/to/game",
            database_raw="/path/to/raw.sqlite",
            database="/path/to/db.sqlite",
            logs="/path/to/logs",
            backups="/path/to/backups",
            wiki="/path/to/wiki",
        )
        assert config.enabled is False

    def test_resolved_methods(self, tmp_path: Path):
        """Test all resolved_*() methods on VariantConfig."""
        config = VariantConfig(
            name="Test",
            app_id="12345",
            unity_project="$REPO_ROOT/unity",
            editor_scripts="$REPO_ROOT/scripts",
            game_files="$REPO_ROOT/game",
            database_raw="$REPO_ROOT/raw.sqlite",
            database="$REPO_ROOT/db.sqlite",
            logs="$REPO_ROOT/logs",
            backups="$REPO_ROOT/backups",
            images_output="$REPO_ROOT/images",
            wiki="$REPO_ROOT/wiki",
        )

        assert config.resolved_unity_project(tmp_path) == tmp_path / "unity"
        assert config.resolved_editor_scripts(tmp_path) == tmp_path / "scripts"
        assert config.resolved_game_files(tmp_path) == tmp_path / "game"
        assert config.resolved_database_raw(tmp_path) == tmp_path / "raw.sqlite"
        assert config.resolved_database(tmp_path) == tmp_path / "db.sqlite"
        assert config.resolved_logs(tmp_path) == tmp_path / "logs"
        assert config.resolved_backups(tmp_path) == tmp_path / "backups"
        assert config.resolved_images_output(tmp_path) == tmp_path / "images"


class TestConfig:
    """Tests for root Config model."""

    def test_minimal_valid_config(self):
        """Test creating minimal valid Config."""
        config = Config()

        # Check defaults
        assert config.version == "0.3"
        assert config.default_variant == "main"
        assert isinstance(config.global_, GlobalConfig)
        assert config.variants == {}

    def test_config_with_variants(self):
        """Test creating Config with variant configurations."""
        config = Config(
            variants={
                "main": VariantConfig(
                    name="Main Game",
                    app_id="2382520",
                    unity_project="/path/to/unity",
                    editor_scripts="/path/to/scripts",
                    game_files="/path/to/game",
                    database_raw="/path/to/raw.sqlite",
                    database="/path/to/db.sqlite",
                    logs="/path/to/logs",
                    backups="/path/to/backups",
                    wiki="/path/to/wiki",
                )
            }
        )

        assert "main" in config.variants
        assert config.variants["main"].name == "Main Game"
        assert config.variants["main"].app_id == "2382520"

    def test_global_alias_works(self):
        """Test that 'global' alias works for 'global_' field."""
        # Using alias in dict format (as would come from TOML)
        config_dict = {
            "version": "0.3",
            "default_variant": "main",
            "global": {"logging": {"level": "debug"}},
            "variants": {},
        }

        config = Config.model_validate(config_dict)
        assert config.global_.logging.level == "debug"

    def test_custom_default_variant(self):
        """Test setting custom default variant."""
        config = Config(default_variant="playtest")
        assert config.default_variant == "playtest"

    def test_multiple_variants(self):
        """Test config with multiple variants."""
        config = Config(
            variants={
                "main": VariantConfig(
                    name="Main",
                    app_id="1",
                    unity_project="/main/unity",
                    editor_scripts="/scripts",
                    game_files="/main/game",
                    database_raw="/main/raw.sqlite",
                    database="/main/db.sqlite",
                    logs="/main/logs",
                    backups="/main/backups",
                    wiki="/main/wiki",
                ),
                "playtest": VariantConfig(
                    name="Playtest",
                    app_id="2",
                    unity_project="/playtest/unity",
                    editor_scripts="/scripts",
                    game_files="/playtest/game",
                    database_raw="/playtest/raw.sqlite",
                    database="/playtest/db.sqlite",
                    logs="/playtest/logs",
                    backups="/playtest/backups",
                    wiki="/playtest/wiki",
                ),
            }
        )

        assert len(config.variants) == 2
        assert "main" in config.variants
        assert "playtest" in config.variants
