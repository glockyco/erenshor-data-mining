# MapTileCapture Mod

Native BepInEx and Lunaris plugins share the loader-neutral capture runtime.
For the full capture pipeline (Python orchestrator, tile generation, zone setup), see the
`tile-capture` skill.

## Build & Deploy

```bash
# First time only — copies game DLLs into lib/ (required for dotnet build)
uv run erenshor mod setup --mod map-tile-capture

# From repo root — always use these, not dotnet directly
uv run erenshor mod build --mod map-tile-capture
uv run erenshor mod deploy --mod map-tile-capture

# Game must be restarted to pick up a new DLL
pkill -f "Erenshor.exe"
```

## Tunable Constants

The native `Plugin.BepInEx.cs` and `Plugin.Lunaris.cs` adapters expose the same public
tuning properties — no loader config or recompile needed for runtime tuning via HotRepl:

- `BackgroundR/G/B` — camera clear colour for areas outside terrain
- `IndoorDirectional*` / `IndoorAmbient*` — lighting for zones with `usingSun = false`
- `DefaultStabilityFrames`, `DefaultSceneLoadTimeoutSecs`

## Non-Obvious Constraints

- **Newtonsoft.Json only** — `System.Text.Json` is not available on Unity's Mono runtime.
- **ILRepack** merges Fleck and, for BepInEx only, Newtonsoft.Json into the output DLL.
  Lunaris supplies Newtonsoft.Json; never merge loader or game/runtime references.
- `GeometrySuppressor` is `IDisposable` and owned by `CaptureController`; unload cleanup
  must dispose it so the temporary directional light and all suppressed state are restored.
- Scene load via `GameData.SceneChange.ChangeScene()` — not `SceneManager.LoadScene()` —
  to get correct per-zone atmosphere and lighting initialisation.
