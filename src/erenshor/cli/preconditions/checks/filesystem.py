"""Filesystem precondition checks.

Check functions for file and directory existence and permissions.
These are general-purpose checks that can be parameterized for
different paths.
"""

import os
from pathlib import Path

from ..base import PreconditionResult


def file_exists(context: dict[str, Any]) -> PreconditionResult:
    """Check if a file exists.

    Generic file existence check. Uses 'file_path' from context.

    Args:
        context: Check context containing 'file_path' key.

    Returns:
        PreconditionResult indicating success or failure.
    """
    file_path = Path(context.get("file_path", ""))

    if not file_path or not file_path.exists():
        return PreconditionResult(
            passed=False,
            check_name="file_exists",
            message=f"File not found: {file_path.name if file_path else 'unknown'}",
            detail=f"Missing: {file_path}" if file_path else "No file path provided in context",
        )

    if not file_path.is_file():
        return PreconditionResult(
            passed=False,
            check_name="file_exists",
            message=f"Path is not a file: {file_path.name}",
            detail=f"Expected file, found directory: {file_path}",
        )

    return PreconditionResult(
        passed=True,
        check_name="file_exists",
        message=f"File exists: {file_path.name}",
    )


def directory_exists(context: dict[str, Any]) -> PreconditionResult:
    """Check if a directory exists.

    Generic directory existence check. Uses 'directory_path' from context.

    Args:
        context: Check context containing 'directory_path' key.

    Returns:
        PreconditionResult indicating success or failure.
    """
    dir_path = Path(context.get("directory_path", ""))

    if not dir_path or not dir_path.exists():
        return PreconditionResult(
            passed=False,
            check_name="directory_exists",
            message=f"Directory not found: {dir_path.name if dir_path else 'unknown'}",
            detail=f"Missing: {dir_path}" if dir_path else "No directory path provided in context",
        )

    if not dir_path.is_dir():
        return PreconditionResult(
            passed=False,
            check_name="directory_exists",
            message=f"Path is not a directory: {dir_path.name}",
            detail=f"Expected directory, found file: {dir_path}",
        )

    return PreconditionResult(
        passed=True,
        check_name="directory_exists",
        message=f"Directory exists: {dir_path.name}",
    )


def directory_writable(context: dict[str, Any]) -> PreconditionResult:
    """Check if a directory is writable.

    Checks both that the directory exists and that we have write permissions.
    Uses 'directory_path' from context.

    Args:
        context: Check context containing 'directory_path' key.

    Returns:
        PreconditionResult indicating success or failure.
    """
    dir_path_str = context.get("directory_path", "")

    if not dir_path_str:
        return PreconditionResult(
            passed=False,
            check_name="directory_writable",
            message="No directory path provided",
            detail="Context must contain 'directory_path' key",
        )

    dir_path = Path(dir_path_str)

    if not dir_path.exists():
        # Check if parent is writable (so we can create the directory)
        parent = dir_path.parent
        if not parent.exists():
            return PreconditionResult(
                passed=False,
                check_name="directory_writable",
                message=f"Directory and parent do not exist: {dir_path.name}",
                detail=f"Missing: {dir_path}\nParent also missing: {parent}",
            )

        if not os.access(parent, os.W_OK):
            return PreconditionResult(
                passed=False,
                check_name="directory_writable",
                message=f"Cannot create directory: {dir_path.name}",
                detail=f"No write permission to parent: {parent}",
            )

        return PreconditionResult(
            passed=True,
            check_name="directory_writable",
            message=f"Can create directory: {dir_path.name}",
        )

    if not dir_path.is_dir():
        return PreconditionResult(
            passed=False,
            check_name="directory_writable",
            message=f"Path is not a directory: {dir_path.name}",
            detail=f"Expected directory, found file: {dir_path}",
        )

    if not os.access(dir_path, os.W_OK):
        return PreconditionResult(
            passed=False,
            check_name="directory_writable",
            message=f"Directory not writable: {dir_path.name}",
            detail=f"No write permission: {dir_path}",
        )

    return PreconditionResult(
        passed=True,
        check_name="directory_writable",
        message=f"Directory writable: {dir_path.name}",
    )
