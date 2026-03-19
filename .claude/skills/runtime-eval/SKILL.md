# Runtime Eval (HotRepl)

Execute C# code inside the running game over WebSocket. Inspect scene state, test
rendering changes, and prototype fixes without a build/deploy cycle.

## Quick Start

```bash
# Check if game + HotRepl mod are running
uv run erenshor eval ping

# Evaluate C# expression
uv run erenshor eval run '2 + 2'

# Inspect game state
uv run erenshor eval run 'SceneManager.GetActiveScene().name'
uv run erenshor eval run 'UnityEngine.Object.FindObjectsOfType<Renderer>().Length'

# JSON output for programmatic use
uv run erenshor eval run --json 'Camera.main.transform.position'

# Reset REPL state (clear variables/definitions)
uv run erenshor eval reset
```

## Architecture

HotRepl is a standalone project at `~/Projects/HotRepl`. The Erenshor CLI wraps its
WebSocket protocol.

- **HotRepl mod**: BepInEx plugin, WebSocket server on port 18590
- **Mono.CSharp.Evaluator**: Compiles and executes C# 7 code at runtime
- **REPL state persists**: Variables and types survive across eval calls
- **Thread.Abort watchdog**: Infinite loops are killed after configurable timeout

## Important: Unity API Access

Static Unity methods need the full `UnityEngine.Object.` prefix:
```bash
# WRONG - FindObjectsOfType is not a global function
uv run erenshor eval run 'FindObjectsOfType<Camera>().Length'

# RIGHT
uv run erenshor eval run 'UnityEngine.Object.FindObjectsOfType<Camera>().Length'
```

`using UnityEngine;` is pre-imported, so types like `Camera`, `Vector3`, `Renderer`,
`LayerMask`, `SceneManager` work without qualification. Only static methods on
`UnityEngine.Object` need the prefix.

## REPL State

Variables persist across calls:
```bash
uv run erenshor eval run 'var renderers = UnityEngine.Object.FindObjectsOfType<Renderer>();'
uv run erenshor eval run 'renderers.Length'
uv run erenshor eval run 'renderers.Select(r => r.gameObject.name).Take(5).ToArray()'
```

Use `erenshor eval reset` to clear all state.

## Timeout

Default timeout: 10 seconds. Configurable per-eval:
```bash
uv run erenshor eval run --timeout 3000 'while(true){}'
# => Error: Thread was being aborted. (after ~3s, game stays responsive)
```

## C# 7 Limitation

The Mono compiler supports C# 7.x only. No async/await, nullable annotations,
switch expressions, records, or ranges. All REPL/debugging features (LINQ, lambdas,
foreach, class definitions, generics) work fine.

## Common Debugging Patterns

```bash
# List all unique layers in scene
uv run erenshor eval run 'UnityEngine.Object.FindObjectsOfType<Renderer>()
    .Select(r => LayerMask.LayerToName(r.gameObject.layer))
    .Distinct().OrderBy(x => x).ToArray()'

# Find objects by name pattern
uv run erenshor eval run 'UnityEngine.Object.FindObjectsOfType<Renderer>()
    .Where(r => r.gameObject.name.Contains("Trigger"))
    .Select(r => new { r.gameObject.name, layer = LayerMask.LayerToName(r.gameObject.layer) })
    .ToArray()'

# Check camera culling mask
uv run erenshor eval run 'Camera.main?.cullingMask'

# Inspect a specific object's components
uv run erenshor eval run 'var obj = GameObject.Find("SomeObject");
    obj?.GetComponents<Component>().Select(c => c.GetType().Name).ToArray()'

# Modify rendering live
uv run erenshor eval run 'RenderSettings.ambientLight = new Color(1f, 1f, 1f);'
```

## Deploying HotRepl

HotRepl is deployed as two DLLs to BepInEx/plugins/:
- `HotRepl.BepInEx.dll` (merged: Core + Fleck + Newtonsoft.Json)
- `mcs.dll` (Mono C# compiler, shipped separately)

```bash
# Build from HotRepl project
cd ~/Projects/HotRepl && dotnet build src/HotRepl.BepInEx/

# Copy to game
cp src/HotRepl.BepInEx/bin/Debug/netstandard2.1/HotRepl.BepInEx.dll "$ERENSHOR_GAME_PATH/BepInEx/plugins/"
cp src/HotRepl.BepInEx/bin/Debug/netstandard2.1/mcs.dll "$ERENSHOR_GAME_PATH/BepInEx/plugins/"
```

## Key Files

| File | Purpose |
|---|---|
| `~/Projects/HotRepl/` | Standalone HotRepl project |
| `src/erenshor/application/eval/client.py` | Python WebSocket client |
| `src/erenshor/cli/commands/eval.py` | CLI commands (run, ping, reset) |
