---
name: mod-development
description: Native BepInEx and Lunaris mod development patterns, game class reference, and WebSocket protocol. Use when writing or modifying companion mods in src/mods/.
---

# Companion Mod Development

Patterns for native BepInEx and Lunaris mods. Assumes familiarity with Unity
lifecycle and Harmony basics (Prefix/Postfix, `__instance`, private field
access).

## Project Layout

Each mod is a directory under `src/mods/`. Common structure:

```
src/mods/<ModName>/
├── docs/                  # REQUIREMENTS.md, ARCHITECTURE.md
├── src/
│   ├── Plugin.BepInEx.cs  # Native BepInEx entrypoint and adapters
│   ├── Plugin.Lunaris.cs  # Native Lunaris entrypoint and adapters
│   ├── <Mod>Runtime.cs    # Shared lifecycle and behavior
│   ├── PluginInfo.cs      # GUID, name, generated version
│   ├── Config/            # Loader-neutral contracts/settings
│   ├── Patches/           # Shared Harmony patches
│   └── ...                # Mod-specific components
├── lib/                   # Shared game references populated by mod setup
│   ├── bepinex/           # Isolated BepInEx references
│   └── lunaris/           # Isolated Lunaris references
├── resources/             # Embedded resources (if any)
└── <ModName>.csproj
```

See each mod's ARCHITECTURE.md for internal design.

## Architecture Patterns

**Generic + Adapter**: Separate testable logic from Unity dependencies:
```csharp
// Generic - testable without Unity
public class EntityTracker<TCharacter> where TCharacter : class { }

// Adapter - wires to game types
public class EntityTrackerAdapter : IEntityTracker {
    private readonly EntityTracker<Character> _inner;
}
```

**Static Property Injection**: Harmony patches are static, so inject
dependencies via static properties before calling `PatchAll()`:
```csharp
QuestAssignPatch.Tracker = _state;
PointerOverUIPatch.Window = _window;
_harmony.PatchAll();
```

## Game Reference

Decompiled source: `variants/{variant}/unity/ExportedProject/Assets/Scripts/`

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

Use `-V main`, `-V playtest`, or `-V demo` to select the game installation.
Standard CrossOver installs are discovered by Steam App ID. Deployment activates
the selected loader, so exit the game before switching loaders and restart it
before testing.

```bash
uv run erenshor -V playtest mod setup
uv run erenshor -V playtest mod build --mod <id> --loader all
uv run erenshor -V playtest mod status
uv run erenshor -V playtest mod deploy --mod <id> --loader bepinex
uv run erenshor -V playtest mod deploy --mod <id> --loader lunaris
uv run erenshor -V playtest mod launch
```

BepInEx plugins install under `BepInEx/plugins/`. Lunaris plugins install under
the game's top-level `plugins/` directory. Check `BepInEx/LogOutput.log` for a
BepInEx target. Use Lunaris' in-game log UI for a Lunaris target. See the
`mod-pipeline` skill for shared-install proxy switching and package publication.

## Common Pitfalls

**Parameter names must match exactly** - Game uses underscore prefixes like
`_incdmg`, `_attacker`. Harmony requires exact matches.

**Unity lifecycle** - Don't access Unity objects before initialization. Use
null checks: `if (_character?.MyStats == null) return;`

**Plugin object lifetime** — every BepInEx and Lunaris entrypoint must make
`gameObject.hideFlags = HideFlags.HideAndDontSave;` the first operation in
`Awake()`, before config, events, Harmony, servers, renderers, or child objects.
BepInEx 5 otherwise exposes its shared manager when `HideManagerGameObject` is
disabled; Lunaris creates a separate `GameObject` per plugin and only applies
`DontDestroyOnLoad`, which does not protect it from Erenshor's scene cleanup.

**Scene changes** - Characters are destroyed on scene change. Clear tracked
entities and re-scan on `SceneManager.sceneLoaded`.

**Threading** - Patches run on Unity's main thread. WebSocket operations go
on background threads. Use thread-safe collections for shared state.

**BepInEx config persistence** — config files use CRLF line endings. Changing the default key in code does not update existing `.cfg` files. Delete the config file to reset, or edit it directly (mind the `\r`).

## Loader and NuGet Dependencies

BepInEx package references are private compile assets. Lunaris and its shared
runtime assemblies come from the loader-specific `lib/lunaris/` references
provisioned by `mod setup`. Never copy loader or game assemblies into a package.

Typical BepInEx-side package references include:

```xml
<PackageReference Include="BepInEx.Core" PrivateAssets="all" />
<PackageReference Include="Newtonsoft.Json" />
<PackageReference Include="ILRepack.Lib.MSBuild.Task" />
<!-- Add Fleck for a WebSocket server if needed. -->
```

Do not put versions in a project file. `src/Directory.Packages.props` owns every
NuGet version. The mod project owns separate BepInEx and Lunaris lockfiles. After
a package change, regenerate and verify both graphs:

```bash
dotnet restore src/mods/<Mod>/<Mod>.csproj -p:ModLoader=bepinex --force-evaluate
dotnet restore src/mods/<Mod>/<Mod>.csproj -p:ModLoader=lunaris --force-evaluate
erenshor test dependency-state
```

