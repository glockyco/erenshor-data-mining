"""Find a variant's game files in the CrossOver Steam client installation.

The Steam client inside a CrossOver bottle installs and updates every variant.
Each installed app has ``<library>/steamapps/appmanifest_<app_id>.acf`` and its
files under ``<library>/steamapps/common/<installdir>``. The app id in the
manifest name is the only key: no path is configured per machine.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

CROSSOVER_BOTTLES_ROOT = Path.home() / "Library/Application Support/CrossOver/Bottles"
STEAM_LIBRARY = Path("drive_c/Program Files (x86)/Steam/steamapps")


class GameInstallationError(ValueError):
    """Raised when a variant's installation is absent, ambiguous, or unusable."""


@dataclass(frozen=True, slots=True)
class GameInstallation:
    """One Steam client installation of a variant."""

    path: Path
    manifest: Path
    bottle: str

    @property
    def managed_dir(self) -> Path:
        return self.path / "Erenshor_Data" / "Managed"


def read_manifest_fields(manifest: Path, keys: set[str]) -> dict[str, str]:
    """Read quoted scalar fields at any depth of a Steam app manifest.

    Raises:
        GameInstallationError: If the manifest cannot be read.
    """
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise GameInstallationError(f"Cannot read Steam app manifest {manifest}: {error}") from error
    found: dict[str, str] = {}
    for line in lines:
        parts = line.split('"')
        if len(parts) >= 4 and parts[1] in keys and parts[1] not in found:
            found[parts[1]] = parts[3]
    return found


def find_game_installation(variant: str, app_id: str) -> GameInstallation:
    """Return the CrossOver Steam installation of ``variant``.

    ``CROSSOVER_BOTTLE`` limits the search to one bottle.

    Raises:
        GameInstallationError: If no bottle has the app, several bottles have
            it, a manifest cannot be read or has no installdir, or the
            installation lacks its managed assembly directory. Each condition
            has its own message because each has a different fix.
    """
    if sys.platform != "darwin":
        raise GameInstallationError(
            f"Variant {variant!r} (Steam app {app_id}) is found only in a CrossOver Steam bottle on macOS, "
            f"and this platform is {sys.platform}."
        )
    bottle_name = os.environ.get("CROSSOVER_BOTTLE")
    if bottle_name:
        bottle_dirs = [CROSSOVER_BOTTLES_ROOT / bottle_name]
    elif CROSSOVER_BOTTLES_ROOT.is_dir():
        bottle_dirs = sorted(path for path in CROSSOVER_BOTTLES_ROOT.iterdir() if path.is_dir())
    else:
        bottle_dirs = []

    matches: list[GameInstallation] = []
    unusable: list[str] = []
    for bottle_dir in bottle_dirs:
        steamapps = bottle_dir / STEAM_LIBRARY
        manifest = steamapps / f"appmanifest_{app_id}.acf"
        if not manifest.is_file():
            continue
        install_dir = read_manifest_fields(manifest, {"installdir"}).get("installdir")
        if not install_dir:
            raise GameInstallationError(f"Steam app manifest has no installdir: {manifest}")
        installation = GameInstallation(steamapps / "common" / install_dir, manifest, bottle_dir.name)
        if installation.managed_dir.is_dir():
            matches.append(installation)
        else:
            unusable.append(f"{installation.path} (missing {installation.managed_dir})")

    if len(matches) > 1:
        joined = "\n  ".join(str(match.path) for match in matches)
        raise GameInstallationError(
            f"Variant {variant!r} (Steam app {app_id}) is installed in several CrossOver bottles:\n  {joined}\n"
            "Set CROSSOVER_BOTTLE to the bottle to use."
        )
    if matches:
        return matches[0]
    if unusable:
        joined = "\n  ".join(unusable)
        raise GameInstallationError(
            f"Variant {variant!r} (Steam app {app_id}) has an installation without its managed assemblies:\n"
            f"  {joined}\nVerify the game files in the Steam client."
        )
    searched = ", ".join(str(path) for path in bottle_dirs) or str(CROSSOVER_BOTTLES_ROOT)
    raise GameInstallationError(
        f"Variant {variant!r} (Steam app {app_id}) is not installed in a CrossOver Steam bottle "
        f"(searched {searched}). Install it through the Steam client in the bottle."
    )
