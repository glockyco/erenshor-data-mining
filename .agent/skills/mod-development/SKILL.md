---
name: mod-development
description: Use when changing native BepInEx or Lunaris companion mod code, loader adapters, AdventureGuide UI, or the InteractiveMapCompanion protocol.
---

# Companion mod development

Use `mod-pipeline` for setup, builds, deployment, and releases. Use `runtime-eval` for HotRepl inspection.

## Change a native mod

1. Keep game behavior in the shared runtime. Keep `Plugin.BepInEx.cs` and `Plugin.Lunaris.cs` as loader adapters.
2. Set `gameObject.hideFlags = HideFlags.HideAndDontSave` first in each entrypoint's `Awake()`. Scene cleanup can destroy unhidden plugin objects.
3. Initialize patch dependencies before `Harmony.PatchAll()`. Match game method parameter names exactly, including leading underscores.
4. On unload, remove event handlers, unpatch Harmony, clear patch statics, and dispose renderers and servers. Lunaris can unload plugins when DLLs change.
5. Use Newtonsoft.Json for game-side JSON. Unity's Mono does not supply `System.Text.Json`.
6. Keep NuGet versions in `src/Directory.Packages.props`. Restore both graphs after a dependency change:

```bash
dotnet restore src/mods/<Mod>/<Mod>.csproj -p:ModLoader=bepinex --force-evaluate
dotnet restore src/mods/<Mod>/<Mod>.csproj -p:ModLoader=lunaris --force-evaluate
uv run erenshor test dependency-state
```

Lunaris references come from `mod setup`. Merge only dependencies the active loader does not provide.

## AdventureGuide

- Keep lifecycle, state, rendering, and cleanup in `AdventureGuideRuntime` (`src/mods/AdventureGuide/src/Plugin.cs`). Both entrypoints call it.
- Use the private ImGui context in `src/mods/AdventureGuide/src/Rendering/ImGuiRenderer.cs`. Draw from plugin `OnGUI()`, not Lunaris `OnImGuiDraw()`. Restore the previous context after each frame.
- Keep `ImGuiIO.DisplaySize` equal to the screen size. Pair each `ImGui.Begin` with `ImGui.End` in `finally`, even when `Begin` returns false.
- Use `Theme.WindowStyleScope()` for window styling. The renderer loads embedded Roboto through `ImGui.MemAlloc` and `AddFontFromMemoryTTF`.
- Poll configured `KeyCode` values through `UnityKeyboardInput`. Do not depend on Lunaris `IKeybind` events for gameplay shortcuts.
- Use `LunarisConfigBackend` for guide settings. It uses `Read`, `Write`, and `OnChanged`. Do not replace it with an unrelated `Config.Register<T>()` path.
- Clear `GameData.PlayerTyping` on unload when the guide set it. Remove scene and config handlers, patches, tracker state, fonts, and camera caches.
- If a Lunaris DLL change does not appear in a running game, restart the game. Check Lunaris' in-game log UI.

## InteractiveMapCompanion protocol

The WebSocket server binds `0.0.0.0:18585` by default. The configured port can change. Multiple clients can connect.

- On connection, send `handshake` with `protocolVersion`, `modVersion`, `zone`, and `capabilities: ["entities"]`.
- Send complete `stateUpdate` snapshots at the configured interval (default 100 ms). Each has `zone`, Unix-millisecond `timestamp`, and `entities`.
- On a zone transition, send `zoneChange` with `previousZone`, `zone`, and `timestamp`. Clients must clear the old zone's entities.
- Encode compact camelCase JSON and omit null fields. Entity positions use scene-local Unity `[x, y, z]` coordinates.
- Keep `id`, `entityType`, `name`, `position`, and `rotation` in each entity. `level`, `rarity`, `characterClass`, and `owner` are conditional.
- `ProtocolVersion.Current` is `0.2.0`. Check client handling before changing it. Entity IDs are Unity instance IDs, not stable spawn IDs.
- Classify the player first, then pets (`Master != null`), then SimPlayers, then hostile or friendly NPCs. Exclude mining nodes and chests.
- Ignore inbound client messages. Do not advertise spawn, marker, or waypoint capabilities without implementing the server and client handlers.

When adding a message, update `src/mods/InteractiveMapCompanion/src/Protocol/Messages.cs`, its producer, the map consumer, and protocol behavior tests together. The Thunderstore package ships the DLL, not internal protocol documents.
