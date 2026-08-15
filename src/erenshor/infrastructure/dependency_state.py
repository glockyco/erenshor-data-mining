"""Repository dependency-state validation helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from erenshor.infrastructure.dotnet_projects import MAINTAINED_DOTNET_RESTORE_TARGETS

_ACTION_REFERENCE = re.compile(r"^\s*(?:-\s*)?uses:\s*[\"']?(?P<target>[^\"'#\s]+)")
_COMMIT_SHA = re.compile(r"[0-9a-fA-F]{40}")
_NIX_UPDATER_WORKFLOW = ".github/workflows/update-nix-dependencies.yml"
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


def nix_updater_ownership_violations(repo_root: Path) -> tuple[str, ...]:
    """Return conflicts between Renovate and the dedicated Nix updater."""
    violations: list[str] = []
    renovate_path = repo_root / "renovate.json"
    try:
        renovate = json.loads(renovate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return (f"renovate.json cannot be read: {error}",)

    rules = renovate.get("packageRules", [])
    if not isinstance(rules, list):
        return ("renovate.json packageRules must be a list",)

    def manager_is_reserved(manager: str, dependency_type: str | None = None) -> bool:
        for rule in rules:
            if not isinstance(rule, dict) or rule.get("enabled") is not False:
                continue
            managers = rule.get("matchManagers", [])
            if manager not in managers:
                continue
            if dependency_type is None or dependency_type in rule.get("matchDepTypes", []):
                return True
        return False

    if not manager_is_reserved("nix"):
        violations.append("Renovate must disable the nix manager")
    if not manager_is_reserved("npm", "packageManager"):
        violations.append("Renovate must reserve npm packageManager assertions for the Nix updater")

    workflow_path = repo_root / _NIX_UPDATER_WORKFLOW
    if not workflow_path.is_file():
        violations.append(f"{_NIX_UPDATER_WORKFLOW} is missing")
        return tuple(violations)

    workflow = workflow_path.read_text(encoding="utf-8")
    required_fragments = {
        "nix flake update": "refresh flake.lock",
        "nix run .#sync-pnpm-version": "synchronize the pnpm assertion",
        "automation/update-nix-dependencies": "use one stable proposal branch",
        "flake.lock\n            package.json": "commit only flake state and its pnpm assertion",
        "gh workflow run ci.yml": "dispatch canonical CI for the proposal",
    }
    for fragment, requirement in required_fragments.items():
        if fragment not in workflow:
            violations.append(f"{_NIX_UPDATER_WORKFLOW} must {requirement}")

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
