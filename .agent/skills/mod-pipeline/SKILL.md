---
name: mod-pipeline
description: Mod build, deploy, and publish lifecycle. Use when building, deploying, or publishing mods.
---

# Companion Mod Build Pipeline

End-to-end automated pipeline for building companion mods with CalVer versioning,
metadata generation, and website integration. Version numbers are derived from git
commit history—never manually specified.

## Pipeline Overview

**5 stages**: setup → build → deploy/publish → website build → deploy

```
Developer Code Changes
  ↓
git commit
  ↓ (pre-commit hook)
validate-mods-metadata.py ← catches config issues early
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
npm run build (from src/maps/)
  ├─ prebuild: uv run erenshor mod publish && tiles manifest
  ├─ vite build: includes static/mods/ and static/mods-metadata.json
  └─ dist/ ready for deployment
  ↓
wrangler deploy
  └─ Website live with latest mods + metadata
```

## Command Reference

### Build Mods (generates metadata)
```bash
uv run erenshor mod build              # Build all mods
uv run erenshor mod build --mod interactive-map-companion  # Specific mod
```

Outputs:
- `src/mods/mods-metadata.json` - Metadata with current versions
- `src/maps/static/mods-metadata.json` - Mirror for website
- DLLs in `src/mods/{ModName}/bin/Debug/netstandard2.1/`

### Deploy to BepInEx (for local testing)
```bash
uv run erenshor mod deploy             # Build + copy to game BepInEx/plugins/
uv run erenshor mod setup              # Copy game DLLs to mod lib/ dirs first
uv run erenshor mod launch             # Launch the game
```

### Publish to Website (CI calls this via prebuild)
```bash
uv run erenshor mod publish            # Build + stage for website deployment
```

Outputs:
- DLLs in `src/maps/static/mods/`
- Metadata at `src/maps/static/mods-metadata.json`

### Publish to Thunderstore
```bash
uv run erenshor mod thunderstore --mod mod-id       # Build and upload
uv run erenshor mod thunderstore --mod mod-id --dry-run  # Test without uploading
```

Requirements:
- `dotnet tool install -g tcli`
- `TCLI_AUTH_TOKEN` in `.env`
- `thunderstore.toml` config in mod directory
- `thunderstore/README.md`, `thunderstore/CHANGELOG.md`, and `thunderstore/icon.png`

Version auto-increments if releasing multiple times same day (YYYY.MDD.R format).

**Two distinct build modes — ILRepack vs. no ILRepack**:

| Build path | ILRepack | Output | Used for |
|------------|----------|--------|---------|
| `mod build` / `mod deploy` / `mod publish` | Yes | Single merged DLL | Local testing, website download |
| `mod thunderstore` | No (`-p:SkipILRepack=true`) | Separate DLLs | Thunderstore (reviewers require separate DLLs) |

The `thunderstore.toml` `[[build.copy]]` sections list each DLL individually
(`InteractiveMapCompanion.dll`, `Fleck.dll`, `Newtonsoft.Json.dll`) because the
Thunderstore build uses the non-merged output. The `ILRepack.targets` file skips
all merge steps when `SkipILRepack=true` is set.

When adding a new NuGet dependency to a mod that has Thunderstore support:
- The dependency is automatically included in the ILRepack-merged website DLL
- Add it explicitly to `thunderstore.toml` `[[build.copy]]` so it's included in
  the Thunderstore package too

### Validate Metadata (runs automatically in pre-commit + CI)
```bash
uv run python3 scripts/validate-mods-metadata.py
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
`npm run build` in `src/maps/`:
- prebuild calls `uv run erenshor mod publish` → ensures DLLs + metadata ready
- vite includes `static/mods/` and `static/mods-metadata.json`
- Fails if mod publish fails (strict mode prevents stale deployments)

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
2. `git commit` (pre-commit validates metadata)
3. `uv run erenshor mod publish` (stages for website)
4. `npm run build` in src/maps/ (prebuild calls publish)
5. Deploy website

### Test Mod Locally
1. `uv run erenshor mod build --mod mod-id`
2. `uv run erenshor mod deploy --mod mod-id`
3. `uv run erenshor mod launch`
4. Check `BepInEx/LogOutput.log` for errors

### Fix Metadata Issues
If metadata validation fails:
1. `git status` to see what changed
2. Check `src/mods/mods-config.yaml` for syntax errors
3. `uv run python3 scripts/validate-mods-metadata.py` for details
4. Fix issues and commit again

## Key Design Principles

**Single Source of Truth**: Version from git, everything else derives from config.

**Atomic Metadata**: Both metadata files written together, never out of sync.

**Fail Fast**: Validation in pre-commit catches issues before pushing.

**No Manual Steps**: Website build automatically stages mods.

**Reproducible**: Same commit always produces same version.

**Versioned History**: Metadata committed so version history is trackable.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Build fails: "No DLLs in lib/" | Run `uv run erenshor mod setup` first |
| Version shows "0.0.0-unknown" | Check git history exists for mod directory |
| Metadata invalid (pre-commit blocks) | Run validation script to see details |
| Website shows stale mods | Run `npm run build` from `src/maps/` |
| DLL not in website static/ | Run `uv run erenshor mod publish` |

## Architecture Files

- `src/erenshor/cli/commands/mod.py` - CLI with setup/build/deploy/publish commands
- `scripts/generate-mod-version.py` - CalVer generation from git
- `scripts/generate-mods-metadata.py` - Metadata generation from config + versions
- `scripts/validate-mods-metadata.py` - Metadata validation for CI/pre-commit
- `src/mods/mods-config.yaml` - Master mod configuration
- `.pre-commit-config.yaml` - Pre-commit hook definition
- `.github/workflows/ci.yml` - CI validation job
- `src/maps/package.json` - Website prebuild integration
