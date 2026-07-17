# MapTileCapture Mod

Native BepInEx and Lunaris plugins share the loader-neutral capture runtime.
For the full capture pipeline (Python orchestrator, tile generation, zone setup), see the
`tile-capture` skill.

## Build & Deploy

```bash
# First time only — provisions game and both loader references for every mod
uv run erenshor -V playtest mod setup

# Build both native targets
uv run erenshor -V playtest mod build --mod map-tile-capture --loader all

# Deploy one target and activate its loader
uv run erenshor -V playtest mod deploy --mod map-tile-capture --loader bepinex
# or:
uv run erenshor -V playtest mod deploy --mod map-tile-capture --loader lunaris
```

Exit the game before deployment and restart it after switching loaders. Use
BepInEx when the capture workflow needs HotRepl runtime tuning.

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
