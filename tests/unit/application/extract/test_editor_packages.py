"""Unit tests for restoring the Unity Editor's NuGet dependencies."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from erenshor.application.extract.editor_packages import (
    PackageRestoreError,
    host_runtime_id,
    read_packages_config,
    restore_packages,
)

PACKAGES_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<packages>
  <package id="SQLite-net" version="1.9.172" manuallyInstalled="true" />
  <package id="SQLitePCLRaw.lib.e_sqlite3" version="2.1.2" />
</packages>
"""


def _nupkg(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


MANAGED_PACKAGE = _nupkg(
    {
        "SQLite-net.nuspec": b"<package/>",
        "lib/net45/SQLite-net.dll": b"old-framework",
        "lib/netstandard2.0/SQLite-net.dll": b"managed",
        "lib/netstandard2.0/SQLite-net.xml": b"docs",
    }
)

NATIVE_PACKAGE = _nupkg(
    {
        "runtimes/osx-arm64/native/libe_sqlite3.dylib": b"arm64",
        "runtimes/osx-x64/native/libe_sqlite3.dylib": b"x64",
        "runtimes/win-x64/native/e_sqlite3.dll": b"windows",
    }
)

ARCHIVES = {
    "sqlite-net": MANAGED_PACKAGE,
    "sqlitepclraw.lib.e_sqlite3": NATIVE_PACKAGE,
}


def _fake_download(url: str) -> bytes:
    for package_id, payload in ARCHIVES.items():
        if f"/{package_id}/" in url:
            return payload
    raise AssertionError(f"unexpected download: {url}")


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "packages.config"
    path.write_text(PACKAGES_CONFIG)
    return path


def _restore(config_path: Path, tmp_path: Path, **kwargs: object):
    return restore_packages(
        packages_config=config_path,
        packages_dir=tmp_path / "Packages",
        cache_dir=tmp_path / "cache",
        runtime_id="osx-arm64",
        download=_fake_download,
        **kwargs,  # type: ignore[arg-type]
    )


def test_reads_pinned_versions(config_path: Path) -> None:
    """Every declared package keeps its pinned version."""
    packages = read_packages_config(config_path)

    assert [(package.id, package.version) for package in packages] == [
        ("SQLite-net", "1.9.172"),
        ("SQLitePCLRaw.lib.e_sqlite3", "2.1.2"),
    ]


def test_rejects_config_without_packages(tmp_path: Path) -> None:
    """An empty config is a configuration error, not an empty restore."""
    path = tmp_path / "packages.config"
    path.write_text("<packages></packages>")

    with pytest.raises(PackageRestoreError, match="No packages declared"):
        read_packages_config(path)


def test_extracts_one_managed_framework(config_path: Path, tmp_path: Path) -> None:
    """The newest supported framework wins, and older copies stay out of Unity."""
    result = _restore(config_path, tmp_path)

    package_dir = result.packages_dir / "SQLite-net.1.9.172"
    assert (package_dir / "lib/netstandard2.0/SQLite-net.dll").read_bytes() == b"managed"
    assert not (package_dir / "lib/net45").exists()
    # Unity only needs assemblies; documentation would just become another asset.
    assert not (package_dir / "lib/netstandard2.0/SQLite-net.xml").exists()


def test_extracts_only_the_host_native_runtime(config_path: Path, tmp_path: Path) -> None:
    """Two same-named native libraries would collide as Unity plugins."""
    result = _restore(config_path, tmp_path)

    package_dir = result.packages_dir / "SQLitePCLRaw.lib.e_sqlite3.2.1.2"
    assert (package_dir / "runtimes/osx-arm64/native/libe_sqlite3.dylib").read_bytes() == b"arm64"
    assert not (package_dir / "runtimes/osx-x64").exists()
    assert not (package_dir / "runtimes/win-x64").exists()


def test_reuses_restored_packages(config_path: Path, tmp_path: Path) -> None:
    """A second restore is a no-op, so it stays cheap enough to gate the rip."""
    first = _restore(config_path, tmp_path)
    second = _restore(config_path, tmp_path)

    assert len(first.restored) == 2
    assert first.reused == ()
    assert second.restored == ()
    assert len(second.reused) == 2


def test_force_replaces_existing_content(config_path: Path, tmp_path: Path) -> None:
    """--force repairs a partially written package directory."""
    result = _restore(config_path, tmp_path)
    stale = result.packages_dir / "SQLite-net.1.9.172" / "lib/netstandard2.0/SQLite-net.dll"
    stale.write_bytes(b"corrupt")

    _restore(config_path, tmp_path, force=True)

    assert stale.read_bytes() == b"managed"


def test_caches_downloaded_archives(config_path: Path, tmp_path: Path) -> None:
    """Archives land in the cache so a forced restore needs no network."""
    _restore(config_path, tmp_path)

    cached = sorted(path.name for path in (tmp_path / "cache").iterdir())
    assert cached == ["sqlite-net.1.9.172.nupkg", "sqlitepclraw.lib.e_sqlite3.2.1.2.nupkg"]

    def _no_network(url: str) -> bytes:
        raise AssertionError(f"download attempted for {url}")

    restore_packages(
        packages_config=config_path,
        packages_dir=tmp_path / "Packages",
        cache_dir=tmp_path / "cache",
        runtime_id="osx-arm64",
        download=_no_network,
        force=True,
    )


def test_rejects_package_without_usable_payload(tmp_path: Path) -> None:
    """A package Unity cannot consume fails the restore instead of silently vanishing."""
    config = tmp_path / "packages.config"
    config.write_text('<packages><package id="Empty" version="1.0.0" /></packages>')

    with pytest.raises(PackageRestoreError, match="no assembly Unity can use"):
        restore_packages(
            packages_config=config,
            packages_dir=tmp_path / "Packages",
            cache_dir=tmp_path / "cache",
            runtime_id="osx-arm64",
            download=lambda _url: _nupkg({"lib/net6.0/Empty.dll": b"too new"}),
        )


def test_host_runtime_id_matches_this_machine() -> None:
    """The identifier is one nuget.org actually publishes runtimes for."""
    assert host_runtime_id() in {
        "osx-arm64",
        "osx-x64",
        "linux-arm64",
        "linux-x64",
        "win-arm64",
        "win-x64",
    }
