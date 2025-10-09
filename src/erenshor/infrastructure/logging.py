"""Central logging configuration for the application.

Provides consistent logging setup across all modules with proper formatting,
log levels, and third-party logger silencing.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

__all__ = ["setup_logging", "get_logger"]


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """Configure application-wide logging with consistent format.

    Sets up root logger with console and optional file handlers. Silences
    noisy third-party loggers (httpx, sqlalchemy) to reduce noise.

    Args:
        level: Log level as string ("DEBUG", "INFO", "WARNING", "ERROR")
        log_file: Optional path to log file. If provided, logs to both
                  console and file.

    Example:
        >>> setup_logging(level="DEBUG", log_file=Path("app.log"))
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter with timestamp, level, module, and message
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance for a module.

    Args:
        name: Logger name, typically __name__ from calling module

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing items")
    """
    return logging.getLogger(name)
