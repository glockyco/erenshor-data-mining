---
name: runtime-eval
description: Runtime C# evaluation via HotRepl WebSocket. Use when inspecting live game state, debugging mod behavior, or prototyping fixes without a build cycle.
---

# Runtime Eval (HotRepl)

Execute C# code inside the running game over WebSocket. Inspect scene state, test
rendering changes, and prototype fixes without a build/deploy cycle.

## Start a HotRepl session

HotRepl is a BepInEx development dependency for Erenshor. It is not a Lunaris
plugin, and `mod launch` does not install it. With the game closed, activate
BepInEx, then launch the selected variant through Steam:

```bash
uv run erenshor mod activate --loader bepinex
uv run erenshor mod launch
uv run erenshor eval ping
```

The default variant is `main`. Pass `-V playtest` or `-V demo` before `mod` and
`eval` only when that variant is intentional. `mod deploy --loader bepinex`
also activates BepInEx when deploying a companion mod. Never swap or copy
`winhttp.dll` by hand.

HotRepl remains installed between sessions. Normal use only requires selecting
BepInEx and launching the game. Wait for Steam and the game process to finish
starting before treating a failed ping as a loader failure.

## Install or update the HotRepl host

HotRepl is maintained in `~/Projects/HotRepl/`. The current BepInEx host is a
multi-assembly deployment. Build the host from that checkout:

```bash
dotnet build ~/Projects/HotRepl/src/HotRepl.BepInEx --nologo -v q
```

The deploy source is
`src/HotRepl.BepInEx/bin/Debug/netstandard2.1/`. Deploy every top-level DLL
from that output into a dedicated `BepInEx/plugins/HotRepl/` directory. Replace the
existing HotRepl directory as one unit so every assembly comes from the same
build. The set includes `HotRepl.BepInEx.dll`, `HotRepl.Core.dll`,
`HotRepl.Protocol.dll`, evaluator and Unity-command assemblies, Fleck,
Newtonsoft.Json, and `mcs.dll`. Ensure no HotRepl DLLs remain at the
`BepInEx/plugins/` root because duplicate or partial deployments produce
assembly resolution failures.

Host deployment is an install/update operation, not part of every launch. It
must happen while the game is closed and currently has no `erenshor mod`
command. Use the complete build output rather than inventing an allowlist.
After starting the game, `BepInEx/LogOutput.log` should contain
`HotRepl v… loaded — REPL on 127.0.0.1:18590.`

## Eval commands

```bash
uv run erenshor eval ping                                     # Check connection
uv run erenshor eval run 'SceneManager.GetActiveScene().name' # Evaluate expression
uv run erenshor eval run --json 'GameData.PlayerControl.transform.position'
uv run erenshor eval reset                                    # Clear REPL state
uv run erenshor eval watch 'GameData.PlayerControl.transform.position'  # Stream
uv run erenshor eval complete 'Camera.main.'                  # Autocomplete
```

## Combat evaluation

For controlled experiments that validate damage, healing, resistance, proc,
resource, or cooldown behavior, use the `combat-evaluation` skill. Keep this
skill focused on HotRepl commands, evaluator constraints, and runtime access.

## Scene safety in loops

A loop that instantiates GameObjects each iteration can flood the scene and hang
the game: subsequent evals (even `ping`) time out and the process may not
recover on its own. Two facts learned from combat benchmarking:

- `SpellVessel.ResolveSpell` spawns a resolve particle system per call with
  `cullingMode = AlwaysSimulate`, so orphaned effects keep burning CPU. Cap loop
  iterations (a few hundred), split large samples across calls, and check `eval
  ping` latency between batches. See `combat-evaluation` for suppressing the FX
  by target distance.
- `UpdateSocialLog.chatLogLines` is a static list capped at 1500 that trims from
  the front. Counting log matches across a saturated log is unreliable; prefer a
  numeric signal (e.g. `target.DmgFromPlayerSource`) for detection.

If a loop hangs the game, killing and relaunching is faster than waiting for the
scene to drain.

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
suffixed assembly names like `AdventureGuide-639098010137845420`.

**HotRepl auto-resets on hot reload**: When a ScriptEngine-style assembly loads,
HotRepl detects it and rebuilds the evaluator session, filtering out superseded
assemblies. Types resolve to the newest version automatically. REPL variable
state is lost on reset (expected — F6 is a code change, not a data continuation).

**When auto-reset doesn't help**: If you encounter cross-assembly errors
despite auto-reset (e.g., after multiple rapid F6 reloads), use `eval reset`
manually. The reflection pattern below also works as a fallback for any
cross-assembly access:

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

## Triggering ScriptEngine hot reload

After `uv run erenshor mod deploy --mod <id> --loader bepinex --scripts`, trigger
ScriptEngine directly through HotRepl. The deployment activates BepInEx, so
restart the game first if Lunaris was active:

```bash
uv run erenshor eval run '
var asm = AppDomain.CurrentDomain.GetAssemblies()
    .First(a => a.GetName().Name == "ScriptEngine");
var type = asm.GetType("ScriptEngine.ScriptEngine");
var inst = UnityEngine.Object.FindObjectsOfTypeAll(type).First();
type.GetMethod(
    "ReloadPlugins",
    System.Reflection.BindingFlags.Instance
        | System.Reflection.BindingFlags.Public
        | System.Reflection.BindingFlags.NonPublic)
    .Invoke(inst, null);
"reloaded"
'
```

Why this shape matters:
- `FindObjectOfType(type)` can return null for the ScriptEngine singleton
- `FindObjectsOfTypeAll(type).First()` finds the `BepInEx_Manager` instance
- `ReloadPlugins` is an instance method, not static

After the reload, check `BepInEx/LogOutput.log` for:
- `Script Engine] Reloaded all plugins!`
- your mod's startup log block
- any reload-time exceptions

HotRepl auto-resets its evaluator session after ScriptEngine reload, so the
connection dropping and reconnecting once is expected.

## AdventureGuide DebugAPI

For AdventureGuide inspection, **prefer DebugAPI over raw reflection**. DebugAPI
methods are static and resolve correctly after F6 hot reload thanks to HotRepl's
auto-reset.

```bash
# Mod state overview
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpState()'

# Quest details
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpQuest("TheQuestDBName")'

# Navigation state (target, waypoint, ground path)
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpNav()'


# All quests in current zone
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpZoneQuests()'
```

## Performance Profiling

For live runtime timing, use the `in-game-performance-profiling` skill.

Keep this skill focused on HotRepl usage, evaluation quirks, and inspection.
Move detailed benchmarking patterns, Stopwatch helpers, and profiling workflow
guidance into the profiling skill so `runtime-eval` stays concise.

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
