# Justice for F7

Native dual-loader plugin that extends Erenshor's F7 "Hide UI" key to also hide
world-space UI — nameplates, damage numbers, target rings, XP orbs, cast bars,
and loot prompts.

Justice for F7 has native BepInEx and Lunaris builds. The BepInEx artifact is
the Thunderstore release (`WoW_Much/JusticeForF7`). The Lunaris artifact is
the Erenshor Vault release. See `vault/` for listing assets and manual
publishing notes.

## Architecture

```
src/
├── Plugin.BepInEx.cs     # Native BepInEx entrypoint
├── Plugin.Lunaris.cs     # Native Lunaris entrypoint
├── JusticeContracts.cs   # Loader-neutral settings and logging contracts
├── JusticeRuntime.cs     # Shared lifecycle, patches, and cleanup
├── PluginInfo.cs         # GUID/name + generated version constant
├── JusticeSettings.cs    # Lunaris Config.Register settings (per-category toggles)
├── WorldUIHider.cs       # Finds and hides/restores world-space renderers
└── Patches/              # Harmony patches: F7 canvas detection + transient suppression
```

## How it works

1. **F7 detection**: `TypeTextPatch` (postfix on `TypeText.Update`) watches
   `GameData.MainCanvas.enabled` each frame and drives the hider on transitions,
   running a periodic re-scan while hidden to catch newly spawned elements.
2. **Hiding**: `WorldUIHider` toggles `Renderer.enabled` (and target-ring
   GameObjects) rather than `TextMeshPro.enabled`, which the game manages itself,
   and restores exactly what it disabled when F7 is pressed again.
3. **Suppression**: `DmgPopPatch` and `XPBubPatch` prefix the game's popup/orb
   factories to skip creating transient elements while the UI is hidden.

## Building and distribution

Set up references once, then select the native loader explicitly:

```bash
uv run erenshor mod setup
uv run erenshor mod build --mod justice-for-f7 --loader bepinex
uv run erenshor mod deploy --mod justice-for-f7 --loader bepinex
uv run erenshor mod build --mod justice-for-f7 --loader lunaris
uv run erenshor mod deploy --mod justice-for-f7 --loader lunaris
```

BepInEx deployment follows `thunderstore.toml` and installs the DLL under
`<game>/BepInEx/plugins/JusticeForF7/`. Lunaris deploys to `<game>/plugins`.
Each deploy also activates its loader. Exit the game before switching, then
restart before testing. Prepare the Lunaris artifact for manual Vault upload
with:

```bash
uv run erenshor mod vault --mod justice-for-f7
```

The canonical local Thunderstore check packages all four public BepInEx mods
without uploading:

```bash
uv run erenshor mod thunderstore --dry-run
```

A real upload requires exactly one `--mod justice-for-f7` and a
non-placeholder `TCLI_AUTH_TOKEN`. There is no GitHub release automation.

Lunaris plugins may support loader-managed reloads, but this mod's release
verification uses a full game restart after deployment. See the
`mod-development` and `mod-pipeline` skills.

## Configuration

Both loaders expose a master `Enabled` switch, logging, the re-scan interval,
and a per-category toggle for each world-UI element through their native config
systems. See `JusticeSettings.cs`.
