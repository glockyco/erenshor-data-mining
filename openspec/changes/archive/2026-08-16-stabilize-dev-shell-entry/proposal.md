## Why

A routine `flake.lock` refresh invalidates the nix-direnv profile and makes the next directory entry compile Swift and multiple .NET SDKs from source. Git itself remains fast, but the automatic shell transition blocks every command behind an avoidable Darwin toolchain build.

## What Changes

- Use the supported hash-pinned binary .NET runtime and SDK variants for the Erenshor development toolchain on Darwin.
- Use AssetRipper's official hash-pinned native release on Darwin instead of rebuilding its self-contained application during shell entry.
- Add a flake check that rejects Swift and source-built .NET VMR derivations in the Darwin development-shell plan.
- Preserve the selected .NET 9 and .NET 10 toolchains, AssetRipper, automatic nix-direnv entry, and the existing Linux behavior.
- Remove interrupted nix-direnv temporary profiles after the corrected shell evaluates successfully.

## Capabilities

### New Capabilities

- `development-environment`: Defines responsive, reproducible automatic shell entry and the required Darwin toolchain closure.

### Modified Capabilities

None.

## Impact

The change affects `flake.nix`, `flake.lock` only if evaluation changes its input graph, development-shell checks, and contributor guidance. It changes no game files, project dependency locks, runtime deployment state, or command-line interfaces. The migration boundary is the Nix development-shell closure; broader runtime and CLI packaging remains in the planned `nix-development-environment` change.
