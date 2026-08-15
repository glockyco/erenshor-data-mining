{
  description = "Erenshor data mining and companion tooling";

  inputs = {
    # Track the same nixpkgs release the workstation pins so the dev shell and
    # the host system share one evaluated package set and one binary cache.
    nixpkgs.url = "https://flakehub.com/f/NixOS/nixpkgs/0.2605";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
    }:
    let
      # AssetRipper, the .NET SDKs and the Node toolchain all build on these.
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];

      forAllSystems = nixpkgs.lib.genAttrs systems;

      packageManager = (builtins.fromJSON (builtins.readFile ./package.json)).packageManager;
      assertPnpmVersion =
        pkgs:
        let
          expected = "pnpm@${pkgs.pnpm_10.version}";
        in
        pkgs.lib.assertMsg (
          packageManager == expected
        ) "package.json provides ${packageManager}; the Nix toolchain provides ${expected}";

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      lockedPythonOverlay = workspace.mkPyprojectOverlay {
        # Wheels are already the uv.lock-selected artifacts. pyproject.nix
        # installs each one in its own derivation and fixes native runtime paths
        # there, instead of leaking loader settings into unrelated processes.
        sourcePreference = "wheel";
      };

      editablePythonOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
      };

      # Editable builds only need project metadata and enough package structure
      # for Hatchling to discover the live source tree. Unrelated repository
      # edits must not rebuild the Python environment.
      editableSourceOverlay = _final: prev: {
        erenshor = prev.erenshor.overrideAttrs (_old: {
          src = nixpkgs.lib.fileset.toSource {
            root = ./.;
            fileset = nixpkgs.lib.fileset.unions [
              ./README.md
              ./pyproject.toml
              ./src/erenshor/__init__.py
            ];
          };
        });
      };

      pythonSets = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          base = pkgs.callPackage pyproject-nix.build.packages { python = pkgs.python314; };
        in
        base.overrideScope (
          nixpkgs.lib.composeManyExtensions [
            pyproject-build-systems.overlays.wheel
            lockedPythonOverlay
          ]
        )
      );

      dotnetSdk =
        pkgs:
        pkgs.dotnetCorePackages.combinePackages [
          pkgs.dotnetCorePackages.sdk_9_0
          pkgs.dotnetCorePackages.sdk_10_0
        ];
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        assert assertPnpmVersion pkgs;
        {
          bootstrap = pkgs.writeShellApplication {
            name = "erenshor-bootstrap";
            runtimeInputs = [
              pkgs.git
              pkgs.nodejs_22
              pkgs.pnpm_10
              (dotnetSdk pkgs)
            ];
            text = ''
              if [[ ! -f flake.nix || ! -f uv.lock || ! -f pnpm-lock.yaml ]]; then
                echo "Run nix run .#bootstrap from the repository root." >&2
                exit 1
              fi

              export DOTNET_CLI_TELEMETRY_OPTOUT=1
              export DOTNET_NOLOGO=1

              pnpm install --frozen-lockfile
              dotnet tool restore
            '';
          };

          python = pythonSets.${system}.mkVirtualEnv "erenshor-python-env" workspace.deps.all;
        }
      );

      apps = forAllSystems (system: {
        bootstrap = {
          type = "app";
          program = "${self.packages.${system}.bootstrap}/bin/erenshor-bootstrap";
        };
      });

      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system}.overrideScope (
            nixpkgs.lib.composeManyExtensions [
              editablePythonOverlay
              editableSourceOverlay
            ]
          );
          pythonEnvironment = pythonSet.mkVirtualEnv "erenshor-dev-env" workspace.deps.all;
        in
        assert assertPnpmVersion pkgs;
        {
          default = pkgs.mkShellNoCC {
            # Nix builds the uv.lock-selected Python environment. The remaining
            # packages are non-Python project toolchains.
            packages = [
              pythonEnvironment
              pkgs.uv
              pkgs.git
              (dotnetSdk pkgs)
              pkgs.nodejs_22
              pkgs.pnpm_10
              pkgs.bun
              pkgs.assetripper
              pkgs.sqlite
              pkgs.gitleaks
              pkgs.actionlint
              pkgs.renovate
            ];

            env = {
              # uv remains the documented command runner, but Nix exclusively
              # owns the environment and uv must never mutate it.
              UV_NO_SYNC = "1";
              UV_PROJECT_ENVIRONMENT = "${pythonEnvironment}";
              UV_PYTHON = pythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";

              DOTNET_CLI_TELEMETRY_OPTOUT = "1";
              DOTNET_NOLOGO = "1";
            };

            # Editable packages need the live checkout path rather than the
            # flake source copied into the Nix store.
            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT="$(git rev-parse --show-toplevel)"
            '';
          };
        }
      );

      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt-tree);

      checks = forAllSystems (system: {
        bootstrap = self.packages.${system}.bootstrap;
        python = self.packages.${system}.python;
        devShell = self.devShells.${system}.default;
      });
    };
}
