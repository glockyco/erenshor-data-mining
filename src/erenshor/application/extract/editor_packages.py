"""Restore the NuGet dependencies the Unity Editor export scripts compile against.

`src/Assets/packages.config` pins the packages, and NuGetForUnity normally
materialises them into `src/Assets/Packages/` from inside the Editor. That
directory is gitignored build output, so a fresh checkout has none of it and the
batch export fails to compile with unresolved `SQLite` references. This module
performs the same restore from the CLI, without opening Unity.

Only the assemblies Unity can consume are unpacked: one managed target framework
per package, plus the native runtime for the host so the SQLite provider can
load `e_sqlite3` in the Editor. Extracting every runtime would give Unity several
plugins with one file name and an ambiguous import.
"""

from __future__ import annotations

import io
import platform
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from loguru import logger

# Unity 2021.3 compiles against netstandard2.1; every earlier target it accepts is
# listed so a package that predates netstandard still resolves.
TARGET_FRAMEWORK_PREFERENCE: tuple[str, ...] = (
    "netstandard2.1",
    "netstandard2.0",
    "net472",
    "net471",
    "net47",
    "net462",
    "net461",
    "net46",
    "net45",
)

NUGET_FLAT_CONTAINER = "https://api.nuget.org/v3-flatcontainer"


class PackageRestoreError(Exception):
    """Raised when a pinned Editor dependency cannot be restored."""


@dataclass(frozen=True, slots=True)
class PackageRef:
    """One pinned package from `packages.config`."""

    id: str
    version: str

    @property
    def directory_name(self) -> str:
        """Directory NuGetForUnity uses for this package inside `Assets/Packages`."""
        return f"{self.id}.{self.version}"

    @property
    def nupkg_name(self) -> str:
        """File name of the package archive on nuget.org."""
        return f"{self.id.lower()}.{self.version.lower()}.nupkg"

    @property
    def download_url(self) -> str:
        """Flat-container URL of the package archive."""
        return f"{NUGET_FLAT_CONTAINER}/{self.id.lower()}/{self.version.lower()}/{self.nupkg_name}"


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """Observable outcome of a restore."""

    packages_dir: Path
    runtime_id: str
    restored: tuple[PackageRef, ...]
    reused: tuple[PackageRef, ...]


Downloader = Callable[[str], bytes]


def read_packages_config(path: Path) -> tuple[PackageRef, ...]:
    """Parse the pinned package list.

    Args:
        path: Path to `packages.config`.

    Returns:
        Every pinned package, in file order.

    Raises:
        PackageRestoreError: If the file is missing or an entry lacks id/version.
    """
    if not path.is_file():
        raise PackageRestoreError(f"packages.config not found: {path}")

    root = ElementTree.fromstring(path.read_text(encoding="utf-8-sig"))
    packages: list[PackageRef] = []
    for element in root.findall("package"):
        package_id = element.get("id")
        version = element.get("version")
        if not package_id or not version:
            raise PackageRestoreError(f"Incomplete package entry in {path}: {ElementTree.tostring(element)!r}")
        packages.append(PackageRef(id=package_id, version=version))

    if not packages:
        raise PackageRestoreError(f"No packages declared in {path}")
    return tuple(packages)


def host_runtime_id() -> str:
    """Return the .NET runtime identifier of the machine running the Editor.

    Returns:
        A runtime identifier such as `osx-arm64`.

    Raises:
        PackageRestoreError: If the platform has no known identifier.
    """
    machine = platform.machine().lower()
    architecture = {
        "arm64": "arm64",
        "aarch64": "arm64",
        "x86_64": "x64",
        "amd64": "x64",
    }.get(machine)
    system = {"darwin": "osx", "linux": "linux", "windows": "win"}.get(platform.system().lower())

    if architecture is None or system is None:
        raise PackageRestoreError(f"Unsupported host for native NuGet payloads: {platform.system()} {machine}")
    return f"{system}-{architecture}"


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "erenshor-cli"})
    try:
        with urlopen(request, timeout=120) as response:
            return bytes(response.read())
    except (HTTPError, URLError, TimeoutError) as exc:
        raise PackageRestoreError(f"Failed to download {url}: {exc}") from exc


def _cached_archive(package: PackageRef, cache_dir: Path, download: Downloader) -> bytes:
    cached = cache_dir / package.nupkg_name
    if cached.is_file():
        return cached.read_bytes()

    payload = download(package.download_url)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(payload)
    return payload


def _select_managed_framework(archive: zipfile.ZipFile) -> str | None:
    """Pick the best target framework directory the archive offers, if any."""
    available = {
        Path(name).parts[1].lower()
        for name in archive.namelist()
        if name.lower().startswith("lib/") and len(Path(name).parts) > 2
    }
    for framework in TARGET_FRAMEWORK_PREFERENCE:
        if framework in available:
            return framework
    return None


def _extract_package(package: PackageRef, payload: bytes, target_dir: Path, runtime_id: str) -> None:
    """Unpack the assemblies Unity needs into a staged package directory."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        framework = _select_managed_framework(archive)
        native_prefix = f"runtimes/{runtime_id}/native/"
        extracted = 0

        for name in archive.namelist():
            if name.endswith("/"):
                continue
            parts = Path(name).parts
            lowered = name.lower()

            is_managed = (
                framework is not None
                and lowered.startswith("lib/")
                and len(parts) == 3
                and parts[1].lower() == framework
                and lowered.endswith(".dll")
            )
            is_native = lowered.startswith(native_prefix)
            if not (is_managed or is_native):
                continue

            destination = target_dir / Path(*parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
            extracted += 1

        if extracted == 0:
            raise PackageRestoreError(
                f"{package.directory_name} has no assembly Unity can use: "
                f"no supported lib/ framework and no runtimes/{runtime_id}/native payload"
            )


def restore_packages(
    packages_config: Path,
    packages_dir: Path,
    cache_dir: Path,
    runtime_id: str | None = None,
    download: Downloader | None = None,
    force: bool = False,
) -> RestoreResult:
    """Materialise every pinned package into the Unity `Packages` directory.

    Args:
        packages_config: Path to `src/Assets/packages.config`.
        packages_dir: Destination `src/Assets/Packages` directory.
        cache_dir: Directory holding downloaded `.nupkg` archives.
        runtime_id: Runtime identifier for native payloads; host default when None.
        download: Archive fetcher; the nuget.org flat container when None.
        force: Re-extract packages that are already present.

    Returns:
        Which packages were written and which were already in place.

    Raises:
        PackageRestoreError: If the config is unusable or a package cannot be restored.
    """
    packages = read_packages_config(packages_config)
    resolved_runtime = runtime_id if runtime_id is not None else host_runtime_id()
    fetch = download if download is not None else _download

    restored: list[PackageRef] = []
    reused: list[PackageRef] = []

    packages_dir.mkdir(parents=True, exist_ok=True)
    for package in packages:
        target_dir = packages_dir / package.directory_name
        if target_dir.is_dir() and not force:
            reused.append(package)
            continue

        payload = _cached_archive(package, cache_dir, fetch)
        with tempfile.TemporaryDirectory(dir=packages_dir) as staging_root:
            staging = Path(staging_root) / package.directory_name
            _extract_package(package, payload, staging, resolved_runtime)
            if target_dir.exists():
                shutil.rmtree(target_dir)
            staging.replace(target_dir)
        restored.append(package)
        logger.info(f"Restored Editor package: {package.directory_name}")

    return RestoreResult(
        packages_dir=packages_dir,
        runtime_id=resolved_runtime,
        restored=tuple(restored),
        reused=tuple(reused),
    )
