import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"
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


def test_thunderstore_packaging_assets_and_identity_present() -> None:
    manifest = (MOD_ROOT / "thunderstore.toml").read_text()
    assert (MOD_ROOT / "thunderstore" / "README.md").exists()
    assert (MOD_ROOT / "thunderstore" / "CHANGELOG.md").exists()
    assert (MOD_ROOT / "vault" / "icon.png").exists()
    assert not (MOD_ROOT / "thunderstore" / "icon.png").exists()
    assert 'namespace = "WoW_Much"' in manifest
    assert 'name = "AdventureGuide"' in manifest
    assert 'BepInEx-BepInExPack = "5.4.2304"' in manifest
    assert "In-game quest companion with GPS navigation." in manifest


def test_thunderstore_plugin_allowlist_is_strict() -> None:
    config = tomllib.loads((MOD_ROOT / "thunderstore.toml").read_text())
    assert config["build"]["icon"] == "./vault/icon.png"
    copies = config["build"]["copy"]
    sources = {Path(item["source"]).name for item in copies}
    assert sources == {
        "AdventureGuide.dll",
        "ImGui.NET.dll",
        "Newtonsoft.Json.dll",
        "System.Numerics.Vectors.dll",
        "cimgui.dll",
    }
    assert all(item["target"] == "plugins/AdventureGuide/" for item in copies)


def test_vault_listing_assets_present_and_consistent() -> None:
    config = _vault_config()

    mod = config["mod"]
    assert mod["mod_ref"] == "adventure-guide"
    assert mod["name"]
    assert mod["short_description"]
    assert set(mod["tags"]) <= KNOWN_VAULT_TAGS

    for key in ("full_description", "changelog", "icon"):
        referenced = VAULT_ROOT / config["assets"][key]
        assert referenced.exists(), f"{key} -> {referenced} missing"


def test_vault_package_ships_only_the_plugin_assembly() -> None:
    config = _vault_config()
    package = config["package"]

    # Lunaris provides ImGui.NET, Newtonsoft.Json, and System.Numerics.Vectors,
    # so the Vault package bundles no dependency DLLs.
    assert package["asset_files"] == []

    # The main file must match the assembly the build actually emits.
    csproj = (MOD_ROOT / "AdventureGuide.csproj").read_text()
    assert "<AssemblyName>AdventureGuide</AssemblyName>" in csproj
    assert package["main_file"] == "AdventureGuide.dll"


def test_vault_changelog_top_entry_uses_calver_version_heading() -> None:
    changelog = (VAULT_ROOT / "CHANGELOG.md").read_text()
    # Vault requires x.y.z; the project uses YYYY.MDD.R CalVer.
    headings = [line for line in changelog.splitlines() if line.startswith("## v")]
    assert headings, "CHANGELOG must have at least one '## vX.Y.Z' heading"
    version = headings[0].removeprefix("## v").strip()
    parts = version.split(".")
    assert len(parts) == 3, f"version {version!r} must have three numeric segments"
    assert all(part.isdigit() for part in parts), f"version {version!r} must be numeric"
