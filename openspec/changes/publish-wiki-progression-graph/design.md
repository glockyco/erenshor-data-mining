## Context

See `proposal.md` for the motivation. The state on 2026-10-18, on a clean database built in an owned worktree from the export of build 24405256:

- `gate_conditions` holds 469 gates with 543 atoms on zone lines, characters, spawn points, and vendor items: `quest_done`, `quest_not_done`, `item_held`, `key_held`, `room_furnished`, `planning_slot_item`, and `encounter_won`. `planning_portal_slots` types the 40 planning-table slots as 4 dedicated and 36 rune slots. `zone_line_destination_contexts` marks the Reliquary Hall exit as a saved return.
- The item provenance contract holds 8,985 acquisitions and 10,303 uses, each acquisition with its conditions, locations, and player access state. `QuestRepository.get_quest_panel_rows` projects the completion routes of 196 quests with their sources, required items by resource variant, and dialog conditions. `CharacterRepository.get_character_placements` projects every copy's placements with their gates, stop quests, furniture, trigger items, entries, and damage releases.
- The wiki's views follow `publish-wiki-data-views` D1 to D3: a builder in `src/erenshor/application/wiki_lua/`, a declared `DataView` checked at generation, a repository module with `p.render`, and a template. The native identity catalog of `wiki generate-lua` labels character copies that share an article.
- The wiki runs MediaWiki 1.43 with Scribunto, TemplateStyles, and Gadgets. It has no Mermaid or graph extension. The repository already deploys four gadgets through `wiki deploy-interface`.
- A throwaway projection of these producers, written for this design, found 1,224 nodes, 2,715 ways, and 3,356 needs, about 210 KB as JSON without labels. The upstream of one raid plane holds about 270 nodes. An item has up to 144 ways, most of them droppers.
- The Adventure Guide builds its own `EntityGraph` from the same clean database and adds guide-only facts from `quest_guides/graph_overrides.toml`. Four of those facts are gates that the clean database lacks.

## Goals / Non-Goals

**Goals:**

- One projection from the shared producers to a requirement graph, checked at generation, with the relation semantics of the shipped game code.
- A text rendering that works without JavaScript, and an explorer that stays readable for a raid's upstream.

**Non-Goals:**

- A layout of all 1,224 nodes in one picture. Search and focus reach every node.
- A boolean solver that tells a reader which ways they can take with their own save.

## Decisions

### D1. A wiki view with a drawing gadget

The graph is a view in the sense of `publish-wiki-data-views`: `Module:Erenshor/Data/Progression` (bot-owned), `Module:Erenshor/Progression` and `Template:Progression graph` (repository-owned). A repository gadget draws the graph in the container that the view renders.

Alternatives considered:

- A route of the map site. Rejected: players read the wiki, and the maintainer asked for the wiki.
- A window of the Adventure Guide. Rejected: C# interface work, a mod release, and a reader who has to run the game.
- A drawn image or Mermaid text on a page. Rejected: wiki.gg has no Mermaid extension (the siteinfo of erenshor.wiki.gg lists none), and a picture goes stale with each build and cannot hold the whole graph.

### D2. Facts come from the shared producers

The builder reads the item provenance repository, the quest panel rows, the character placements, `gate_conditions`, `zone_lines_with_zoning_capability`, `zone_line_destination_contexts`, `planning_portal_slots`, `teleports`, and the encounter tables. These are the producers that the item pages, the quest panels, and the guide read, so the graph agrees with them.

Alternative considered: project the guide's `EntityGraph`. Rejected: the wiki would depend on guide code and on guide-only overrides, and a wrong fact would be fixed in the guide instead of the shared producer that owns it.

### D3. Nodes have ways, and ways have needs

A node is a zone, quest, item, character copy, game mechanism (`mechanic:auction_house` and the other acquisition mechanisms without a source), or account state. Each node lists ways. A way is an alternative. Each need of a way is required. Zones, quests, items, and copies take their labels and pages from the link and native identity catalogs. Mechanism and state nodes take theirs from one table in the builder, and generation fails for a node without a label.

