import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "Sprint"
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


def _sprint_registry_block(registry: str) -> str:
    start = registry.index('"sprint":')
    end = registry.index("}", start)
    return registry[start:end]


def test_thunderstore_packaging_retired_for_sprint() -> None:
    # Sprint is Lunaris-only now; no Thunderstore packaging remains.
    assert not (MOD_ROOT / "thunderstore.toml").exists()
    assert not (MOD_ROOT / "thunderstore").exists()

    registry = (REPO_ROOT / "src" / "erenshor" / "cli" / "commands" / "mod.py").read_text()
    assert "WoW_Much/Sprint" not in registry
    assert '"thunderstore"' not in _sprint_registry_block(registry)


def test_sprint_uses_lunaris_loader() -> None:
    from erenshor.cli.commands.mod import MODS

    mod = MODS["sprint"]
    assert mod["loader"] == "lunaris"
    assert "thunderstore" not in mod
    assert "0Harmony.dll" in mod["lunaris_dlls"]


def test_vault_listing_assets_present_and_consistent() -> None:
    config = _vault_config()

    mod = config["mod"]
    assert mod["mod_ref"] == "sprint"
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
    csproj = (MOD_ROOT / "Sprint.csproj").read_text()
    assert "<AssemblyName>Sprint</AssemblyName>" in csproj
    assert package["main_file"] == "Sprint.dll"


def test_vault_changelog_top_entry_uses_calver_version_heading() -> None:
    changelog = (VAULT_ROOT / "CHANGELOG.md").read_text()
    # Vault requires x.y.z; the project uses YYYY.MDD.R CalVer.
    headings = [line for line in changelog.splitlines() if line.startswith("## v")]
    assert headings, "CHANGELOG must have at least one '## vX.Y.Z' heading"
    version = headings[0].removeprefix("## v").strip()
    parts = version.split(".")
    assert len(parts) == 3, f"version {version!r} must have three numeric segments"
    assert all(part.isdigit() for part in parts), f"version {version!r} must be numeric"
