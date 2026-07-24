"""Release planning and execution for companion-mod distributions.

The release workflow owns filesystem and archive validation, CalVer policy, and
ordering of remote and process operations.  The CLI supplies presentation and
injects process or remote clients at the boundary.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tomllib
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from erenshor.application.mods.artifacts import is_forbidden_runtime_dll
from erenshor.application.mods.catalog import iter_mods, lookup_mod, public_mods

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

VAULT_API_BASE = "https://erenshorvault.app/api"
THUNDERSTORE_API_BASE = "https://thunderstore.io/api/experimental/package"
ProcessRunner = Callable[..., Any]
BuildClient = Callable[..., Any]
ThunderstoreVersionLookup = Callable[[str, str], str]
VaultVersionLookup = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class ThunderstoreCopy:
    source: Path
    target: PurePosixPath
    package_path: PurePosixPath


@dataclass(frozen=True, slots=True)
class ThunderstoreManifest:
    path: Path
    namespace: str
    name: str
    icon: Path
    readme: Path
    changelog: Path
    outdir: Path
    copies: tuple[ThunderstoreCopy, ...]
    static_input_paths: tuple[Path, ...]
    input_paths: tuple[Path, ...]
    allowed_package_names: frozenset[str]


@dataclass(frozen=True, slots=True)
class ThunderstoreRelease:
    mod_id: str
    mod_dir: Path
    manifest: ThunderstoreManifest
    version: str
    static_input_hashes: tuple[tuple[Path, str], ...] = ()
    input_hashes: tuple[tuple[Path, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ThunderstorePackage:
    release: ThunderstoreRelease
    path: Path
    hashes: tuple[tuple[Path, str], ...]


@dataclass(frozen=True, slots=True)
class ThunderstorePlan:
    releases: tuple[ThunderstoreRelease, ...]
    dry_run: bool


@dataclass(frozen=True, slots=True)
class ThunderstoreResult:
    plan: ThunderstorePlan
    packages: tuple[ThunderstorePackage, ...]
    published: tuple[ThunderstorePackage, ...] = ()


@dataclass(frozen=True, slots=True)
class VaultListing:
    path: Path
    changelog: Path
    mod_ref: str


@dataclass(frozen=True, slots=True)
class VaultRelease:
    mod_id: str
    mod_dir: Path
    listing: VaultListing
    version: str
    dll: Path
    changelog_version: str


@dataclass(frozen=True, slots=True)
class VaultPlan:
    releases: tuple[VaultRelease, ...]


@dataclass(frozen=True, slots=True)
class VaultResult:
    plan: VaultPlan


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except (ValueError, FileNotFoundError, OSError):
        return False
    return True


def _resolve_manifest_file(raw: object, *, mod_dir: Path, repo_root: Path, label: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError(f"{label} must be a relative path")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError(f"{label} must be a relative path")
    unresolved = mod_dir / candidate
    if unresolved.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    resolved = unresolved.resolve(strict=False)
    if not _path_within(resolved, repo_root):
        raise ValueError(f"{label} is outside the repository")
    return resolved


def _require_regular_file(path: Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{label} is not a regular file: {path}")


def parse_thunderstore_manifest(
    manifest_path: Path,
    mod_dir: Path,
    repo_root: Path,
    *,
    expected_namespace: str | None = None,
    expected_name: str | None = None,
) -> ThunderstoreManifest:
    """Parse and validate one Thunderstore manifest without build outputs."""
    if manifest_path.is_symlink():
        raise ValueError("Thunderstore manifest must not be a symlink")
    manifest_path = manifest_path.resolve(strict=False)
    mod_dir = mod_dir.resolve(strict=True)
    repo_root = repo_root.resolve(strict=True)
    if not _path_within(manifest_path, mod_dir) or not _path_within(manifest_path, repo_root):
        raise ValueError("Thunderstore manifest must be inside the mod and repository")
    _require_regular_file(manifest_path, "Thunderstore manifest")
    try:
        with manifest_path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid Thunderstore TOML: {exc}") from exc

    package = data.get("package")
    build = data.get("build")
    if not isinstance(package, dict) or not isinstance(build, dict):
        raise ValueError("Thunderstore TOML requires [package] and [build] tables")
    namespace = package.get("namespace")
    name = package.get("name")
    if not isinstance(namespace, str) or not namespace or not isinstance(name, str) or not name:
        raise ValueError("Thunderstore package namespace and name are required")
    if expected_namespace is not None and namespace != expected_namespace:
        raise ValueError(f"manifest namespace is {namespace!r}, expected {expected_namespace!r}")
    if expected_name is not None and name != expected_name:
        raise ValueError(f"manifest name is {name!r}, expected {expected_name!r}")

    icon = _resolve_manifest_file(build.get("icon"), mod_dir=mod_dir, repo_root=repo_root, label="build.icon")
    readme = _resolve_manifest_file(build.get("readme"), mod_dir=mod_dir, repo_root=repo_root, label="build.readme")
    changelog = _resolve_manifest_file(
        build.get("changelog"), mod_dir=mod_dir, repo_root=repo_root, label="build.changelog"
    )
    outdir = _resolve_manifest_file(build.get("outdir"), mod_dir=mod_dir, repo_root=repo_root, label="build.outdir")
    if outdir.exists() and (not outdir.is_dir() or outdir.is_symlink()):
        raise ValueError(f"build.outdir is not a directory: {outdir}")
    for label, path in (("build.icon", icon), ("build.readme", readme), ("build.changelog", changelog)):
        _require_regular_file(path, label)

    copies_raw = build.get("copy", [])
    if not isinstance(copies_raw, list):
        raise ValueError("build.copy must be an array of tables")
    copies: list[ThunderstoreCopy] = []
    package_names: set[str] = {"manifest.json", "icon.png", "README.md", "CHANGELOG.md"}
    for index, entry in enumerate(copies_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"build.copy[{index}] must be a table")
        source = _resolve_manifest_file(
            entry.get("source"), mod_dir=mod_dir, repo_root=repo_root, label=f"build.copy[{index}].source"
        )
        if source.exists() and (not source.is_file() or source.is_symlink()):
            raise ValueError(f"build.copy[{index}].source is not a regular file: {source}")
        if is_forbidden_runtime_dll(source.name):
            raise ValueError(f"build.copy[{index}].source is a game/runtime DLL: {source.name}")
        source_relative = source.relative_to(repo_root)
        if source_relative.parts and source_relative.parts[0] == "variants":
            raise ValueError(f"build.copy[{index}].source must not use variant game assets")
        target_raw = entry.get("target")
        if not isinstance(target_raw, str) or not target_raw or "\\" in target_raw:
            raise ValueError(f"build.copy[{index}].target must be a relative POSIX path")
        if target_raw.startswith("/") or ":" in target_raw:
            raise ValueError(f"build.copy[{index}].target must be a relative POSIX path")
        target_parts = target_raw.rstrip("/").split("/")
        if any(part in {"", ".", ".."} for part in target_parts):
            raise ValueError(f"build.copy[{index}].target must be a normalized relative POSIX path")
        target = PurePosixPath(target_raw.rstrip("/"))
        if not target.parts or any(part in {"", ".", ".."} for part in target.parts):
            raise ValueError(f"build.copy[{index}].target must be a normalized relative POSIX path")
        package_path = target / source.name
        package_name = package_path.as_posix()
        if package_name in package_names:
            raise ValueError(f"duplicate Thunderstore package path: {package_name}")
        package_names.add(package_name)
        copies.append(ThunderstoreCopy(source, target, package_path))

    static_input_paths = (manifest_path, icon, readme, changelog)
    input_paths = static_input_paths + tuple(copy.source for copy in copies)
    return ThunderstoreManifest(
        path=manifest_path,
        namespace=namespace,
        name=name,
        icon=icon,
        readme=readme,
        changelog=changelog,
        outdir=outdir,
        copies=tuple(copies),
        static_input_paths=static_input_paths,
        input_paths=input_paths,
        allowed_package_names=frozenset(package_names),
    )


def _hash_paths(paths: tuple[Path, ...]) -> tuple[tuple[Path, str], ...]:
    hashes: list[tuple[Path, str]] = []
    for path in paths:
        _require_regular_file(path, "Thunderstore build input")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes.append((path, digest.hexdigest()))
    return tuple(hashes)


def hash_release_inputs(manifest: ThunderstoreManifest) -> tuple[tuple[Path, str], ...]:
    """Hash the manifest and every declared build input."""
    return _hash_paths(manifest.input_paths)


def require_unchanged_inputs(hashes: tuple[tuple[Path, str], ...]) -> None:
    current = dict(_hash_paths(tuple(path for path, _ in hashes)))
    for path, expected in hashes:
        if current.get(path) != expected:
            raise ValueError(f"Thunderstore input changed during release: {path}")


def thunderstore_package_path(manifest: ThunderstoreManifest, version: str) -> Path:
    return manifest.outdir / f"{manifest.namespace}-{manifest.name}-{version}.zip"


def remove_stale_thunderstore_package(manifest: ThunderstoreManifest, version: str) -> None:
    package = thunderstore_package_path(manifest, version)
    if package.is_symlink() or (package.exists() and not package.is_file()):
        raise ValueError(f"expected package output is not a regular file: {package}")
    package.unlink(missing_ok=True)


def locate_thunderstore_package(manifest: ThunderstoreManifest, version: str) -> Path:
    expected = thunderstore_package_path(manifest, version)
    matches = [path for path in manifest.outdir.glob(expected.name) if path.is_file() and not path.is_symlink()]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one package ZIP {expected.name} in {manifest.outdir}")
    package = matches[0].resolve(strict=True)
    if not _path_within(package, manifest.outdir):
        raise ValueError("Thunderstore package is outside its configured output directory")
    return package


def include_thunderstore_changelog(package: Path, manifest: ThunderstoreManifest) -> None:
    """Add the declared changelog that current tcli versions omit."""
    changelog_name = "CHANGELOG.md"
    changelog = manifest.changelog.read_bytes()
    try:
        with zipfile.ZipFile(package, mode="a") as archive:
            matching_entries = [info for info in archive.infolist() if info.filename == changelog_name]
            if len(matching_entries) > 1:
                raise ValueError("package contains duplicate CHANGELOG.md entries")
            if matching_entries:
                if archive.read(changelog_name) != changelog:
                    raise ValueError("package CHANGELOG.md does not match build.changelog")
                return

            info = zipfile.ZipInfo(changelog_name)
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, changelog, compress_type=zipfile.ZIP_DEFLATED)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"could not add Thunderstore changelog: {exc}") from exc


def validate_thunderstore_package(package: Path, manifest: ThunderstoreManifest) -> None:
    if not _path_within(package, manifest.outdir):
        raise ValueError("Thunderstore package is outside its configured output directory")
    try:
        with zipfile.ZipFile(package) as archive:
            infos = archive.infolist()
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"invalid Thunderstore package ZIP: {exc}") from exc
    names: list[str] = []
    for info in infos:
        name = info.filename
        if not name or "\\" in name or name.startswith("/"):
            raise ValueError(f"invalid package path: {name!r}")
        path = PurePosixPath(name)
        if any(part in {"", ".", ".."} for part in path.parts) or info.is_dir() or name.endswith("/"):
            raise ValueError(f"invalid package entry: {name!r}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink is not allowed in package: {name}")
        if is_forbidden_runtime_dll(path.name):
            raise ValueError(f"game/runtime DLL is not allowed in package: {name}")
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError("package contains duplicate entries")
    actual = set(names)
    allowed = set(manifest.allowed_package_names)
    if actual - allowed:
        raise ValueError(f"package contains unexpected entries: {', '.join(sorted(actual - allowed))}")
    required = {"manifest.json", "icon.png", "README.md", "CHANGELOG.md"} | {
        copy.package_path.as_posix() for copy in manifest.copies
    }
    missing = required - actual
    if missing:
        raise ValueError(f"package is missing entries: {', '.join(sorted(missing))}")
    try:
        with zipfile.ZipFile(package) as archive:
            packaged_changelog = archive.read("CHANGELOG.md")
        declared_changelog = manifest.changelog.read_bytes()
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"could not verify Thunderstore changelog: {exc}") from exc
    if packaged_changelog != declared_changelog:
        raise ValueError("package CHANGELOG.md does not match build.changelog")


def next_calver_revision(date_prefix: str, latest_version: str | None) -> str:
    """Return the next ``YYYY.MDD.R`` revision for a date prefix."""
    revision = 0
    if latest_version and latest_version.startswith(f"{date_prefix}."):
        with contextlib.suppress(IndexError, ValueError):
            revision = int(latest_version.split(".")[2]) + 1
    return f"{date_prefix}.{revision}"


def latest_calver_for_prefix(versions: Sequence[str], date_prefix: str) -> str | None:
    """Select the highest revision for ``date_prefix`` independent of order."""

    def revision(version: str) -> int:
        try:
            return int(version.split(".")[2])
        except (IndexError, ValueError):
            return -1

    matching = [version for version in versions if version.startswith(f"{date_prefix}.")]
    return max(matching, key=revision) if matching else None


def get_vault_version(mod_ref: str, *, now: datetime | None = None) -> str:
    """Compute the next Vault CalVer version.

    Vault's listing endpoint is intentionally best-effort, matching the manual
    release workflow.  An unavailable listing starts the revision at zero.
    """
    current = now or datetime.now(UTC)
    date_prefix = f"{current.year}.{current.month}{current.day:02d}"
    url = f"{VAULT_API_BASE}/mods/{mod_ref}/versions"
    request = Request(url, headers={"User-Agent": "erenshor-cli/1.0"})
    versions: list[str] = []
    try:
        with urlopen(request, timeout=10) as resp:
            data = json.loads(resp.read())
        if isinstance(data, dict) and isinstance(data.get("versions"), list):
            versions = [
                str(value["version"]) for value in data["versions"] if isinstance(value, dict) and value.get("version")
            ]
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        pass
    return next_calver_revision(date_prefix, latest_calver_for_prefix(versions, date_prefix))


def get_thunderstore_version(namespace: str, name: str, *, now: datetime | None = None) -> str:
    """Compute the next Thunderstore version, failing on lookup errors."""
    current = now or datetime.now(UTC)
    date_prefix = f"{current.year}.{current.month}{current.day:02d}"
    url = f"{THUNDERSTORE_API_BASE}/{namespace}/{name}/"
    request = Request(url, headers={"User-Agent": "erenshor-cli/1.0"})
    try:
        with urlopen(request, timeout=10) as resp:
            data = json.loads(resp.read())
        if not isinstance(data, dict) or not isinstance(data.get("latest"), dict):
            raise ValueError("response has no latest package record")
        latest_version = data["latest"].get("version_number")
        if not isinstance(latest_version, str) or not latest_version.strip():
            raise ValueError("response has no version_number")
        parts = latest_version.split(".")
        if (
            len(parts) != 3
            or len(parts[0]) != 4
            or len(parts[1]) not in {3, 4}
            or any(not part.isdigit() for part in parts)
        ):
            raise ValueError(f"invalid version_number: {latest_version!r}")
        month = int(parts[1][:-2])
        day = int(parts[1][-2:])
        if not 1 <= month <= 12 or not 1 <= day <= 31:
            raise ValueError(f"invalid version_number: {latest_version!r}")
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        raise RuntimeError(f"Thunderstore version lookup failed for {namespace}/{name}: {exc}") from exc
    return next_calver_revision(date_prefix, latest_version)


def check_tcli_available() -> bool:
    """Check whether tcli is available, including the default dotnet tools dir."""
    dotnet_tools = Path.home() / ".dotnet" / "tools"
    path_env = os.environ.get("PATH", "")
    if str(dotnet_tools) not in path_env:
        os.environ["PATH"] = f"{path_env}{os.pathsep}{dotnet_tools}"
    return shutil.which("tcli") is not None


def _select_thunderstore_mods(mod: str | None, dry_run: bool) -> tuple[str, ...]:
    if not dry_run and mod is None:
        raise ValueError("real Thunderstore publishing requires exactly one --mod")
    if mod is not None:
        try:
            definition = lookup_mod(mod)
        except KeyError as exc:
            raise ValueError(f"Unknown mod: {mod}") from exc
        if not definition.public or definition.thunderstore_id is None:
            raise ValueError(f"{mod} is not configured for Thunderstore")
        return (mod,)
    return tuple(definition.mod_id for definition in public_mods() if definition.thunderstore_id is not None)


def plan_thunderstore(
    cli_ctx: CLIContext,
    mod: str | None = None,
    *,
    dry_run: bool = False,
    token: str = "",
    version_lookup: ThunderstoreVersionLookup | None = None,
    tcli_available: Callable[[], bool] | None = None,
) -> ThunderstorePlan:
    """Preflight every selected release before any build or package process."""
    available = check_tcli_available if tcli_available is None else tcli_available
    if not available():
        raise RuntimeError("tcli not found")
    if not dry_run and (
        not token.strip() or token.strip().lower() in {"your_token_here", "your-token-here", "changeme"}
    ):
        raise ValueError("TCLI_AUTH_TOKEN is missing or still a placeholder")
    selected = _select_thunderstore_mods(mod, dry_run)
    lookup_version = get_thunderstore_version if version_lookup is None else version_lookup
    releases: list[ThunderstoreRelease] = []
    from erenshor.application.mods import local_workflow

    for mod_id in selected:
        definition = lookup_mod(mod_id)
        ts_id = definition.thunderstore_id
        if not ts_id or ts_id.count("/") != 1:
            raise ValueError(f"invalid Thunderstore id for {mod_id}")
        namespace, name = ts_id.split("/", 1)
        mod_dir = local_workflow.mod_dir(cli_ctx, mod_id).resolve(strict=False)
        manifest = parse_thunderstore_manifest(
            mod_dir / "thunderstore.toml",
            mod_dir,
            cli_ctx.repo_root,
            expected_namespace=namespace,
            expected_name=name,
        )
        version = lookup_version(namespace, name)
        static_hashes = _hash_paths(manifest.static_input_paths)
        releases.append(ThunderstoreRelease(mod_id, mod_dir, manifest, version, static_input_hashes=static_hashes))
    return ThunderstorePlan(tuple(releases), dry_run)


def build_thunderstore(
    cli_ctx: CLIContext,
    plan: ThunderstorePlan,
    *,
    build_client: BuildClient | None = None,
    runner: ProcessRunner = subprocess.run,
) -> ThunderstorePlan:
    """Build every preflighted release and hash all declared inputs."""
    if build_client is None:
        from erenshor.application.mods import local_workflow

        build_client = local_workflow.build_mods
    built: list[ThunderstoreRelease] = []
    for release in plan.releases:
        require_unchanged_inputs(release.static_input_hashes)
        result = build_client(
            cli_ctx,
            release.mod_id,
            version=release.version,
            loader="bepinex",
            runner=runner,
        )
        if result is not None:
            failed = tuple(getattr(result, "failed", ()))
            issues = tuple(getattr(result, "artifact_issues", ()))
            if failed:
                raise RuntimeError(f"Build failed for: {', '.join(str(value) for value in failed)}")
            if issues:
                raise ValueError("built artifact verification failed")
        require_unchanged_inputs(release.static_input_hashes)
        built.append(replace(release, input_hashes=hash_release_inputs(release.manifest)))
    return replace(plan, releases=tuple(built))


def package_thunderstore(
    plan: ThunderstorePlan,
    *,
    runner: ProcessRunner = subprocess.run,
) -> tuple[ThunderstorePackage, ...]:
    """Package and validate every release before any publication."""
    packages: list[ThunderstorePackage] = []
    for release in plan.releases:
        require_unchanged_inputs(release.input_hashes)
        remove_stale_thunderstore_package(release.manifest, release.version)
        try:
            result = runner(
                [
                    "tcli",
                    "build",
                    "--package-version",
                    release.version,
                    "--config-path",
                    str(release.manifest.path),
                ],
                cwd=release.mod_dir,
                check=False,
            )
        except OSError as exc:
            raise RuntimeError(f"Could not run tcli build: {exc}") from exc
        if result.returncode != 0:
            raise RuntimeError("Package build failed")
        require_unchanged_inputs(release.input_hashes)
        package = locate_thunderstore_package(release.manifest, release.version)
        include_thunderstore_changelog(package, release.manifest)
        validate_thunderstore_package(package, release.manifest)
        packages.append(ThunderstorePackage(release, package, _hash_paths((package,))))
    return tuple(packages)


def publish_thunderstore(
    packages: Sequence[ThunderstorePackage],
    token: str,
    *,
    runner: ProcessRunner = subprocess.run,
    environ: dict[str, str] | None = None,
) -> tuple[ThunderstorePackage, ...]:
    """Publish only packages that remain byte-for-byte unchanged."""
    published: list[ThunderstorePackage] = []
    base_env = os.environ if environ is None else environ
    for package in packages:
        require_unchanged_inputs(package.release.input_hashes)
        require_unchanged_inputs(package.hashes)
        try:
            result = runner(
                [
                    "tcli",
                    "publish",
                    "--file",
                    str(package.path),
                    "--config-path",
                    str(package.release.manifest.path),
                ],
                cwd=package.release.mod_dir,
                check=False,
                env={**base_env, "TCLI_AUTH_TOKEN": token},
            )
        except OSError as exc:
            raise RuntimeError(f"Could not run tcli publish: {exc}") from exc
        if result.returncode != 0:
            raise RuntimeError("Publish failed")
        published.append(package)
    return tuple(published)


def execute_thunderstore(
    cli_ctx: CLIContext,
    mod: str | None = None,
    *,
    dry_run: bool = False,
    token: str = "",
    version_lookup: ThunderstoreVersionLookup | None = None,
    tcli_available: Callable[[], bool] | None = None,
    build_client: BuildClient | None = None,
    runner: ProcessRunner = subprocess.run,
) -> ThunderstoreResult:
    """Run the complete preflight, build, package, and optional publish flow."""
    plan = plan_thunderstore(
        cli_ctx,
        mod,
        dry_run=dry_run,
        token=token,
        version_lookup=version_lookup,
        tcli_available=tcli_available,
    )
    built_plan = build_thunderstore(cli_ctx, plan, build_client=build_client, runner=runner)
    packages = package_thunderstore(built_plan, runner=runner)
    published = () if dry_run else publish_thunderstore(packages, token, runner=runner)
    return ThunderstoreResult(built_plan, packages, published)


def parse_vault_listing(listing_path: Path, mod_dir: Path, repo_root: Path) -> VaultListing:
    """Validate and parse one Vault listing and its release changelog."""
    if listing_path.is_symlink():
        raise ValueError("Vault listing must not be a symlink")
    listing_path = listing_path.resolve(strict=False)
    mod_dir = mod_dir.resolve(strict=True)
    repo_root = repo_root.resolve(strict=True)
    if not _path_within(listing_path, mod_dir) or not _path_within(listing_path, repo_root):
        raise ValueError("Vault listing must be inside the mod and repository")
    _require_regular_file(listing_path, "Vault listing")
    try:
        with listing_path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid Vault TOML: {exc}") from exc
    mod_table = data.get("mod")
    if not isinstance(mod_table, dict):
        raise ValueError("Vault TOML requires a [mod] table")
    mod_ref = mod_table.get("mod_ref")
    if not isinstance(mod_ref, str) or not mod_ref.strip() or "/" in mod_ref or "\\" in mod_ref:
        raise ValueError("Vault mod_ref must be a non-empty relative identifier")
    assets = data.get("assets")
    changelog_raw: object = "CHANGELOG.md"
    if isinstance(assets, dict) and assets.get("changelog") is not None:
        changelog_raw = assets.get("changelog")
    changelog = _resolve_manifest_file(
        changelog_raw,
        mod_dir=listing_path.parent,
        repo_root=repo_root,
        label="assets.changelog",
    )
    _require_regular_file(changelog, "Vault changelog")
    return VaultListing(listing_path, changelog, mod_ref.strip())


def _vault_mod_ids(cli_ctx: CLIContext, mod: str | None) -> tuple[str, ...]:
    from erenshor.application.mods import local_workflow

    if mod is not None:
        try:
            lookup_mod(mod)
        except KeyError as exc:
            raise ValueError(f"Unknown mod: {mod}") from exc
        listing = local_workflow.mod_dir(cli_ctx, mod) / "vault" / "vault.toml"
        if not listing.is_file():
            raise ValueError(f"{mod} has no vault/vault.toml listing")
        return (mod,)
    return tuple(
        definition.mod_id
        for definition in iter_mods()
        if (local_workflow.mod_dir(cli_ctx, definition.mod_id) / "vault" / "vault.toml").is_file()
    )


def plan_vault(
    cli_ctx: CLIContext,
    mod: str | None = None,
    *,
    version_lookup: VaultVersionLookup | None = None,
) -> VaultPlan:
    """Validate every eligible Vault listing and compute immutable release plans."""
    from erenshor.application.mods import local_workflow

    lookup_version = get_vault_version if version_lookup is None else version_lookup
    releases: list[VaultRelease] = []
    for mod_id in _vault_mod_ids(cli_ctx, mod):
        mod_dir = local_workflow.mod_dir(cli_ctx, mod_id).resolve(strict=False)
        listing = parse_vault_listing(mod_dir / "vault" / "vault.toml", mod_dir, cli_ctx.repo_root)
        definition = lookup_mod(mod_id)
        version = lookup_version(listing.mod_ref)
        changelog_text = listing.changelog.read_text()
        headings = [line for line in changelog_text.splitlines() if line.startswith("## v")]
        changelog_version = headings[0].removeprefix("## v").strip() if headings else ""
        dll = local_workflow.mod_output_dir(cli_ctx, mod_id, "lunaris") / definition.dll_name
        releases.append(VaultRelease(mod_id, mod_dir, listing, version, dll, changelog_version))
    return VaultPlan(tuple(releases))


def build_vault(
    cli_ctx: CLIContext,
    plan: VaultPlan,
    *,
    build_client: BuildClient | None = None,
    runner: ProcessRunner = subprocess.run,
) -> VaultResult:
    """Build each planned Vault release using the Lunaris target."""
    if build_client is None:
        from erenshor.application.mods import local_workflow

        build_client = local_workflow.build_mods
    for release in plan.releases:
        result = build_client(
            cli_ctx,
            release.mod_id,
            version=release.version,
            loader="lunaris",
            runner=runner,
        )
        if result is not None:
            failed = tuple(getattr(result, "failed", ()))
            issues = tuple(getattr(result, "artifact_issues", ()))
            if failed:
                raise RuntimeError(f"Build failed for: {', '.join(str(value) for value in failed)}")
            if issues:
                raise ValueError("built artifact verification failed")
    return VaultResult(plan)


def execute_vault(
    cli_ctx: CLIContext,
    mod: str | None = None,
    *,
    version_lookup: VaultVersionLookup | None = None,
    build_client: BuildClient | None = None,
    runner: ProcessRunner = subprocess.run,
) -> VaultResult:
    """Run Vault listing validation, planning, and Lunaris build preparation."""
    plan = plan_vault(cli_ctx, mod, version_lookup=version_lookup)
    return build_vault(cli_ctx, plan, build_client=build_client, runner=runner)