- Gates on one subject combine with AND and their groups with OR. The builder multiplies them out into ways. A subject whose gates yield more than 32 ways fails generation, so that a reviewer sees an explosion instead of a silent cut. Sources do not count toward this limit.
- A planning-table rune slot is interchangeable (`planning_portal_slots.slot_kind = 'rune'`). Its six identical ways collapse into one need with the slot role `rune slot`. A dedicated slot keeps its slot name.
- A character node is the exact copy that the game places or spawns. Copies of one article can hold different loot and places: the Azynthian Keeper that drops Eldrich Crystal is one copy of its article. A copy's ways are its placements: the zone, or the source zone of each entry line when `target_entries` restricts it, plus the placement's gates, stop quests (`quest not done`), furniture (`room furnished`), quest spawn (`quest done`), and trigger item (`summoned with`).

### D4. The relation vocabulary

A need names a node and one relation. Generation rejects any fact that the table does not map.

| Relation | The node needs | Source fact |
|---|---|---|
| `zone line` | the source zone of a usable incoming line | `zone_lines_with_zoning_capability`, or a line with an activation gate |
| `in zone`, `entered from` | the zone of a placement, or the source zone of its entry line | placements, `target_entries` |
| `quest done`, `quest not done` | a quest | gate atoms, stop quests, quest spawns, dialog conditions |
| `key`, `held` | an item | `key_held`, `item_held` |
| `planning slot` | an item, with the slot role | `planning_slot_item` with `planning_portal_slots` |
| `room furnished` | a furniture item, with the room | `room_furnished`, placement furniture |
| `defeated` | a character copy, marked advisory | `encounter_won` |
| `account state` | a state node with its required value | account-scoped `encounter_conditions` |
| `summoned with` | the trigger item | placement trigger items |
| `teleport` | the item that teleports there | `teleports` |
| `drops`, `sells`, `gives` | the source copy | acquisitions `character_drop`, `vendor`, `dialog` |
| `reward` | the quest | acquisition `quest_reward` |
| `mold`, `material` | the template and each material with its quantity | acquisition `crafting`, uses `crafting_material` |
| `mined in`, `fished in`, `found in` | the zone of the location | acquisitions `mining`, `fishing`, `fishing_bonus`, `item_bag` |
| `contained in` | the item that holds it | acquisition `item_drop` |
| `auction house`, `world drop`, `starting gear`, `game window` | a mechanism node | acquisitions `auction_house`, `special_world_drop`, `common_world_item`, `starting_class`, `ui_grant` |
| `turn in to`, `talk to`, `enter`, `read`, `defeat`, `hear`, `event` | the route's source, with keywords for `talk to` | quest completion routes |
| `required item` | an item with its quantity | the route's resource variant |
| `completed with` | the other quest, while this one is active | `quest_complete_other_quests` |
| `release` | the item or copy that makes a copy vulnerable | `character_damage_releases` |
| `condition` | no node, a fixed text | release mechanisms without a node |

An acquisition condition becomes a need when its phase is `availability` and its predicate is one of the gate atoms above. Operation inputs of a turn-in are the quest's own required items and are not repeated. Predicates that describe a quantity, a roll, a class, a level window, a time of day, or an ownership limit are properties of the source, not progression, and the item pages show them.

### D5. A quest needs a completion route, not its acquisition

The shipped code completes a quest without checking that it is in the journal. `TradeWindow.CompleteTrade` (`TradeWindow.cs`, lines 299 to 386) tests only the required items and `Quest.QuestAvailable`, which rejects a completed quest that does not repeat. `NPCDialog` (line 75), `ItemIcon` on read (line 161), `ZoneAnnounce` (line 80), and `Character` on death (line 912) call `GameData.FinishQuest` directly. Only `CompleteOtherQuests` tests `GameData.HasQuest` (`TradeWindow.cs`, line 392). So a quest's ways are its completion routes, and acquisition routes are left to the quest panel. The `completed with` way says that the quest must be active.

A scripted completion keeps the route's source when the export records one. Otherwise the way holds one `event` need without a node, which says that a scripted event completes the quest. She Sees You is such a quest: the export records the script, `SivTorchLight`, and no source.

### D6. A kill release joins the ways that kill

A release is a need of the ways that require the kill: an item's `drops` way, a quest's `defeat` way, and a `defeated` atom. It is not a need of the copy, because the same copy can be a turn-in target: players give Lost Faith to Stardust to make it vulnerable. The mechanisms map as follows:

