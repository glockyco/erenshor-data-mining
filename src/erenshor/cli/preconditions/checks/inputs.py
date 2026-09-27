"""Preflight checks for command inputs and external tools."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Literal

from erenshor.cli.preconditions.base import PreconditionCheck, PreconditionResult


def required_path(key: str, relative: str = "", *, kind: Literal["file", "directory"] = "file") -> PreconditionCheck:
    """Require a file or directory resolved from the CLI context."""

    def check(context: dict[str, Any]) -> PreconditionResult:
        path = Path(context[key]) / relative
        try:
            present = path.is_file() if kind == "file" else path.is_dir()
        except OSError as error:
            return PreconditionResult(False, f"required_{key}", f"Cannot inspect {path}", str(error))
        if not present:
            return PreconditionResult(False, f"required_{key}", f"Required {kind} not found: {path}")
        return PreconditionResult(True, f"required_{key}", f"Required {kind} exists: {path}")

    check.__name__ = f"required_{key}"
    return check


def program_available(program: str, *, extra_dirs: tuple[Path, ...] = ()) -> PreconditionCheck:
    """Require a named executable before starting external work."""

    def check(context: dict[str, Any]) -> PreconditionResult:
        if shutil.which(program) is None and not any((directory / program).is_file() for directory in extra_dirs):
            return PreconditionResult(
                False,
                f"program_{program}",
                f"{program} not found on PATH",
                f"Install {program} in the Nix development shell or add its tool directory to PATH.",
            )
        return PreconditionResult(True, f"program_{program}", f"{program} is available")

    check.__name__ = f"program_{program}"
    return check


def wiki_credentials(context: dict[str, Any]) -> PreconditionResult:
    """Require bot credentials before wiki writes, except for image dry runs."""
    config = context["config"].global_.mediawiki
    if context.get("dry_run") or (config.bot_username and config.bot_password):
        return PreconditionResult(True, "wiki_credentials", "Wiki credentials available")
    return PreconditionResult(
        False,
        "wiki_credentials",
        "MediaWiki bot credentials not configured",
        "Configure bot_username and bot_password in the local configuration.",
    )


def game_installation(context: dict[str, Any]) -> PreconditionResult:
    """Resolve the selected variant's runnable installation without changing it."""
    from erenshor.application.mods.local_workflow import GameInstallationError, get_game_path

    try:
        game_path = get_game_path(context["cli_ctx"])
    except GameInstallationError as error:
        return PreconditionResult(False, "game_installation", "Cannot resolve game installation", str(error))
    if game_path is None:
        return PreconditionResult(
            False,
            "game_installation",
            f"Game installation not found for {context['variant']}",
            "Install the selected Steam app or set [variants.<name>] game_install.",
        )
    return PreconditionResult(True, "game_installation", f"Game installation: {game_path}")
