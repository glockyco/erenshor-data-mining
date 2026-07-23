"""Behavior contracts for static and built companion-mod artifact verification."""

from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.application.mods.artifacts import (
    ArtifactIssue,
    ModArtifactSpec,
    verify_built_mod_artifacts,
    verify_static_mod_artifacts,
)

_SPEC = ModArtifactSpec(
    mod_id="test-mod",
    directory=Path("src/mods/TestMod"),
    display_name="Test Mod",
    dll_name="TestMod.dll",
    loaders=("bepinex", "lunaris"),
    public=True,
    thunderstore_id="WoW_Much/TestMod",
)


def _write_fixture(tmp_path: Path) -> tuple[Path, ModArtifactSpec]:
    root = tmp_path / "repo"
    mod = root / "src/mods/TestMod"
    (mod / "thunderstore").mkdir(parents=True)
    (mod / "vault").mkdir()
    (mod / "resources").mkdir()
    (mod / "resources/data.json").write_text("{}", encoding="utf-8")
    (mod / "thunderstore/icon.png").write_bytes(b"icon")
    (mod / "thunderstore/README.md").write_text("# Test Mod", encoding="utf-8")
    (mod / "thunderstore/CHANGELOG.md").write_text("# Changelog\n\n## v2026.723.0\n", encoding="utf-8")
    (mod / "vault/icon.png").write_bytes(b"icon")
    (mod / "vault/README.md").write_text("# Test Mod", encoding="utf-8")
    (mod / "vault/CHANGELOG.md").write_text("# Changelog\n\n## v2026.723.0\n", encoding="utf-8")
    (mod / "thunderstore.toml").write_text(
        """[package]
namespace = "WoW_Much"
name = "TestMod"
[package.dependencies]
BepInEx-BepInExPack = "5.4.2304"
[build]
icon = "./thunderstore/icon.png"
readme = "./thunderstore/README.md"
changelog = "./thunderstore/CHANGELOG.md"
outdir = "./thunderstore/build"
[[build.copy]]
source = "./bin/Debug/netstandard2.1/bepinex/TestMod.dll"
target = "plugins/TestMod/"
""",
        encoding="utf-8",
    )
    (mod / "vault/vault.toml").write_text(
        """[mod]
name = "Test Mod"
mod_ref = "test-mod"
tags = ["utility"]
[assets]
full_description = "README.md"
changelog = "CHANGELOG.md"
icon = "icon.png"
[package]
main_file = "TestMod.dll"
asset_files = []
""",
        encoding="utf-8",
    )
    (mod / "TestMod.csproj").write_text(
        """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <AssemblyName>TestMod</AssemblyName>
    <RootNamespace>TestMod</RootNamespace>
  </PropertyGroup>
  <ItemGroup>
    <EmbeddedResource Include="resources/data.json" LogicalName="TestMod.data.json" />
  </ItemGroup>
</Project>
""",
        encoding="utf-8",
    )
    return root, _SPEC


def _output(root: Path, loader: str = "bepinex", content: bytes = b"TestMod.data.json") -> Path:
    output = root / "src/mods/TestMod/bin/Debug/netstandard2.1" / loader
    output.mkdir(parents=True)
    (output / "TestMod.dll").write_bytes(content)
    return output


def _checks(issues: tuple[ArtifactIssue, ...]) -> set[str]:
    return {issue.check for issue in issues}


def test_static_and_built_happy_path_does_not_require_copy_source(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)

    assert verify_static_mod_artifacts(root, (spec,)) == ()
    assert not (root / "src/mods/TestMod/bin/Debug/netstandard2.1/bepinex/TestMod.dll").exists()

    _output(root, "bepinex")
    _output(root, "lunaris")
    assert verify_built_mod_artifacts(root, (spec,), (("test-mod", "bepinex"), ("test-mod", "lunaris"))) == ()