- `trade_turn_in` with a `quest_variant` condition needs that variant's required items.
- `shivering_phantom_wards` and `combat_ward_cycle` with `character` or `character_dead` conditions need those copies defeated.
- `npc_protector_weather` with the state `raining` becomes the condition "only while it rains". `Invoke Storm`, which Tempestalia casts, resets the rain timer (`SpellVessel.cs`, line 2160), and rain then begins once the sky is dark enough (`AtmosphereColors.cs`, line 414). The clean database records neither, so the graph names no item for the rain.
- Other mechanisms that the current build uses, such as `health_phase_timer` and `reliquary_wards`, become fixed condition texts. A new mechanism fails generation.

### D7. Paths that no player can take are left out

A zone line is left out when its destination is saved state, when it is inactive and no gate records its activation, or when a `never` atom closes every group. An acquisition is left out unless its player access state is `verified_player` or `unconfirmed_player`. An unconfirmed source keeps a flag that both renderings show. A node without a way stays in the graph and says that the data records none, such as Prison and, until D11 lands, Azynthi's Garden (Dimensional Rift).

### D8. The data module

`Module:Erenshor/Data/Progression` maps each node's stable key to rows of two types, declared once as a `DataView` with a `type` field:

- One `node` row holds `kind` and `label`, a native identity reference with its name and optional page.
- Each `need` row holds `way` (an integer from 1), `relation`, and `need` (a native identity reference, absent only for `condition` and `event`), with the optional `quantity`, `slot`, `keywords`, `text`, `advisory`, and `unconfirmed`.

Keys resolve in the link catalog or the native identity catalog. The existing checks for markup, line breaks, types, and undeclared fields apply. The estimated size of 0.5 to 1 MB stays under the page budget. When it grows past the budget, the module is published in shards under a new title (`adopt-data-backed-wiki` D1).

### D9. The view and the template

`{{Progression graph}}` takes `stablekey`. Without it, the view resolves the current page through `Link.pageKeys` for zones, quests, items, and characters, and shows an error with the keys when more than one entity matches. Without any entity on the page, the view opens the explorer on the four raid planes, the zones that need a `planning slot` with a dedicated slot.

The view renders:

1. A short legend that says what a way and a need are, and that the graph shows only what the game data records.
2. The target's ways as nested lists, linking each node through `Module:Erenshor/Link`. A node already shown is referenced, not repeated. The lists stop at a depth of 6.
3. A container with the whole graph as JSON (`mw.text.jsonEncode` over plain tables copied from the `mw.loadData` result) and the target's key, for the gadget.

A key without data shows a message and adds `Pages with missing Erenshor progression data`.

### D10. The gadget

`progression-graph` holds the drawing code and loads only through a small default gadget, `progression-graph-loader`, which loads it when the page holds the container. The module:

- Draws an SVG with a layered layout: needs on the left, the focus on the right, nodes ordered within each layer by repeated barycenter sweeps, and cycles broken at back edges. A way with several needs gets a small junction. Solid edges are required needs, dashed edges are alternatives.
- Expands by relation. Quests, gates, required items, rewards, crafting, and releases expand. A zone's gate-free entrances and an item's sources beyond the first four start as collapsed groups with a count. The reader expands and collapses each node.
- Offers a search over every node by name, a switch between needs and unlocks (the reversed edges), pan and zoom, and a side panel that lists the focused node's ways as text with links.
- Makes every node a focusable element with a label, focuses it on Enter, and moves through neighbours with the arrow keys.
- Takes colours from the skin's CSS variables, so it follows the light and dark themes.
- Catches every failure, logs it, and leaves the text rendering visible.

Pure functions (the graph model, expansion, layering, and ordering) live apart from the DOM code and have node tests beside `semantic-link-picker-core.test.js`.

Alternatives considered:

- A third-party graph library copied into `MediaWiki:` pages. Rejected: no dependency manager would track the copy, ELK.js weighs about 1.5 MB and carries the EPL licence, and the focused subgraphs are small directed graphs that a layered layout handles.
- A canvas. Rejected: canvas has no elements for the keyboard or screen readers.
- Mark nodes reachable from the start as open, and stop the expansion there. Rejected: new characters start in Stowaway's Step (`CharSelectManager.cs`, line 1147), and every zone beyond it needs Wyland's Note, A Way To Erenshor, or The Game Continues..., so nothing would be open. Expansion by relation needs no such baseline.

