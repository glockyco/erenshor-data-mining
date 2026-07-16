---
name: mod-pipeline
description: BepInEx companion-mod build, deploy, and publish lifecycle with git-derived CalVer versioning. Use when building, deploying (hot-reload or production), or publishing a mod via uv run erenshor mod.
---

# Companion Mod Build Pipeline

End-to-end automated pipeline for building companion mods with CalVer versioning,
metadata generation, and website integration. Version numbers are derived from git
commit history—never manually specified.

## Pipeline Overview

**5 stages**: setup → build → deploy/publish → maps build → maps deploy

```
Developer Code Changes
  ↓
git commit
  ↓ (CI / website prebuild)
generate-mods-metadata.py ← catches config issues before deployment
  ↓
uv run erenshor mod build
  ├─ Compiles with dotnet
  ├─ Generates CalVer version from git (YYYY.M.D.{decimal_hash})
  ├─ Merges dependencies via ILRepack
  └─ Generates metadata to both:
     ├─ src/mods/mods-metadata.json (source of truth, versioned in git)
     └─ src/maps/static/mods-metadata.json (for website)
  ↓
uv run erenshor mod publish
  ├─ Calls build internally
  ├─ Copies DLLs to src/maps/static/mods/
  ├─ Verifies metadata is present
  └─ Ready for website deployment
  ↓
uv run erenshor maps build
  ├─ publishes mods for the selected variant
  ├─ generates the tiles manifest and OpenGraph image
  ├─ verifies and builds the SvelteKit site
  └─ stamps build/.build-info.json
  ↓
uv run erenshor maps deploy
  └─ Website live with latest mods + metadata
```

## Command Reference

### Build Mods (generates metadata)
```bash
uv run erenshor mod build                              # Build every mod's default loader target
uv run erenshor mod build --mod interactive-map-companion
uv run erenshor mod build --mod sprint --loader lunaris
uv run erenshor mod build --loader all                 # Build both targets for every mod
```

`--loader` accepts `default`, `bepinex`, `lunaris`, or `all` for `mod build`.
`default` selects each mod's configured loader; the registry defaults are
Lunaris for Adventure Guide, Sprint, and Justice for F7, and BepInEx for both
map companions and Map Tile Capture. Every registry mod has both native
targets, so `bepinex` and `lunaris` explicitly select one target and `all`
builds both. The public F7 set is Adventure Guide, Interactive Map Companion,
Sprint, and Justice for F7; the two other registry mods are internal.

The loader is passed to dotnet as `-p:ModLoader=<loader>`. Target-specific
artifacts are never written to an unsuffixed shared directory:

- `src/mods/{ModName}/bin/<Configuration>/netstandard2.1/<loader>/`
- `src/mods/{ModName}/obj/<loader>/`

Metadata remains generated in:

- `src/mods/mods-metadata.json` - Metadata with current versions
- `src/maps/static/mods-metadata.json` - Mirror for the website

### Deploy Mods
```bash
uv run erenshor mod deploy                              # Build + deploy each default target
uv run erenshor mod deploy --mod sprint --loader lunaris
uv run erenshor mod deploy --mod interactive-map-companion --loader bepinex
```

`mod deploy --loader` accepts `default`, `bepinex`, or `lunaris` (not `all`);
`default` uses each mod's configured loader. BepInEx targets install under
`<game>/BepInEx/plugins`. Native Lunaris targets for **all six registry mods**
install under `<game>/plugins` next to `Erenshor.exe`. The `--scripts` option
is BepInEx-only and deploys to `<game>/BepInEx/scripts` for ScriptEngine hot
reload; it is invalid for Lunaris targets.

Run setup before the first build (or after changing the game install):

```bash
uv run erenshor mod setup                              # Copy game + union loader refs
uv run erenshor mod launch                             # Launch the game
```

Setup provisions the union of references needed by both BepInEx and Lunaris
targets. Lunaris shared assemblies come from the resolved Lunaris library
directory, not from the game or BepInEx copies.

### Variant targeting (`ERENSHOR_GAME_PATH` wins over `-V`)

