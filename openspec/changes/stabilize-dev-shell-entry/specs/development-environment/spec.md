## Purpose

Define a reproducible development shell that remains practical for automatic entry and does not compile avoidable platform toolchains during routine lock refreshes.

## ADDED Requirements

### Requirement: Automatic shell entry remains operational
The repository SHALL support automatic nix-direnv entry after a clean checkout or flake-lock refresh. On Darwin, realizing the development shell SHALL use supported fixed-output binary .NET toolchains when Nixpkgs provides them for the selected versions.

#### Scenario: Flake lock invalidates the cached profile
- **WHEN** nix-direnv reevaluates the development shell after `flake.lock` changes
- **THEN** the Darwin build plan contains no Swift compiler derivation
- **AND** it contains no source-built .NET VMR or bootstrap SDK derivation
- **AND** shell realization can use the configured binary cache for the selected .NET toolchains

### Requirement: Darwin host tools use minimal reproducible sources
A self-contained host tool SHALL use its official fixed-output native release on Darwin when that release preserves the accepted command behavior. The development shell SHALL NOT rebuild the same application and its managed runtime from source during automatic entry.

#### Scenario: AssetRipper enters the development shell
- **WHEN** Nix evaluates AssetRipper as part of the Darwin shell
- **THEN** it selects the official archive for the host architecture
- **AND** it verifies the archive with a declared SHA-256 hash
- **AND** its dependency plan contains no managed SDK, Swift compiler, or native application compilation edge

### Requirement: Tool behavior remains available
The optimized development shell SHALL preserve the project toolchain and supported host platforms.

#### Scenario: Developer enters the shell
- **WHEN** the corrected shell finishes loading
- **THEN** .NET SDK 9 and .NET SDK 10 are available
- **AND** AssetRipper is available
- **AND** the existing Python, JavaScript, database, security, and workflow tools remain available

#### Scenario: Linux evaluates the shell
- **WHEN** a supported Linux system evaluates or builds the development shell
- **THEN** it retains the existing Nixpkgs toolchain selection and project behavior
