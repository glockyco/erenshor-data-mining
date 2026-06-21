# Sprint

Native Lunaris plugin that adds a configurable sprint key to Erenshor. Hold or
toggle a key to multiply the player's run speed.

Distributed through the Erenshor Vault — see `vault/` for the listing assets and
publishing notes.

## Architecture

```
src/
├── Plugin.cs                   # LunarisPlugin entry; registers config, applies the patch, drives input
├── PluginInfo.cs               # GUID/name + generated version constant
├── Config/SprintSettings.cs    # Lunaris Config.Register settings (keybind, toggle, multiplier)
├── Core/SprintRuntime.cs       # Static sprint state + speed application, shared with the patch
└── Patches/CalcStatsPatch.cs   # Harmony postfix reapplying sprint after stat recalcs
```

## How it works

1. **Input**: `Plugin.Update()` reads the Lunaris keybind each frame — `IsHeld`
   for hold mode, edge-detected for toggle mode — and updates `SprintRuntime`.
2. **Speed**: `SprintRuntime.Apply()` recomputes `actualRunSpeed` from the
   game's base + status-effect speed, multiplying the total while sprinting and
   respecting the minimum-speed floor.
3. **Persistence**: `CalcStatsPatch` (postfix on `Stats.CalcStats`) reapplies
   sprint whenever the game recalculates stats (equipment, buffs), so vanilla
   recalculation never overwrites it. Only the player's `Stats` are affected.

## Building

```bash
uv run erenshor mod setup                 # stage game + Lunaris DLLs into lib/ (first time)
uv run erenshor mod build --mod sprint    # build bin/Debug/netstandard2.1/Sprint.dll
uv run erenshor mod deploy --mod sprint   # copy to the game's plugins/ (restart to load)
uv run erenshor mod vault --mod sprint    # prepare an Erenshor Vault release
```

Native Lunaris plugins do not hot-reload by replacing the DLL — restart the game
after deploying. See the `mod-development` and `mod-pipeline` skills for the
shared workflow.

## Configuration

Settings live in the Lunaris config UI: sprint key (default Left Shift), toggle
mode, and the speed multiplier (1.0–10.0). See `Config/SprintSettings.cs`.