def test_static_reports_manifest_identity_mismatch(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    manifest = root / "src/mods/TestMod/thunderstore.toml"
    manifest.write_text(manifest.read_text().replace('name = "TestMod"', 'name = "Wrong"'), encoding="utf-8")

    issues = verify_static_mod_artifacts(root, (spec,))
    assert "thunderstore-identity" in _checks(issues)

    root, spec = _write_fixture(tmp_path / "vault")
    vault = root / "src/mods/TestMod/vault/vault.toml"
    vault.write_text(vault.read_text().replace('mod_ref = "test-mod"', 'mod_ref = "wrong"'), encoding="utf-8")
    assert "vault-identity" in _checks(verify_static_mod_artifacts(root, (spec,)))


def test_static_reports_missing_embedded_source(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    (root / "src/mods/TestMod/resources/data.json").unlink()

    issues = verify_static_mod_artifacts(root, (spec,))
    assert "embedded-resources" in _checks(issues)


def test_static_reports_duplicate_logical_name_and_package_path(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    project = root / "src/mods/TestMod/TestMod.csproj"
    project.write_text(
        project.read_text().replace(
            "</ItemGroup>",
            (
                '<EmbeddedResource Include="resources/data.json">'
                "<LogicalName>TestMod.data.json</LogicalName></EmbeddedResource>\n  </ItemGroup>"
            ),
        ),
        encoding="utf-8",
    )
    manifest = root / "src/mods/TestMod/thunderstore.toml"
    manifest.write_text(
        manifest.read_text() + '\n[[build.copy]]\nsource = "./other/TestMod.dll"\ntarget = "plugins/TestMod/"\n',
        encoding="utf-8",
    )

    issues = verify_static_mod_artifacts(root, (spec,))
    assert "embedded-resources" in _checks(issues)
    assert "thunderstore-package-paths" in _checks(issues)


def test_static_rejects_unexpected_package_file(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    manifest = root / "src/mods/TestMod/thunderstore.toml"
    manifest.write_text(
        manifest.read_text()
        + "\n[[build.copy]]\n"
        + 'source = "./bin/Debug/netstandard2.1/bepinex/Helper.dll"\n'
        + 'target = "plugins/TestMod/"\n',
        encoding="utf-8",
    )

    issues = verify_static_mod_artifacts(root, (spec,))
    assert "thunderstore-copy-declarations" in _checks(issues)


def test_static_reports_forbidden_declared_dll(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    manifest = root / "src/mods/TestMod/thunderstore.toml"
    manifest.write_text(
        manifest.read_text()
        + "\n[[build.copy]]\n"
        + 'source = "./bin/Debug/netstandard2.1/bepinex/UnityEngine.dll"\n'
        + 'target = "plugins/TestMod/"\n',
        encoding="utf-8",
    )

    issues = verify_static_mod_artifacts(root, (spec,))
    assert "thunderstore-forbidden-dll" in _checks(issues)


def test_built_reports_forbidden_dll_and_missing_expected_dll(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    output = _output(root)
    (output / "deps").mkdir()
    (output / "deps/UnityEngine.dll").write_bytes(b"runtime")
    (output / "TestMod.dll").unlink()

    issues = verify_built_mod_artifacts(root, (spec,), (("test-mod", "bepinex"),))
    assert "built-output-dll" in _checks(issues)
    assert "built-forbidden-dll" in _checks(issues)

    _output(root, "lunaris")
    (root / "src/mods/TestMod/bin/Debug/netstandard2.1/lunaris/Lunaris.dll").write_bytes(b"runtime")
    issues = verify_built_mod_artifacts(root, (spec,), (("test-mod", "lunaris"),))
    assert "built-forbidden-dll" in _checks(issues)


def test_built_reports_missing_logical_resource_name(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    _output(root, content=b"not an assembly resource")

    issues = verify_built_mod_artifacts(root, (spec,), (("test-mod", "bepinex"),))
    assert "built-resources" in _checks(issues)


def test_static_rejects_bad_traversal_and_symlink_owned_input(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    manifest = root / "src/mods/TestMod/thunderstore.toml"
    manifest.write_text(manifest.read_text().replace("./thunderstore/README.md", "../README.md"), encoding="utf-8")
    issues = verify_static_mod_artifacts(root, (spec,))
    assert "thunderstore-assets" in _checks(issues)

    root, spec = _write_fixture(tmp_path / "loader")
    manifest = root / "src/mods/TestMod/thunderstore.toml"
    manifest.write_text(
        manifest.read_text().replace(
            "bin/Debug/netstandard2.1/bepinex/TestMod.dll",
            "bin/Debug/netstandard2.1/lunaris/TestMod.dll",
        ),
        encoding="utf-8",
    )
    assert "thunderstore-copy-declarations" in _checks(verify_static_mod_artifacts(root, (spec,)))

    root, spec = _write_fixture(tmp_path / "dot-target")
    manifest = root / "src/mods/TestMod/thunderstore.toml"
    manifest.write_text(
        manifest.read_text().replace('target = "plugins/TestMod/"', 'target = "./plugins/TestMod/"'),
        encoding="utf-8",
    )
    assert "thunderstore-copy-declarations" in _checks(verify_static_mod_artifacts(root, (spec,)))

    root, spec = _write_fixture(tmp_path / "colon")
    manifest = root / "src/mods/TestMod/thunderstore.toml"
    manifest.write_text(manifest.read_text().replace("plugins/TestMod/", "plugins/Test:Mod/"), encoding="utf-8")
    issues = verify_static_mod_artifacts(root, (spec,))
    assert "thunderstore-copy-declarations" in _checks(issues)

    root, spec = _write_fixture(tmp_path / "symlink")
    (root / "src/mods/TestMod/vault/icon.png").unlink()
    (root / "src/mods/TestMod/vault/icon.png").symlink_to(root / "src/mods/TestMod/thunderstore/icon.png")
    issues = verify_static_mod_artifacts(root, (spec,))
    assert "vault-assets" in _checks(issues)

    root, spec = _write_fixture(tmp_path / "directory-symlink")
    mod_path = root / "src/mods/TestMod"
    real_mod_path = root / "src/mods/RealMod"
    mod_path.rename(real_mod_path)
    mod_path.symlink_to(real_mod_path, target_is_directory=True)
    issues = verify_static_mod_artifacts(root, (spec,))
    assert "catalog-directory" in _checks(issues)


def test_static_rejects_changelog_ownership_and_bad_heading(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    manifest = root / "src/mods/TestMod/thunderstore.toml"
    manifest.write_text(
        manifest.read_text().replace("./thunderstore/CHANGELOG.md", "./vault/CHANGELOG.md"), encoding="utf-8"
    )
    (root / "src/mods/TestMod/vault/CHANGELOG.md").write_text(
        "# Changelog\n\n## Notes\n\n## v1.2.3\n",
        encoding="utf-8",
    )

    issues = verify_static_mod_artifacts(root, (spec,))
    assert "changelog-ownership" in _checks(issues)
    assert "changelog-heading" in _checks(issues)


def test_static_rejects_icon_dependency_tag_and_vault_package_mutations(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    thunderstore = root / "src/mods/TestMod/thunderstore.toml"
    thunderstore.write_text(thunderstore.read_text().replace("5.4.2304", "5.4.0"), encoding="utf-8")
    vault = root / "src/mods/TestMod/vault/vault.toml"
    vault.write_text(
        vault.read_text()
        .replace('["utility"]', '["unknown"]')
        .replace("asset_files = []", 'asset_files = ["extra.txt"]'),
        encoding="utf-8",
    )
    (root / "src/mods/TestMod/vault/icon.png").write_bytes(b"different")

    issues = verify_static_mod_artifacts(root, (spec,))
    assert "thunderstore-dependencies" in _checks(issues)
    assert "vault-identity" in _checks(issues)
    assert "icon-consistency" in _checks(issues)


def test_static_aggregates_in_spec_and_check_order(tmp_path: Path) -> None:
    root, spec = _write_fixture(tmp_path)
    broken = ModArtifactSpec(
        mod_id="broken",
        directory=Path("missing"),
        display_name="Broken",
        dll_name="Broken.dll",
        loaders=("bepinex",),
        public=False,
        thunderstore_id=None,
    )

    issues = verify_static_mod_artifacts(root, (spec, broken))
    assert issues[-1].mod_id == "broken"
    assert [issue.check for issue in issues if issue.mod_id == "broken"] == ["catalog-directory"]


@pytest.mark.parametrize("name", ["Assembly-CSharp.dll", "BepInEx.dll", "Lunaris.dll", "0Harmony.dll"])
def test_forbidden_runtime_names_are_checked_case_insensitively(tmp_path: Path, name: str) -> None:
    root, spec = _write_fixture(tmp_path)
    manifest = root / "src/mods/TestMod/thunderstore.toml"
    manifest.write_text(
        manifest.read_text()
        + f'\n[[build.copy]]\nsource = "./bin/Debug/netstandard2.1/bepinex/{name}"\ntarget = "plugins/TestMod/"\n',
        encoding="utf-8",
    )

    assert "thunderstore-forbidden-dll" in _checks(verify_static_mod_artifacts(root, (spec,)))
