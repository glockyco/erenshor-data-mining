"""Tests for Unity precondition checks."""

from pathlib import Path
from unittest.mock import Mock

from erenshor.cli.preconditions.checks.unity import editor_scripts_linked, unity_project_exists, unity_version_matches


def test_unity_project_exists_with_valid_project(tmp_path: Path):
    """Test unity_project_exists passes with valid Unity project."""
    unity_dir = tmp_path / "Unity"
    unity_dir.mkdir()
    exported_project = unity_dir / "ExportedProject"
    exported_project.mkdir()
    (exported_project / "Assets").mkdir()
    (exported_project / "ProjectSettings").mkdir()

    context = {"unity_project": unity_dir}
    result = unity_project_exists(context)

    assert result.passed is True
    assert "valid" in result.message.lower()


def test_unity_project_exists_when_directory_missing(tmp_path: Path):
    """Test unity_project_exists fails when directory doesn't exist."""
    unity_dir = tmp_path / "nonexistent"

    context = {"unity_project": unity_dir}
    result = unity_project_exists(context)

    assert result.passed is False
    assert "not found" in result.message.lower()


def test_unity_project_exists_without_assets(tmp_path: Path):
    """Test unity_project_exists fails without Assets directory."""
    unity_dir = tmp_path / "Unity"
    unity_dir.mkdir()
    exported_project = unity_dir / "ExportedProject"
    exported_project.mkdir()
    (exported_project / "ProjectSettings").mkdir()

    context = {"unity_project": unity_dir}
    result = unity_project_exists(context)

    assert result.passed is False
    assert "no assets" in result.message.lower()


def test_unity_project_exists_without_project_settings(tmp_path: Path):
    """Test unity_project_exists fails without ProjectSettings directory."""
    unity_dir = tmp_path / "Unity"
    unity_dir.mkdir()
    exported_project = unity_dir / "ExportedProject"
    exported_project.mkdir()
    (exported_project / "Assets").mkdir()

    context = {"unity_project": unity_dir}
    result = unity_project_exists(context)

    assert result.passed is False
    assert "no projectsettings" in result.message.lower()


def test_unity_project_exists_when_path_is_file(tmp_path: Path):
    """Test unity_project_exists fails when path is a file."""
    test_file = tmp_path / "notadir.txt"
    test_file.write_text("content")

    context = {"unity_project": test_file}
    result = unity_project_exists(context)

    assert result.passed is False
    assert "not a directory" in result.message.lower()


def test_editor_scripts_linked_with_valid_symlink(tmp_path: Path):
    """Test editor_scripts_linked passes with valid symlink."""
    repo_root = tmp_path / "repo"
    unity_dir = tmp_path / "unity"

    # Create source directory
    source_editor = repo_root / "src" / "Assets" / "Editor"
    source_editor.mkdir(parents=True)
    (source_editor / "test.cs").write_text("// test")

    # Create Unity project with ExportedProject subdirectory
    exported_project = unity_dir / "ExportedProject"
    (exported_project / "Assets").mkdir(parents=True)
    editor_link = exported_project / "Assets" / "Editor"
    editor_link.symlink_to(source_editor)

    context = {
        "unity_project": unity_dir,
        "repo_root": repo_root,
    }
    result = editor_scripts_linked(context)

    assert result.passed is True
    assert "linked" in result.message.lower()


def test_editor_scripts_linked_when_missing(tmp_path: Path):
    """Test editor_scripts_linked fails when symlink doesn't exist."""
    repo_root = tmp_path / "repo"
    unity_dir = tmp_path / "unity"
    exported_project = unity_dir / "ExportedProject"
    (exported_project / "Assets").mkdir(parents=True)

    context = {
        "unity_project": unity_dir,
        "repo_root": repo_root,
    }
    result = editor_scripts_linked(context)

    assert result.passed is False
    assert "not linked" in result.message.lower()


def test_editor_scripts_linked_when_not_symlink(tmp_path: Path):
    """Test editor_scripts_linked fails when Editor is regular directory."""
    repo_root = tmp_path / "repo"
    unity_dir = tmp_path / "unity"

    # Create regular directory instead of symlink
    exported_project = unity_dir / "ExportedProject"
    editor_dir = exported_project / "Assets" / "Editor"
    editor_dir.mkdir(parents=True)

    context = {
        "unity_project": unity_dir,
        "repo_root": repo_root,
    }
    result = editor_scripts_linked(context)

    assert result.passed is False
    assert "not a symlink" in result.message.lower()


def test_editor_scripts_linked_when_wrong_target(tmp_path: Path):
    """Test editor_scripts_linked fails when symlink points to wrong location."""
    repo_root = tmp_path / "repo"
    unity_dir = tmp_path / "unity"

    # Create source directory
    source_editor = repo_root / "src" / "Assets" / "Editor"
    source_editor.mkdir(parents=True)

    # Create wrong target
    wrong_target = tmp_path / "wrong"
    wrong_target.mkdir()

    # Create symlink pointing to wrong location
    exported_project = unity_dir / "ExportedProject"
    (exported_project / "Assets").mkdir(parents=True)
    editor_link = exported_project / "Assets" / "Editor"
    editor_link.symlink_to(wrong_target)

    context = {
        "unity_project": unity_dir,
        "repo_root": repo_root,
    }
    result = editor_scripts_linked(context)

    assert result.passed is False
    assert "wrong location" in result.message.lower()


def test_unity_version_matches_with_correct_version(tmp_path: Path):
    """Test unity_version_matches passes when version is in path."""
    unity_path = tmp_path / "Unity" / "Hub" / "Editor" / "2021.3.45f2" / "Unity"
    unity_path.parent.mkdir(parents=True)
    unity_path.write_text("unity")

    unity_config = Mock()
    unity_config.version = "2021.3.45f2"
    unity_config.resolved_path.return_value = unity_path

    global_config = Mock()
    global_config.unity = unity_config

    config = Mock()
    config.global_ = global_config

    context = {
        "config": config,
        "repo_root": tmp_path,
    }
    result = unity_version_matches(context)

    assert result.passed is True
    assert "2021.3.45f2" in result.message


def test_unity_version_matches_when_unity_missing(tmp_path: Path):
    """Test unity_version_matches fails when Unity not found."""
    unity_path = tmp_path / "nonexistent" / "Unity"

    unity_config = Mock()
    unity_config.version = "2021.3.45f2"
    unity_config.resolved_path.return_value = unity_path

    global_config = Mock()
    global_config.unity = unity_config

    config = Mock()
    config.global_ = global_config

    context = {
        "config": config,
        "repo_root": tmp_path,
    }
    result = unity_version_matches(context)

    assert result.passed is False
    assert "not found" in result.message.lower()


def test_unity_version_matches_with_wrong_version(tmp_path: Path):
    """Test unity_version_matches fails when version doesn't match."""
    # Unity path with different version
    unity_path = tmp_path / "Unity" / "2020.1.0f1" / "Unity"
    unity_path.parent.mkdir(parents=True)
    unity_path.write_text("unity")

    unity_config = Mock()
    unity_config.version = "2021.3.45f2"  # Expected version
    unity_config.resolved_path.return_value = unity_path

    global_config = Mock()
    global_config.unity = unity_config

    config = Mock()
    config.global_ = global_config

    context = {
        "config": config,
        "repo_root": tmp_path,
    }
    result = unity_version_matches(context)

    assert result.passed is False
    assert "mismatch" in result.message.lower()
