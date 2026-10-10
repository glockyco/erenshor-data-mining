"""Unit tests for guide CLI commands."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
import typer
from typer.main import get_command

from erenshor.cli.commands import guide

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext


def test_guide_app_registers_commands() -> None:
    command = get_command(guide.app)

    assert set(command.commands) == {"compile", "export-mod"}


def test_compile_rejects_missing_database_before_writing_guide(
    cli_context: CLIContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = cli_context.config.variants[cli_context.variant].resolved_database(cli_context.repo_root)
    db_path.unlink()
    output = tmp_path / "guide.json"
    monkeypatch.setattr(
        "erenshor.application.guide.generator.generate",
        Mock(side_effect=AssertionError("compiled without database")),
    )

    with pytest.raises(typer.Exit) as error:
        guide.compile(SimpleNamespace(obj=cli_context), output=output, overrides=None)

    assert error.value.exit_code == 1
    assert db_path.name in capsys.readouterr().out.replace("\n", "")
    assert not output.exists()


def test_export_mod_rejects_missing_override_before_writing(
    cli_context: CLIContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    overrides = tmp_path / "missing-overrides.toml"
    output = tmp_path / "quest-guide.json"
    monkeypatch.setattr(
        "erenshor.application.guide.generator.generate",
        Mock(side_effect=AssertionError("read absent overrides")),
    )

    with pytest.raises(typer.Exit) as error:
        guide.export_mod(SimpleNamespace(obj=cli_context), output=output, overrides=overrides)

    assert error.value.exit_code == 1
    assert overrides.name in capsys.readouterr().out.replace("\n", "")
    assert not output.exists()