For deploy and launch, a **valid existing** `ERENSHOR_GAME_PATH` always
overrides `-V`. Thus `ERENSHOR_GAME_PATH=/path/to/main` combined with
`erenshor -V playtest mod deploy` still deploys to main. Do not leave a path
for one variant exported while working on another: unset it to use the
selected `-V` variant, or set it explicitly to that variant's installation.

```bash
unset ERENSHOR_GAME_PATH
uv run erenshor -V playtest mod deploy --mod sprint --loader lunaris

ERENSHOR_GAME_PATH="$HOME/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Erenshor Playtest" \
  uv run erenshor -V playtest mod deploy --mod sprint --loader lunaris
```

An invalid path is warned about and does not override the selected variant.
See `_get_game_path` in `src/erenshor/cli/commands/mod.py` for the resolution
order.

### Lunaris compile libraries

Lunaris compile-time references are shipped by Lunaris in a single
`LunarisLibs.zip`. `mod setup` sources them only from the resolved Lunaris lib
directory; it never scavenges the game or BepInEx install, whose copies may be
incomplete or differ from what Lunaris loads at runtime.

Resolution order (highest first):
1. `ERENSHOR_LUNARIS_LIB_DIR` environment variable
2. `[global.mods] lunaris_lib_dir` in `.erenshor/config.local.toml`
3. Auto-fetched cache: `mod setup` downloads `LunarisLibs.zip` (from
   `[global.mods] lunaris_libs_url`) and extracts the DLLs to
   `.erenshor/cache/lunaris-libs/`

`Lunaris.dll` itself is the loader and is **not** in `LunarisLibs.zip`; it
resolves from the game install (or `ERENSHOR_LUNARIS_DLL`). With neither env
var nor config set, setup auto-fetches the cache; set `lunaris_lib_dir` only
for a pre-extracted copy such as a local Lunaris source checkout.

### Publish to Website (CI calls this via prebuild)
```bash
uv run erenshor mod publish            # Build default targets + stage for website
```

Website publishing preserves each mod's configured default loader. It stages
the resulting default-target DLLs in `src/maps/static/mods/`; it does not
select or publish an `all` loader build.

Outputs:
- DLLs in `src/maps/static/mods/`
- Metadata at `src/maps/static/mods-metadata.json`

### Publish to Thunderstore
```bash
uv run erenshor mod thunderstore --mod mod-id           # Build BepInEx package and upload
uv run erenshor mod thunderstore --mod mod-id --dry-run # Test without uploading
```

Thunderstore packages are **BepInEx** packages. Only the public F7 set
(Adventure Guide, Interactive Map Companion, Sprint, and Justice for F7) is
eligible for public distribution, and a mod must also have Thunderstore
packaging metadata. Native Lunaris distribution uses the Erenshor Vault
instead; the Vault package is a Lunaris package and is not a Thunderstore
package.

Requirements:
- `dotnet tool install -g tcli`
- `TCLI_AUTH_TOKEN` in `.env`
- `thunderstore.toml` config in mod directory
- `thunderstore/README.md`, `thunderstore/CHANGELOG.md`, and `thunderstore/icon.png`

Version auto-increments if releasing multiple times same day (YYYY.MDD.R format).

**Two distinct build modes — ILRepack vs. no ILRepack**:

| Build path | ILRepack | Output | Used for |
|------------|----------|--------|---------|
| `mod build` / `mod deploy` / `mod publish` | Yes | Single merged DLL in the selected loader target directory | Local testing, website download |
| `mod thunderstore` | No (`-p:SkipILRepack=true`) | Separate DLLs in the BepInEx target directory | Thunderstore (reviewers require separate DLLs) |

The `thunderstore.toml` `[[build.copy]]` sections list each DLL individually
(`InteractiveMapCompanion.dll`, `Fleck.dll`, `Newtonsoft.Json.dll`) because the
Thunderstore build uses the non-merged output. The `ILRepack.targets` file skips
all merge steps when `SkipILRepack=true` is set.

When adding a new NuGet dependency to a mod that has Thunderstore support:
- The dependency is automatically included in the ILRepack-merged website DLL
- Add it explicitly to `thunderstore.toml` `[[build.copy]]` so it's included in
  the Thunderstore package too

### Validate Metadata (runs automatically in CI)
```bash
uv run python3 scripts/generate-mods-metadata.py
```

