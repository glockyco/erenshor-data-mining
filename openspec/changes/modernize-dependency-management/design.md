## Context

See `proposal.md` for motivation and scope. The repository has four dependency ecosystems plus GitHub Actions. Nix already supplies the Python environment, Node 22, pnpm 10, .NET 9 and 10 SDKs, and other development tools to local and CI commands.

The current boundaries are inconsistent:

- The root pnpm workspace includes `src/maps`, but `src/maps` also has npm and pnpm lockfiles.
- The Bun-based item exporter has a second JavaScript lock and is absent from both the root workspace and the Nix development toolchain.
- Python has a sound `pyproject.toml` and `uv.lock` boundary that Nix consumes.
- Maintained C# projects repeat floating package ranges and have no dependency locks.
- Eight identical `dotnet-tools.json` files claim root ownership of the same CSharpier version.
- The shared Renovate preset groups every non-major update across ecosystems and rebases only on conflicts.
- Codecov can reject an upload while the unit job reports success.
- Third-party Actions use mutable tags.
- The protected branch requires current aggregate CI, but administrators can bypass it and force pushes are allowed.

The canonical project command remains `uv run erenshor ...`. Direct package-manager commands remain limited to dependency generation, bootstrap, and validation.

## Goals / Non-Goals

**Goals:**

- Make each dependency file part of one explicit ownership graph.
- Make clean checkout bootstrap and CI consume identical committed state.
- Make update pull requests complete, isolated, and reviewable.
- Keep project-specific update policy in this repository.
- Make external dependency reporting fail closed.
- Use the current CLI verification leaves without bot-specific test paths.

**Non-Goals:**

- Hide all ecosystems behind a custom dependency abstraction.
- Add bot-specific behavior to product code.
- Build or deploy game data during dependency validation.
- Add automerge, a merge queue, or required peer review.
- Centralize package metadata that must remain project-specific, such as `PrivateAssets`, aliases, and loader conditions.

## Decisions

### 1. Use Nix for toolchains and native managers for project dependencies

Nix remains the authoritative source for executable toolchains. Native managers remain authoritative for project dependency graphs.

| Boundary | Declared state | Resolved state | Automated owner |
|---|---|---|---|
| Nix inputs and toolchains | `flake.nix` | `flake.lock` | Dedicated Nix updater |
| Python | `pyproject.toml` | `uv.lock` and the Nix-built environment | Renovate |
| JavaScript workspace | Root and workspace `package.json` files | Root `pnpm-lock.yaml` | Renovate |
| Maintained .NET projects | `src/Directory.Packages.props` plus project metadata | Per-project `packages.lock.json` | Renovate |
| .NET local tools | Root `.config/dotnet-tools.json` | Tool manifest restore | Renovate |
| GitHub Actions | Workflow YAML | Full commit SHAs | Renovate |

The Nix updater must also refresh any exact language-native assertion of a Nix-provided tool. CI compares the asserted pnpm version with `pnpm --version`. Renovate must not update that assertion independently.

Alternatives considered:

- Use Nix for all dependency graphs. Rejected because native lockfiles are required by ecosystem tooling, editors, and dependency bots.
- Let every native manager install its own toolchain. Rejected because local and CI versions would diverge from the existing Nix shell.
- Omit the pnpm package-manager assertion. Rejected because non-Nix tooling and Renovate would not know the intended pnpm version.

### 2. Make the root pnpm workspace the only JavaScript dependency boundary

Delete `src/maps/package-lock.json`, `src/maps/pnpm-lock.yaml`, and `src/tools/item-export/bun.lock`. Keep both project manifests as workspace packages and keep one root `pnpm-lock.yaml`. Add an exact root `packageManager` assertion that matches the Nix-provided pnpm.

The item exporter continues to run on Bun because it uses `bun:sqlite`, but pnpm owns its dependency graph. Add Bun to the Nix development toolchain instead of letting a second package manager own that graph. Remove `@sveltejs/adapter-auto` because the map configuration uses `@sveltejs/adapter-static`. Regenerate the root lock through the Nix shell.

