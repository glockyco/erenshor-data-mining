import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "JusticeForF7"
VAULT_ROOT = MOD_ROOT / "vault"

# Tag slugs returned by GET https://erenshorvault.app/api/tags.
KNOWN_VAULT_TAGS = {
    "audio",
    "automation",
    "gameplay",
    "graphics",
    "library",
    "performance",
    "quality-of-life",
    "social",
    "ui",
    "utility",
}


def _vault_config() -> dict[str, Any]:
    return tomllib.loads((VAULT_ROOT / "vault.toml").read_text())


def test_thunderstore_packaging_declared_for_justice_for_f7() -> None:
    manifest = tomllib.loads((MOD_ROOT / "thunderstore.toml").read_text())

    assert manifest["package"]["namespace"] == "WoW_Much"
    assert manifest["package"]["name"] == "JusticeForF7"
    assert manifest["package"]["dependencies"]["BepInEx-BepInExPack"] == "5.4.2304"
    assert manifest["build"]["icon"] == "./vault/icon.png"
    assert not (MOD_ROOT / "thunderstore" / "icon.png").exists()
    assert manifest["build"]["readme"] == "./thunderstore/README.md"
    assert manifest["build"]["outdir"] == "./thunderstore/build"
    assert manifest["build"]["changelog"] == "./thunderstore/CHANGELOG.md"

    copies = manifest["build"]["copy"]
    assert copies == [
        {
            "source": "./bin/Debug/netstandard2.1/bepinex/JusticeForF7.dll",
            "target": "plugins/JusticeForF7/",
        }
    ]
    assert (MOD_ROOT / "thunderstore" / "README.md").exists()
    assert (MOD_ROOT / "thunderstore" / "CHANGELOG.md").exists()


def test_justice_for_f7_declares_dual_loader_support() -> None:
    from erenshor.cli.commands.mod import MODS

    mod = MODS["justice-for-f7"]
    assert mod["loaders"] == ["bepinex", "lunaris"]
    assert mod["default_loader"] == "lunaris"
    assert mod["public"] is True
    assert "0Harmony.dll" in mod["lunaris_dlls"]


def test_vault_listing_assets_present_and_consistent() -> None:
    config = _vault_config()

    mod = config["mod"]
    assert mod["mod_ref"] == "justice-for-f7"
    assert mod["name"]
    assert mod["short_description"]
    assert set(mod["tags"]) <= KNOWN_VAULT_TAGS

    for key in ("full_description", "changelog", "icon"):
        referenced = VAULT_ROOT / config["assets"][key]
        assert referenced.exists(), f"{key} -> {referenced} missing"


def test_vault_package_ships_only_the_plugin_assembly() -> None:
    config = _vault_config()
    package = config["package"]

    # Lunaris provides 0Harmony, so the Vault package bundles no dependency DLLs.
    assert package["asset_files"] == []

    # The main file must match the assembly the build actually emits.
    csproj = (MOD_ROOT / "JusticeForF7.csproj").read_text()
    assert "<AssemblyName>JusticeForF7</AssemblyName>" in csproj
    assert package["main_file"] == "JusticeForF7.dll"


def test_vault_changelog_top_entry_uses_calver_version_heading() -> None:
    changelog = (VAULT_ROOT / "CHANGELOG.md").read_text()
    # Vault requires x.y.z; the project uses YYYY.MDD.R CalVer.
    headings = [line for line in changelog.splitlines() if line.startswith("## v")]
    assert headings, "CHANGELOG must have at least one '## vX.Y.Z' heading"
    version = headings[0].removeprefix("## v").strip()
    parts = version.split(".")
    assert len(parts) == 3, f"version {version!r} must have three numeric segments"
    assert all(part.isdigit() for part in parts), f"version {version!r} must be numeric"
