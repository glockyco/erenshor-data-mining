import hashlib
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "InteractiveMapCompanion"
VAULT_ROOT = MOD_ROOT / "vault"


def _vault_config() -> dict[str, Any]:
    return tomllib.loads((VAULT_ROOT / "vault.toml").read_text())


def test_interactive_map_companion_vault_listing_is_complete() -> None:
    config = _vault_config()
    mod = config["mod"]
    assets = config["assets"]

    assert isinstance(mod, dict)
    assert mod["mod_ref"] == "interactive-map-companion"
    assert mod["name"] == "Interactive Map Companion"
    assert set(mod["tags"]) <= {"gameplay", "quality-of-life", "ui", "utility"}
    assert isinstance(assets, dict)
    for asset in ("full_description", "changelog", "icon"):
        assert (VAULT_ROOT / assets[asset]).is_file()


def test_interactive_map_companion_vault_ships_one_native_plugin() -> None:
    package = _vault_config()["package"]

    assert isinstance(package, dict)
    assert package["main_file"] == "InteractiveMapCompanion.dll"
    assert package["asset_files"] == []
    assert (
        "<AssemblyName>InteractiveMapCompanion</AssemblyName>"
        in (MOD_ROOT / "InteractiveMapCompanion.csproj").read_text()
    )


def test_vault_reuses_the_published_map_icon() -> None:
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    assert digest(VAULT_ROOT / "icon.png") == digest(MOD_ROOT / "thunderstore" / "icon.png")
