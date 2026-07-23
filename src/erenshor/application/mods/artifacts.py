"""Static and built verification for companion-mod distribution artifacts.

The verifier deliberately owns no process execution and does not import the CLI.  It
is usable by both the static ``test mods`` preflight and the post-build gate.
"""

from __future__ import annotations

import re
import tomllib
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Keep this list in sync with the game assemblies copied by ``mod setup``.  The
# names are intentionally lower-cased for case-insensitive package/output checks.
_REQUIRED_DLLS = (
    "Assembly-CSharp.dll",
    "UnityEngine.dll",
    "UnityEngine.CoreModule.dll",
    "UnityEngine.InputLegacyModule.dll",
    "UnityEngine.IMGUIModule.dll",
    "UnityEngine.UIModule.dll",
    "UnityEngine.UI.dll",
    "UnityEngine.TextRenderingModule.dll",
    "UnityEngine.AIModule.dll",
    "UnityEngine.PhysicsModule.dll",
    "Unity.TextMeshPro.dll",
    "com.rlabrecque.steamworks.net.dll",
)
REQUIRED_DLLS = _REQUIRED_DLLS
_FORBIDDEN_DLLS = frozenset(name.casefold() for name in (*_REQUIRED_DLLS, "BepInEx.dll", "Lunaris.dll", "0Harmony.dll"))


def is_forbidden_runtime_dll(name: str) -> bool:
    """Return whether a DLL is a game/loader runtime that must not ship."""
    return name.casefold() in _FORBIDDEN_DLLS


