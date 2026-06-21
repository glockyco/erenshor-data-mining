# Justice for F7

Native Lunaris plugin that extends Erenshor's F7 "Hide UI" key to also hide
world-space UI — nameplates, damage numbers, target rings, XP orbs, cast bars,
and loot prompts.

Distributed through the Erenshor Vault — see `vault/` for the listing assets and
publishing notes.

## Architecture

```
src/
├── Plugin.cs             # LunarisPlugin entry; registers config, applies patches, tracks scenes
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

## Building

```bash
uv run erenshor mod setup                        # stage game + Lunaris DLLs into lib/ (first time)
uv run erenshor mod build --mod justice-for-f7   # build bin/Debug/netstandard2.1/JusticeForF7.dll
uv run erenshor mod deploy --mod justice-for-f7  # copy to the game's plugins/ (restart to load)
uv run erenshor mod vault --mod justice-for-f7   # prepare an Erenshor Vault release
```

Native Lunaris plugins do not hot-reload by replacing the DLL — restart the game
after deploying. See the `mod-development` and `mod-pipeline` skills.

## Configuration

Settings live in the Lunaris config UI: a master `Enabled` switch, logging, the
re-scan interval, and a per-category toggle for each world-UI element. See
`JusticeSettings.cs`.
