"""Logging setup and configuration with Loguru.

This module configures Loguru as the logging backend for the Erenshor pipeline.
It provides both console output (colorized, INFO+) and file logging (detailed,
with rotation and compression).

Configuration:
- Log level: Configurable via config (debug/info/warn/error)
- Console format: Simple, colorized format for readability
- File format: Detailed format with function/line numbers
- Rotation: 10 MB per file
- Retention: 7 days
- Compression: gzip (.gz)

The setup_logging() function is idempotent and can be called multiple times
safely. Each call will reconfigure logging handlers based on the provided
configuration.
"""

import sys

from loguru import logger

from erenshor.infrastructure.config.loader import get_repo_root
from erenshor.infrastructure.config.schema import Config


class LoggingSetupError(Exception):
    """Raised when logging setup fails.

    This can occur when:
    - Log directory cannot be created
    - File permissions prevent writing logs
    - Invalid log level specified
    """

    pass


def setup_logging(config: Config, variant: str | None = None) -> None:
    """Configure Loguru logging with console and file handlers.

    Sets up logging with two handlers:
    1. Console (stderr): Colorized, simple format, for interactive use
    2. File: Detailed format with rotation/compression, for persistence

    The function is idempotent - calling it multiple times will remove existing
    handlers and reconfigure logging. This allows changing log levels or
    switching between variants at runtime.

    Args:
        config: Configuration object containing logging settings.
        variant: Optional variant name for variant-specific log files.
            If None, uses global log directory.

    Raises:
        LoggingSetupError: If logging setup fails (directory creation,
            permissions, invalid configuration).

    Example:
        >>> from erenshor.infrastructure.config.loader import load_config
        >>> config = load_config()
        >>> setup_logging(config)  # Global logging
        >>> setup_logging(config, variant="main")  # Variant-specific logging
    """
    # Remove all existing handlers (idempotent)
    logger.remove()

    # Normalize log level (config uses lowercase, Loguru uses uppercase)
    log_level = config.global_.logging.level.upper()

    # Validate log level
    valid_levels = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR"}
    if log_level not in valid_levels:
        raise LoggingSetupError(
            f"Invalid log level: {log_level}\n"
            f"Valid levels: {', '.join(sorted(valid_levels))}\n"
            f"Check your configuration file."
        )

    # Normalize WARN -> WARNING (Loguru uses WARNING)
    if log_level == "WARN":
        log_level = "WARNING"

    # Console handler: Colorized, simple format
    console_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <level>{message}</level>"

    logger.add(
        sys.stderr,
        format=console_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Determine log file path
    repo_root = get_repo_root()

    if variant is not None:
        # Variant-specific logs
        if variant not in config.variants:
            raise LoggingSetupError(
                f"Unknown variant: {variant}\n"
                f"Available variants: {', '.join(config.variants.keys())}\n"
                f"Check your configuration or variant name."
            )

        log_dir = config.variants[variant].resolved_logs(repo_root)
        log_file = log_dir / "erenshor_{time:YYYY-MM-DD}.log"
    else:
        # Global logs
        log_dir = config.global_.paths.resolved_logs(repo_root)
        log_file = log_dir / "erenshor_{time:YYYY-MM-DD}.log"

    # Create log directory if it doesn't exist
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise LoggingSetupError(
            f"Failed to create log directory: {log_dir}\n"
            f"Error: {e}\n"
            f"Check directory permissions and available disk space."
        ) from e

    # File handler: Detailed format with rotation/compression
    file_format = "{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}"

    try:
        logger.add(
            str(log_file),
            format=file_format,
            level=log_level,
            rotation="10 MB",  # Rotate when file reaches 10 MB
            retention="7 days",  # Keep logs for 7 days
            compression="gz",  # Compress rotated logs with gzip
            backtrace=True,
            diagnose=True,
            enqueue=True,  # Thread-safe logging
        )
    except (OSError, PermissionError) as e:
        raise LoggingSetupError(
            f"Failed to configure file logging: {log_file}\n"
            f"Error: {e}\n"
            f"Check file permissions and available disk space."
        ) from e

    # Log successful setup
    logger.info(f"Logging configured: level={log_level}, variant={variant or 'global'}, log_dir={log_dir}")
