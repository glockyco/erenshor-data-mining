---
name: mod-pipeline
description: BepInEx and Lunaris companion-mod setup, build, deploy, and local publication commands.
---

# Companion Mod Pipeline

This project builds every companion mod for both native loaders. BepInEx and
Lunaris may coexist in the same game installation. Their plugin trees remain
installed side by side, while the CLI atomically selects the active loader by
switching the root `winhttp.dll` proxy:

- **BepInEx** installs to `<game>/BepInEx/plugins` (or `BepInEx/scripts` for
  hot reload).
- **Lunaris** installs to `<game>/plugins`, next to `Erenshor.exe`.
- `mod deploy --loader <loader>` deploys that native target and activates its
  loader. Restart the game before testing a newly selected loader.
- `mod setup` provisions the references for both targets. It is not itself
  loader-selectable.

Thunderstore and Vault are different distribution paths. **Thunderstore
packages contain BepInEx artifacts. Vault releases contain Lunaris artifacts.**
The public set is exactly:

| Local id | Thunderstore package |
| --- | --- |
| `adventure-guide` | `WoW_Much/AdventureGuide` |
| `interactive-map-companion` | `WoW_Much/InteractiveMapCompanion` |
| `sprint` | `WoW_Much/Sprint` |
| `justice-for-f7` | `WoW_Much/JusticeForF7` |

The registry's other mods (`interactive-maps-companion` and
`map-tile-capture`) are internal and local-install only. They are not
Thunderstore or Vault releases.

## Local setup

Run setup before the first build, and again after changing the game install:

```bash
uv run erenshor mod setup
```

Setup copies game references and the resolved loader references into each
mod's `lib/` tree. Lunaris references come from the configured Lunaris library
(or the cache downloaded by setup), not from BepInEx's copies.

`-V main`, `-V playtest`, and `-V demo` select the matching runnable install.
Resolution is variant-specific:

1. `[variants.<name>] game_install` from `.erenshor/config.local.toml`, when set.
2. The selected variant's Steam App ID inside `CROSSOVER_BOTTLE`. If the bottle
   variable is unset, a unique matching CrossOver bottle is discovered.
3. The legacy `ERENSHOR_GAME_PATH` process-wide override, only when its
   `steam_appid.txt` does not contradict the selected variant.
4. For `mod setup` only, the selected variant's extracted `game_files` path.

Deploy, status, activation, and launch require a runnable install. They never
fall back to extracted game files, which prevents `-V demo` from modifying main
when the demo is not installed.

Standard CrossOver installs therefore need only the variant flag:

```bash
uv run erenshor -V playtest mod setup
uv run erenshor -V playtest mod status
```

Use `game_install` for an external Steam library or another non-standard
layout. The same variant selection applies to deploy, status, activation, and
launch.

## Loader-targeted build and deploy

`mod build --loader` accepts `default`, `bepinex`, `lunaris`, or `all`.
`default` follows each registry entry's configured default. Use an explicit
loader for reproducible local work. `all` builds both targets, but does not
choose a deployment target. A deployment without `--mod` must specify one
loader because one game process cannot activate mixed defaults.

Inspect or switch a prepared install without rebuilding mods:

```bash
uv run erenshor -V playtest mod status
uv run erenshor -V playtest mod activate --loader lunaris
```

Activation requires the loader installers' saved proxies. Lunaris normally
preserves BepInEx as `winhttp.bepinex-backup.dll`; the CLI also recognizes the
established legacy backup names. It refuses unknown, conflicting, symlinked,
or missing proxies instead of overwriting an unrelated `winhttp.dll`.

### Native BepInEx

```bash
uv run erenshor mod build --mod <public-id> --loader bepinex
uv run erenshor mod deploy --mod <public-id> --loader bepinex
```

BepInEx deployment follows each public mod's Thunderstore copy manifest, so
local testing uses the same nested plugin layout and runtime dependencies as
the package. Internal mods deploy their merged, loader-specific DLL directly
to `<game>/BepInEx/plugins`. For ScriptEngine hot reload, deploy the same target
with `--scripts` (BepInEx only):

```bash
uv run erenshor mod deploy --mod <public-id> --loader bepinex --scripts
```

Deploy all six native targets and activate BepInEx:

```bash
uv run erenshor -V playtest mod deploy --loader bepinex
```

### Native Lunaris

```bash
uv run erenshor mod build --mod <public-id> --loader lunaris
uv run erenshor mod deploy --mod <public-id> --loader lunaris
```

Lunaris deploys the native DLL to `<game>/plugins`. Restart the game after a
Lunaris deployment. `--scripts` is not valid for this loader.

