# MapTileCapture BepInEx Mod

BepInEx plugin that renders orthographic map captures from inside the running game.
For the full capture pipeline (Python orchestrator, tile generation, zone setup), see the
`tile-capture` skill.

## Build & Deploy

```bash
# From repo root — always use these, not dotnet directly
uv run erenshor mod build --mod map-tile-capture
uv run erenshor mod deploy --mod map-tile-capture

# Game must be restarted to pick up a new DLL
pkill -f "Erenshor.exe"
```

## Tunable Constants

`Plugin.cs` exposes `public static float` fields — no BepInEx config, no recompile needed
for runtime tuning via HotRepl:

- `BackgroundR/G/B` — camera clear colour for areas outside terrain
- `IndoorDirectional*` / `IndoorAmbient*` — lighting for zones with `usingSun = false`
- `DefaultStabilityFrames`, `DefaultSceneLoadTimeoutSecs`

## Non-Obvious Constraints

- **Newtonsoft.Json only** — `System.Text.Json` is not available on Unity's Mono runtime.
- **ILRepack** merges Fleck + Newtonsoft.Json into the output DLL. If you add a NuGet
  dependency, update `ILRepack.targets` or it won't be available at runtime.
- `GeometrySuppressor` is `IDisposable` — always use it in a `using` block. It creates a
  temporary directional light that must be destroyed on exit.
- Scene load via `GameData.SceneChange.ChangeScene()` — not `SceneManager.LoadScene()` —
  to get correct per-zone atmosphere and lighting initialisation.
