"""Repository dependency-state validation helpers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from erenshor.infrastructure.dotnet_projects import MAINTAINED_DOTNET_RESTORE_TARGETS

_ACTION_REFERENCE = re.compile(r"^\s*(?:-\s*)?uses:\s*[\"']?(?P<target>[^\"'#\s]+)")
_COMMIT_SHA = re.compile(r"[0-9a-fA-F]{40}")
_ROOT_DEPENDENCY_FILES = (
    ".config/dotnet-tools.json",
    "flake.lock",
    "flake.nix",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "renovate.json",
    "src/Directory.Build.props",
    "src/Directory.Packages.props",
    "src/mods/nuget.config",
    "uv.lock",
)


def dependency_state_paths() -> tuple[str, ...]:
    """Return every authoritative dependency manifest and lock path."""
    paths = set(_ROOT_DEPENDENCY_FILES)
    for target in MAINTAINED_DOTNET_RESTORE_TARGETS:
        paths.add(target.project)
        if target.lock_file is not None:
            paths.add(target.lock_file)
    return tuple(sorted(paths))


def dependency_state_snapshot(repo_root: Path) -> dict[str, str | None]:
    """Hash dependency files so validators cannot silently rewrite committed state."""
    snapshot: dict[str, str | None] = {}
    for relative_path in dependency_state_paths():
        path = repo_root / relative_path
        snapshot[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return snapshot


def immutable_action_reference_violations(repo_root: Path) -> tuple[str, ...]:
    """Return GitHub workflow Action references that are not full commit SHAs."""
    workflows = repo_root / ".github" / "workflows"
    violations: list[str] = []
    for path in sorted((*workflows.glob("*.yml"), *workflows.glob("*.yaml"))):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = _ACTION_REFERENCE.match(line)
            if match is None:
                continue
            target = match.group("target")
            if target.startswith("./"):
                continue
            if "@" not in target:
                violations.append(f"{path.relative_to(repo_root)}:{line_number}: {target} has no commit ref")
                continue
            reference = target.rsplit("@", 1)[1]
            if _COMMIT_SHA.fullmatch(reference) is None:
                violations.append(
                    f"{path.relative_to(repo_root)}:{line_number}: {target} does not use a full commit SHA"
                )
    return tuple(violations)


def locked_nuget_restore_commands() -> tuple[tuple[str, ...], ...]:
    """Build one force-evaluated locked restore command per maintained lock graph."""
    commands: list[tuple[str, ...]] = []
    for target in MAINTAINED_DOTNET_RESTORE_TARGETS:
        if target.lock_file is None:
            continue
        properties = tuple(f"-p:{name}={value}" for name, value in target.properties)
        commands.append(
            (
                "dotnet",
                "restore",
                target.project,
                "--locked-mode",
                "--force-evaluate",
                *properties,
            )
        )
    return tuple(commands)
