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

BepInEx deployment follows `thunderstore.toml` and installs the plugin plus its
runtime files under `<game>/BepInEx/plugins/AdventureGuide/`. Lunaris deploys
the native DLL to `<game>/plugins`. Each deploy also activates that loader.
Exit the game before switching, then restart before testing. To prepare a local
Vault artifact for manual upload, run
`uv run erenshor mod vault --mod adventure-guide`.
There is no GitHub release automation. The canonical local Thunderstore check
packages all four public mods without uploading:

```bash
uv run erenshor --dry-run mod thunderstore
```

A real Thunderstore upload requires exactly one `--mod adventure-guide` and a
non-placeholder `TCLI_AUTH_TOKEN`.

## Architecture

```
src/
├── Plugin.BepInEx.cs   # Native BepInEx entrypoint
├── Plugin.Lunaris.cs   # Native Lunaris entrypoint
├── Plugin.cs           # Shared lifecycle and runtime wiring
├── PluginInfo.cs       # Generated version constant (Directory.Build.targets)
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
   (embedded Roboto), and a Unity `CommandBuffer`. Lunaris supplies the native
   ImGui runtime for the Lunaris target. The BepInEx package ships the official
   `ImGui.NET` managed and Windows x64 native runtime files. The renderer sets
   its context for the whole frame and restores the previous one in a `finally`
   block.

5. **Input isolation**: `PointerOverUIPatch` patches
   `EventSystem.IsPointerOverGameObject()` to return true when the cursor is over
   a guide window, blocking game input. It tracks drag state for fast drags and
   skips hit-testing while `Cursor.lockState` is locked (camera drag).

6. **Navigation**: `Navigation/` computes cross-zone routes (`ZoneGraph`) and
   renders the GPS arrow, optional ground path, and floating world markers above
   quest-relevant NPCs.

Gate availability is shared by quest sources, spawns, and zone routes. The guide
uses live quest, inventory, keyring, account, and stored furnishing state to evaluate access.
Locked sources and zone lines show the missing requirements, with quest links
where available.
Cross-zone navigation follows an entrance that reaches the selected placement,
even when another entrance into the same zone is closer.
Changing zones keeps the chosen source while the guide follows its requirements.
Quest and inventory changes preserve the current waypoint when its target and
available entrances have not changed.
Reliquary raid portals require their stone in the dedicated planning-table slot.
Other planning-table portals accept their rune in any rune slot. Holding an item
or completing its quest does not open either kind of route.
Claimed accounts are not sent through the Reliquary fight again. Return routing
follows the current character's saved destination, not the portal's serialized default.
Objectives preview one source before navigation. The objective's NAV button
chooses among available sources, including another deposit when one is mined.
Use "Choose a source" to follow a specific alternative or its ingredient and
quest sources. Crafted sources retain their recipe while navigation follows
missing materials. Repeated material slots require their combined quantity.
Repeated placements share one source choice. Expand its locations to inspect
their positions and access requirements. Furnished-room vendors remain separate
by room so selecting one does not hide the other rooms.
Browsing quests does not change tracking or navigation. The tracker retains the
current next action, and the quest panel shows it when that quest is selected.
The source picker keeps chances with their actions and shows fishing rates with
their catch restrictions, including outside the catch window.

Offering-activated sources stay part of the selected quest's navigation. The guide
follows a missing offering's sources, then directs the player to the activation
site. When its summoned characters are live, navigation follows them instead.
Competing offerings show a warning before activation. These activities do not
create separate guide quests or saved completion state.

## Data Pipeline

`uv run erenshor guide export-mod` reads the selected variant's clean database,
builds the entity graph with the TOML overrides in
`quest_guides/graph_overrides.toml` (or `--overrides`), and writes
`quest_guides/quest-guide.json`, which the csproj embeds.

Generate the guide only from a complete canonical item-provenance clean build.
The provenance repository rejects missing or incompatible data, so generation
cannot fall back to independent raw-source selection.

Keep reviewed player-facing preparation wording in the override file's
`source_notes`, not in availability gates. Generation checks that the underlying
release mechanism and referenced items still exist, so wording cannot silently
outlive the mechanic it explains.

## Configuration

Settings are available through each loader's native config system. BepInEx
stores settings in `BepInEx/config/wow-much.adventure-guide.cfg` and ImGui
window state in `BepInEx/config/adventureguide/imgui.ini`. Lunaris stores
settings in `<game>/plugins/config/adventureguide.lpcfg` and window state in
`<game>/plugins/config/adventureguide/imgui.ini`. Keys are grouped into
`General`, `Navigation`, `World Markers`, and `Tracker` sections (see
`Config/GuideConfig.cs`). Defaults: open guide **L**, quest tracker **K**, toggle
ground path **P**.

See the `mod-development` skill for the shared build/deploy/hot-reload workflow.
