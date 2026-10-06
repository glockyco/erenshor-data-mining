---
name: mod-pipeline
description: Use when setting up mod references, building or deploying a native loader target, or preparing Thunderstore and Vault releases.
---

# Companion mod pipeline

Run commands from the development shell. Use `-V main`, `-V playtest`, or `-V demo` before `mod` to select the installation. The CLI resolves the selected Steam app ID inside a CrossOver bottle. Set `CROSSOVER_BOTTLE` if several bottles contain that variant.

## Set up and select a loader

1. Close the game. Install BepInEx and Lunaris once if you need both targets.
2. Run `uv run erenshor mod setup` to provision game references and both loader reference sets. Repeat after changing the game installation.
3. Run `uv run erenshor -V playtest mod status` to check the selected installation, available loader proxies, and active loader.
4. Use `uv run erenshor -V playtest mod activate --loader bepinex` or `--loader lunaris` when switching. Restart the game after switching.

Both plugin trees can remain installed. Activation replaces the root `winhttp.dll` from an installer-saved proxy. If activation rejects an unknown, conflicting, missing, or symlinked proxy, repair the loader installation. Do not replace `winhttp.dll` by hand.

## Build, deploy, and inspect

```bash
uv run erenshor -V playtest mod build --mod adventure-guide --loader all
uv run erenshor -V playtest mod deploy --mod adventure-guide --loader bepinex
uv run erenshor -V playtest mod deploy --mod adventure-guide --loader lunaris
```

Use one `--loader` per deployment. `build --loader all` builds both targets but does not activate one. `deploy` builds again, copies the selected target, and activates its loader. Deployment without `--mod` requires an explicit loader because the registry defaults span both loaders.

- Public BepInEx deployment follows `thunderstore.toml` copy targets under `<game>/BepInEx/plugins/`. Internal `map-tile-capture` deploys its DLL directly there.
- Lunaris deployment copies the native DLL into `<game>/plugins/`. Restart the game and enable a manually deployed plugin in the Lunaris plugin installer. A Vault-browser installation enables it during install. `Plugin found` alone does not mean enabled.
- For BepInEx hot reload, first run `uv run erenshor mod dev-setup`. Then use `uv run erenshor mod deploy --mod adventure-guide --loader bepinex --scripts`. This copies the DLL and PDB to `BepInEx/scripts/`. Reload with F6 or use the reflection call in `runtime-eval`.
- For BepInEx load failures, check `BepInEx/LogOutput.log` and the manifest's nested copy target. For Lunaris failures, check the in-game log UI and the enable state.

`mod dev-setup` installs ScriptEngine and ConfigurationManager, not HotRepl. See `runtime-eval` for the separate HotRepl installation. `--scripts` does not support Lunaris.

## Thunderstore release (BepInEx)

The public mods are `adventure-guide`, `interactive-map-companion`, `sprint`, and `justice-for-f7`. `map-tile-capture` has no public release listing.

1. Install `tcli` with `dotnet tool install -g tcli` if it is absent.
2. Run `uv run erenshor --dry-run mod thunderstore` to build and validate all four packages without uploading. A single-mod check uses `uv run erenshor --dry-run mod thunderstore --mod adventure-guide`.
3. For an intentional upload, set a real `TCLI_AUTH_TOKEN` in the environment or local `.env`. Run `uv run erenshor mod thunderstore --mod adventure-guide`.

The CLI looks up the next version through Thunderstore. A network or malformed-response error stops the release. It checks declared package inputs, builds BepInEx, runs `tcli build`, inserts `build.changelog` as `CHANGELOG.md`, and validates the ZIP against `thunderstore.toml`. It checks input hashes again before `tcli publish --file` uploads that ZIP. A real upload requires exactly one public `--mod`. Never include a token in a logged command.

## Erenshor Vault release (Lunaris)

1. Check the mod's `vault/vault.toml`, `vault/README.md`, `vault/CHANGELOG.md`, and `vault/icon.png`.
2. Run `uv run erenshor mod vault --mod adventure-guide`. The CLI queries Vault versions and builds the Lunaris DLL with the next `YYYY.MDD.R` version embedded.
3. If the command warns that the changelog's first version differs, correct the top entry before upload. The warning does not stop the build.
4. Create the first listing at `erenshorvault.app/new-mod` from the listing fields and assets. For later versions, add the DLL as the main file, with no asset files. Enter the printed version and the top changelog entry.

Vault upload is manual. The CLI does not call a Vault write API. Lunaris supplies ImGui.NET, Newtonsoft.Json, and System.Numerics.Vectors for AdventureGuide. Upload the Lunaris DLL, not a Thunderstore BepInEx ZIP. The embedded version matters because Lunaris compares it with the Vault version.
