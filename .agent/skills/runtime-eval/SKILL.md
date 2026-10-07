---
name: runtime-eval
description: Use when inspecting live Erenshor state or debugging a BepInEx mod through the HotRepl C# evaluator.
---

# Runtime evaluation with HotRepl

Use `in-game-performance-profiling` for timing methods. Use `combat-evaluation` for controlled combat experiments.

## Start and stop a session

1. Close the game and select BepInEx: `uv run erenshor mod activate --loader bepinex`.
2. Start `uv run erenshor mod launch` in a separate terminal. With a native loader active, it launches the selected game's executable through CrossOver and waits for exit.
3. After the game starts, run `uv run erenshor eval ping`. If it fails, allow startup to finish before checking `BepInEx/LogOutput.log` for HotRepl errors.
4. Exit the game when finished. If the tracked session remains, run `uv run erenshor mod launch --recover` to stop only the recorded matching process.

Use `-V playtest` or `-V demo` before both `mod` and `eval` for those variants. HotRepl is a BepInEx plugin, not a Lunaris plugin. `mod dev-setup` does not install it.

## Install or update HotRepl

Use the separate checkout at `~/src/github.com/glockyco/HotRepl`. Build its BepInEx host with the .NET SDK:

```bash
HOTREPL=~/src/github.com/glockyco/HotRepl
dotnet build "$HOTREPL/src/HotRepl.BepInEx" --nologo -v q
```

With the game closed, replace the dedicated `<game>/BepInEx/plugins/HotRepl/` directory as one unit. Copy every top-level DLL from `$HOTREPL/src/HotRepl.BepInEx/bin/Debug/netstandard2.1/` into it. Remove old HotRepl DLLs from `BepInEx/plugins/` itself. A partial or duplicate assembly set causes resolution failures. No `erenshor mod` command installs this host. The default server listens on `127.0.0.1:18590`.

## Evaluate code

```bash
uv run erenshor eval ping
uv run erenshor eval run 'SceneManager.GetActiveScene().name'
uv run erenshor eval run --json 'GameData.PlayerControl.transform.position'
uv run erenshor eval run --timeout 30000 'System.DateTime.UtcNow'
uv run erenshor eval watch --interval 60 'GameData.PlayerControl.transform.position'
uv run erenshor eval complete 'Camera.main.'
uv run erenshor eval reset
```

`--timeout` is milliseconds (default 10000). Variables persist between calls until reset. The Mono evaluator supports C# 7.x. Do not use records, switch expressions, nullable annotations, or anonymous types. Prefix static Unity object queries with `UnityEngine.Object`, such as `UnityEngine.Object.FindObjectsOfType<Camera>()`.

For AdventureGuide, use its static diagnostics before reflection:

```bash
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpState()'
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpQuest("Quest DB name")'
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpNav()'
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpZoneQuests()'
uv run erenshor eval run 'AdventureGuide.Diagnostics.DebugAPI.DumpMarkers()'
```

## ScriptEngine reload

For BepInEx scripts deployed with `--scripts`, press F6 or call ScriptEngine through HotRepl:

```bash
uv run erenshor eval run '
var asm = AppDomain.CurrentDomain.GetAssemblies().First(a => a.GetName().Name == "ScriptEngine");
var type = asm.GetType("ScriptEngine.ScriptEngine");
var inst = UnityEngine.Object.FindObjectsOfTypeAll(type).First();
type.GetMethod("ReloadPlugins", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic).Invoke(inst, null);
"reloaded"
'
```

HotRepl resets its evaluator after a ScriptEngine assembly loads. It drops stored variables and resolves the newest assembly. If cross-assembly errors persist after rapid reloads, run `uv run erenshor eval reset`. Check `BepInEx/LogOutput.log` for reload errors.

Keep scene-creating loops short. `SpellVessel.ResolveSpell` can leave simulated particle systems behind. Stop between batches, check `eval ping`, and exit the game if it no longer responds.
