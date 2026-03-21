# InteractiveMapCompanion Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Unity Game                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Character│  │ Character│  │ Character│  │SpawnPoint│   │
│  │ (Player) │  │(SimPlayer│  │  (NPC)   │  │          │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │              │          │
│       └─────────────┴─────────────┴──────────────┘          │
│                           │                                  │
│                    ┌──────┴──────┐                          │
│                    │EntityTracker│ ◄── Scene events          │
│                    └──────┬──────┘                          │
│                           │                                  │
│  ┌────────────┐    ┌──────┴──────┐    ┌──────────────┐     │
│  │ MarkerAPI  │───►│ StateManager│◄───│SpawnTracker  │     │
│  └────────────┘    └──────┬──────┘    └──────────────┘     │
│                           │                                  │
│                    ┌──────┴──────┐                          │
│                    │ Serializer  │                          │
│                    └──────┬──────┘                          │
│                           │                                  │
│                    ┌──────┴──────┐                          │
│                    │WebSocket Srv│ ◄── Fleck                │
│                    └──────┬──────┘                          │
└───────────────────────────┼─────────────────────────────────┘
                            │ ws://0.0.0.0:18584
                            ▼
┌───────────────────────────────────────────────────────────┐
│                    Map Website                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │WebSocket Clnt│─►│ Live State   │─►│ Entity Layer │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└───────────────────────────────────────────────────────────┘
```

## Project Structure

```
src/mods/InteractiveMapCompanion/
├── docs/
│   ├── REQUIREMENTS.md
│   └── ARCHITECTURE.md
├── src/
│   ├── Plugin.cs              # Entry point, manual wiring
│   ├── PluginInfo.cs          # GUID, name, version
│   ├── Config/
│   │   └── ModConfig.cs       # BepInEx configuration
│   ├── Entities/
│   │   ├── IEntityTracker.cs
│   │   ├── EntityTracker.cs   # Generic, testable
│   │   ├── EntityTrackerAdapter.cs
│   │   ├── EntityClassifier.cs
│   │   ├── EntityExtractor.cs
│   │   ├── EntityFinder.cs
│   │   └── EntityData.cs
│   ├── Overlay/               # In-game map overlay (Steam HTML Surface)
│   │   ├── MapOverlay.cs
│   │   ├── BrowserManager.cs
│   │   ├── BrowserRenderer.cs
│   │   └── InputForwarder.cs
│   ├── Patches/
│   │   ├── CharSelectManagerPatch.cs
│   │   └── MapKeyPatches.cs
│   ├── Protocol/
│   │   ├── Messages.cs        # Message types
│   │   ├── MessageSerializer.cs  # Newtonsoft.Json, camelCase
│   │   └── ProtocolVersion.cs
│   ├── Server/
│   │   ├── IWebSocketServer.cs
│   │   └── WebSocketServer.cs
│   │   └── ClientHandler.cs   # (planned)
│   ├── State/
│   │   ├── IBroadcastLoop.cs  # Current implementation
│   │   └── BroadcastLoop.cs   # (planned: StateManager)
│   ├── Spawns/                # (planned)
│   │   ├── ISpawnTracker.cs
│   │   ├── SpawnTracker.cs
│   │   └── RespawnTimer.cs
│   └── Markers/               # (planned)
│       ├── IMarkerAPI.cs      # Public interface
│       ├── MarkerRegistry.cs
│       └── MarkerDefinition.cs
├── lib/                       # Game DLLs (not committed)
└── InteractiveMapCompanion.csproj
```

## Key Patterns

### Manual Wiring

Components wired directly in `Plugin.Awake()` (DI framework was removed
to reduce dependencies for Thunderstore packaging):

```csharp
var finder = new EntityFinder();
var classifier = new EntityClassifier();
var extractor = new EntityExtractor();
var tracker = new EntityTrackerAdapter(finder, classifier, extractor, _ => true);

_server = new WebSocketServer(_config, Log);
_broadcastLoop = new BroadcastLoop(tracker, _server, _config, ...);
```

Planned: reintroduce DI via `ServiceCollection` when StateManager,
SpawnTracker, and MarkerAPI are implemented.

### Generic + Adapter Pattern

Separates testable logic from Unity dependencies:

```csharp
// Generic - testable without Unity
public class EntityTracker<TCharacter> where TCharacter : class
{
    private readonly Func<TCharacter, EntityData> _extractor;
    // Pure logic, no Unity calls
}

// Adapter - wires to game types
public class EntityTrackerAdapter : IEntityTracker
{
    private readonly EntityTracker<Character> _inner;
    // Handles Unity-specific concerns
}
```

### State Management

Currently implemented as `BroadcastLoop` which ticks on `Update()`,
collects entity data from `EntityTracker`, and broadcasts via WebSocket.

Planned: refactor into `StateManager` that aggregates entities, spawn
timers (SpawnTracker), and third-party markers (MarkerAPI) into a
unified `GameState` object.

## Data Flow

### Outbound (Game → Website)

1. **EntityTracker** scans scene for Character components
2. **SpawnTracker** monitors death/respawn events
3. **MarkerRegistry** holds third-party markers
4. **StateManager** aggregates all data
5. **MessageSerializer** converts to JSON
6. **WebSocketServer** broadcasts to clients

### Inbound (Website → Game)

1. **WebSocketServer** receives client message
2. **ClientHandler** parses and validates
3. **Event emitted** for message type
4. **Handlers** process (set waypoint, etc.)
5. **Acknowledgment** sent to client

## Threading

- **Main thread**: Unity callbacks, entity tracking, state updates
- **Background threads**: WebSocket I/O (Fleck handles this)
- **Synchronization**: Thread-safe collections for client list, marker registry

## Extension Points

### Third-Party Markers

Other mods register markers via `IMarkerAPI`:

```csharp
// Discovery
var mapCompanion = Chainloader.PluginInfos
    .GetValueOrDefault("wow-much.interactive-map-companion");
var api = mapCompanion?.Instance as IMarkerAPI;

// Registration
api?.RegisterMarker(new MarkerDefinition { ... });
```

### Client Message Events

Mods can subscribe to handle custom interactions:

```csharp
stateManager.OnWaypointSet += (pos, zone) => { ... };
stateManager.OnPingReceived += (pos, zone) => { ... };
```

## Protocol Versioning

Protocol version `0.x.y` indicates alpha - breaking changes expected.

Handshake includes version for client validation:

```json
{
  "type": "handshake",
  "protocolVersion": "0.1.0",
  ...
}
```

Clients should warn on version mismatch, not hard fail.

## Configuration

BepInEx ConfigEntry pattern:

```csharp
public class ModConfig
{
    public ConfigEntry<int> Port { get; }
    public ConfigEntry<int> UpdateInterval { get; }
    // ...

    public ModConfig(ConfigFile config)
    {
        Port = config.Bind("Server", "Port", 18584, "WebSocket port");
        // ...
    }
}
```

## Error Handling

- **Never crash the game**: All external calls wrapped in try/catch
- **Log errors**: Use BepInEx logger
- **Graceful degradation**: Missing data → empty arrays, not exceptions
- **Client errors**: Invalid messages logged and ignored
