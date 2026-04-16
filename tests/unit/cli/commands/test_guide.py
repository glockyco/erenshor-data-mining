"""Unit tests for guide CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from erenshor.cli.commands import guide

runner = CliRunner()


def test_help_lists_compile() -> None:
    result = runner.invoke(guide.app, ["--help"])

    assert result.exit_code == 0
    assert "compile" in result.stdout
