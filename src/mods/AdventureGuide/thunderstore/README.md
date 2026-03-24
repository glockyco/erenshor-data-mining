# Adventure Guide

Every quest. Every item source. Click and go.

In-game quest companion for Erenshor. 170+ quests with step-by-step
walkthroughs, GPS navigation, and floating world markers above every
quest-relevant NPC. All data auto-extracted from game assets.

![Quest window with walkthroughs and navigation buttons](https://erenshor-maps.wowmuch1.workers.dev/adventure-guide-window.png)

## Navigate to anything

Every quest step has a **[NAV]** button. Click it and a directional
arrow points you to your target — across zone boundaries, chaining
through multiple connections to get you there.

Need an item? Every source is listed — enemy drops, vendors, mining
nodes, fishing spots, crafting recipes, quest rewards. Click any source
and the arrow takes you to it. When a source is another quest's reward,
that quest's walkthrough unfolds inline with its own nav buttons.

## See what you've been missing

![World markers above NPCs showing quest state and respawn timers](https://erenshor-maps.wowmuch1.workers.dev/adventure-guide-markers.png)

Floating icons appear above NPCs in the game world — quest givers
you've walked past, turn-in targets waiting for your items, enemies you
need to hunt down. Kill a quest mob and its marker switches to a skull
with a live respawn countdown. Night-only spawns show the spawn window
and current game time so you know when to come back.

## Know the whole path

![Navigation arrow and ground path guiding to target](https://erenshor-maps.wowmuch1.workers.dev/adventure-guide-nav.png)

Each step tells you who to talk to, what to say, where to go, and what
items to collect. Level estimates on quests and steps show what you're
ready for and help you tackle things in the right order. Come back after
a week and your progress, item counts, and active step are right where
you left them.

## Install

Requires [BepInEx 5](https://thunderstore.io/c/erenshor/p/BepInEx/BepInExPack/).

**Thunderstore install:** Use a mod manager — no manual file placement needed.

**Manual install:** Download the mod and copy the `AdventureGuide/`
folder into `BepInEx/plugins/`. Your directory should look like:

```
Erenshor/
└── BepInEx/
    └── plugins/
        └── AdventureGuide/
            ├── AdventureGuide.dll
            ├── Newtonsoft.Json.dll
            ├── ImGui.NET.dll
            ├── System.Numerics.Vectors.dll
            └── System.Runtime.CompilerServices.Unsafe.dll
```

Press **L** to open the Adventure Guide in-game.

## Configuration

Config file: `BepInEx/config/wow-much.adventure-guide.cfg`
(generated on first launch).

Or edit in-game with
[Configuration Manager](https://github.com/BepInEx/BepInEx.ConfigurationManager)
(F1).