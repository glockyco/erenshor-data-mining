"""Unit tests for guide CLI commands."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
import typer

from erenshor.cli.commands import guide

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext


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
