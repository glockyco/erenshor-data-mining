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
"""

from .setup import setup_logging

__all__ = ["setup_logging"]
