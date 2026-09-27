"""Inputs required before a mod command changes files or game state."""

from __future__ import annotations

from typing import Any

from erenshor.application.mods import local_workflow
from erenshor.application.mods.artifacts import REQUIRED_DLLS
from erenshor.application.mods.catalog import lookup_mod
from erenshor.cli.preconditions.base import PreconditionResult
from erenshor.cli.preconditions.checks.inputs import game_installation
from erenshor.infrastructure.steam.installation import GameInstallationError


def mod_setup_source(context: dict[str, Any]) -> PreconditionResult:
    """Require the installed game's managed assemblies and loader references."""
    try:
        selected = local_workflow.resolve_build_targets(context.get("mod"), context.get("loader", "all"))
        game = local_workflow.get_game_path(context["cli_ctx"])
    except (GameInstallationError, ValueError) as error:
        return PreconditionResult(False, "mod_setup_source", "Cannot resolve mod references", str(error))
    managed = local_workflow.managed_dir(game)
    missing = [managed / name for name in REQUIRED_DLLS if not (managed / name).is_file()]
    for mod_id, loader in selected:
        if loader == "bepinex":
            missing.extend(
                game / "BepInEx/core" / name
                for name in lookup_mod(mod_id).bepinex_dlls
                if not (game / "BepInEx/core" / name).is_file()
            )
    if missing:
        return PreconditionResult(
            False,
            "mod_setup_source",
            "Mod reference assemblies missing",
            "\n".join(str(path) for path in dict.fromkeys(missing)),
        )
    return PreconditionResult(True, "mod_setup_source", f"Managed references: {managed}")


def mod_references(context: dict[str, Any]) -> PreconditionResult:
    """Plan all selected builds before running the first compiler invocation."""
    try:
        local_workflow.plan_builds(context["cli_ctx"], context.get("mod"), loader=context.get("loader", "default"))
    except (OSError, ValueError) as error:
        return PreconditionResult(False, "mod_references", "Cannot build selected mods", str(error))
    return PreconditionResult(True, "mod_references", "Selected mod references available")


def dev_tools_configured(context: dict[str, Any]) -> PreconditionResult:
    """Check the loader and download configuration before writing plugin paths."""
    installation = game_installation(context)
    if not installation.passed:
        return installation
    game = local_workflow.get_game_path(context["cli_ctx"])
    bepinex = game / "BepInEx"
    if not bepinex.is_dir():
        return PreconditionResult(False, "dev_tools_configured", f"BepInEx not installed at {bepinex}")
    if context["config"].global_.bepinex_dev_tools is None:
        return PreconditionResult(False, "dev_tools_configured", "[global.bepinex_dev_tools] not configured")
    return PreconditionResult(True, "dev_tools_configured", "BepInEx development tools configured")


def launch_installation(context: dict[str, Any]) -> PreconditionResult:
    """Recovery and PID inspection do not need an installed game."""
    if context.get("recover") or context.get("inspect_pid") is not None:
        return PreconditionResult(True, "launch_installation", "Session operation needs no game installation")
    return game_installation(context)
