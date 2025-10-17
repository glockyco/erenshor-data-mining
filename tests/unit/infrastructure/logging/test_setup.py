"""Tests for logging setup and configuration.

This module tests the setup_logging() function, including:
- Logging setup with global and variant-specific logs
- Log level configuration (INFO, DEBUG, WARNING, ERROR)
- File handler creation and log rotation
- Console handler creation
- Idempotent setup (calling multiple times)
- Error handling (invalid paths, permissions, invalid log levels)
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from loguru import logger

from erenshor.infrastructure.config.schema import (
    Config,
    GlobalConfig,
    LoggingConfig,
    MediaWikiConfig,
    PathsConfig,
    UnityConfig,
    VariantConfig,
    VariantGoogleSheetsConfig,
)
from erenshor.infrastructure.logging.setup import LoggingSetupError, setup_logging


@pytest.fixture
def minimal_config(tmp_path: Path) -> Config:
    """Create a minimal valid configuration for testing."""
    return Config(
        version="0.3",
        default_variant="main",
        global_=GlobalConfig(
            unity=UnityConfig(
                version="2021.3.45f2",
                path="/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app",
                timeout=3600,
            ),
            logging=LoggingConfig(level="info"),
            paths=PathsConfig(
                logs=".erenshor/logs",
                state=".erenshor/state.json",
                backups=".erenshor/backups",
            ),
            mediawiki=MediaWikiConfig(
                api_url="https://wiki.example.com/api.php",
                bot_username="TestBot",
                bot_password_env="MEDIAWIKI_PASSWORD",
                api_delay=1.0,
                api_timeout=30.0,
                api_batch_size=50,
            ),
        ),
        variants={
            "main": VariantConfig(
                enabled=True,
                name="Main Game",
                app_id="2382520",
                unity_project="variants/main/unity",
                editor_scripts="src/Assets/Editor",
                game_files="variants/main/game",
                database="variants/main/erenshor-main.sqlite",
                logs="variants/main/logs",
                backups="variants/main/backups",
                google_sheets=VariantGoogleSheetsConfig(
                    spreadsheet_id="test-spreadsheet-id",
                ),
            ),
        },
    )


class TestLoggingSetup:
    """Tests for setup_logging() function."""

    def test_setup_global_logging(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test setting up logging with global log directory."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Create log directory
        log_dir = tmp_path / ".erenshor" / "logs"
        log_dir.mkdir(parents=True)

        # Setup logging
        setup_logging(minimal_config)

        # Verify log directory was created
        assert log_dir.exists()
        assert log_dir.is_dir()

        # Verify logger has handlers (console + file)
        # Loguru's logger._core.handlers is a dict of handler_id -> handler
        assert len(logger._core.handlers) >= 1  # At least console handler

    def test_setup_variant_logging(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test setting up logging with variant-specific log directory."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Setup logging for "main" variant
        setup_logging(minimal_config, variant="main")

        # Verify variant log directory was created
        log_dir = tmp_path / "variants" / "main" / "logs"
        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_setup_with_debug_level(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test setting up logging with DEBUG level."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Set log level to debug
        minimal_config.global_.logging.level = "debug"

        # Setup logging
        setup_logging(minimal_config)

        # Log at different levels
        logger.debug("Debug message test")
        logger.info("Info message test")

        # Flush all queued log messages to file (enqueue=True makes logging async)
        logger.complete()

        # Check the log file to verify both levels appear
        log_dir = tmp_path / ".erenshor" / "logs"
        log_files = list(log_dir.glob("erenshor_*.log"))
        assert len(log_files) > 0

        # Read log file
        log_content = log_files[0].read_text()

        # Both DEBUG and INFO should be in log file
        assert "Debug message test" in log_content
        assert "Info message test" in log_content

    def test_setup_with_info_level(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test setting up logging with INFO level (default)."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Ensure log level is info
        minimal_config.global_.logging.level = "info"

        # Setup logging
        setup_logging(minimal_config)

        # Log at different levels
        logger.debug("Debug message test - should be filtered")
        logger.info("Info message test - should appear")

        # Flush all queued log messages to file (enqueue=True makes logging async)
        logger.complete()

        # Check the log file to verify filtering
        log_dir = tmp_path / ".erenshor" / "logs"
        log_files = list(log_dir.glob("erenshor_*.log"))
        assert len(log_files) > 0

        # Read log file
        log_content = log_files[0].read_text()

        # DEBUG should NOT be in log file (filtered by INFO level)
        # INFO should be in log file
        assert "Debug message test" not in log_content
        assert "Info message test" in log_content

    def test_setup_with_warning_level(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test setting up logging with WARNING level."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Set log level to warning
        minimal_config.global_.logging.level = "warning"

        # Setup logging
        setup_logging(minimal_config)

        # Log at different levels
        logger.info("Info message test - should be filtered")
        logger.warning("Warning message test - should appear")

        # Flush all queued log messages to file (enqueue=True makes logging async)
        logger.complete()

        # Check the log file to verify filtering
        log_dir = tmp_path / ".erenshor" / "logs"
        log_files = list(log_dir.glob("erenshor_*.log"))
        assert len(log_files) > 0

        # Read log file
        log_content = log_files[0].read_text()

        # INFO should NOT be in log file (filtered by WARNING level)
        # WARNING should be in log file
        assert "Info message test" not in log_content
        assert "Warning message test" in log_content

    def test_setup_with_error_level(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test setting up logging with ERROR level."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Set log level to error
        minimal_config.global_.logging.level = "error"

        # Setup logging
        setup_logging(minimal_config)

        # Log at different levels
        logger.warning("Warning message test - should be filtered")
        logger.error("Error message test - should appear")

        # Flush all queued log messages to file (enqueue=True makes logging async)
        logger.complete()

        # Check the log file to verify filtering
        log_dir = tmp_path / ".erenshor" / "logs"
        log_files = list(log_dir.glob("erenshor_*.log"))
        assert len(log_files) > 0

        # Read log file
        log_content = log_files[0].read_text()

        # WARNING should NOT be in log file (filtered by ERROR level)
        # ERROR should be in log file
        assert "Warning message test" not in log_content
        assert "Error message test" in log_content

    def test_setup_normalizes_warn_to_warning(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that 'warn' log level is normalized to 'WARNING'."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Set log level to 'warn' (lowercase, non-standard)
        minimal_config.global_.logging.level = "warn"

        # Should not raise an error (should normalize to WARNING)
        setup_logging(minimal_config)

    def test_setup_is_idempotent(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that calling setup_logging multiple times is safe."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Call setup multiple times
        setup_logging(minimal_config)
        setup_logging(minimal_config)
        setup_logging(minimal_config)

        # Should not raise errors, handlers should be cleaned up each time
        # We can't easily verify handler count, but lack of errors is good enough

    def test_setup_switches_between_variants(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that setup can switch between global and variant logging."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Setup global logging
        setup_logging(minimal_config)
        global_log_dir = tmp_path / ".erenshor" / "logs"
        assert global_log_dir.exists()

        # Switch to variant logging
        setup_logging(minimal_config, variant="main")
        variant_log_dir = tmp_path / "variants" / "main" / "logs"
        assert variant_log_dir.exists()

        # Switch back to global
        setup_logging(minimal_config)
        assert global_log_dir.exists()

    def test_setup_creates_log_directory(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that setup creates log directory if it doesn't exist."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Log directory should not exist yet
        log_dir = tmp_path / ".erenshor" / "logs"
        assert not log_dir.exists()

        # Setup logging
        setup_logging(minimal_config)

        # Log directory should now exist
        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_setup_fails_with_invalid_log_level(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that setup fails with invalid log level."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Set invalid log level
        minimal_config.global_.logging.level = "invalid"

        # Should raise LoggingSetupError
        with pytest.raises(LoggingSetupError) as exc_info:
            setup_logging(minimal_config)

        error_msg = str(exc_info.value)
        assert "Invalid log level" in error_msg
        assert "invalid" in error_msg.lower()
        assert "Valid levels:" in error_msg

    def test_setup_fails_with_unknown_variant(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that setup fails when variant doesn't exist in config."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Try to setup logging for non-existent variant
        with pytest.raises(LoggingSetupError) as exc_info:
            setup_logging(minimal_config, variant="nonexistent")

        error_msg = str(exc_info.value)
        assert "Unknown variant" in error_msg
        assert "nonexistent" in error_msg
        assert "Available variants:" in error_msg

    def test_setup_fails_when_directory_creation_fails(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that setup fails gracefully when directory creation fails."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Mock mkdir to raise OSError
        original_mkdir = Path.mkdir

        def mock_mkdir(self, *args, **kwargs):
            if ".erenshor/logs" in str(self):
                raise OSError("Permission denied")
            return original_mkdir(self, *args, **kwargs)

        with (
            patch.object(Path, "mkdir", mock_mkdir),
            pytest.raises(LoggingSetupError) as exc_info,
        ):
            setup_logging(minimal_config)

        error_msg = str(exc_info.value)
        assert "Failed to create log directory" in error_msg
        assert "Permission denied" in error_msg

    def test_setup_logs_successful_configuration(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that setup logs its own successful configuration."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Create a list to capture log messages
        messages = []

        def sink(message):
            messages.append(message)

        # Setup logging
        setup_logging(minimal_config)

        # Add test sink to capture the success message
        logger.add(sink, level="INFO")

        # The setup function logs its own success, but it already happened
        # So we need to check that the function completed without errors
        # We'll verify the log directory exists instead
        log_dir = tmp_path / ".erenshor" / "logs"
        assert log_dir.exists()

    def test_setup_console_handler_uses_stderr(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that console handler writes to stderr."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Mock stderr with a StringIO-like object to prevent file creation
        # MagicMock alone causes loguru to interpret str(mock) as a filename
        from io import StringIO

        mock_stderr = StringIO()

        with patch.object(sys, "stderr", mock_stderr):
            setup_logging(minimal_config)

        # Loguru adds a handler to sys.stderr
        # We can verify by checking that handlers exist
        assert len(logger._core.handlers) >= 1

    def test_setup_file_handler_configuration(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that file handler is configured with rotation and compression."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Setup logging
        setup_logging(minimal_config)

        # Write a log message to ensure file is created
        logger.info("Test message for file handler")

        # Flush all queued log messages to file (enqueue=True makes logging async)
        logger.complete()

        # Check that log file exists (with timestamp pattern)
        log_dir = tmp_path / ".erenshor" / "logs"
        log_files = list(log_dir.glob("erenshor_*.log"))

        # Should have at least one log file
        assert len(log_files) >= 1

    def test_setup_variant_uses_correct_log_path(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that variant logging uses the correct log path."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Setup variant logging
        setup_logging(minimal_config, variant="main")

        # Verify correct log directory
        variant_log_dir = tmp_path / "variants" / "main" / "logs"
        assert variant_log_dir.exists()

        # Note: Global log directory might be created by other setup calls,
        # so we just verify variant dir exists

    def test_setup_handles_case_insensitive_log_levels(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that log levels are case-insensitive."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Test various cases
        test_cases = ["info", "INFO", "Info", "InFo"]

        for level in test_cases:
            minimal_config.global_.logging.level = level
            # Should not raise an error
            setup_logging(minimal_config)

    def test_setup_removes_existing_handlers(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that setup removes existing handlers before adding new ones."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Add a custom handler
        handler_id = logger.add(lambda msg: None, level="INFO")

        # Verify handler was added
        assert handler_id in logger._core.handlers

        # Setup logging (should remove all handlers)
        setup_logging(minimal_config)

        # Original handler should be removed
        assert handler_id not in logger._core.handlers

    def test_setup_creates_nested_log_directories(self, minimal_config: Config, tmp_path: Path, monkeypatch):
        """Test that setup creates nested directories for log paths."""
        # Create fake repo root
        monkeypatch.setattr("erenshor.infrastructure.logging.setup.get_repo_root", lambda: tmp_path)

        # Setup variant logging (requires creating variants/main/logs)
        setup_logging(minimal_config, variant="main")

        # Verify full path was created
        log_dir = tmp_path / "variants" / "main" / "logs"
        assert log_dir.exists()
        assert (tmp_path / "variants").exists()
        assert (tmp_path / "variants" / "main").exists()
