"""Typed immutable catalog for maintained companion mods.

The catalog is application-owned so verification, build, deployment, and release
commands all consume the same ordered definitions without sharing mutable CLI
state.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from erenshor.application.mods.artifacts import ModArtifactSpec

LoaderName = Literal["bepinex", "lunaris"]


@dataclass(frozen=True, slots=True)
class ModDefinition:
    """Immutable build and distribution metadata for one maintained mod."""

    mod_id: str
    directory: Path
    display_name: str
    dll_name: str
    loaders: tuple[LoaderName, ...]
    default_loader: LoaderName
    public: bool
    thunderstore_id: str | None = None
    thunderstore_files: tuple[str, ...] = ()
    bepinex_dlls: tuple[str, ...] = ()
    lunaris_dlls: tuple[str, ...] = ()
    vault_mod_ref: str | None = None

    def artifact_spec(self) -> ModArtifactSpec:
        """Return the artifact-verifier view of this definition."""
        return ModArtifactSpec(
            mod_id=self.mod_id,
            directory=self.directory,
            display_name=self.display_name,
            dll_name=self.dll_name,
            loaders=self.loaders,
            public=self.public,
            thunderstore_id=self.thunderstore_id,
            thunderstore_files=self.thunderstore_files,
        )


# Keep this order stable.  Build, deploy, release, and verification output use it.
_MOD_DEFINITIONS: tuple[ModDefinition, ...] = (
    ModDefinition(
        mod_id="interactive-map-companion",
        directory=Path("src/mods/InteractiveMapCompanion"),
        display_name="Interactive Map Companion",
        dll_name="InteractiveMapCompanion.dll",
        loaders=("bepinex", "lunaris"),
        default_loader="bepinex",
        public=True,
        thunderstore_id="WoW_Much/InteractiveMapCompanion",
        thunderstore_files=("InteractiveMapCompanion.dll",),
        # Harmony ships with BepInEx, not with the game — copy from BepInEx/core/
        bepinex_dlls=("0Harmony.dll",),
        lunaris_dlls=("Newtonsoft.Json.dll", "0Harmony.dll"),
        vault_mod_ref="interactive-map-companion",
    ),
    ModDefinition(
        mod_id="justice-for-f7",
        directory=Path("src/mods/JusticeForF7"),
        display_name="Justice for F7",
        dll_name="JusticeForF7.dll",
        loaders=("bepinex", "lunaris"),
        default_loader="lunaris",
        public=True,
        thunderstore_id="WoW_Much/JusticeForF7",
        thunderstore_files=("JusticeForF7.dll",),
        lunaris_dlls=("0Harmony.dll",),
        vault_mod_ref="justice-for-f7",
    ),
    ModDefinition(
        mod_id="sprint",
        directory=Path("src/mods/Sprint"),
        display_name="Sprint",
        dll_name="Sprint.dll",
        loaders=("bepinex", "lunaris"),
        default_loader="lunaris",
        public=True,
        thunderstore_id="WoW_Much/Sprint",
        thunderstore_files=("Sprint.dll",),
        lunaris_dlls=("0Harmony.dll",),
        vault_mod_ref="sprint",
    ),
    ModDefinition(
        mod_id="map-tile-capture",
        directory=Path("src/mods/MapTileCapture"),
        display_name="Map Tile Capture",
        dll_name="MapTileCapture.dll",
        loaders=("bepinex", "lunaris"),
        default_loader="bepinex",
        public=False,
        bepinex_dlls=("0Harmony.dll",),
        lunaris_dlls=("Newtonsoft.Json.dll", "0Harmony.dll"),
    ),
    ModDefinition(
        mod_id="adventure-guide",
        directory=Path("src/mods/AdventureGuide"),
        display_name="Adventure Guide",
        dll_name="AdventureGuide.dll",
        loaders=("bepinex", "lunaris"),
        default_loader="lunaris",
        public=True,
        thunderstore_id="WoW_Much/AdventureGuide",
        thunderstore_files=(
            "AdventureGuide.dll",
            "ImGui.NET.dll",
            "Newtonsoft.Json.dll",
            "System.Numerics.Vectors.dll",
            "System.Runtime.CompilerServices.Unsafe.dll",
            "cimgui.dll",
        ),
        bepinex_dlls=("0Harmony.dll",),
        lunaris_dlls=(
            "ImGui.NET.dll",
            "Newtonsoft.Json.dll",
            "System.Numerics.Vectors.dll",
            "0Harmony.dll",
        ),
        vault_mod_ref="adventure-guide",
    ),
)

_EXPECTED_MOD_IDS = (
    "interactive-map-companion",
    "justice-for-f7",
    "sprint",
    "map-tile-capture",
    "adventure-guide",
)
if tuple(definition.mod_id for definition in _MOD_DEFINITIONS) != _EXPECTED_MOD_IDS:
    raise ValueError("Maintained mod catalog inventory or order changed")

_BY_ID = MappingProxyType({definition.mod_id: definition for definition in _MOD_DEFINITIONS})
if len(_BY_ID) != len(_MOD_DEFINITIONS):
    raise ValueError("Duplicate mod id in maintained mod catalog")
if any(definition.default_loader not in definition.loaders for definition in _MOD_DEFINITIONS):
    raise ValueError("Mod default loader must be one of its supported loaders")


def lookup_mod(mod_id: str) -> ModDefinition:
    """Look up one maintained mod by stable id."""
    return _BY_ID[mod_id]


def iter_mods() -> Iterator[ModDefinition]:
    """Iterate all maintained mods in their declared order."""
    return iter(_MOD_DEFINITIONS)


def public_mods() -> tuple[ModDefinition, ...]:
    """Select public maintained mods in their declared order."""
    return tuple(definition for definition in _MOD_DEFINITIONS if definition.public)


def artifact_specs() -> tuple[ModArtifactSpec, ...]:
    """Return artifact specifications for all maintained mods in order."""
    return tuple(definition.artifact_spec() for definition in _MOD_DEFINITIONS)


__all__ = [
    "LoaderName",
    "ModDefinition",
    "artifact_specs",
    "iter_mods",
    "lookup_mod",
    "public_mods",
]
