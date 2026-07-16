# Sprint

Native dual-loader plugin that adds a configurable sprint key to Erenshor. Hold
or toggle a key to multiply the player's run speed.

Sprint has native Lunaris and BepInEx adapters over one shared lifecycle. The
Lunaris release is distributed through the Erenshor Vault; the BepInEx release
is distributed through Thunderstore.

## Architecture

```
src/
├── Plugin.BepInEx.cs          # BepInEx adapter and KeyboardShortcut binding
├── Plugin.Lunaris.cs          # Lunaris adapter and IKeybind binding
├── PluginInfo.cs              # GUID/name + generated version constant
├── Config/                    # Loader-neutral contract and Lunaris settings
├── Core/SprintRuntime.cs      # Shared lifecycle, input, speed, patch, cleanup
└── Patches/CalcStatsPatch.cs  # Harmony postfix forwarding stat recalculation
```

## How it works

1. **Input**: each loader maps its native keybind to a `Func<bool>`. The shared
   lifecycle uses that pressed state for hold mode or edge-detects it for toggle
   mode.
2. **Speed**: `SprintRuntime` recomputes `actualRunSpeed` from the game's base +
   status-effect speed, multiplying the total while sprinting and respecting the
   minimum-speed floor.
3. **Persistence**: the `CalcStats` postfix reapplies sprint whenever the game
   recalculates stats (equipment, buffs), so vanilla recalculation never
   overwrites sprint. Only the player's `Stats` are affected.
4. **Cleanup**: both adapters forward unload to the shared idempotent lifecycle,
   which restores base speed before unpatching and resetting static state.

## Building

```bash
uv run erenshor mod setup
uv run erenshor mod build --mod sprint --loader lunaris
uv run erenshor mod build --mod sprint --loader bepinex
uv run erenshor mod deploy --mod sprint --loader lunaris
uv run erenshor mod deploy --mod sprint --loader bepinex
```

The Lunaris Vault package contains only `Sprint.dll`. The BepInEx Thunderstore
package also contains only the loader-specific `Sprint.dll`; BepInEx supplies
Harmony and other shared dependencies.

## Configuration

Both loaders expose Enabled, sprint key, toggle mode, and the speed multiplier.
The defaults are Enabled, Left Shift, hold mode, and `1.5x`. The multiplier
range is `1.0–10.0`.
