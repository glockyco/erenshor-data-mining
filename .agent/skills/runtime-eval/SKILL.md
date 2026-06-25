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

## Plugin prerequisites

HotRepl needs **two** DLLs in `BepInEx/plugins/`:
- `HotRepl.BepInEx.dll` — the plugin itself
- `mcs.dll` — required by `HotRepl.Evaluator.MonoCSharpEvaluator`. HotRepl loads but crashes on first eval if missing.

A fresh game install (e.g. a newly-installed playtest beta) typically has neither. Copy both from a working install:

```bash
cp "$MAIN_INSTALL/BepInEx/plugins/HotRepl.BepInEx.dll" "$NEW_INSTALL/BepInEx/plugins/"
cp "$MAIN_INSTALL/BepInEx/plugins/mcs.dll" "$NEW_INSTALL/BepInEx/plugins/"
```

Restart the game; `BepInEx/LogOutput.log` should report `HotRepl … REPL on port 18590`.

### Lunaris-based installs (HotRepl needs the BepInEx loader)

HotRepl is a **multi-assembly** BepInEx plugin (HotRepl.Core/Protocol/Evaluator +
Roslyn + `mcs` + Fleck) and only loads under the **BepInEx** loader (the doorstop
`winhttp.dll` proxy). Some installs now use the **Lunaris** loader instead — its own
`winhttp.dll`, with BepInEx's kept as `winhttp.bepinex-backup.dll` (the playtest is
like this today).

HotRepl does **not** drop into Lunaris's `plugins/`. Lunaris loads only single,
self-contained plugin DLLs (Sprint, JusticeForF7 are each one ILRepacked DLL):
`PluginLoader.ScanPlugin` reads each `plugins/**/*.dll` from an in-memory stream
with a Cecil resolver that has no sibling-directory context, so HotRepl's
cross-assembly attribute refs (HotRepl.Core, Newtonsoft.Json) fail to resolve,
`HotRepl.Core`/`HotRepl.Protocol` never load, and `eval ping` fails.

To use HotRepl on a Lunaris install, temporarily swap the loader, then restore —
**only while the game is closed**:

```bash
PT="…/Erenshor Playtest"
cp -f "$PT/winhttp.dll" "$PT/winhttp.lunaris.dll"        # back up Lunaris loader (once)
cp -f "$PT/winhttp.bepinex-backup.dll" "$PT/winhttp.dll" # activate BepInEx
# launch via Steam, load a character, run eval/export, quit the game, then:
cp -f "$PT/winhttp.lunaris.dll" "$PT/winhttp.dll"        # restore Lunaris
```

A proper fix (keep the install on Lunaris) would require ILRepacking HotRepl into one
self-contained plugin DLL, or a Lunaris-side resolver change. Until then, the loader
swap is the supported path. Launch via **Steam** (not a bare `wine` call from another
cwd) so the app-local `winhttp.dll` bootstraps.

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

After `erenshor mod deploy --mod <id> --scripts`, trigger ScriptEngine
directly through HotRepl:

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
