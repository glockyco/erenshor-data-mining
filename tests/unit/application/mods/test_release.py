"""Focused tests for application-owned mod release planning and sequencing."""

from __future__ import annotations

import subprocess
import zipfile
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from erenshor.application.mods import release
from erenshor.application.mods.catalog import lookup_mod


def _ctx(root: Path) -> SimpleNamespace:
    return SimpleNamespace(repo_root=root, variant="main")


def _fixture(root: Path, mod_id: str = "sprint") -> tuple[SimpleNamespace, release.ThunderstoreManifest]:
    definition = lookup_mod(mod_id)
    mod_dir = root / definition.directory
    build_dir = mod_dir / "bin/Debug/netstandard2.1/bepinex"
    thunderstore = mod_dir / "thunderstore"
    build_dir.mkdir(parents=True)
    thunderstore.mkdir(parents=True)
    (build_dir / definition.dll_name).write_bytes(b"compiled")
    (thunderstore / "icon.png").write_bytes(b"icon")
    (thunderstore / "README.md").write_text("# Fixture\n")
    (thunderstore / "CHANGELOG.md").write_text("# Changelog\n")
    manifest_path = mod_dir / "thunderstore.toml"
    package_name = definition.dll_name[:-4].replace(" ", "") if mod_id != "sprint" else "Sprint"
    manifest_path.write_text(
        f"""[package]
namespace = "WoW_Much"
name = "{package_name}"

[build]
icon = "./thunderstore/icon.png"
readme = "./thunderstore/README.md"
changelog = "./thunderstore/CHANGELOG.md"
outdir = "./thunderstore/build"

[[build.copy]]
source = "./bin/Debug/netstandard2.1/bepinex/{definition.dll_name}"
target = "plugins/{definition.dll_name[:-4]}/"
"""
    )
    expected_name = "Sprint" if mod_id == "sprint" else definition.dll_name[:-4].replace(" ", "")
    manifest = release.parse_thunderstore_manifest(
        manifest_path,
        mod_dir,
        root,
        expected_namespace="WoW_Much",
        expected_name=expected_name,
    )
    return _ctx(root), manifest


def _write_package(manifest: release.ThunderstoreManifest, version: str) -> Path:
    package = manifest.outdir / f"{manifest.namespace}-{manifest.name}-{version}.zip"
    package.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package, "w") as archive:
        for name in set(manifest.allowed_package_names) - {"CHANGELOG.md"}:
            archive.writestr(name, b"package")
    return package


def test_plan_is_immutable_and_remote_failure_precedes_build(tmp_path: Path) -> None:
    ctx, _manifest = _fixture(tmp_path)
    build_calls: list[str] = []

    def remote(_namespace: str, _name: str) -> str:
        raise RuntimeError("Thunderstore unavailable")

    with pytest.raises(RuntimeError, match="unavailable"):
        release.execute_thunderstore(
            ctx,
            "sprint",
            dry_run=True,
            version_lookup=remote,
            tcli_available=lambda: True,
            build_client=lambda *_args, **_kwargs: build_calls.append("build"),
        )
    assert build_calls == []

    plan = release.plan_thunderstore(
        ctx,
        "sprint",
        dry_run=True,
        version_lookup=lambda _namespace, _name: "2099.101.0",
        tcli_available=lambda: True,
    )
    with pytest.raises(FrozenInstanceError):
        plan.dry_run = False  # type: ignore[misc]


def test_dry_run_builds_and_validates_without_publish(tmp_path: Path) -> None:
    ctx, manifest = _fixture(tmp_path)
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def runner(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        if args[1] == "build":
            _write_package(manifest, args[3])
        return subprocess.CompletedProcess(args, 0)

    def build_client(_ctx: Any, _mod: str, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(failed=(), artifact_issues=())

    result = release.execute_thunderstore(
        ctx,
        "sprint",
        dry_run=True,
        version_lookup=lambda _namespace, _name: "2099.101.0",
        tcli_available=lambda: True,
        build_client=build_client,
        runner=runner,
    )

    assert len(result.packages) == 1
    assert result.published == ()
    assert [args[1] for args, _kwargs in calls] == ["build"]
    release.validate_thunderstore_package(result.packages[0].path, manifest)


def test_package_input_mutation_fails_before_publish(tmp_path: Path) -> None:
    ctx, manifest = _fixture(tmp_path)
    calls: list[str] = []

    def runner(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args[1])
        if args[1] == "build":
            _write_package(manifest, args[3])
            manifest.readme.write_text("changed")
        return subprocess.CompletedProcess(args, 0)

    with pytest.raises(ValueError, match="changed during release"):
        release.execute_thunderstore(
            ctx,
            "sprint",
            dry_run=False,
            token="sentinel",
            version_lookup=lambda _namespace, _name: "2099.101.0",
            tcli_available=lambda: True,
            build_client=lambda *_args, **_kwargs: SimpleNamespace(failed=(), artifact_issues=()),
            runner=runner,
        )
    assert calls == ["build"]


def test_vault_listing_validation_and_lunaris_plan(tmp_path: Path) -> None:
    definition = lookup_mod("sprint")
    mod_dir = tmp_path / definition.directory
    vault = mod_dir / "vault"
    vault.mkdir(parents=True)
    changelog = vault / "CHANGELOG.md"
    changelog.write_text("# Changelog\n## v2099.101.0\n")
    (vault / "vault.toml").write_text('[mod]\nmod_ref = "sprint"\n')
    plan = release.plan_vault(
        _ctx(tmp_path),
        "sprint",
        version_lookup=lambda _ref: "2099.101.1",
    )
    assert plan.releases[0].listing.mod_ref == "sprint"
    assert plan.releases[0].dll.name == definition.dll_name
    assert plan.releases[0].changelog_version == "2099.101.0"
