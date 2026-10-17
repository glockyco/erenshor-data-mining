from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from erenshor.cli.preconditions.checks.extract import clean_build_outputs

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext


@pytest.mark.parametrize("setting", ["database", "profiles", "images_output", "backups"])
def test_clean_build_rejects_each_cross_checkout_output(cli_context: CLIContext, tmp_path: Path, setting: str) -> None:
    cli_context.repo_root = tmp_path
    (tmp_path / ".git").write_text("gitdir: /main/.git/worktrees/test")
    owner = tmp_path / "other-checkout"
    owner.mkdir()
    (owner / ".git").mkdir()
    variant = cli_context.config.variants["main"]
    if setting == "profiles":
        (tmp_path / "profiles").symlink_to(owner / "profiles", target_is_directory=True)
    else:
        cli_context.config.variants["main"] = variant.model_copy(update={setting: str(owner / setting)})
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))

    result = clean_build_outputs({"config": cli_context.config, "variant": "main", "repo_root": tmp_path})

    assert not result.passed
    assert setting in result.message
    assert "Refusing cross-checkout write" in (result.detail or "")
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*")) == before


def test_clean_build_accepts_owned_outputs_and_shared_read_inputs(cli_context: CLIContext, tmp_path: Path) -> None:
    cli_context.repo_root = tmp_path
    (tmp_path / ".git").mkdir()
    owner = tmp_path / "other-checkout"
    owner.mkdir()
    (owner / ".git").mkdir()
    variant = cli_context.config.variants["main"]
    cli_context.config.variants["main"] = variant.model_copy(
        update={
            "unity_project": str(owner / "unity"),
            "wiki": str(owner / "wiki"),
            "database_raw": str(owner / "raw.sqlite"),
        }
    )

    result = clean_build_outputs({"config": cli_context.config, "variant": "main", "repo_root": tmp_path})

    assert result.passed
