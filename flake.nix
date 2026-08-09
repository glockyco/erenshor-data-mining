{
  description = "Erenshor data mining and companion tooling";

  inputs = {
    # Track the same nixpkgs release the workstation pins so the dev shell and
    # the host system share one evaluated package set and one binary cache.
    nixpkgs.url = "https://flakehub.com/f/NixOS/nixpkgs/0.2605";
  };

  outputs =
    { self, nixpkgs }:
    let
      # AssetRipper, the .NET SDKs and the Node toolchain all build on these.
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];

      forAllSystems =
        f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShellNoCC {
          # Versions mirror .github/workflows/ci.yml. CI installs them with the
          # setup-* actions; keep both sides in step when either moves.
          packages = [
            # Python 3.14 with uv managing the project virtualenv.
            pkgs.uv
            pkgs.python314

            # `erenshor test mods`, `erenshor test contract` and the CodeFacts
            # and ExportSurface tools need both SDKs: the tools target net9.0
            # and the mod test projects target net10.0.
            (pkgs.dotnetCorePackages.combinePackages [
              pkgs.dotnetCorePackages.sdk_9_0
              pkgs.dotnetCorePackages.sdk_10_0
            ])

            # Interactive map workspace.
            pkgs.nodejs_22
            pkgs.pnpm_10

            # `erenshor extract rip` drives the AssetRipper GUI over its local
            # HTTP API; `[global.assetripper] path` resolves it from PATH.
            pkgs.assetripper

            # Ad-hoc inspection of the raw and clean databases.
            pkgs.sqlite

            # The pre-commit secret scan, matching the CI security job.
            pkgs.gitleaks
          ];

          env = {
            # The shell already supplies an interpreter, and a uv-downloaded
            # CPython would silently diverge from it.
            UV_PYTHON = "${pkgs.python314}/bin/python3.14";
            UV_PYTHON_DOWNLOADS = "never";

            DOTNET_CLI_TELEMETRY_OPTOUT = "1";
            DOTNET_NOLOGO = "1";
          };
        };
      });

      formatter = forAllSystems (pkgs: pkgs.nixfmt-tree);

      checks = forAllSystems (pkgs: {
        devShell = self.devShells.${pkgs.stdenv.hostPlatform.system}.default;
      });
    };
}
