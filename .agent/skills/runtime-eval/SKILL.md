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

Use `-V playtest` or `-V demo` before both `mod` and `eval` for those variants. HotRepl has a BepInEx host and a Lunaris host; the installed host must match the active loader. `mod dev-setup` installs neither.

Under Lunaris, quitting the game crashes inside Lunaris's own `Bridge.ClearCache()` after the save completes. End the crashed process only after `saving game...` appears in `Player.log`. When Steam is not connected, `ApplyOptions.ApplyGFX` throws "Steamworks is not initialized", leaves the camera far clip at 1 m (sky only) and blocks menu clicks; make sure no game on the same Steam account is running elsewhere.

## Install or update HotRepl

Use the separate checkout at `~/src/github.com/glockyco/HotRepl`. Build its BepInEx host with the .NET SDK:

```bash
HOTREPL=~/src/github.com/glockyco/HotRepl
dotnet build "$HOTREPL/src/HotRepl.BepInEx" --nologo -v q
```

With the game closed, replace the dedicated `<game>/BepInEx/plugins/HotRepl/` directory as one unit. Copy every top-level DLL from `$HOTREPL/src/HotRepl.BepInEx/bin/Debug/netstandard2.1/` into it. Remove old HotRepl DLLs from `BepInEx/plugins/` itself. A partial or duplicate assembly set causes resolution failures. No `erenshor mod` command installs this host. The default server listens on `127.0.0.1:18590`.

For Lunaris, build `$HOTREPL/src/HotRepl.Host.Lunaris/HotRepl.Host.Lunaris.csproj` with `-p:LunarisPath=<repo>/src/mods/AdventureGuide/lib/lunaris/Lunaris.dll`. Replace `<game>/plugins/HotRepl/` with the contents of its `bin/Debug/netstandard2.1/plugins/HotRepl/` directory. Lunaris starts manually installed plugins disabled; enable HotRepl once in the Lunaris plugin installer. The enabled state persists in `plugins/config/pluginManifests.lpm`. Lunaris hot-reloads the host when its DLL changes, but libraries such as `HotRepl.Core.dll` load once per game process, so changes to them need a restart.

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

The client requires HotRepl protocol v2. `eval ping` measures connection plus handshake
latency (there is no v2 ping request) and reports the host and evaluator. `run --json`
prints the native JSON value and its `hasValue`, `valueType`, `truncated` and
`truncatedBytes` metadata without parsing the value a second time. Plain output marks
oversized values as `<truncated: N bytes>` rather than presenting them as null results.
`watch --json` prints each raw subscription frame; a subscription error ends the watch.
All server errors display `kind/code: message`; JSON errors retain the v2 `error` envelope
including `retryable` and `details`. `complete --cursor -1` omits the optional v2 cursor,
letting the server choose the end of the expression.

## Typed commands, jobs and artifacts

The installed BepInEx host includes HotRepl.UnityCommands. Discover the current catalog
and schemas before invoking a command:

```bash
uv run erenshor eval commands
uv run erenshor eval describe unity.app.info
uv run erenshor eval call unity.app.info --args '{}' --json
uv run erenshor eval journal --kind command --limit 20 --json
```

`call --args` requires a JSON object. Sync commands return `command_result`; job
commands return `job_accepted` and the client polls `job_status` until `job_result`.
`call --timeout` is an overall command/job deadline in milliseconds (default 30000)
and is also sent as the command's server timeout. Ctrl-C or a deadline requests
`job_cancel` for an accepted job. Stopping a watch or cancelling an eval sends
`cancel` with a separate request ID and the original `targetId`.

Successful calls verify every artifact's finalization, byte size and SHA-256 before
returning the terminal response. To print a named UTF-8 attachment from a command,
add `--artifact NAME` instead of `--json`; names come from the command's descriptor
and returned artifact map. This does not delete the server's files. Wine `C:\...`
paths are mapped through the selected variant's existing CrossOver Steam bottle
resolver (including `CROSSOVER_BOTTLE`), and `Z:\...` uses the shared host-root mapping.
Do not trust domain-specific content solely because its hash verifies: check the
command's schema and expected record counts before using exported JSON as game data.

`journal` returns recent eval and command entries; omit `--kind` to include both.
An `assembly_reload` notification is shown on stderr, leaving JSON stdout intact.
Command descriptors and catalogs are fetched afresh, so reloads cannot leave cached
schemas behind. `session_evicted` fails pending operations with the server's reason
and optional replacing client name.

## AdventureGuide diagnostics

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
