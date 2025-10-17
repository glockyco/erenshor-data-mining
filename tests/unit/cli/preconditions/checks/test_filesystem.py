"""Tests for filesystem precondition checks."""

import os
from pathlib import Path

import pytest

from erenshor.cli.preconditions.checks.filesystem import directory_exists, directory_writable, file_exists


def test_file_exists_when_file_present(tmp_path: Path):
    """Test file_exists passes when file is present."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    context = {"file_path": test_file}
    result = file_exists(context)

    assert result.passed is True
    assert "exists" in result.message.lower()


def test_file_exists_when_file_missing(tmp_path: Path):
    """Test file_exists fails when file is missing."""
    test_file = tmp_path / "missing.txt"

    context = {"file_path": test_file}
    result = file_exists(context)

    assert result.passed is False
    assert "not found" in result.message.lower()


def test_file_exists_when_path_is_directory(tmp_path: Path):
    """Test file_exists fails when path is a directory."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()

    context = {"file_path": test_dir}
    result = file_exists(context)

    assert result.passed is False
    assert "not a file" in result.message.lower()


def test_file_exists_with_no_path():
    """Test file_exists fails when no path provided."""
    context = {}
    result = file_exists(context)

    assert result.passed is False


def test_directory_exists_when_directory_present(tmp_path: Path):
    """Test directory_exists passes when directory is present."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()

    context = {"directory_path": test_dir}
    result = directory_exists(context)

    assert result.passed is True
    assert "exists" in result.message.lower()


def test_directory_exists_when_directory_missing(tmp_path: Path):
    """Test directory_exists fails when directory is missing."""
    test_dir = tmp_path / "missing_dir"

    context = {"directory_path": test_dir}
    result = directory_exists(context)

    assert result.passed is False
    assert "not found" in result.message.lower()


def test_directory_exists_when_path_is_file(tmp_path: Path):
    """Test directory_exists fails when path is a file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    context = {"directory_path": test_file}
    result = directory_exists(context)

    assert result.passed is False
    assert "not a directory" in result.message.lower()


def test_directory_writable_when_directory_writable(tmp_path: Path):
    """Test directory_writable passes when directory is writable."""
    test_dir = tmp_path / "writable_dir"
    test_dir.mkdir()

    context = {"directory_path": test_dir}
    result = directory_writable(context)

    assert result.passed is True
    assert "writable" in result.message.lower()


def test_directory_writable_when_parent_writable(tmp_path: Path):
    """Test directory_writable passes when directory doesn't exist but parent is writable."""
    test_dir = tmp_path / "new_dir"  # Doesn't exist yet

    context = {"directory_path": test_dir}
    result = directory_writable(context)

    assert result.passed is True
    assert "can create" in result.message.lower()


def test_directory_writable_with_path_is_file(tmp_path: Path):
    """Test directory_writable fails when path is a file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    context = {"directory_path": test_file}
    result = directory_writable(context)

    assert result.passed is False
    assert "not a directory" in result.message.lower()


def test_directory_writable_with_no_path():
    """Test directory_writable fails when no path provided."""
    context = {}
    result = directory_writable(context)

    assert result.passed is False
    assert "no directory path" in result.message.lower()


@pytest.mark.skipif(os.name == "nt", reason="Permission tests unreliable on Windows")
def test_directory_writable_when_read_only(tmp_path: Path):
    """Test directory_writable fails when directory is read-only."""
    test_dir = tmp_path / "readonly_dir"
    test_dir.mkdir()

    # Make directory read-only
    test_dir.chmod(0o444)

    context = {"directory_path": test_dir}
    result = directory_writable(context)

    # Restore permissions for cleanup
    test_dir.chmod(0o755)

    assert result.passed is False
    assert "not writable" in result.message.lower()
