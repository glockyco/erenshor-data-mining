"""Configuration loader with two-layer TOML override system.

This module implements configuration loading from TOML files with a two-layer
override system:

1. Base layer: config.toml (required, project defaults)
2. Override layer: config.local.toml (optional, user-specific overrides)

The loader performs deep merging of configurations, where local values override
base values at any nesting level. Validation is performed using Pydantic models
to ensure configuration correctness.

Path expansion (e.g., $REPO_ROOT, $HOME) is NOT performed during loading.
Path resolution is handled separately via the resolve_path() function and
property methods on config models.
"""

import tomllib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .schema import Config


class ConfigLoadError(Exception):
    """Raised when configuration loading fails.

    This exception is raised for file access errors, TOML parsing errors,
    or validation errors during configuration loading.
    """

    pass


def _find_repo_root() -> Path:
    """Find repository root by searching for .git directory.

    Searches upward from current working directory until .git directory
    is found or filesystem root is reached.

    Returns:
        Path to repository root directory.

    Raises:
        ConfigLoadError: If repository root cannot be found.
    """
    current = Path.cwd().resolve()

    # Search upward for .git directory
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent

    raise ConfigLoadError(
        "Could not find repository root. " "Make sure you are running from within the Erenshor repository."
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override values taking precedence.

    Merging rules:
    - If key exists only in base: use base value
    - If key exists only in override: use override value
    - If key exists in both:
        - Primitive types (str, int, bool, etc.): override wins
        - Dicts: recursively merge
        - Lists: override replaces base entirely
        - None in override: treated as override value (replaces base)

    Args:
        base: Base dictionary (typically from config.toml).
        override: Override dictionary (typically from config.local.toml).

    Returns:
        New dictionary with merged values. Original dicts are not modified.

    Example:
        >>> base = {"a": 1, "b": {"x": 1, "y": 2}}
        >>> override = {"b": {"x": 10}, "c": 3}
        >>> _deep_merge(base, override)
        {"a": 1, "b": {"x": 10, "y": 2}, "c": 3}
    """
    result = base.copy()

    for key, override_value in override.items():
        if key not in result:
            # Key only in override: use override value
            result[key] = override_value
        else:
            base_value = result[key]

            # Both values are dicts: recursively merge
            if isinstance(base_value, dict) and isinstance(override_value, dict):
                result[key] = _deep_merge(base_value, override_value)
            else:
                # Primitive, list, or type mismatch: override wins
                result[key] = override_value

    return result


def get_repo_root() -> Path:
    """Get repository root directory.

    Searches upward from current working directory until .git directory
    is found. This is the same logic used by load_config().

    Returns:
        Path to repository root directory.

    Raises:
        ConfigLoadError: If repository root cannot be found.

    Example:
        >>> repo_root = get_repo_root()
        >>> print(repo_root)
        /Users/joe/Projects/Erenshor
    """
    return _find_repo_root()


def load_config() -> Config:
    """Load and validate configuration from TOML files.

    Loads configuration using a two-layer system:
    1. config.toml (required): Project defaults from repository
    2. config.local.toml (optional): User-specific overrides

    The loader performs deep merging where local values override base values
    at any nesting level. The merged configuration is validated against the
    Pydantic schema before being returned.

    Returns:
        Validated Config instance with merged configuration.

    Raises:
        ConfigLoadError: If configuration cannot be loaded or validated.
            Common causes:
            - Repository root not found
            - config.toml is missing
            - TOML syntax errors in config files
            - Configuration values fail validation

    Example:
        >>> config = load_config()
        >>> print(config.default_variant)
        main
        >>> print(config.global_.unity.version)
        2021.3.45f2
    """
    # Find repository root
    try:
        repo_root = _find_repo_root()
    except ConfigLoadError as e:
        raise ConfigLoadError(f"Failed to find repository root: {e}") from e

    # Define config file paths
    base_config_path = repo_root / "config.toml"
    local_config_path = repo_root / "config.local.toml"

    # Load base configuration (required)
    if not base_config_path.exists():
        raise ConfigLoadError(
            f"Base configuration file not found: {base_config_path}\n"
            f"Expected config.toml in repository root: {repo_root}\n"
            f"This file is required and should be committed to version control."
        )

    try:
        with base_config_path.open("rb") as f:
            base_config = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigLoadError(
            f"Invalid TOML syntax in {base_config_path}:\n{e}\n" f"Fix the syntax error and try again."
        ) from e
    except OSError as e:
        raise ConfigLoadError(f"Failed to read {base_config_path}: {e}") from e

    # Load local configuration (optional)
    config_data = base_config
    if local_config_path.exists():
        try:
            with local_config_path.open("rb") as f:
                local_config = tomllib.load(f)

            # Deep merge: local overrides base
            config_data = _deep_merge(base_config, local_config)

        except tomllib.TOMLDecodeError as e:
            raise ConfigLoadError(
                f"Invalid TOML syntax in {local_config_path}:\n{e}\n" f"Fix the syntax error and try again."
            ) from e
        except OSError as e:
            raise ConfigLoadError(f"Failed to read {local_config_path}: {e}") from e

    # Validate with Pydantic schema
    try:
        config = Config.model_validate(config_data)
    except ValidationError as e:
        # Format validation errors for clarity
        error_messages = []
        for error in e.errors():
            location = " -> ".join(str(loc) for loc in error["loc"])
            message = error["msg"]
            error_messages.append(f"  {location}: {message}")

        raise ConfigLoadError(
            "Configuration validation failed:\n" + "\n".join(error_messages) + "\n"
            f"Check your configuration files:\n"
            f"  Base: {base_config_path}\n"
            f"  Local: {local_config_path if local_config_path.exists() else '(not present)'}"
        ) from e

    return config
