## 1. Shared Renovate Prerequisite

- [ ] 1.1 Create the coordinated `modernize-shared-renovate-policy` OpenSpec change in `glockyco/renovate-config`.
- [ ] 1.2 Remove repository-wide dependency grouping and conflict-only rebasing from the shared preset.
- [ ] 1.3 Validate the shared preset and audit every repository that extends it.
- [ ] 1.4 Merge the shared preset change before enabling Erenshor project-specific rules.

## 2. Dependency Ownership Cutover

- [x] 2.1 Record the current manifest, lockfile, updater, open-PR, and branch-protection state for migration evidence.
- [ ] 2.2 Add the Nix-matched root pnpm `packageManager` assertion and its version-consistency check.
- [ ] 2.3 Delete both nested Maps lockfiles and the item-exporter Bun lock, add the item exporter to the root workspace, and remove unused `@sveltejs/adapter-auto`.
- [ ] 2.4 Add Bun to the Nix toolchain, regenerate the root pnpm lock for every workspace package, and prove a frozen install from a clean checkout.
- [x] 2.5 Delete the seven duplicate nested .NET tool manifests and prove root manifest discovery from a mod directory.
- [x] 2.6 Run the Maps verification leaf and item-exporter type check, then confirm no active workflow reads a removed lockfile.
- [x] 2.7 Commit the ownership cutover as `chore(deps): establish canonical dependency boundaries`.

## 3. Reproducible NuGet State

- [ ] 3.1 Resolve and record the current effective NuGet versions for every maintained C# project.
- [ ] 3.2 Add `src/Directory.Packages.props`, move maintained package versions out of project files, and replace duplicate mod NuGet configs with one mapped source configuration.
- [x] 3.3 Add `src/Directory.Build.props` to enable dependency locks only for maintained projects.
- [ ] 3.4 Generate and commit lockfiles for all maintained projects with packages.
- [x] 3.5 Add one locked-restore inventory that covers every maintained C# project without including generated variant projects.
- [ ] 3.6 Prove locked restore fails after a controlled stale-manifest change, then restore the valid state.
- [x] 3.7 Run contract and mod verification leaves against locked dependency state.
- [x] 3.8 Commit NuGet centralization as `chore(dotnet): centralize and lock package resolution`.

## 4. xUnit v3 Migration

- [x] 4.1 Replace xUnit v2 references with the xUnit v3 package set in central package management.
- [x] 4.2 Convert all seven maintained test projects to the required executable test-project form.
- [x] 4.3 Update runner and test SDK metadata, remove the unused coverage collector, and retain VSTest TRX reporting.
- [x] 4.4 Regenerate affected NuGet lockfiles.
- [x] 4.5 Run every native contract and mod test project and verify retained TRX reports.
- [x] 4.6 Commit the migration as `test(dotnet): migrate maintained tests to xunit v3`.

## 5. Canonical Dependency-State Verification

- [x] 5.1 Add a dependency-state leaf to the canonical `erenshor test` command.
- [x] 5.2 Validate flake checks and Python lock freshness without mutating the Nix Python environment.
- [x] 5.3 Validate pnpm assertion consistency and a frozen root workspace install.
- [x] 5.4 Validate root .NET tool restore and locked NuGet restore for the maintained project inventory.
- [x] 5.5 Validate Renovate configuration and immutable third-party Action references.
- [x] 5.6 Add focused tests for each stale-state failure and for complete successful dependency state.
- [x] 5.7 Add the dependency-state job to CI and to the `CI Success` aggregate.
- [x] 5.8 Prove a controlled stale lock fails both the leaf and aggregate CI contract.
- [x] 5.9 Commit the gate as `feat(test): add dependency-state verification`.

## 6. Fail-Closed CI Authentication

- [ ] 6.1 Restrict workflow-level permissions to read-only repository contents.
- [ ] 6.2 Upgrade Codecov with unit-job-only OIDC permission and fail-closed upload behavior.
- [ ] 6.3 Verify one pull-request run reports an accepted Codecov upload.
- [ ] 6.4 Remove the obsolete long-lived Codecov secret after OIDC succeeds.
- [x] 6.5 Pin every third-party Action to a verified full commit SHA with a release comment.
- [x] 6.6 Run workflow and dependency-state validation against all pinned references.
- [ ] 6.7 Commit CI hardening as `ci: make dependency verification fail closed`.

## 7. Project-Specific Update Automation

- [ ] 7.1 Configure Renovate managers so Renovate excludes Nix state and owns all supported non-Nix state.
- [ ] 7.2 Require dashboard approval for non-security major updates and immediate proposals for vulnerability alerts.
- [ ] 7.3 Add only documented compatibility groups for SvelteKit and Vite, ESLint, deck.gl, .NET test tooling, and GitHub Actions.
- [ ] 7.4 Add ecosystem labels, manual merge policy, and a short non-security release age.
- [ ] 7.5 Install the dedicated Nix updater for this repository with ownership of flake state and matching pnpm assertions.
- [ ] 7.6 Run Renovate and Nix updater dry runs and prove that no file has two automated owners.
- [ ] 7.7 Commit repository automation as `chore(deps): define project update policy`.

## 8. Guidance and Clean Cutover

- [ ] 8.1 Update `AGENTS.md` with the authoritative dependency ownership table and regeneration commands.
- [ ] 8.2 Update the map and mod skills where lock, bootstrap, test, or NuGet workflows changed.
- [ ] 8.3 Document manual major-update review, security-update handling, and updater failure recovery.
- [ ] 8.4 Remove obsolete lockfile references from maintained documentation and scripts.
- [ ] 8.5 Commit guidance as `docs(deps): document canonical update workflow`.

## 9. Repository Protection and Queue Reset

- [ ] 9.1 Enable administrator enforcement and disable force pushes on `main` while preserving strict `CI Success` and linear history.
- [ ] 9.2 Verify the exact branch-protection state through the GitHub API.
- [ ] 9.3 Merge the migration commits only after `uv run erenshor test ci` passes from clean dependency state.
- [ ] 9.4 Close or supersede every dependency pull request generated from the old ownership model.
- [ ] 9.5 Trigger fresh Renovate and Nix update runs from the migrated `main` branch.
- [ ] 9.6 Verify one non-major update, one approved major update, one coupled group, and one controlled failure follow the specification.
- [ ] 9.7 Confirm the dependency dashboard contains no duplicate, unavailable-by-rename, or obsolete-lockfile entries.
- [ ] 9.8 Archive this OpenSpec change only after repository state and automation match every requirement.
