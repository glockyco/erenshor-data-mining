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


def _thunderstore_config() -> dict[str, Any]:
    return tomllib.loads((MOD_ROOT / "thunderstore.toml").read_text())


def test_thunderstore_packaging_is_native_bepinex() -> None:
    config = _thunderstore_config()
    package = config["package"]
    build = config["build"]

    assert package["namespace"] == "WoW_Much"
    assert package["name"] == "Sprint"
    assert package["dependencies"] == {"BepInEx-BepInExPack": "5.4.2304"}
    assert (MOD_ROOT / build["icon"]).resolve() == (VAULT_ROOT / "icon.png").resolve()
    assert (MOD_ROOT / build["readme"]).exists()
    assert (MOD_ROOT / build["changelog"]).exists()

    copies = build["copy"]
    assert len(copies) == 1
    assert copies[0] == {
        "source": "./bin/Debug/netstandard2.1/bepinex/Sprint.dll",
        "target": "plugins/Sprint/",
    }


def test_native_adapters_share_idempotent_lifecycle() -> None:
    runtime = (MOD_ROOT / "src" / "Core" / "SprintRuntime.cs").read_text()
    assert "Start(ISprintSettings settings, Func<bool> isSprintPressed)" in runtime
    assert "internal static bool Start" in runtime
    assert "internal static void Stop()" in runtime
    assert "if (!_started)" in runtime
    assert "Apply(_playerStats, false)" in runtime
    assert "_harmony?.UnpatchSelf()" in runtime

    for loader in ("BepInEx", "Lunaris"):
        source = (MOD_ROOT / "src" / f"Plugin.{loader}.cs").read_text()
        awake = source.index("private void Awake()")
        awake_body = source[awake : source.index("}", awake)]
        assert "gameObject.hideFlags = HideFlags.HideAndDontSave;" in awake_body
        assert source.index("gameObject.hideFlags") < source.index("SprintRuntime.Start")
        assert "SprintRuntime.Tick()" in source
        assert "SprintRuntime.Stop()" in source


def test_sprint_declares_dual_loader_support() -> None:
    from erenshor.cli.commands.mod import MODS

    mod = MODS["sprint"]
    assert mod["loaders"] == ["bepinex", "lunaris"]
    assert mod["default_loader"] == "lunaris"
    assert mod["thunderstore"] == "WoW_Much/Sprint"
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
