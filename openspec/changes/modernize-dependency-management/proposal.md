## Why

Dependency updates currently cross conflicting package-manager boundaries, use floating .NET versions, and can report success after an external upload fails. The repository needs one coherent dependency model so every update is reproducible, reviewable, and validated by the same toolchain used for development.

## What Changes

- Establish one authoritative manifest and lock boundary for each ecosystem.
- Keep Nix as the canonical owner of development and CI toolchain versions.
- Make the root pnpm workspace the only JavaScript dependency boundary.
- Centralize NuGet versions and add locked restore for maintained C# projects.
- Keep `pyproject.toml` and `uv.lock` as the Python dependency boundary.
- Assign `flake.lock` to the dedicated Nix updater and all other supported manifests to Renovate.
- Replace broad update grouping with compatibility-based groups and explicit approval for major updates.
- Make dependency validation fail closed in CI, including coverage upload and lock freshness.
- Harden `main` so required checks also apply to administrators and force pushes are disabled.
- Pin third-party GitHub Actions to immutable commit SHAs and let Renovate update their digests.
- **BREAKING**: Remove the nested Maps locks, the standalone item-exporter Bun lock, duplicate .NET tool manifests and NuGet source files, floating NuGet ranges, and the unused `@sveltejs/adapter-auto` dependency.
- **BREAKING**: Recreate the current Renovate queue after the new ownership rules replace its generated branches.

### Goals

- One owner for every dependency declaration, lockfile, generated branch, and required status.
- Repeatable dependency resolution on developer machines and in CI.
- Small update pull requests that match real compatibility and validation boundaries.
- Manual review for major migrations, with immediate handling for security updates.
- A clean migration that removes obsolete state instead of preserving compatibility paths.

### Non-goals

- Automerge dependency pull requests.
- Replace the project CLI with direct package-manager workflows.
- Change game-data, mod runtime, map behavior, or deployment targets.
- Combine all ecosystems under one language package manager.
- Add a merge queue or mandatory peer review to this solo-maintainer repository.

### Migration Boundary

The migration changes dependency manifests, lockfiles, CI, Renovate policy, GitHub Actions references, repository settings, and related guidance. It does not modify shipped-game files, generated game data, deployed artifacts, or application behavior.

## Capabilities

### New Capabilities

- `dependency-management`: Defines authoritative dependency state, automated update behavior, validation gates, and protected merge requirements for every maintained ecosystem.

### Modified Capabilities

None.

## Impact

Affected files include `flake.nix`, `flake.lock`, `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`, the removed `src/tools/item-export/bun.lock`, `pyproject.toml`, `uv.lock`, C# project files, new NuGet central-management files, `.config/dotnet-tools.json`, `.github/workflows/ci.yml`, `renovate.json`, shared Renovate policy, and dependency guidance. GitHub branch protection also changes. Existing Renovate pull requests become obsolete and must be recreated after the migration.
