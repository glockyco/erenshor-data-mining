"""Unit tests for guide CLI commands."""

from __future__ import annotations

from typer.main import get_command

from erenshor.cli.commands import guide


def test_guide_app_registers_commands() -> None:
    command = get_command(guide.app)

    assert set(command.commands) == {"compile", "export-mod"}
