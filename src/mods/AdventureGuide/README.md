# Adventure Guide

Native dual-loader plugin that adds an in-game quest guide overlay to Erenshor.
Shows step-by-step objectives, item tracking with live inventory counts, GPS
navigation, floating world markers, and a quest tracker.

Adventure Guide has native BepInEx and Lunaris builds. The BepInEx artifact is
the Thunderstore release (`WoW_Much/AdventureGuide`). The Lunaris artifact is
the Erenshor Vault release. See `vault/` for Vault listing assets and manual
publishing notes.

## Local build and distribution

Set up references once, then select the loader explicitly:

```bash
uv run erenshor mod setup
uv run erenshor mod build --mod adventure-guide --loader bepinex
uv run erenshor mod deploy --mod adventure-guide --loader bepinex
uv run erenshor mod build --mod adventure-guide --loader lunaris
uv run erenshor mod deploy --mod adventure-guide --loader lunaris
```

BepInEx deploys to `<game>/BepInEx/plugins`. Lunaris deploys to
`<game>/plugins`. Restart after a Lunaris deployment. To prepare a local Vault
artifact for manual upload, run `uv run erenshor mod vault --mod adventure-guide`.
There is no GitHub release automation. The canonical local Thunderstore check
packages all four public mods without uploading:

```bash
uv run erenshor mod thunderstore --dry-run
```

A real Thunderstore upload requires exactly one `--mod adventure-guide` and a
non-placeholder `TCLI_AUTH_TOKEN`.

## Architecture

```
src/
├── Plugin.BepInEx.cs   # Native BepInEx entrypoint
├── Plugin.Lunaris.cs   # Native Lunaris entrypoint
├── Plugin.cs           # Shared lifecycle and runtime wiring
├── PluginInfo.cs       # Generated version constant (scripts/generate-mod-version.py)
├── Config/             # Loader-neutral settings plus native config adapters
├── Data/               # GuideData (embedded quest-guide.json), QuestEntry, step scene resolver
├── State/              # Quest/tracker state, step progress, game-UI visibility
├── UI/                 # Guide window, quest list/detail panels, tracker window, theme
├── Rendering/          # Private ImGui context + Unity CommandBuffer renderer, CimguiNative
├── Navigation/         # Arrow/ground-path renderers, zone graph, world markers, spawn trackers
├── Patches/            # Harmony patches (quest assign/finish, inventory, markers, input)
└── Diagnostics/        # DebugAPI for HotRepl inspection
resources/
└── Roboto-Regular.ttf  # Embedded font (quest-guide.json is embedded from quest_guides/)
```

## How It Works

1. **Data**: `GuideData` loads `quest-guide.json` from an embedded assembly
   resource at startup and provides O(1) lookup by DBName and StableKey.

2. **State**: `QuestStateTracker` syncs from `GameData.HasQuest` and
   `GameData.CompletedQuests`. Harmony postfixes on `AssignQuest`/`FinishQuest`
   keep it current, using a dirty flag for lazy UI updates.

3. **Step detection**: the current step is derived from live game state — item
   counts from `GameData.PlayerInv.StoredSlots`, zone from the scene name. Steps
   that can't be detected (talk, kill) default to showing as active.

4. **Rendering**: `Plugin.OnGUI()` drives a private ImGui renderer
   (`Rendering/ImGuiRenderer.cs`) that owns its own ImGui context, font atlas
   (embedded Roboto), and a Unity `CommandBuffer`, using the Lunaris-provided
   `ImGui.NET`/`cimgui` binaries. The renderer sets its context for the whole
   frame and restores the previous one in a `finally` block.

5. **Input isolation**: `PointerOverUIPatch` patches
   `EventSystem.IsPointerOverGameObject()` to return true when the cursor is over
   a guide window, blocking game input. It tracks drag state for fast drags and
   skips hit-testing while `Cursor.lockState` is locked (camera drag).

6. **Navigation**: `Navigation/` computes cross-zone routes (`ZoneGraph`) and
   renders the GPS arrow, optional ground path, and floating world markers above
   quest-relevant NPCs.

## Data Pipeline

The guide commands share the entity-graph build and TOML override input:

```bash
uv run erenshor guide compile     # Dense guide.json diagnostics/internal data
uv run erenshor guide export-mod  # Embedded quest-guide.json shipping wrapper
```

`guide compile` writes `quest_guides/guide.json` by default. It is the dense,
indexed representation intended for diagnostics and internal data processing.
`guide export-mod` writes `quest_guides/quest-guide.json` by default. This
compact wrapper is the artifact embedded by the csproj and loaded by the
shipping plugin.

Both commands read the selected variant's clean database and accept
`--overrides` for a `quest_guides/graph_overrides.toml` file. TOML graph
overrides are the only manual curation path. No per-quest JSON overrides are
used.

## Configuration

Settings are available through each loader's native config system. BepInEx stores
`adventureguide/imgui.ini` under its config path. Lunaris stores its settings in
`<Game Folder>/plugins/config/adventureguide.lpcfg`. Keys are grouped
into `General`, `Navigation`, `World Markers`, and `Tracker` sections (see
`Config/GuideConfig.cs`). Defaults: open guide **L**, quest tracker **K**, toggle
ground path **P**.

See the `mod-development` skill for the shared build/deploy/hot-reload workflow.
