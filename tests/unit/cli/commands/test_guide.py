"""Unit tests for guide CLI commands."""

from __future__ import annotations

from typer.main import get_command

from erenshor.cli.commands import guide


def test_guide_app_registers_compile_command() -> None:
    command = get_command(guide.app)

    assert command.name == "compile"
