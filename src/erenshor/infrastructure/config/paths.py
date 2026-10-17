"""Path resolution with variable expansion.

This module provides path resolution functionality for configuration values.
It supports expansion of special variables:
- $REPO_ROOT: Repository root directory
- $HOME: User's home directory
- ~: User's home directory (shell shorthand)

All resolved paths are returned as pathlib.Path objects for type safety.
"""

from pathlib import Path


class PathResolutionError(Exception):
    """Raised when path resolution fails.

    This can occur when:
    - A required path does not exist (when validation is enabled)
    - Path expansion results in invalid path
    """

    pass


def resolve_path(path: str, repo_root: Path, validate: bool = False) -> Path:
    """Resolve path with variable expansion to absolute Path object.

    Expands special variables and converts to absolute path:
    - $REPO_ROOT: Replaced with repository root directory
    - $HOME: Replaced with user's home directory
    - ~: Replaced with user's home directory (shell shorthand)

    Args:
        path: Path string potentially containing variables.
        repo_root: Repository root directory for $REPO_ROOT expansion.
        validate: If True, verify that the resolved path exists.

    Returns:
        Absolute Path object with variables expanded.

    Raises:
        PathResolutionError: If validation is enabled and path does not exist.

    Examples:
        >>> repo = Path("/Users/joe/Projects/Erenshor")
        >>> resolve_path("$REPO_ROOT/variants/main", repo)
        PosixPath('/Users/joe/Projects/Erenshor/variants/main')

        >>> resolve_path("$HOME/.config/erenshor", repo)
        PosixPath('/Users/joe/.config/erenshor')

        >>> resolve_path("~/Documents/erenshor", repo)
        PosixPath('/Users/joe/Documents/erenshor')

        >>> resolve_path("variants/main", repo)
        PosixPath('/Users/joe/Projects/Erenshor/variants/main')
    """
    # Start with original path
    resolved = path

    # Expand $REPO_ROOT
    if "$REPO_ROOT" in resolved:
        resolved = resolved.replace("$REPO_ROOT", str(repo_root))

    # Expand $HOME
    if "$HOME" in resolved:
        resolved = resolved.replace("$HOME", str(Path.home()))

    # Convert to Path object first
    resolved_path = Path(resolved)

    # Expand ~ (shell shorthand for home directory)
    # Path.expanduser() handles ~ expansion properly
    resolved_path = resolved_path.expanduser()

    # Make absolute if not already
    if not resolved_path.is_absolute():
        # Relative paths are relative to repo root
        resolved_path = repo_root / resolved_path

    # Validate existence if requested
    if validate and not resolved_path.exists():
        raise PathResolutionError(
            f"Path does not exist: {resolved_path}\n"
            f"Original path: {path}\n"
            f"Ensure the path is correct and the file/directory exists."
        )

    return resolved_path


def checkout_root(path: Path) -> Path | None:
    """Find the checkout containing a path, including Git worktree files."""
    resolved = path.resolve()
    return next((parent for parent in (resolved, *resolved.parents) if (parent / ".git").exists()), None)


def require_owned_write_path(path: Path, repo_root: Path) -> None:
    """Reject output paths that resolve into a different checkout.

    Explicit output locations outside Git checkouts remain valid. Both the
    target and its parent matter because atomic publication replaces the
    directory entry rather than following a final file symlink.
    """
    expected_root = repo_root.resolve()
    for destination in (path, path.parent):
        owner = checkout_root(destination)
        if owner is not None and owner != expected_root:
            raise PathResolutionError(
                f"Refusing cross-checkout write: {path} resolves into {owner}, "
                f"not {expected_root}. Use a worktree-owned output path in "
                ".erenshor/config.local.toml. On macOS, clone SQLite files with "
                "/bin/cp -c instead of symlinking them. Shared inputs may remain symlinks."
            )
