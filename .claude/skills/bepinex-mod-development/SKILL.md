---
name: bepinex-mod-development
description: BepInEx mod development patterns. Use when working on InteractiveMapCompanion, adding hooks, or finding game methods.
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