_KNOWN_VAULT_TAGS = frozenset(
    {
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
)
_THUNDERSTORE_DEPENDENCIES = {"BepInEx-BepInExPack": "5.4.2304"}
_CALVER_HEADING = re.compile(r"^## v?(\d{4})\.(\d{3,4})\.(\d+)(?:\s|$)")


@dataclass(frozen=True)
class ModArtifactSpec:
    """Catalog information needed to verify one mod's artifacts."""

    mod_id: str
    directory: Path
    display_name: str
    dll_name: str
    loaders: tuple[str, ...]
    public: bool
    thunderstore_id: str | None
    thunderstore_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtifactIssue:
    """One deterministic artifact verification finding."""

    mod_id: str
    check: str
    detail: str


@dataclass(frozen=True)
class _CopyDeclaration:
    source_name: str
    source: Path | None
    package_path: str | None
    target_error: str | None = None


def _issue(spec: ModArtifactSpec, check: str, detail: str) -> ArtifactIssue:
    return ArtifactIssue(spec.mod_id, check, detail)


def _repo_path(repo_root: Path, raw: Path) -> Path:
    """Resolve a catalog path without following an owned symlink first."""
    return raw if raw.is_absolute() else repo_root / raw


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except (FileNotFoundError, OSError, ValueError):
        return False
    return True


def _symlink_component(path: Path, root: Path) -> Path | None:
    """Return the first symlink component below root, if one exists."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return path if path.is_symlink() else None
    current = root
    for component in relative.parts:
        current /= component
        try:
            if current.is_symlink():
                return current
        except OSError:
            return current
    return None


def _normal_relative(
    raw: object,
    *,
    allow_parent: bool = False,
    allow_trailing: bool = False,
    allow_leading_dot: bool = True,
) -> PurePosixPath:
    """Validate a repository/package relative POSIX path and normalize ``./``.

    Owned source paths may opt into a leading ``./``. Package targets never
    may. Package targets may conventionally opt into one trailing slash. All
    other empty, dot, traversal, Windows, absolute, and drive-like forms are
    rejected.
    """
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError("must be a relative POSIX path")
    if raw.startswith("/") or ":" in raw:
        raise ValueError("must be a relative POSIX path")
    if raw.endswith("/"):
        if not allow_trailing:
            raise ValueError("must be a normalized relative POSIX path")
        raw = raw[:-1]
    if raw.startswith("./"):
        if not allow_leading_dot:
            raise ValueError("must be a normalized relative POSIX path")
        raw = raw[2:]
    if not raw or raw.startswith("/"):
        raise ValueError("must be a normalized relative POSIX path")
    parts = raw.split("/")
    if any(not part or part == "." for part in parts):
        raise ValueError("must be a normalized relative POSIX path")
    if not allow_parent and ".." in parts:
        raise ValueError("must be a normalized relative POSIX path")
    return PurePosixPath(*parts)


def _resolve_owned(
    raw: object,
    *,
    base: Path,
    repo_root: Path,
    allow_parent: bool = False,
    allow_trailing: bool = False,
) -> Path:
    """Resolve an owned path, rejecting escapes and every symlink component."""
    relative = _normal_relative(raw, allow_parent=allow_parent, allow_trailing=allow_trailing)
    candidate = base / Path(*relative.parts)
    if not _is_within(candidate, repo_root):
        raise ValueError("must remain inside the repository")
    link = _symlink_component(candidate, repo_root)
    if link is not None:
        raise ValueError(f"must not use symlink {link}")
    return candidate


def _regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} is not a regular file: {path}")


def _read_toml(path: Path, label: str) -> dict[str, object]:
    _regular_file(path, label)
    try:
        with path.open("rb") as stream:
            value = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: top-level value must be a table")
    return value


def _table(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a table")
    return value


def _string(table: dict[str, object], key: str, label: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return value


def _tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _parse_project(project: Path, repo_root: Path) -> tuple[str | None, tuple[tuple[str, Path, bool], ...]]:
    try:
        root = ET.parse(project).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ValueError(f"invalid project XML: {exc}") from exc

    assembly_name: str | None = None
    root_namespace: str | None = None
    resources: list[tuple[str, Path, bool]] = []
    for element in root.iter():
        name = _tag_name(element)
        if name == "AssemblyName" and element.text and assembly_name is None:
            assembly_name = element.text.strip()
        elif name == "RootNamespace" and element.text and root_namespace is None:
            root_namespace = element.text.strip()
        elif name == "EmbeddedResource":
            include = element.attrib.get("Include")
            if not include:
                raise ValueError("EmbeddedResource must have an Include")
            try:
                source = _resolve_owned(
                    include,
                    base=project.parent,
                    repo_root=repo_root,
                    allow_parent=True,
                )
                source_valid = True
            except ValueError:
                source = project.parent / Path(include)
                source_valid = False
            logical_name = element.attrib.get("LogicalName")
            if not logical_name:
                for child in element:
                    if _tag_name(child) == "LogicalName" and child.text:
                        logical_name = child.text.strip()
                        break
            if not logical_name:
                # SDK default logical names use the root namespace and the
                # relative include path with directory separators as dots.
                include_path = Path(include)
                relative_name = ".".join(include_path.parts)
                logical_name = ".".join(part for part in (root_namespace, relative_name) if part)
            resources.append((logical_name, source, source_valid))
    return assembly_name, tuple(resources)


def _load_project(
    spec: ModArtifactSpec, directory: Path, repo_root: Path
) -> tuple[Path | None, str | None, tuple[tuple[str, Path, bool], ...], ArtifactIssue | None]:
    expected_project = directory / f"{directory.name}.csproj"
    if expected_project.is_symlink() or not expected_project.is_file():
        return None, None, (), _issue(spec, "catalog-project", f"missing project: {expected_project}")
    try:
        assembly_name, resources = _parse_project(expected_project, repo_root)
    except ValueError as exc:
        return expected_project, None, (), _issue(spec, "catalog-project", str(exc))
    return expected_project, assembly_name, resources, None


def _manifest_identity(spec: ModArtifactSpec, thunderstore: dict[str, object]) -> None:
    package = _table(thunderstore.get("package"), "package")
    if not spec.thunderstore_id or spec.thunderstore_id.count("/") != 1:
        raise ValueError("catalog Thunderstore identity must be namespace/name")
    expected_namespace, expected_name = spec.thunderstore_id.split("/", 1)
    namespace = _string(package, "namespace", "package")
    name = _string(package, "name", "package")
    if namespace != expected_namespace or name != expected_name:
        raise ValueError(f"expected package identity {expected_namespace}/{expected_name}, got {namespace}/{name}")
    _table(thunderstore.get("build"), "build")


def _resolve_manifest_asset(raw: object, *, base: Path, repo_root: Path, label: str) -> Path:
    try:
        path = _resolve_owned(raw, base=base, repo_root=repo_root)
        _regular_file(path, label)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc
    return path


def _parse_thunderstore_copies(
    spec: ModArtifactSpec,
    build: dict[str, object],
    *,
    mod_dir: Path,
    repo_root: Path,
) -> tuple[tuple[_CopyDeclaration, ...], tuple[str, ...], tuple[str, ...], str | None]:
    raw_copies = build.get("copy", [])
    if not isinstance(raw_copies, list):
        return (), (), (), "build.copy must be an array of tables"
    declarations: list[_CopyDeclaration] = []
    forbidden: list[str] = []
    package_paths: list[str] = []
    expected_names = spec.thunderstore_files or (spec.dll_name,)
    expected_counts = Counter(expected_names)
    actual_names: list[str] = []
    errors: list[str] = []
    expected_target: str | None = None
    if spec.thunderstore_id and spec.thunderstore_id.count("/") == 1:
        expected_target = f"plugins/{spec.thunderstore_id.split('/', 1)[1]}"
    for index, raw_entry in enumerate(raw_copies):
        if not isinstance(raw_entry, dict):
            errors.append(f"build.copy[{index}] must be a table")
            continue
        source_raw = raw_entry.get("source")
        source_name = Path(source_raw).name if isinstance(source_raw, str) else "<invalid>"
        source: Path | None = None
        source_relative: PurePosixPath | None = None
        try:
            source_relative = _normal_relative(source_raw)
            source = _resolve_owned(source_raw, base=mod_dir, repo_root=repo_root)
            if source.exists():
                _regular_file(source, f"build.copy[{index}].source")
            elif source.is_symlink():
                raise ValueError(f"build.copy[{index}].source must not be a symlink")
        except ValueError as exc:
            errors.append(f"build.copy[{index}].source: {exc}")
            source = None
        actual_names.append(source_name)
        if is_forbidden_runtime_dll(source_name):
            forbidden.append(f"build.copy[{index}].source declares forbidden DLL {source_name}")
        target_raw = raw_entry.get("target")
        package_path: str | None = None
        target_error: str | None = None
        try:
            target = _normal_relative(
                target_raw,
                allow_trailing=True,
                allow_leading_dot=False,
            )
            package_path = (target / source_name).as_posix()
            package_paths.append(package_path)
            if source_name in expected_counts and source_relative is not None:
                expected_source = f"bin/Debug/netstandard2.1/bepinex/{source_name}"
                if source_relative.as_posix() != expected_source:
                    actual_source = source_relative.as_posix()
                    errors.append(f"build.copy[{index}] expected source is {expected_source!r}, got {actual_source!r}")
            if source_name in expected_counts and expected_target is not None and target.as_posix() != expected_target:
                errors.append(f"build.copy[{index}] expected target is {expected_target!r}, got {target.as_posix()!r}")
            if is_forbidden_runtime_dll(source_name):
                forbidden.append(f"build.copy[{index}] package path declares forbidden DLL {package_path}")
        except ValueError as exc:
            target_error = str(exc)
            errors.append(f"build.copy[{index}].target: {exc}")
        declarations.append(_CopyDeclaration(source_name, source, package_path, target_error))
    actual_counts = Counter(actual_names)
    if actual_counts != expected_counts:
        missing = sorted((expected_counts - actual_counts).elements())
        unexpected = sorted((actual_counts - expected_counts).elements())
        errors.append(f"build.copy inventory mismatch: missing={missing!r}, unexpected={unexpected!r}")
    return tuple(declarations), tuple(forbidden), tuple(package_paths), "; ".join(errors) if errors else None


def _validate_package_paths(package_paths: Iterable[str]) -> str | None:
    reserved = {"manifest.json", "icon.png", "readme.md", "changelog.md"}
    seen: set[str] = set(reserved)
    duplicates: list[str] = []
    for path in package_paths:
        normalized = path.casefold()
        if normalized in seen:
            duplicates.append(path)
        seen.add(normalized)
    return f"duplicate package paths: {', '.join(duplicates)}" if duplicates else None


def _manifest_dependencies(thunderstore: dict[str, object]) -> None:
    package = _table(thunderstore.get("package"), "package")
    dependencies = package.get("dependencies")
    if not isinstance(dependencies, dict) or any(
        dependencies.get(name) != version for name, version in _THUNDERSTORE_DEPENDENCIES.items()
    ):
        raise ValueError("package.dependencies must include BepInEx-BepInExPack = 5.4.2304")


def _parse_vault_identity(spec: ModArtifactSpec, vault: dict[str, object]) -> None:
    mod = _table(vault.get("mod"), "mod")
    package = _table(vault.get("package"), "package")
    display_name = _string(mod, "name", "mod")
    mod_ref = _string(mod, "mod_ref", "mod")
    main_file = _string(package, "main_file", "package")
    if display_name != spec.display_name or mod_ref != spec.mod_id or main_file != spec.dll_name:
        raise ValueError(
            f"expected mod/name/main {spec.mod_id}/{spec.display_name}/{spec.dll_name}, "
            f"got {mod_ref}/{display_name}/{main_file}"
        )
    _normal_relative(main_file)
    if "/" in main_file or is_forbidden_runtime_dll(main_file):
        raise ValueError(f"package.main_file is not a permitted plugin DLL: {main_file}")

    tags = mod.get("tags")
    if not isinstance(tags, list) or any(not isinstance(tag, str) or tag not in _KNOWN_VAULT_TAGS for tag in tags):
        raise ValueError("mod.tags contains an unknown Vault tag slug")
    asset_files = package.get("asset_files")
    if not isinstance(asset_files, list) or asset_files:
        raise ValueError("package.asset_files must be an empty list; Vault ships only the plugin main_file")
    if any(not isinstance(asset, str) for asset in asset_files):
        raise ValueError("package.asset_files must contain only path strings")


def _validate_asset_changelog(path: Path, label: str) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{label}: could not read changelog: {exc}") from exc
    headings = [line for line in text.splitlines() if line.startswith("## ") and not line.startswith("### ")]
    match = _CALVER_HEADING.fullmatch(headings[0]) if headings else None
    valid_calver = False
    if match is not None:
        date_code = match.group(2)
        month = int(date_code[:-2])
        day = int(date_code[-2:])
        valid_calver = 1 <= month <= 12 and 1 <= day <= 31
    if not valid_calver:
        raise ValueError(f"{label} must start its version history with numeric ## vX.Y.Z")


def _owned_relative_to(path: Path, base: Path) -> tuple[str, ...] | None:
    try:
        return path.relative_to(base).parts
    except ValueError:
        return None


def _run_static_spec(spec: ModArtifactSpec, repo_root: Path) -> tuple[ArtifactIssue, ...]:
    issues: list[ArtifactIssue] = []
    raw_directory = _repo_path(repo_root, Path(spec.directory))
    directory = raw_directory
    if (
        not _is_within(directory, repo_root)
        or _symlink_component(directory, repo_root) is not None
        or not directory.is_dir()
    ):
        issues.append(
            _issue(spec, "catalog-directory", f"catalog directory is not a repository directory: {directory}")
        )
        # All subsequent checks are artifact-local and cannot be meaningful.
        return tuple(issues)

    project, assembly_name, resources, project_issue = _load_project(spec, directory, repo_root)
    if project_issue is not None:
        issues.append(project_issue)
    if project is not None and assembly_name is not None and assembly_name != Path(spec.dll_name).stem:
        issues.append(
            _issue(
                spec,
                "catalog-assembly-name",
                f"AssemblyName is {assembly_name!r}, expected {Path(spec.dll_name).stem!r}",
            )
        )
    if project is not None and assembly_name is None and project_issue is None:
        issues.append(_issue(spec, "catalog-assembly-name", "project does not declare AssemblyName"))

    missing_resources = [
        logical_name
        for logical_name, source, source_valid in resources
        if not source_valid or source.is_symlink() or not source.is_file() or not _is_within(source, repo_root)
    ]
    if missing_resources:
        issues.append(
            _issue(spec, "embedded-resources", f"missing or unsafe embedded sources: {', '.join(missing_resources)}")
        )
    resource_names: set[str] = set()
    duplicate_resources: list[str] = []
    for logical_name, _, _ in resources:
        if logical_name in resource_names:
            duplicate_resources.append(logical_name)
        resource_names.add(logical_name)
    if duplicate_resources:
        issues.append(
            _issue(spec, "embedded-resources", f"duplicate logical resource names: {', '.join(duplicate_resources)}")
        )
    if spec.public:
        thunderstore_path = directory / "thunderstore.toml"
        vault_path = directory / "vault" / "vault.toml"
        try:
            thunderstore = _read_toml(thunderstore_path, "Thunderstore manifest")
        except ValueError as exc:
            issues.append(_issue(spec, "thunderstore-identity", str(exc)))
            thunderstore = None
        try:
            vault = _read_toml(vault_path, "Vault manifest")
        except ValueError as exc:
            issues.append(_issue(spec, "vault-identity", str(exc)))
            vault = None

        thunderstore_changelog: Path | None = None
        vault_changelog: Path | None = None
        thunderstore_icon: Path | None = None
        vault_icon: Path | None = None
        if thunderstore is not None:
            try:
                _manifest_identity(spec, thunderstore)
            except ValueError as exc:
                issues.append(_issue(spec, "thunderstore-identity", str(exc)))
            try:
                _manifest_dependencies(thunderstore)
            except ValueError as exc:
                issues.append(_issue(spec, "thunderstore-dependencies", str(exc)))
            build: dict[str, object] | None = None
            asset_errors: list[str] = []
            try:
                build = _table(thunderstore.get("build"), "build")
            except ValueError as exc:
                asset_errors.append(str(exc))
            if build is not None:
                for key in ("icon", "readme", "changelog"):
                    try:
                        path = _resolve_manifest_asset(
                            build.get(key), base=directory, repo_root=repo_root, label=f"build.{key}"
                        )
                    except ValueError as exc:
                        asset_errors.append(str(exc))
                        continue
                    if key == "icon":
                        thunderstore_icon = path
                    if key == "changelog":
                        thunderstore_changelog = path
                # outdir is optional at static preflight; when present it is
                # still a strict repo-contained path and cannot be a symlink.
                if build.get("outdir") is not None:
                    try:
                        outdir = _resolve_owned(
                            build.get("outdir"), base=directory, repo_root=repo_root, allow_trailing=True
                        )
                        if outdir.exists() and (outdir.is_symlink() or not outdir.is_dir()):
                            raise ValueError(f"build.outdir is not a directory: {outdir}")
                    except ValueError as exc:
                        asset_errors.append(str(exc))
            if asset_errors:
                issues.append(_issue(spec, "thunderstore-assets", "; ".join(asset_errors)))
            try:
                build = _table(thunderstore.get("build"), "build")
                copies, forbidden, package_paths, copy_error = _parse_thunderstore_copies(
                    spec, build, mod_dir=directory, repo_root=repo_root
                )
                if copy_error:
                    issues.append(_issue(spec, "thunderstore-copy-declarations", copy_error))
                if forbidden:
                    issues.append(_issue(spec, "thunderstore-forbidden-dll", "; ".join(forbidden)))
                package_error = _validate_package_paths(package_paths)
                if package_error:
                    issues.append(_issue(spec, "thunderstore-package-paths", package_error))
                # Keep ``copies`` consumed here so malformed declarations do
                # not accidentally appear valid merely because sources exist.
                del copies
            except ValueError as exc:
                issues.append(_issue(spec, "thunderstore-copy-declarations", str(exc)))
        if vault is not None:
            try:
                _parse_vault_identity(spec, vault)
            except ValueError as exc:
                issues.append(_issue(spec, "vault-identity", str(exc)))
            assets: dict[str, object] | None = None
            asset_errors = []
            try:
                assets = _table(vault.get("assets"), "assets")
            except ValueError as exc:
                asset_errors.append(str(exc))
            if assets is not None:
                for key in ("full_description", "changelog", "icon"):
                    try:
                        path = _resolve_manifest_asset(
                            assets.get(key),
                            base=directory / "vault",
                            repo_root=repo_root,
                            label=f"assets.{key}",
                        )
                    except ValueError as exc:
                        asset_errors.append(str(exc))
                        continue
                    if key == "changelog":
                        vault_changelog = path
                    elif key == "icon":
                        vault_icon = path
            if asset_errors:
                issues.append(_issue(spec, "vault-assets", "; ".join(asset_errors)))

        if thunderstore_icon is not None and vault_icon is not None:
            try:
                if thunderstore_icon.read_bytes() != vault_icon.read_bytes():
                    issues.append(
                        _issue(spec, "icon-consistency", "Thunderstore and Vault icons must have identical bytes")
                    )
            except OSError as exc:
                issues.append(_issue(spec, "icon-consistency", f"could not compare published icons: {exc}"))

        if thunderstore_changelog is not None or vault_changelog is not None:
            ownership_errors: list[str] = []
            if thunderstore_changelog is None:
                ownership_errors.append("Thunderstore changelog is unavailable")
            else:
                relative = _owned_relative_to(thunderstore_changelog, directory)
                if relative is None or not relative or relative[0] != "thunderstore":
                    ownership_errors.append("Thunderstore changelog must be owned under thunderstore/")
            if vault_changelog is None:
                ownership_errors.append("Vault changelog is unavailable")
            else:
                relative = _owned_relative_to(vault_changelog, directory)
                if relative is None or not relative or relative[0] != "vault":
                    ownership_errors.append("Vault changelog must be owned under vault/")
            if (
                thunderstore_changelog is not None
                and vault_changelog is not None
                and thunderstore_changelog == vault_changelog
            ):
                ownership_errors.append("Thunderstore and Vault changelogs must be separately owned")
            if ownership_errors:
                issues.append(_issue(spec, "changelog-ownership", "; ".join(ownership_errors)))
            heading_errors: list[str] = []
            for label, changelog_path in (
                ("Thunderstore", thunderstore_changelog),
                ("Vault", vault_changelog),
            ):
                if changelog_path is not None:
                    try:
                        _validate_asset_changelog(changelog_path, label)
                    except ValueError as exc:
                        heading_errors.append(str(exc))
            if heading_errors:
                issues.append(_issue(spec, "changelog-heading", "; ".join(heading_errors)))
    return tuple(issues)


def verify_static_mod_artifacts(repo_root: Path, specs: Sequence[ModArtifactSpec]) -> tuple[ArtifactIssue, ...]:
    """Verify catalog/manifests/resources without requiring build copy sources."""
    try:
        root = Path(repo_root).resolve(strict=True)
    except (FileNotFoundError, OSError):
        root = Path(repo_root).absolute()
    issues: list[ArtifactIssue] = []
    for spec in specs:
        issues.extend(_run_static_spec(spec, root))
    return tuple(issues)


def _static_resources(spec: ModArtifactSpec, repo_root: Path) -> tuple[tuple[str, Path, bool], ...]:
    directory = _repo_path(repo_root, Path(spec.directory))
    project = directory / f"{directory.name}.csproj"
    if not project.is_file() or project.is_symlink():
        return ()
    try:
        _, resources = _parse_project(project, repo_root)
    except ValueError:
        return ()
    return resources


def _run_built_spec(
    spec: ModArtifactSpec, repo_root: Path, targets: Sequence[tuple[str, str]]
) -> tuple[ArtifactIssue, ...]:
    issues: list[ArtifactIssue] = []
    directory = _repo_path(repo_root, Path(spec.directory))
    selected = [loader for mod_id, loader in targets if mod_id == spec.mod_id]
    for loader in selected:
        if loader not in spec.loaders:
            issues.append(_issue(spec, "built-output-dll", f"unsupported loader target {loader!r}"))
            continue
        output_dir = directory / "bin" / "Debug" / "netstandard2.1" / loader
        dll_path = output_dir / spec.dll_name
        output_valid = True
        try:
            if not _is_within(output_dir, repo_root):
                raise ValueError("build output is outside the repository")
            link = _symlink_component(output_dir, repo_root)
            if link is not None:
                raise ValueError(f"build output uses symlink {link}")
            _regular_file(dll_path, "expected plugin DLL")
        except ValueError as exc:
            output_valid = False
            issues.append(_issue(spec, "built-output-dll", f"{loader}: {exc}"))
        if not output_dir.is_dir() or output_dir.is_symlink():
            continue
        forbidden: list[str] = []
        try:
            for path in output_dir.rglob("*"):
                if path.is_file() and is_forbidden_runtime_dll(path.name):
                    forbidden.append(path.relative_to(output_dir).as_posix())
        except OSError as exc:
            issues.append(_issue(spec, "built-forbidden-dll", f"{loader}: could not inspect output: {exc}"))
        if forbidden:
            issues.append(
                _issue(spec, "built-forbidden-dll", f"{loader}: forbidden runtime DLLs: {', '.join(sorted(forbidden))}")
            )
        resources = _static_resources(spec, repo_root)
        if resources and output_valid:
            try:
                plugin_bytes = dll_path.read_bytes()
            except OSError as exc:
                issues.append(_issue(spec, "built-resources", f"{loader}: could not read plugin DLL: {exc}"))
                continue
            missing = [name for name, _, _ in resources if name.encode("utf-8") not in plugin_bytes]
            if missing:
                issues.append(
                    _issue(spec, "built-resources", f"{loader}: missing logical resource names: {', '.join(missing)}")
                )
    return tuple(issues)


def verify_built_mod_artifacts(
    repo_root: Path,
    specs: Sequence[ModArtifactSpec],
    targets: Sequence[tuple[str, str]],
) -> tuple[ArtifactIssue, ...]:
    """Verify successful loader outputs selected by ``targets``."""
    try:
        root = Path(repo_root).resolve(strict=True)
    except (FileNotFoundError, OSError):
        root = Path(repo_root).absolute()
    issues: list[ArtifactIssue] = []
    known = {spec.mod_id for spec in specs}
    for spec in specs:
        issues.extend(_run_built_spec(spec, root, targets))
    for mod_id, loader in targets:
        if mod_id not in known:
            issues.append(ArtifactIssue(mod_id, "built-output-dll", f"unknown mod target {mod_id!r} ({loader})"))
    return tuple(issues)


def format_artifact_issues(issues: Iterable[ArtifactIssue]) -> str:
    """Render issues for CLI diagnostics, preserving supplied order."""
    return "\n".join(f"{issue.mod_id} [{issue.check}]: {issue.detail}" for issue in issues)


__all__ = [
    "REQUIRED_DLLS",
    "ArtifactIssue",
    "ModArtifactSpec",
    "format_artifact_issues",
    "is_forbidden_runtime_dll",
    "verify_built_mod_artifacts",
    "verify_static_mod_artifacts",
]