Deploy all six native targets and activate Lunaris:

```bash
uv run erenshor -V playtest mod deploy --loader lunaris
```

Replace `<public-id>` with any registry id when working on an internal mod.
Internal mods remain local-install only.

Build outputs are isolated by loader under:

```text
src/mods/<ModName>/bin/<Configuration>/netstandard2.1/<loader>/
```

## Thunderstore: local package and optional upload

The Thunderstore command is the only public-upload command. It packages the
**BepInEx** build, validates the package locally, and never uses Lunaris
artifacts. The command resolves the next package version through the
Thunderstore version API. Network, HTTP, timeout, malformed-response, and
schema errors are hard failures rather than silently choosing a version.

Install the CLI once:

```bash
dotnet tool install -g tcli
```

A dry run with no `--mod` is the canonical local release check. It packages
all four public mods and **never uploads**:

```bash
uv run erenshor mod thunderstore --dry-run
```

A dry run for one public mod is also available:

```bash
uv run erenshor mod thunderstore --mod adventure-guide --dry-run
```

A real upload requires exactly one public `--mod` and a non-placeholder
`TCLI_AUTH_TOKEN` (export a real token or provide it through the repository's
local `.env` loading):

```bash
uv run erenshor mod thunderstore --mod adventure-guide
```

The token is used only for the `tcli publish` subprocess. Do not put a token
in a command copied into logs or documentation. Omitting `--mod` is allowed
only with `--dry-run`. It is rejected for a real upload.

Each selected mod is preflighted before any build. The pipeline then performs
the explicit BepInEx build, runs `tcli build`, locates the expected package
ZIP, validates its contents against the manifest allowlist, and only then
publishes. The package must contain only the manifest, icon, README, and the
exact declared copy targets. Game/runtime DLLs and unsafe paths are rejected. Manifest and declared-input
hashes are checked again immediately before upload, so a changed package input
cannot be published accidentally.

The exact upload command issued by the pipeline is:

```text
TCLI_AUTH_TOKEN=TOKEN tcli publish --file VALIDATED_ZIP --config-path MANIFEST
```

The token is supplied only through the subprocess environment. The validated
ZIP is passed explicitly so `tcli publish` cannot rebuild and upload an
unvalidated artifact.

There is no GitHub Actions release or upload automation. Run the command
locally when an upload is intentionally requested.

## Vault: local Lunaris artifact and manual upload

Vault releases use the **Lunaris** build, not the Thunderstore package. Prepare
one public mod locally:

```bash
uv run erenshor mod vault --mod adventure-guide
```

The command computes the next Vault version, builds the Lunaris artifact, and
prints the artifact and manual-upload information. Upload the resulting DLL
(and the matching top entry from `vault/CHANGELOG.md`) through the Erenshor
Vault website. The Vault write API is not automated. Keep this process manual.
There is no GitHub Actions release workflow.

## Website publication

Website staging is separate from both public package registries:

```bash
uv run erenshor mod publish
```

It builds each mod's configured default loader and stages the resulting DLLs
and generated metadata under `src/maps/static/`. This is not a Thunderstore or
Vault upload.

## Troubleshooting

- **Missing `lib/` references:** run `uv run erenshor mod setup` and verify the
  game path and Lunaris library configuration.
- **Wrong game variant:** run `mod status` with the intended `-V` flag. Set
  `[variants.<name>] game_install` only for non-standard installs. A standard
  CrossOver Steam install is resolved by App ID before the legacy
  `ERENSHOR_GAME_PATH` fallback.
- **Loader cannot activate:** install both loaders once and keep the backup
  proxies their installers create. `mod status` reports the recognized active
  and available proxies. The CLI will not overwrite an unknown `winhttp.dll`.
- **BepInEx deployment not loading:** run `mod status`, then verify public mods
  use the nested paths declared by their `thunderstore.toml` manifests and
  inspect `BepInEx/LogOutput.log`. Internal mods install directly under
  `BepInEx/plugins`.
- **Lunaris deployment not loading:** verify the DLL is under the game's
  top-level `plugins/` directory and restart the game.
- **Thunderstore upload rejected:** rerun the dry run, verify the manifest's
  declared inputs and copy targets, and use exactly one public `--mod` with a
  real token for the upload.

## Relevant files

- `src/erenshor/cli/commands/mod.py` — setup, build, status, activation, deploy,
  website publication, Thunderstore, and Vault command implementations
- `src/mods/<ModName>/thunderstore.toml` — package manifest and declared build
  inputs/copy targets
- `src/mods/<ModName>/vault/vault.toml` — Vault listing metadata
- `src/mods/mods-config.yaml` — registry metadata and loader defaults
