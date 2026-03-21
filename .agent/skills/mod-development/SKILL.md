---
name: mod-development
description: BepInEx mod development patterns, game class reference, WebSocket protocol. Use when writing or modifying companion mods in src/mods/.
---

# BepInEx Mod Development

Project-specific patterns for InteractiveMapCompanion. Assumes familiarity with
BepInEx and Harmony basics (Prefix/Postfix, `__instance`, private field access).

## Project Structure

```
src/mods/InteractiveMapCompanion/
├── docs/
│   ├── REQUIREMENTS.md     # Feature specifications
│   └── ARCHITECTURE.md     # Component design
├── src/
│   ├── Plugin.cs           # Entry point, composition root
│   ├── PluginInfo.cs       # GUID, name, version
│   ├── Entities/           # Entity tracking and classification
│   ├── Server/             # WebSocket server (Fleck)
│   ├── Protocol/           # Message types and serialization
│   ├── Spawns/             # Spawn point and respawn tracking
│   ├── Markers/            # Third-party marker API
│   └── Config/             # BepInEx configuration
├── lib/                    # Game DLLs (not committed)
└── InteractiveMapCompanion.csproj
```

## Architecture Patterns

**Dependency Injection**: Use `Microsoft.Extensions.DependencyInjection` for
composition. Wire services in `Plugin.Awake()`.

**Generic + Adapter**: Separate testable logic from Unity dependencies:
```csharp
// Generic - testable without Unity
public class EntityTracker<TCharacter> where TCharacter : class { }

// Adapter - wires to game types
public class EntityTrackerAdapter : IEntityTracker {
    private readonly EntityTracker<Character> _inner;
}
```

**Static Property Injection**: Harmony patches are static, so inject services
via static properties before patching:
```csharp
DamageMePatch.Emitter = services.GetRequiredService<IEventEmitter>();
_harmony.PatchAll();
```

## Game Reference

Decompiled source: `variants/playtest/unity/ExportedProject/Assets/Scripts/`

Key classes for entity tracking:

| Class | Purpose |
|-------|---------|
| `Character` | Base for all combatants, has Faction enum |
| `NPC` | Enemy/friendly NPC behavior, SimPlayer flag |
| `SimPlayer` | AI companion behavior |
| `Stats` | Health, level, combat stats |
| `SpawnPoint` | Enemy spawn configuration |

Entity identification:
- Player: `transform.name == "Player"`
- SimPlayer: Has `SimPlayer` component
- Pet: `Master != null` or `SummonedByPlayer`
- NPC: Has `NPC` component, check faction for friendly/hostile

## CLI Commands

```bash
uv run erenshor mod setup    # Copy game DLLs to lib/
uv run erenshor mod build    # Build the mod
uv run erenshor mod deploy   # Build and copy to BepInEx plugins
uv run erenshor mod launch   # Start the game
```

Check `BepInEx/LogOutput.log` for errors.

## Common Pitfalls

**Parameter names must match exactly** - Game uses underscore prefixes like
`_incdmg`, `_attacker`. Harmony requires exact matches.

**Unity lifecycle** - Don't access Unity objects before initialization. Use
null checks: `if (_character?.MyStats == null) return;`

**Scene changes** - Characters are destroyed on scene change. Clear tracked
entities and re-scan on `SceneManager.sceneLoaded`.

**Threading** - Patches run on Unity's main thread. WebSocket operations go
on background threads. Use thread-safe collections for shared state.

**BepInEx config persistence** — config files use CRLF line endings. Changing the default key in code does not update existing `.cfg` files. Delete the config file to reset, or edit it directly (mind the `\r`).

## NuGet Dependencies

```xml
<PackageReference Include="BepInEx.Core" Version="5.*" />
<PackageReference Include="HarmonyX" Version="2.*" />
<PackageReference Include="PolySharp" Version="1.15.0" />  <!-- C# polyfills -->
<PackageReference Include="Microsoft.Extensions.DependencyInjection" Version="9.*" />
<PackageReference Include="System.Text.Json" Version="9.*" />
<PackageReference Include="Fleck" Version="1.*" />  <!-- WebSocket -->
```

## Testing

Unit tests target `net9.0` while mod targets `netstandard2.1`. Use the
generic + adapter pattern to test core logic without Unity runtime.

## Game Input System

- `EventSystem.IsPointerOverGameObject()` gates mouse input in `PlayerControl.cs` and `CameraController.cs`
- IMGUI windows do NOT register with EventSystem. Patch it via Harmony postfix to return true when cursor is over the IMGUI window.
- `Cursor.lockState = CursorLockMode.Locked` moves `Input.mousePosition` to screen center. Skip hit-testing when locked — the game locks cursor during camera drag.
- Camera rotation (right-click): `CameraController.cs` ~line 297, checks `IsPointerOverGameObject`
- Camera orbit (left-click): `CameraController.cs` ~line 339, checks `IsPointerOverGameObject`
- Track drag state: latch `IsMouseOver = true` on mouse-down inside window rect, release on mouse-up. Prevents cursor from outrunning the window during fast drags.

## IMGUI Development

- Defer `GUIStyle` init to first `OnGUI` call — `GUI.skin` is not available in `Awake`
- `GUI.DragWindow()` does not clamp to screen bounds. Clamp `_windowRect` after every `GUILayout.Window` call.
- `Input.mousePosition` updates every frame. `Event.current.mousePosition` updates per IMGUI event. Use `Input.mousePosition` with Y-flip (`Screen.height - y`) for frame-accurate hit testing.
- Use `GUILayout.Window` for draggable windows, `GUILayout.BeginScrollView` for scrollable panels.
- Dark background: create `Texture2D(1,1)`, set pixel, apply. Assign to `GUIStyle.normal.background`.

## Hot Reload Workflow

- Run `erenshor mod dev-setup` once to install ScriptEngine + ConfigurationManager
- `erenshor mod deploy --mod <id> --scripts` copies DLL + PDB to `BepInEx/scripts/`
- Press F6 in game to reload. Press F1 for in-game config editor.
- Mod must implement `OnDestroy()` that unpatches Harmony and removes event handlers.
- Full cycle: `mod build --mod <id>` → `mod deploy --mod <id> --scripts` → F6

## Runtime Debugging

- Use `erenshor eval run '<C# expression>'` for live game inspection. See `runtime-eval` skill for full API.
- `Resources.FindObjectsOfTypeAll(type)` finds DontDestroyOnLoad objects invisible to `FindObjectOfType`
- Inspect private fields: `GetField("_name", BindingFlags.NonPublic | BindingFlags.Instance)`
- After hot reload, multiple assemblies coexist (ScriptEngine appends timestamps). Use `.Last()` to get the active one when searching by assembly name.

## WebSocket Protocol (InteractiveMapCompanion)

Quick reference. Full spec in `src/mods/InteractiveMapCompanion/docs/REQUIREMENTS.md`.

- **Port**: 18585 (configurable), binds 0.0.0.0
- **Format**: JSON with `type` field, camelCase naming
- **Coordinates**: Zone-local Unity coords [x, y, z]

**Server -> Client**: handshake, state, zone_change, spawn_death/spawn_respawn, marker_add/update/remove
**Client -> Server**: set_waypoint/clear_waypoint, ping_location

**Adding messages**: Add record in Protocol/Messages.cs, add to MessageSerializer switch, update REQUIREMENTS.md.
