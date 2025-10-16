"""Central path resolution service for erenshor-wiki.

This module provides a PathResolver class that handles all path resolution
for the project, supporting both development and installed modes with
configurable overrides via environment variables.

Wiki commands always use the main variant.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

__all__ = ["PathResolver", "get_path_resolver"]


# Configure logging level from environment (default: WARNING)
_log_level = os.environ.get("ERENSHOR_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(level=_log_level)
logger = logging.getLogger(__name__)


def _normalize_env_key(subdir: str) -> str:
    """Normalize subdirectory name to environment variable key.

    Args:
        subdir: Subdirectory name (e.g., 'registry', 'wiki_cache', 'out/reports')

    Returns:
        Normalized env key (e.g., 'REGISTRY', 'WIKI_CACHE', 'OUT_REPORTS')
    """
    return subdir.upper().replace("/", "_").replace("-", "_")


class PathResolver:
    """Central path resolution service.

    Provides consistent path resolution for all project paths with support
    for development mode, installed mode, and user overrides via environment
    variables.

    Wiki commands always use the main variant configuration from config.toml.

    Auto-detection priority:
    1. Explicit parameter (PathResolver(root=...))
    2. Environment variable (ERENSHOR_PROJECT_ROOT)
    3. Walk up from cwd to find pyproject.toml
    4. Walk up from cwd to find .git
    5. Use current working directory (with warning)

    Environment Variables:
        ERENSHOR_PROJECT_ROOT: Override project root directory
        ERENSHOR_MAPPING_FILE: Override mapping.json location
        ERENSHOR_REGISTRY_DIR: Override registry/ directory
        ERENSHOR_WIKI_CACHE_DIR: Override wiki_cache/ directory
        ERENSHOR_WIKI_UPDATED_DIR: Override wiki_updated/ directory
        ERENSHOR_DB_PATH: Override database path
        ERENSHOR_ENV_FILE: Override .env file location
        ERENSHOR_REPORTS_DIR: Override reports directory
    """

    def __init__(self, root: Optional[Path] = None, variant: str = "main") -> None:
        """Initialize resolver with optional root override.

        Args:
            root: Explicit project root. If None, auto-detects.
            variant: Variant name for variant-specific paths (default: "main")
        """
        self._root = root.resolve() if root else self._detect_project_root()
        self._variant = variant
        self._mode = self._detect_mode()
        self._variant_config: dict[str, Any] = {}
        self._load_variant_config()
        self._validate_project_root()

        # Log initialization details
        logger.info(
            f"PathResolver initialized: root={self._root}, mode={self._mode}, variant={self._variant}"
        )
        logger.debug(f"Project root exists: {self._root.exists()}")
        logger.debug(f"Database path: {self.db_path}")
        logger.debug(f"Registry dir: {self.registry_dir}")
        logger.debug(f"Cache dir: {self.cache_dir}")
        logger.debug(f"Output dir: {self.output_dir}")

    @staticmethod
    def _detect_project_root() -> Path:
        """Auto-detect project root via marker files.

        Search order:
        1. ERENSHOR_PROJECT_ROOT env var (highest priority)
        2. Current directory and parents for pyproject.toml
        3. Current directory and parents for .git
        4. Fallback to current directory (with warning)

        Returns:
            Path to project root
        """
        # Check env override first
        env_root = os.environ.get("ERENSHOR_PROJECT_ROOT")
        if env_root:
            resolved = Path(env_root).resolve()
            logger.debug(f"Using ERENSHOR_PROJECT_ROOT: {resolved}")
            return resolved

        # Search for marker files
        marker_files = ("pyproject.toml", ".git")
        current = Path.cwd().resolve()

        for parent in [current] + list(current.parents):
            for marker in marker_files:
                if (parent / marker).exists():
                    return parent

        # Fallback to cwd with warning
        logger.warning(
            "Could not find project root markers (pyproject.toml or .git). "
            f"Using current directory: {current}. "
            f"This may cause issues if not running from project root. "
            f"To fix: Either cd to project root, or set ERENSHOR_PROJECT_ROOT environment variable. "
            f"Example: export ERENSHOR_PROJECT_ROOT=/path/to/erenshor-wiki"
        )
        return current

    def _detect_mode(self) -> str:
        """Detect if running in development or installed mode.

        Returns:
            "development" if pyproject.toml exists at root, else "installed"
        """
        if (self._root / "pyproject.toml").exists():
            return "development"
        return "installed"

    def _load_variant_config(self) -> None:
        """Load variant configuration from config.toml.

        Uses TomlConfigLoader to load variant-specific paths.
        Falls back to empty dict if config cannot be loaded.
        """
        try:
            from erenshor.infrastructure.config.toml_loader import load_config

            config = load_config(self._root)
            self._variant_config = config.get_variant_config(self._variant)

            if not self._variant_config:
                logger.warning(
                    f"Variant '{self._variant}' not found in config.toml. "
                    f"Using fallback paths. "
                    f"Available variants: main, playtest, demo"
                )
        except Exception as e:
            logger.warning(
                f"Could not load variant config from config.toml: {e}. "
                f"Using fallback paths."
            )

    def _validate_project_root(self) -> None:
        """Validate that root looks like erenshor-wiki project.

        In development mode, checks for expected structure.
        In installed mode, just ensures the directory exists.
        """
        if not self._root.exists():
            logger.warning(
                f"Project root does not exist: {self._root}. "
                "Some operations may fail. "
                f"To fix: Create the directory or set ERENSHOR_PROJECT_ROOT to a valid path. "
                f"See README.md Path Configuration section for details."
            )
        elif self._mode == "development":
            # In dev mode, check for expected structure markers
            if not (self._root / "src").exists():
                logger.warning(
                    f"Project root {self._root} does not contain 'src/' directory. "
                    "This may not be the correct project root. "
                    f"Current root: {self._root} "
                    f"Expected structure: {self._root}/src/erenshor/ "
                    f"To fix: Set ERENSHOR_PROJECT_ROOT to the correct directory."
                )

    @property
    def root(self) -> Path:
        """Get project root directory."""
        return self._root

    @property
    def mode(self) -> str:
        """Get runtime mode (development or installed)."""
        return self._mode

    # Project structure paths

    @property
    def src_dir(self) -> Path:
        """Get src directory (development mode only).

        Returns:
            Path to src/ directory

        Raises:
            RuntimeError: If called in installed mode
        """
        if self._mode == "development":
            return self._root / "src"
        raise RuntimeError(
            "src_dir only available in development mode. "
            f"Current mode: {self._mode}. "
            f"To use development mode, ensure pyproject.toml exists at project root: {self._root}"
        )

    @property
    def package_dir(self) -> Path:
        """Get package directory.

        Returns:
            Path to erenshor package directory
        """
        if self._mode == "development":
            return self._root / "src" / "erenshor"

        # In installed mode, use importlib to find package
        from importlib.util import find_spec

        spec = find_spec("erenshor")
        if spec and spec.origin:
            return Path(spec.origin).parent
        raise RuntimeError(
            "Cannot locate erenshor package directory. "
            "Package may not be installed correctly. "
            "To fix: Run 'uv install' from project root, or 'pip install -e .' for editable install."
        )

    # Data directories (relative to project root in dev, or configurable in installed)

    def data_dir(self, subdir: str) -> Path:
        """Get data directory path with environment variable override support.

        In development mode, uses project root.
        In installed mode, uses platformdirs for user data directory.

        Args:
            subdir: Subdirectory name (e.g., 'registry', 'wiki_cache')

        Returns:
            Path to data directory
        """
        # Check env var override - normalize to uppercase with underscores
        env_key = f"ERENSHOR_{_normalize_env_key(subdir)}_DIR"
        env_val = os.environ.get(env_key)
        if env_val:
            resolved = Path(env_val).resolve()
            logger.debug(f"Using {env_key}: {resolved}")
            return resolved

        # In development mode, use project root
        if self._mode == "development":
            return self._root / subdir

        # In installed mode, use platformdirs
        from platformdirs import user_data_dir

        base_dir = Path(user_data_dir("erenshor-wiki", "erenshor-wiki"))
        return base_dir / subdir

    @property
    def registry_dir(self) -> Path:
        """Get variant-specific registry directory.

        Returns:
            Path to registry directory for the configured variant
            (e.g., variants/main/registry/)
        """
        # Check env override
        env_key = "ERENSHOR_REGISTRY_DIR"
        env_val = os.environ.get(env_key)
        if env_val:
            resolved = Path(env_val).resolve()
            logger.debug(f"Using {env_key}: {resolved}")
            return resolved

        # Use variant-specific path
        return self._root / "variants" / self._variant / "registry"

    @property
    def cache_dir(self) -> Path:
        """Get variant-specific wiki cache directory.

        Returns:
            Path to wiki_cache directory for the configured variant
            (e.g., variants/main/wiki_cache/)
        """
        # Check env override
        env_key = "ERENSHOR_WIKI_CACHE_DIR"
        env_val = os.environ.get(env_key)
        if env_val:
            resolved = Path(env_val).resolve()
            logger.debug(f"Using {env_key}: {resolved}")
            return resolved

        # Use variant-specific path
        return self._root / "variants" / self._variant / "wiki_cache"

    @property
    def output_dir(self) -> Path:
        """Get variant-specific wiki output directory.

        Returns:
            Path to wiki_updated directory for the configured variant
            (e.g., variants/main/wiki_updated/)
        """
        # Check env override
        env_key = "ERENSHOR_WIKI_UPDATED_DIR"
        env_val = os.environ.get(env_key)
        if env_val:
            resolved = Path(env_val).resolve()
            logger.debug(f"Using {env_key}: {resolved}")
            return resolved

        # Use variant-specific path
        return self._root / "variants" / self._variant / "wiki_updated"

    @property
    def reports_dir(self) -> Path:
        """Get reports output directory."""
        return self.data_dir("out/reports")

    # Config files

    @property
    def mapping_file(self) -> Path:
        """Get mapping.json path.

        Returns:
            Path to mapping.json file
        """
        # Check env override
        env_path = os.environ.get("ERENSHOR_MAPPING_FILE")
        if env_path:
            resolved = Path(env_path).resolve()
            logger.debug(f"Using ERENSHOR_MAPPING_FILE: {resolved}")
            return resolved
        return self._root / "mapping.json"

    @property
    def env_file(self) -> Path:
        """Get .env file path.

        Returns:
            Path to .env file
        """
        # Check env override
        env_path = os.environ.get("ERENSHOR_ENV_FILE")
        if env_path:
            resolved = Path(env_path).resolve()
            logger.debug(f"Using ERENSHOR_ENV_FILE: {resolved}")
            return resolved
        return self._root / ".env"

    @property
    def db_path(self) -> Path:
        """Get database path for the configured variant.

        Returns:
            Path to variant-specific database file (e.g., variants/main/erenshor-main.sqlite)
        """
        # Check env override
        env_path = os.environ.get("ERENSHOR_DB_PATH")
        if env_path:
            resolved = Path(env_path).resolve()
            logger.debug(f"Using ERENSHOR_DB_PATH: {resolved}")
            return resolved

        # Use variant config from config.toml
        if self._variant_config:
            db_path_str = self._variant_config.get("database", "")
            if db_path_str:
                return Path(db_path_str)

        # Fallback to old behavior if config not available
        logger.warning(
            f"No database path configured for variant '{self._variant}'. "
            f"Using fallback: {self._root}/erenshor.sqlite"
        )
        return self._root / "erenshor.sqlite"

    @property
    def zones_json(self) -> Path:
        """Get zones.json config file path.

        Returns:
            Path to zones.json in package infrastructure/config/
        """
        return self.package_dir / "infrastructure" / "config" / "zones.json"

    # Utility methods

    def resolve(self, path: str | Path) -> Path:
        """Resolve a path relative to project root.

        Args:
            path: Absolute or relative path

        Returns:
            Resolved absolute path
        """
        p = Path(path)
        if p.is_absolute():
            return p
        return (self._root / p).resolve()

    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self._mode == "development"

    def is_installed(self) -> bool:
        """Check if running in installed mode."""
        return self._mode == "installed"

    def __repr__(self) -> str:
        """Return debug representation."""
        return f"PathResolver(root={self._root!r}, mode={self._mode!r})"


# Singleton instance
_resolver: Optional[PathResolver] = None


def get_path_resolver(
    root: Optional[Path] = None, variant: str = "main"
) -> PathResolver:
    """Get or create PathResolver singleton.

    Args:
        root: Optional explicit root (for testing or override)
        variant: Variant name for variant-specific paths (default: "main")

    Returns:
        PathResolver instance
    """
    global _resolver
    if _resolver is None or root is not None:
        _resolver = PathResolver(root, variant)
    return _resolver
