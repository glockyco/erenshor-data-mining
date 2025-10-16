"""Logging infrastructure with Loguru.

This module provides logging setup and configuration using Loguru as the
logging backend. It supports both console output and file logging with
rotation, compression, and retention policies.

Key features:
- Colorized console output for readability
- File logging with rotation (10 MB) and retention (7 days)
- Configurable log levels (debug, info, warn, error)
- Variant-specific and global log files
- Clean integration with config system
- Utility functions for common logging patterns
"""

from .setup import setup_logging
from .utils import (
    log_command_end,
    log_command_start,
    log_error,
    log_function,
    log_operation,
    log_progress,
)

__all__ = [
    "log_command_end",
    "log_command_start",
    "log_error",
    "log_function",
    "log_operation",
    "log_progress",
    "setup_logging",
]
