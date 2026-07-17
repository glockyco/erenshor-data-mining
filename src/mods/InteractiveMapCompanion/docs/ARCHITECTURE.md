# Interactive Map Companion Architecture

## Scope

Interactive Map Companion is a native dual-loader mod. Thin BepInEx and Lunaris
entrypoints adapt loader-owned configuration and logging to one
`InteractiveMapRuntime`. The shared runtime tracks live characters, broadcasts
the current state over WebSocket, and owns the optional Steam HTML overlay.

Spawn monitoring, third-party marker registration, and client-to-game navigation
are not implemented. The handshake advertises only the `entities` capability.

## Runtime flow

```text
Plugin.BepInEx.cs ─┐
                   ├─> InteractiveMapRuntime
Plugin.Lunaris.cs ─┘      ├─> EntityTrackerAdapter
                          │     ├─> EntityFinder
                          │     ├─> EntityClassifier
                          │     └─> EntityExtractor
                          ├─> BroadcastLoop
                          │     └─> WebSocketServer (Fleck)
                          ├─> MapOverlay (Steam HTML Surface)
                          └─> Harmony patches

WebSocketServer ── ws://0.0.0.0:18585 ──> map website clients
```

Both entrypoints:

1. mark their owning `GameObject` as `HideAndDontSave` before initialization;
2. create native config and logger adapters;
3. call `InteractiveMapRuntime.Start()` from `Awake()`;
4. forward `Update()`, `OnApplicationQuit()`, and `OnDestroy()`; and
5. call the same idempotent runtime cleanup path.

Only one loader is active in a game process. The loader-specific assemblies are
built separately and must never be compiled into the same target.

## Project structure

```text
src/mods/InteractiveMapCompanion/
├── src/
│   ├── Plugin.BepInEx.cs          # BepInEx entrypoint, config, and logger adapters
│   ├── Plugin.Lunaris.cs          # Lunaris entrypoint, config, and logger adapters
│   ├── InteractiveMapRuntime.cs   # Shared composition and lifecycle
│   ├── IModLogger.cs              # Loader-neutral logging contract
│   ├── PluginInfo.cs
│   ├── Config/
│   │   └── ModConfig.cs           # IModConfig and shared capability calculation
│   ├── Entities/                  # Find, classify, extract, and track Characters
│   ├── Overlay/                   # Steam HTML overlay, rendering, and input
│   ├── Patches/                   # Character-select and map-key Harmony patches
│   ├── Protocol/                  # Messages, serializer, and protocol version
│   ├── Server/                    # Fleck WebSocket server
│   └── State/                     # Timed state and zone-change broadcasts
├── docs/
│   ├── ARCHITECTURE.md
│   └── REQUIREMENTS.md
├── thunderstore/                  # BepInEx package listing assets
├── vault/                         # Lunaris Vault listing assets
└── InteractiveMapCompanion.csproj
```

The loader-neutral entity, protocol, and broadcast logic is covered by the
`tests/InteractiveMapCompanion.Tests/` project.

## Composition and lifecycle

`InteractiveMapRuntime.Start()` performs explicit composition without a DI
container:

1. construct `EntityFinder`, `EntityClassifier`, and `EntityExtractor`;
2. wrap them in `EntityTrackerAdapter`;
3. start `WebSocketServer`;
4. create `BroadcastLoop` and seed it with the active scene;
5. add and configure `MapOverlay` on the loader's `GameObject`; and
6. apply the assembly's Harmony patches.

`Tick()` advances only the broadcast interval. Scene changes are received through
`SceneManager.sceneLoaded` and forwarded to `BroadcastLoop`.

`Stop()` is safe to call repeatedly. It stops broadcasts and the server, stops and
destroys the overlay, detaches scene events, unpatches Harmony, clears patch
statics, and releases component references. `WebSocketServer.Dispose()` closes
clients, disposes Fleck, and restores the process-wide Fleck logging callback.
This cleanup is required for loader-managed unloads and repeat starts.

## Entity tracking

`EntityFinder` supplies live `Character` instances. `EntityClassifier` excludes
mining nodes and treasure chests, then classifies each character as:

- `player`, using `GameData.PlayerControl.Myself`;
- `pet`, when `Character.Master` is present;
- `simplayer`, when the `SimPlayer` component is present;
- `npc_enemy`, from aggressive factions or non-positive world-faction standing;
  or
- `npc_friendly` otherwise.

`EntityExtractor` emits:

- instance ID, type, display name, `[x, y, z]` position, and Y-axis rotation;
- level when stats are available;
- `common` or `boss` rarity for hostile NPCs;
- class display name for the player and SimPlayers; and
- owner name for pets.

Rare-spawn classification and spawn-point identity require spawn context and are
not part of the current entity payload.

## WebSocket protocol

The server binds `ws://0.0.0.0:<Port>` and supports multiple clients. The default
port is `18585`. Fleck owns socket I/O, while entity collection and broadcast
timing originate from Unity's main-thread callbacks.

On connection, the server sends a `handshake`. At the configured interval,
`BroadcastLoop` sends a complete `stateUpdate` when at least one client is
connected. A scene transition sends `zoneChange`, followed by the state for the
new scene. `MessageSerializer` emits camelCase JSON and omits null fields.

Incoming messages are currently logged at debug level and otherwise ignored.
There are no waypoint, ping, command, marker, or spawn-timer handlers.

See `REQUIREMENTS.md` for the exact payload contract and the explicit future
scope.

## Configuration

`IModConfig` is the shared runtime contract. The BepInEx entrypoint binds it to
`ConfigEntry<T>` values. The Lunaris entrypoint binds it to a registered
`MapSettings` object and native keybind.

Both adapters expose the same settings:

- WebSocket port and update interval;
- WebSocket and mod log levels;
- overlay enabled state and toggle key;
- overlay anchor, width, and height; and
- reset-to-defaults state.

Capability calculation is shared in `ModConfigBase` and currently returns only
`entities`.

## Build and deployment

Use the repository CLI rather than invoking `dotnet` directly:

```bash
uv run erenshor mod setup
uv run erenshor mod build --mod interactive-map-companion --loader all
uv run erenshor -V playtest mod deploy --mod interactive-map-companion --loader bepinex
uv run erenshor -V playtest mod deploy --mod interactive-map-companion --loader lunaris
```

Deployment activates the selected loader. See the `mod-pipeline` skill for
variant resolution, shared-install proxy switching, package layouts, and release
commands.