Checks:
- JSON structure and required fields
- CalVer version format
- Status values (current/legacy)
- URL formats
- Feature list

## Versioning System

**Format**: `YYYY.M.D.{DECIMAL_HASH}`

Example: `2026.1.25.2690525247`

**How it works**:
1. `.csproj` target runs `generate-mod-version.py` before compile
2. Script gets latest git commit date for mod directory
3. Converts to CalVer: year.month.day (removes leading zeros, so Jan = 1, not 01)
4. Gets commit SHA, converts 7-char hex hash to decimal
5. Embeds in generated `PluginInfo.g.cs`
6. Version available at runtime: `PluginInfo.Version`

**Dirty tree handling**:
- Debug builds: Append `-dirty-{timestamp}` if uncommitted changes exist
- Release builds: Fail if uncommitted changes

## Metadata Files

| File | Purpose | Committed? |
|------|---------|-----------|
| `src/mods/mods-config.yaml` | Master configuration (names, status, features, ports) | Yes |
| `src/mods/mods-metadata.json` | Generated metadata with versions from git | Yes |
| `src/maps/static/mods-metadata.json` | Copy for website static files | No (generated) |

Metadata generation is idempotent—safe to run multiple times.

## Integration Points

### Pre-commit Hook
Runs when files change: `src/mods/mods-config.yaml` or `scripts/generate-mods-metadata.py`

Validates metadata structure before commits allowed. Developers get immediate
feedback if there are issues.

### CI Pipeline
New `validate-mods` job runs on every push:
- Generates fresh metadata
- Validates structure and format
- Verifies mod count matches config
- Reports versions for each mod

### Website Build
`uv run erenshor maps build`:
- calls `uv run erenshor -V <variant> mod publish` internally
- includes `static/mods/` and `static/mods-metadata.json`
- writes `build/.build-info.json` so deploy can reject stale builds

### Website Display
`src/routes/(app)/mod/+page.svelte`:
- Fetches `/mods-metadata.json` at runtime
- Renders mod cards with version, status, features
- Download links to `/mods/{ModName}.dll`

## Common Workflows

### Add a New Mod
1. Create directory: `src/mods/{ModName}/`
2. Add to `src/mods/mods-config.yaml` with metadata
3. `uv run erenshor mod setup` to copy game DLLs
4. `uv run erenshor mod build` to verify it compiles

### Deploy New Mod Version
1. Make changes to mod source
2. `git commit`
3. `uv run erenshor maps build` (stages mods and builds the website)
4. `uv run erenshor maps deploy`

### Test Mod Locally
1. `uv run erenshor mod build --mod mod-id`
2. `uv run erenshor mod deploy --mod mod-id`
3. `uv run erenshor mod launch`
4. Check `BepInEx/LogOutput.log` for errors

### Fix Metadata Issues
If metadata validation fails:
1. `git status` to see what changed
2. Check `src/mods/mods-config.yaml` for syntax errors
3. `uv run python3 scripts/generate-mods-metadata.py` for details
4. Fix issues and commit again

## Key Design Principles

**Single Source of Truth**: Version from git, everything else derives from config.

**Atomic Metadata**: Both metadata files written together, never out of sync.

**Fail Fast**: CI metadata generation catches issues before deployment.

**No Manual Steps**: Website build automatically stages mods.

**Reproducible**: Same commit always produces same version.

**Versioned History**: Metadata committed so version history is trackable.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Build fails: "No DLLs in lib/" | Run `uv run erenshor mod setup` first |
| Version shows "0.0.0-unknown" | Check git history exists for mod directory |
| Metadata invalid (hook blocks) | Run validation script to see details |
| Website shows stale mods | Run `uv run erenshor maps build` |
| DLL not in website static/ | Run `uv run erenshor mod publish` |

## Architecture Files

- `src/erenshor/cli/commands/mod.py` - CLI with setup/build/deploy/publish commands
- `scripts/generate-mod-version.py` - CalVer generation from git
- `scripts/generate-mods-metadata.py` - Metadata generation and CI validation
- `src/mods/mods-config.yaml` - Master mod configuration
- `lefthook.yml` - Git hook definition
- `.github/workflows/ci.yml` - CI validation job
- `src/maps/README.md` - Website command entry point; maps build/deploy are CLI-owned