Alternatives considered:

- Give `src/maps` its own independent pnpm workspace. Rejected because root scripts, CI, and the current workspace already treat it as one project.
- Keep the nested npm lock for deployment tooling. Rejected because no active command consumes npm state.
- Keep the item exporter as an independent Bun package boundary. Rejected because Bun is needed only at runtime; pnpm can resolve the same packages through the existing root workspace without a competing lock.

### 3. Keep Python's existing manifest and lock model

Keep compatible lower bounds in `pyproject.toml` and exact resolution in `uv.lock`. Nix continues to build the Python environment from `uv.lock`. Renovate owns Python manifest and lock updates.

Validation must check that `uv.lock` is current before Python behavior tests. Nix remains the only owner of the active environment, so CI does not run `uv sync` into a mutable virtual environment.

Alternative considered:

- Pin every Python dependency exactly in `pyproject.toml`. Rejected because the lock already records exact resolution and the manifest should retain compatible requirements.

### 4. Centralize and lock maintained NuGet dependencies under `src`

Add `src/Directory.Packages.props` with Central Package Management enabled. Move all maintained `PackageReference` versions into this file. Keep reference metadata and loader conditions in each project.

Add `src/Directory.Build.props` to enable package lock generation for maintained projects. Commit `packages.lock.json` for each unconditional project graph. Production mod package references vary by `ModLoader`, so each mod commits `packages.bepinex.lock.json` and `packages.lunaris.lock.json`; a single lock cannot represent both conditional graphs. Mod test projects keep one `packages.lock.json` because their package graph is loader-independent. CI performs locked restore for every maintained graph before native builds and tests.

The central files live under `src`, not the repository root. This prevents them from changing generated decompiled projects under `variants/`.

Remove the seven nested mod and test tool manifests. Keep only root `.config/dotnet-tools.json`, which `dotnet tool restore` can discover from every maintained subdirectory.

Migrate all maintained test projects from `xunit` v2 to `xunit.v3` in one explicit test-toolchain change. Update project output type and runner metadata as required by xUnit v3. Do not ask Renovate to infer the package rename.

Alternatives considered:

- Keep floating package ranges. Rejected because restore can change without a reviewed source change.
- Add only central versions without lockfiles. Rejected because transitive resolution would not have a committed audit boundary.
- Put central files at repository root. Rejected because generated variant projects must remain isolated.

### 5. Separate shared Renovate safety defaults from project policy

The shared preset must contain only reusable safety and scheduling defaults. It must not group unrelated dependencies across repositories. Remove `group:allNonMajor` and the explicit `rebaseWhen: conflicted`. Let Renovate use its branch-protection-aware rebase behavior.

The Erenshor repository config owns:

- enabled managers and explicit Nix exclusions
- dashboard approval for non-security major updates
- immediate vulnerability-alert proposals
- compatibility groups for SvelteKit and Vite, ESLint, deck.gl, .NET test tooling, and GitHub Actions
- ecosystem labels and manual merge policy
- a short release age for non-security updates

Known monorepo packages stay in Renovate's standard monorepo groups. Unrelated Python, JavaScript, NuGet, and Action changes never share a repository-wide group.

The shared preset change requires a coordinated change in `glockyco/renovate-config`. Validate every current consumer before publication. Add project-local rules first where a repository needs custom grouping.

Alternatives considered:

- Override the inherited all-non-major group locally. Rejected because nullifying a broad inherited rule is obscure and preserves a poor shared default.
- Create one pull request per dependency. Rejected because peer-coupled toolchains and monorepos require coordinated updates.
- Automerge patches. Rejected because the maintainer requested manual control and current gates are not yet trustworthy.

### 6. Add one fail-closed dependency-state gate

Add a dependency-state leaf to the canonical `erenshor test` command and CI. It validates:

- flake evaluation and required Nix checks
- Python lock freshness without mutating the Nix environment
- root pnpm frozen install and pnpm assertion consistency
- root .NET tool restore
- locked NuGet restore for every maintained project
- Renovate configuration validity
- immutable third-party Action references

