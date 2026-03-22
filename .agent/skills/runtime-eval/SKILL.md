---
name: runtime-eval
description: Runtime C# evaluation via HotRepl WebSocket. Use when inspecting live game state, debugging mod behavior, or prototyping fixes without a build cycle.
---

# Runtime Eval (HotRepl)

Execute C# code inside the running game over WebSocket. Inspect scene state, test
rendering changes, and prototype fixes without a build/deploy cycle.

## Quick Start

```bash
uv run erenshor eval ping                                    # Check connection
uv run erenshor eval run 'SceneManager.GetActiveScene().name' # Evaluate expression
uv run erenshor eval run --json 'GameData.PlayerControl.transform.position'
uv run erenshor eval reset                                    # Clear REPL state
uv run erenshor eval watch 'GameData.PlayerControl.transform.position'  # Stream
uv run erenshor eval complete 'Camera.main.'                  # Autocomplete
```

## C# 7 Limitations

The Mono compiler supports C# 7.x only. These **do not work**:

- `async`/`await`, nullable annotations, switch expressions, records, ranges
- **Anonymous types** (`new { foo = 1 }`) — compiles to internal classes the
  REPL's dynamic assembly can't emit. Use tuples or string concatenation instead.

```bash
# WRONG — anonymous type fails to compile
uv run erenshor eval run 'objects.Select(o => new { o.name, o.tag }).ToArray()'

# RIGHT — use string formatting
uv run erenshor eval run 'objects.Select(o => o.name + " tag=" + o.tag).ToArray()'
```

## ScriptEngine Cross-Assembly Gotchas

Hot-reloaded mods (deployed via `--scripts`, reloaded with F6) get timestamp-
suffixed assembly names like `AdventureGuide-639098010137845420`. This creates
**type identity mismatches** that break common reflection patterns:

**`FindObjectsOfType<T>()` returns empty**: The generic type parameter `T` resolves
from the REPL's assembly context, which differs from the ScriptEngine-loaded assembly.
The runtime sees them as different types.

```bash
# WRONG — T resolves to wrong assembly, returns empty
uv run erenshor eval run 'UnityEngine.Object.FindObjectsOfType<BepInEx.BaseUnityPlugin>().Length'
# => 0

# RIGHT — use typeof() string matching via Resources
uv run erenshor eval run 'Resources.FindObjectsOfTypeAll(typeof(MonoBehaviour)).Where(o => o.GetType().FullName == "AdventureGuide.Plugin").Count()'
# => 1
```

**Reflection with private fields**: After finding an object via string-based type
matching, use the object's own `.GetType()` for reflection — never a separately
loaded `Type`. The field/property metadata must come from the same assembly as the
instance.

```bash
# Pattern: find object by string name, reflect through its own type
uv run erenshor eval run '
var ag = Resources.FindObjectsOfTypeAll(typeof(MonoBehaviour))
    .First(o => o.GetType().FullName == "AdventureGuide.Plugin");
var bf = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
var state = ag.GetType().GetField("_state", bf).GetValue(ag);
state.GetType().GetProperty("CurrentZone").GetValue(state)
'
```

## AdventureGuide DebugAPI

For AdventureGuide inspection, **prefer DebugAPI over raw reflection**. DebugAPI
methods are static, merged into the plugin assembly, and callable without cross-
assembly gymnastics.

```bash
# Mod state overview
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpState()'

# Quest details
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpQuest("TheQuestDBName")'

# Navigation state (target, waypoint, ground path)
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpNav()'

# Entity registry for a display name
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpEntities("A Highwayman Raider")'

# All quests in current zone
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpZoneQuests()'
```

## Unity API Access

Static Unity methods need the full `UnityEngine.Object.` prefix:

```bash
# WRONG
uv run erenshor eval run 'FindObjectsOfType<Camera>().Length'

# RIGHT
uv run erenshor eval run 'UnityEngine.Object.FindObjectsOfType<Camera>().Length'
```

Pre-imported namespaces: `UnityEngine`, `UnityEngine.SceneManagement`, `System.Linq`.

## REPL State

Variables persist across calls. Use `eval reset` to clear.

```bash
uv run erenshor eval run 'var npcs = NPCTable.LiveNPCs;'
uv run erenshor eval run 'npcs.Count'
uv run erenshor eval run 'npcs.Select(n => n.NPCName).Distinct().OrderBy(x => x).ToArray()'
```

## Timeout

Default: 10 seconds. Override per-call:

```bash
uv run erenshor eval run --timeout 3000 'while(true){}'  # ms, killed after ~3s
```

## Key Files

| File | Purpose |
|---|---|
| `~/Projects/HotRepl/` | Standalone HotRepl project |
| `src/erenshor/application/eval/client.py` | Python WebSocket client |
| `src/erenshor/cli/commands/eval.py` | CLI commands |
| `src/mods/AdventureGuide/src/Diagnostics/DebugAPI.cs` | AdventureGuide inspection API |
