## Purpose

Defines how the repository records, updates, validates, and merges dependency state across all maintained ecosystems without conflicting owners or hidden resolution changes.

## ADDED Requirements

### Requirement: Each ecosystem has one authoritative dependency boundary
The repository MUST define one authoritative manifest set and one lock boundary for each maintained dependency ecosystem. A dependency file MUST NOT compete with another lockfile or package manager for the same project.

#### Scenario: JavaScript dependency ownership
- **WHEN** a JavaScript dependency is added or updated in the map or Bun-based item exporter
- **THEN** the root pnpm workspace lock records the complete resolved change
- **AND** no nested npm, pnpm, or Bun lockfile exists
- **AND** Bun remains a Nix-provided runtime rather than a second dependency owner

#### Scenario: Python dependency ownership
- **WHEN** a Python project dependency changes
- **THEN** the Python project manifest declares the compatible requirement
- **AND** the Python lock records the resolved environment

#### Scenario: .NET dependency ownership
- **WHEN** a maintained C# project consumes a NuGet package
- **THEN** its declared version comes from the maintained central package definition
- **AND** package source mapping selects the project-owned feed for each package ID
- **AND** its committed lock records the resolved graph

#### Scenario: Nix dependency ownership
- **WHEN** a Nix input changes
- **THEN** the dedicated Nix updater owns the resulting flake lock change
- **AND** Renovate does not create a competing update for that input

### Requirement: Dependency resolution is repeatable
Development bootstrap and CI MUST resolve dependencies from committed lock state through the Nix-pinned toolchain. Validation MUST fail when a manifest, tool assertion, or lockfile is stale.

#### Scenario: Clean checkout bootstrap
- **WHEN** a developer bootstraps a clean checkout through the documented Nix workflow
- **THEN** JavaScript, Python, .NET tool, and NuGet dependency resolution uses committed state
- **AND** no uncommitted dependency file change is required

#### Scenario: Stale dependency state
- **WHEN** a manifest changes without the corresponding lock or mirrored tool assertion
- **THEN** the canonical local verification command fails
- **AND** CI reports the affected ecosystem before behavior tests can pass

#### Scenario: Toolchain assertion diverges
- **WHEN** a language-native tool assertion differs from the Nix-provided tool version
- **THEN** validation fails with both observed versions

### Requirement: Automated updates have exclusive file ownership
Each dependency-controlled file MUST have one automated updater. An updater MUST produce all manifest, lock, and generated metadata changes that its proposal requires.

#### Scenario: Renovate update
- **WHEN** Renovate proposes a supported non-Nix dependency update
- **THEN** the pull request contains every affected authoritative manifest and lockfile
- **AND** it contains no obsolete or secondary lockfile

#### Scenario: Nix update
- **WHEN** the Nix updater proposes a flake input update
- **THEN** the pull request contains the flake lock and all required matching tool assertions
- **AND** the central control plane uses a short-lived repository-scoped GitHub App token
- **AND** this repository stores no App private key or competing Nix scheduler
- **AND** normal pull-request CI starts without manual workflow approval
- **AND** no other updater opens a duplicate proposal for that state

#### Scenario: Incomplete generated artifacts
- **WHEN** an updater cannot regenerate required dependency state
- **THEN** its proposal is marked failed
- **AND** the protected merge gate does not report success

### Requirement: Update grouping follows compatibility boundaries
Automated dependency grouping MUST combine only dependencies that share a known compatibility, generated-state, or validation boundary. Major updates MUST require explicit dashboard approval unless they remediate a security alert.

#### Scenario: Coupled toolchain update
- **WHEN** packages have peer-version constraints that require a coordinated migration
- **THEN** Renovate proposes one compatibility-group pull request
- **AND** the pull request documents the grouped dependencies

#### Scenario: Unrelated non-major updates
- **WHEN** unrelated ecosystems have non-major updates
- **THEN** their updates do not share one repository-wide pull request

#### Scenario: Major update
- **WHEN** a major update has no active security alert
- **THEN** Renovate waits for explicit dashboard approval before creating its pull request

#### Scenario: Security update
- **WHEN** a supported dependency has an actionable security alert
- **THEN** the updater creates or refreshes its proposal without waiting for the weekly schedule
- **AND** manual merge remains required

### Requirement: Dependency validation fails closed
Every dependency pull request MUST pass lock freshness, static checks, affected builds, behavior tests, and required external reporting. A required integration MUST fail the owning CI job when it rejects or loses an upload.

#### Scenario: Coverage upload succeeds
- **WHEN** the unit test job produces coverage
- **THEN** CI authenticates the upload without a long-lived repository token
- **AND** the unit job passes only after the coverage service accepts the upload

#### Scenario: Coverage upload fails
- **WHEN** the coverage service rejects the upload or authentication fails
- **THEN** the unit job fails
- **AND** the aggregate required status fails

#### Scenario: Ecosystem validation fails
- **WHEN** any dependency lock, build, static check, or behavior test fails
- **THEN** the aggregate required status fails
- **AND** the pull request cannot merge

### Requirement: Third-party workflow code is immutable
Every third-party GitHub Action reference MUST use a verified full commit SHA. Automated updates MAY change that SHA only through a reviewable pull request.

#### Scenario: Workflow action update
- **WHEN** Renovate updates a third-party action
- **THEN** the workflow still references a full commit SHA
- **AND** the pull request identifies the corresponding release version

### Requirement: Protected main enforces manual green merges
The default branch MUST require the current aggregate CI status, linear history, administrator enforcement, and disabled force pushes. Dependency automation MUST NOT automerge pull requests.

#### Scenario: Green current dependency pull request
- **WHEN** a dependency pull request is current with the default branch and all required checks pass
- **THEN** the maintainer can merge it manually

#### Scenario: Failed or stale dependency pull request
- **WHEN** a dependency pull request is stale or a required check fails
- **THEN** branch protection blocks its merge for every actor, including administrators

#### Scenario: Force push attempt
- **WHEN** an actor attempts to force push the default branch
- **THEN** branch protection rejects the update