Behavior leaves continue to run unchanged after dependency state is valid. Native tests use the restored locked state and must not perform an untracked dependency upgrade.

`CI Success` remains the single protected aggregate status. The new dependency-state job becomes an explicit dependency of that aggregate. Any future required job must also be added to the aggregate in the same change.

Alternative considered:

- Rely on individual build failures to detect stale dependency state. Rejected because failures then occur late and report the wrong subsystem.

### 7. Use least-privilege OIDC and fail-closed coverage

Set workflow-level permissions to `contents: read`. Grant `id-token: write` only to the unit job. Upgrade Codecov in the same change that enables OIDC and `fail_ci_if_error: true`. Remove the unused `CODECOV_TOKEN` dependency after a successful OIDC upload.

A Codecov service outage blocks the unit job. This is intentional because the workflow currently presents coverage upload as required verification. If coverage is not required, remove the upload from the gate in a separate reviewed policy change instead of silently ignoring failure.

Alternative considered:

- Keep a long-lived repository token. Rejected because OIDC gives short-lived, scoped authentication.

### 8. Pin third-party Actions to immutable commits

Replace every third-party `uses:` tag with a verified full commit SHA and a version comment. Configure Renovate to update these digests through reviewable pull requests.

Alternative considered:

- Keep major-version tags. Rejected because tags are mutable and execute third-party code in privileged CI.

### 9. Enforce protected manual merges

Keep strict required status checks and linear history. Disable force pushes and enable administrator enforcement. Keep required review count at zero for the solo-maintainer workflow. Keep automerge disabled.

Repository settings remain external GitHub state. The migration records and verifies their exact API state. It does not add another settings-management application.

Alternative considered:

- Add one required approval. Rejected because it blocks self-authored maintenance pull requests in a solo repository.

## Risks / Trade-offs

- [Central NuGet files affect unintended projects] → Scope them under `src` and verify generated `variants/` projects do not import them.
- [Per-project NuGet lockfiles add repository churn] → Central versions keep declarations small, while lock diffs provide required transitive auditability.
- [Nix and pnpm assertions drift] → Give the Nix updater ownership of both and fail CI on any mismatch.
- [Shared Renovate changes alter other repositories] → Audit consumers, add needed local rules first, then publish the shared preset change.
- [A compatibility group hides the package that caused a failure] → Group only documented peer or monorepo boundaries. Keep all other majors separate.
- [Codecov availability blocks merges] → Accept fail-closed behavior. Change the policy explicitly if coverage ceases to be required.
- [Resetting Renovate loses useful green branches] → Recreate updates from the clean ownership model rather than carrying ambiguous generated state forward.
- [Locked restore complicates intentional upgrades] → Document one explicit regeneration command and require the resulting lock diffs in the update commit.

## Migration Plan

1. Land OpenSpec configuration and this reviewed change plan.
2. Publish the generic shared Renovate preset after auditing its consumers.
3. Establish repository dependency ownership: remove secondary locks and tool manifests, declare pnpm, and regenerate canonical state.
4. Centralize NuGet versions and add locked restore without changing test framework behavior.
5. Migrate the complete .NET test stack to xUnit v3.
6. Add the dependency-state leaf and make CI dependency resolution fail closed.
7. Move Codecov to least-privilege OIDC and verify an accepted upload.
8. Pin Actions to full SHAs and validate workflow policy.
9. Add project-specific Renovate rules and install the dedicated Nix updater for this repository.
10. Harden branch protection and verify it through the GitHub API.
11. Close or let Renovate supersede the old dependency pull requests. Trigger a fresh update run from clean `main`.
12. Merge regenerated updates one compatibility boundary at a time.

Each numbered repository change is an atomic commit or pull request. The shared preset is a coordinated external pull request.

Rollback uses Git reverts of complete migration commits. Do not restore dual lockfiles or floating ranges as a partial fallback. Restore branch settings from the recorded pre-migration state only if the required CI gate itself is unavailable.
