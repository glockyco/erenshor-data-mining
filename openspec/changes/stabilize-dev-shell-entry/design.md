## Context

See `proposal.md` for motivation. The measured Git operation takes 0.05 seconds when invoked from outside the repository. The delay occurs before Git starts: entering the directory makes nix-direnv refresh a stale profile because `flake.lock` is newer than its cached profile.

The current Darwin shell selects source-built `.NET` SDK 9 and 10 packages. AssetRipper independently selects the source-built SDK 10 package and rebuilds an application that upstream already publishes as a self-contained native archive. A dry build plan contains 57 local derivations, including Swift 5.10.1, the .NET VMR bootstrap chain, both SDKs, and AssetRipper. Interrupted shell entries do not produce a valid profile, so each later directory entry repeats the work.

Nix owns executable toolchains and `flake.lock` remains the Nix updater's lock boundary. Native project dependencies retain their existing manifests and locks. This change does not alter those ownership rules or branch protection.

## Goals / Non-Goals

**Goals:**

- Remove avoidable Darwin compiler builds from automatic shell entry.
- Give the combined SDK one explicit binary .NET package scope and use AssetRipper's official native release.
- Preserve exact tool availability and automatic nix-direnv behavior.
- Make the closure regression directly reviewable from a bounded dry build plan.

**Non-Goals:**

- Disable direnv, defer shell loading, or hide its output.
- Replace AssetRipper or remove it from the development environment.
- Change project dependencies, game runtime state, or deployment commands.
- Complete the broader runtime-shell split and packaged CLI migration.

## Decisions

### Override the .NET package scope on Darwin

Define one platform function that returns Nixpkgs' ordinary `.NET` package scope on Linux. On Darwin, override the selected runtime and SDK members with their Nixpkgs `*-bin` variants. The binary variants are official Nixpkgs packages with fixed hashes; this keeps Nix ownership and reproducibility while avoiding the unsupported cost of routine local compiler builds.

Overriding the scope is preferable to overriding individual final packages. `combinePackages`, SDK passthrough attributes, runtime selection, and `buildDotnetModule` then resolve the same members from one scope.

Alternatives considered:

- Let the source builds finish once. Rejected because every relevant lock update can invalidate the profile, CI can encounter the same plan, and the build is avoidable.
- Disable automatic direnv loading. Rejected because it hides the expensive closure and degrades the accepted developer workflow.
- Remove .NET or AssetRipper from the shell. Rejected because both are maintained project tools.
- Add a background shell warm-up. Rejected because it preserves the incorrect dependency graph and makes failures less visible.

### Use AssetRipper's official native release on Darwin

Package the upstream `mac_arm64` and `mac_x64` archives as fixed-output sources with the SHA-256 digests published by GitHub. Wrap the self-contained executable with the same `--log=false` argument as Nixpkgs. Linux retains the existing Nixpkgs source package because its build is cacheable and no Darwin entry path consumes it.

Injecting the binary SDK into the Nixpkgs AssetRipper recipe removes Swift but still schedules 24 local derivations and recompiles an application that upstream already publishes for both Darwin architectures. The official archive reduces the corrected plan to five small derivations without changing the selected AssetRipper version or command.

Alternatives considered:

- Rebuild AssetRipper with the binary SDK. Rejected because it preserves avoidable application compilation during automatic shell entry.
- Remove AssetRipper from the default shell. Rejected because the current development contract includes the full host toolchain; the broader runtime-shell split remains separate work.
- Download AssetRipper outside Nix. Rejected because it would lose fixed hashing, declarative platform selection, and updater review.

### Verify the derivation plan and executable contract

Use a bounded `nix build --dry-run` against the Darwin development shell to prove that Swift, `.NET` VMR, and stage-zero SDK derivations are absent before realizing the shell. Then realize the shell and verify `.NET` SDK 9, `.NET` SDK 10, and AssetRipper on `PATH`.

The existing flake check continues to realize the development shell on supported systems. The OpenSpec scenario records the stricter Darwin closure invariant because a sandboxed build cannot query the Nix daemon's derivation graph safely.

### Keep updater and merge behavior unchanged

The central Nix updater remains the only owner of `flake.lock`. This change does not add an updater or modify update grouping. Pull-request CI and protected manual merge remain fail closed through the existing aggregate status.

## Risks / Trade-offs

- [A binary SDK differs from a source-built SDK] → Verify exact SDK versions and run the existing dependency-state and native test gates.
- [An upstream archive changes or selects the wrong architecture] → Pin each published digest, select by Nix host system, and verify the wrapped executable on both CI platforms.
- [A future Nixpkgs update changes binary member names] → Let flake evaluation fail at the selected member instead of silently falling back to source.
- [Interrupted attempts leave temporary direnv profiles] → Remove only generated `flake-tmp-profile.*` entries after no evaluation process remains, then allow one corrected profile refresh.

## Migration Plan

1. Add the platform-specific .NET scope and route the combined SDK through it.
2. Package the official AssetRipper archives for both Darwin architectures.
3. Prove the Darwin dry build plan excludes Swift and source-built .NET bootstrap derivations.
4. Realize the corrected development shell and verify required tools.
5. Run dependency-state, flake, and repository verification gates.
6. Remove stale temporary direnv profiles and allow one normal automatic refresh.
7. Revert the implementation commit to restore the prior scope if a supported command regresses. Do not disable direnv as rollback.
