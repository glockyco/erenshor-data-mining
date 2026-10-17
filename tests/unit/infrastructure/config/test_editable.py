"""Exercise the Nix editable hook without changing an interpreter installation."""

import runpy
import sys
from pathlib import Path

import pytest


@pytest.fixture
def install():
    return runpy.run_path(str(Path(__file__).resolve().parents[4] / "nix/editable.py"))["install"]


@pytest.mark.parametrize("git_marker", ["directory", "file"])
def test_editable_prefers_current_checkout_over_inherited_shell(
    tmp_path: Path, monkeypatch, install, git_marker: str
) -> None:
    root = tmp_path / "worktree"
    package = root / "src/erenshor"
    package.mkdir(parents=True)
    (package / "__init__.py").touch()
    if git_marker == "directory":
        (root / ".git").mkdir()
    else:
        (root / ".git").write_text("gitdir: ../main/.git/worktrees/test")
    nested = root / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    monkeypatch.setenv("REPO_ROOT", str(tmp_path / "main"))
    monkeypatch.setattr(sys, "path", [])

    install()

    assert sys.path == [str(root.resolve() / "src")]


def test_editable_outside_checkout_uses_validated_shell_root(tmp_path: Path, monkeypatch, install) -> None:
    root = tmp_path / "shell-checkout"
    package = root / "src/erenshor"
    package.mkdir(parents=True)
    (package / "__init__.py").touch()
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / ".git").mkdir()
    monkeypatch.chdir(unrelated)
    monkeypatch.setenv("REPO_ROOT", str(root))
    monkeypatch.setattr(sys, "path", [])

    install()

    assert sys.path == [str(root / "src")]


def test_editable_ignores_invalid_shell_root(tmp_path: Path, monkeypatch, install) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REPO_ROOT", str(tmp_path / "missing"))
    monkeypatch.setattr(sys, "path", [])

    install()

    assert sys.path == []
