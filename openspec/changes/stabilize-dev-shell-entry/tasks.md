## 1. Reproducible Toolchain Selection

- [x] 1.1 Route Darwin .NET runtimes and SDKs through Nixpkgs fixed-output binary variants
- [x] 1.2 Package both official Darwin AssetRipper archives as fixed-output sources
- [x] 1.3 Preserve the existing package scope on every supported Linux system

## 2. Regression Contract and Guidance

- [x] 2.1 Prove the Darwin development-shell plan excludes Swift and source-built .NET bootstrap derivations
- [x] 2.2 Verify .NET SDK 9, .NET SDK 10, AssetRipper, and the existing shell tools remain available
- [x] 2.3 Document automatic shell entry behavior and the bounded closure diagnostic

## 3. Acceptance and Cleanup

- [x] 3.1 Run strict OpenSpec validation, formatting, dependency-state, and flake checks
- [x] 3.2 Remove interrupted generated profiles and verify a normal nix-direnv refresh completes once
- [x] 3.3 Measure warm directory entry and Git status latency after the refresh
- [x] 3.4 Commit the specification and implementation as separate atomic changes
- [ ] 3.5 Push the branch and verify required CI before archival