### D11. Facts that only the guide held

Each fact goes to the shared producer that owns its kind, so that the clean database holds it for every consumer:

| Fact | Evidence | Home |
|---|---|---|
| The Duskenlight Coast line into Jaws of Sivakaya opens with the Nighthollow Candle held or She Sees You done | override `override:jaws_entry` | the export or code facts of the script that opens the line |
| Vessel Siraethe appears after A Pious Guest | override `override:piety` | the export of the activation, or a reviewed entry with its reason |
| Shivering Tomb (2) opens after Stand, Angel! | override `override:shivering_angel`, `ShiveringAngel.cs` | the scripted activator export |
| The planning table exists after Claiming the Reliquary | override `override:planning_desk`, the `QuestSpawnListener` on `PlanningDesk`, and the `ui_access` condition that the clean build already puts on the table's Box of Portals | the same activation on every planning-slot zone line |
| The Dimensional Rift moves between Azynthi's Garden and its rift | `SpellVessel.cs`, lines 2261 to 2275 | a code fact and a relation that the clean build derives from it |

The guide keeps its overrides until a separate Adventure Guide change removes those that the clean database then covers. Until then the guide sees the same condition twice, which changes nothing, because gates on one subject combine with AND.

### D12. Owners and write boundaries

| Artifact | Owner | Written by |
|---|---|---|
| `Module:Erenshor/Data/Progression` | bot | `wiki generate-lua` and `wiki deploy-repo-pages --include-generated-data` |
| `Module:Erenshor/Progression`, its testcases, `Template:Progression graph`, the tracking category page | repository | `wiki deploy-repo-pages` with the dependency, render, and drift checks |
| `MediaWiki:Gadget-progression-graph*` and the gadget definition lines | repository | `wiki deploy-interface` under the interface account |
| The section of `Erenshor Wiki:Game Data` | repository | `wiki deploy-repo-pages` |
| `Progression Graph` and the walkthrough | people | the maintainer creates the first by hand, and the placement on the second is a guarded one-time edit after the review of `publish-wiki-data-views` D5 |
| Export, code facts, `barriers.toml`, processor | repository | `extract export`, `extract code-facts`, `extract build` |

### D13. Failure handling, grouping, and rollback

- Generation fails closed on every check of D3, D4, D6, and D8, naming the module, node, way, and fact.
- The view shows a visible message and a tracking category for a missing entity. The gadget never hides the text rendering before it has drawn.
- Commits group by unit: each shared fact, the builder with its tests, the view with its testcases, the gadget with its tests, and the documentation.
- The data module, the view, and the template roll back through the manifest of their `deploy-repo-pages` run, the gadget through `wiki rollback-interface`, and the placement through the guarded-edit manifest. A new page stays after a rollback and needs an administrator to delete it.

## Risks / Trade-offs

- [The whole graph's JSON lands on every page that places the template] → Only the explorer page and a few guide pages place it, and generation reports the JSON size next to the module size.
- [A raid's upstream is large] → Expansion by relation collapses navigation and common sources, nodes expand on demand, and the side panel lists ways as text.
- [`mw.text.jsonEncode` cannot read `mw.loadData` tables directly] → The view copies the rows into plain tables. The local stack checks it with the real module.
- [A game update adds a mechanism] → Generation fails and names it, so the mapping is reviewed instead of guessed.
- [Own layout code] → It is small, pure, and covered by node tests. A library can replace it later without changing the data.
- [Guide and wiki disagree while the guide keeps its overrides] → D11 moves the facts first, so both read the same conditions.

## Migration Plan

1. Land the five shared facts, each with its clean build check.
2. Land the builder, the view, and the gadget. Check them in the local MediaWiki stack with the real data module, in a browser, in both themes and with the keyboard.
3. Deploy after a dry run and approval: the data module, the view module, the template, the category page, the guide section, then the gadget. Parse a live page with the template and open it in a browser.
4. The maintainer creates `Progression Graph`. The walkthrough placement follows the review of `publish-wiki-data-views` D5.

Rollback follows D13.

## Open Questions

- The final title of the explorer page and the pages that place the template. The maintainer decides them at publication. Neither changes the view.