Use Newtonsoft.Json, not System.Text.Json, which is unavailable on Unity's Mono
runtime. Merge only dependencies the selected loader does not provide.

## Testing

Unit tests target `net10.0` while mod targets `netstandard2.1`. Use the
generic + adapter pattern to test core logic without Unity runtime.

## Game Input System

- Lunaris `IKeybind` consumes bound Windows key messages during gameplay and its runtime events are not reliable across installations. Register a `KeyCode` setting and poll it through `UnityKeyboardInput` instead. This uses Lunaris' enum dropdown until the loader fixes its keybind path.
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

- Run `uv run erenshor mod dev-setup` once to install ScriptEngine + ConfigurationManager
- Install or update the multi-assembly HotRepl host separately as documented in the
  `runtime-eval` skill. `mod dev-setup` does not install HotRepl
- With the game closed, run `uv run erenshor mod activate --loader bepinex`, then
  `uv run erenshor mod launch`. Do not swap loader proxy files manually
- `uv run erenshor mod deploy --mod <id> --loader bepinex --scripts` activates
  BepInEx and copies the DLL + PDB to `BepInEx/scripts/`
- Trigger ScriptEngine reload through HotRepl using the `runtime-eval` skill's
  `ReloadPlugins` reflection snippet
- Press F1 for in-game config editor when ConfigurationManager is installed
- Mod must implement `OnDestroy()` that unpatches Harmony and removes event handlers
- Full cycle: `uv run erenshor mod deploy --mod <id> --loader bepinex --scripts`
  → HotRepl `ReloadPlugins` call

## Runtime Debugging

- Use `uv run erenshor eval run '<C# expression>'` for live game inspection. See `runtime-eval` skill for full API.
- `Resources.FindObjectsOfTypeAll(type)` finds DontDestroyOnLoad objects invisible to `FindObjectOfType`
- Inspect private fields: `GetField("_name", BindingFlags.NonPublic | BindingFlags.Instance)`
- After hot reload, multiple assemblies coexist (ScriptEngine appends timestamps). Use `.Last()` to get the active one when searching by assembly name.

## WebSocket Protocol (InteractiveMapCompanion)

Quick reference. Full spec in `src/mods/InteractiveMapCompanion/docs/REQUIREMENTS.md`.

- **Port**: 18585 (configurable), binds 0.0.0.0
- **Format**: JSON with `type` field, camelCase naming
- **Coordinates**: Zone-local Unity coords [x, y, z]

**Server → Client**: `handshake` with the `entities` capability,
`stateUpdate`, and `zoneChange`.

**Client → Server**: not currently supported. Incoming messages are logged and
ignored.

**Adding messages**: Add the DTO/factory in `Protocol/Messages.cs`, emit it from
the owning runtime component, add serialization and behavior coverage, update
the frontend consumer, and update `REQUIREMENTS.md`.

## AdventureGuide

AdventureGuide has BepInEx and Lunaris entry points over one shared runtime. Keep the UI and behaviour the same on both loaders unless the maintainer approves a difference.

- `Plugin.BepInEx.cs` and `Plugin.Lunaris.cs` are thin adapters. Lifecycle, state, rendering, and cleanup stay in `Plugin.cs`.
- The mod owns a private ImGui context, font atlas, input pump, and `CommandBuffer` renderer (`src/mods/AdventureGuide/src/Rendering/ImGuiRenderer.cs`). Lunaris supplies `ImGui.NET.dll` and `cimgui`. BepInEx uses the `ImGui.NET` NuGet package and ships its native files through `thunderstore.toml`. Never check in or load private ImGui binaries.
- Roboto is an embedded resource loaded with `ImGui.MemAlloc` and `AddFontFromMemoryTTF`, not with `Lunaris.IGUI.ImGuiEx.RegisterFont`.
- Draw from `Plugin.OnGUI()` through the private renderer, never from `OnImGuiDraw()`. The renderer sets `ImGui.SetCurrentContext` for the whole frame and restores the previous context in `finally`. Keep `ImGuiIO.DisplaySize` equal to the screen size.
- Wrap window styling in `Theme.WindowStyleScope()`. Pair every `ImGui.Begin` with `ImGui.End` in `finally`, also when `Begin` returns false.
- Do not work around Lunaris keyboard capture over Lunaris-owned windows in this mod. It affects every mod and belongs upstream.
- Lunaris reloads a plugin when its DLL changes, so `OnDestroy()` must undo everything: scene and config handlers, Harmony patches, tracker, window and renderer resources, patch and debug statics, marker fonts, camera and overlap caches, and `GameData.PlayerTyping` if the mod set it. A running Playtest still needs a full restart to load a new Lunaris build.
- Prefer `Config.Register<T>()` with `[Config]`, `[ConfigSection]`, and `[Keybind]`. Use the low-level `Read`/`Write`/`OnChanged` API only for the per-character dynamic keys. Lunaris docs: `https://mizukibelhi.github.io/Lunaris-Docs/`.
- Focused checks: `uv run pytest tests/unit/mods/ -k adventure_guide tests/unit/cli/commands/test_mod.py` and `uv run erenshor mod build --mod adventure-guide --loader all`.
