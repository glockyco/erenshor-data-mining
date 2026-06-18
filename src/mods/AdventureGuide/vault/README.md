# Adventure Guide

Every quest. Every item source. Click and go.

In-game quest companion for Erenshor. 170+ quests with step-by-step
walkthroughs, GPS navigation, and floating world markers above every
quest-relevant NPC.

## Navigate to anything

<img src="https://erenshor-maps.wowmuch1.workers.dev/adventure-guide-window.webp" alt="Quest window with walkthroughs and navigation buttons" style="max-width:100%;height:auto" />

Every quest step has a **[NAV]** button. Click it and a directional
arrow points you to your target — across zone boundaries, chaining
through multiple connections to get you there.

Need an item? Every source is listed — enemy drops, vendors, mining
nodes, fishing spots, crafting recipes, quest rewards. Click any source
and the arrow takes you to it. When a source is another quest's reward,
that quest's walkthrough unfolds inline with its own nav buttons.

## See what you've been missing

<img src="https://erenshor-maps.wowmuch1.workers.dev/adventure-guide-markers.webp" alt="World markers above NPCs showing quest state and respawn timers" style="max-width:100%;height:auto" />

Floating icons appear above NPCs in the game world — quest givers
you've walked past, turn-in targets waiting for your items, enemies you
need to hunt down. Kill a quest mob and its marker switches to a live
respawn countdown. Night-only spawns show the spawn window and
current game time so you know when to come back.

## Know the whole path

<img src="https://erenshor-maps.wowmuch1.workers.dev/adventure-guide-nav.webp" alt="Navigation arrow and ground path guiding to target" style="max-width:100%;height:auto" />

Each step tells you who to talk to, what to say, where to go, and what
items to collect. Level estimates on quests and steps show what you're
ready for and help you tackle things in the right order. Come back after
a week and your progress, item counts, and active step are right where
you left them.

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| **L** | Open the Adventure Guide |
| **K** | Open the quest tracker |
| **P** | Toggle ground path overlay |

## Configuration

Settings are configured through the Lunaris config UI.

| Setting | Default | Description |
|---------|---------|-------------|
| Navigation.ShowArrow | on | GPS arrow pointing to navigation target |
| Navigation.ShowGroundPath | off | Ground path line using NavMesh pathfinding |
| World Markers.Enabled | on | Floating quest icons above NPCs |
| World Markers.Scale | 1.0 | World marker size multiplier |
| Tracker.Enabled | on | Quest tracker overlay |
| Tracker.AutoTrack | on | Auto-track newly accepted quests |
| Tracker.SortMode | Proximity | Sort tracked quests: Proximity, Level, or Alphabetical |
| Tracker.BackgroundOpacity | 0.40 | Tracker overlay transparency |
| General.ReplaceQuestLog | off | Open Adventure Guide instead of the game's quest log |
| General.UiScale | auto | UI size factor (-1 = auto-detect from resolution) |
