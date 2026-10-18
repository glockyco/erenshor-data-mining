## Why

Players learn what unlocks the raids from the hand-written page [Raid Unlocking Walkthrough](https://erenshor.wiki.gg/wiki/Raid_Unlocking_Walkthrough): 66 numbered steps over seven parts, about 2,800 words. Most of its dependencies are not quest prerequisites. They are keys for doors and zone lines, runes for planning-table slots, rituals that open portals, items that summon or release a boss, and turn-ins whose rewards feed the next step. The page is hard to follow, it covers only the first four raids, and nothing checks it against a new game build.

The clean database already holds these relations: the gate conditions of zone lines, placements, vendor items, and item bags, the planning-table portal slots, the item provenance contract, the quest completion routes of the quest panel, the character placements, and the damage releases. No output shows them together.

## What Changes

- A generated wiki view of the whole progression graph. Each node is a zone, quest, item, character copy, or game mechanism. Each node lists its ways, and each way lists what it needs. The view covers every quest and zone, every gated zone line, placement, vendor item, and item bag, every item that a quest, craft, gate, or turn-in produces, and everything upstream of them.
- The view is a bot-owned data module, `Module:Erenshor/Data/Progression`, a repository module that renders a target's requirements as text, and a template, `{{Progression graph}}`.
- A repository gadget draws the graph on pages that place the template: a search, a focused view of what a node needs and what it unlocks, nodes that expand on demand, and links to the wiki pages. Without JavaScript the page keeps the text rendering.
- The template renders its own legend. A main-namespace page `Progression Graph`, which people own like every article, places the template without a target and opens the explorer.
- Five facts that the graph needs and the clean database lacks move into the shared producers: the Jaws of Sivakaya entry, the Ward of Piety gate before Vessel Siraethe, the angel statue before Shivering Tomb (2), the planning table that exists only after Claiming the Reliquary, and the Dimensional Rift that switches between the two Azynthi's Garden scenes.

Non-goals: a picture of all nodes at once (the explorer focuses one target at a time and searches the rest), acquisition routes of quests (the game completes a quest without it being in the journal), level or difficulty advice, the Adventure Guide's graph and its overrides file, and edits of the walkthrough's prose.

Migration boundary: nothing replaces the walkthrough. Placing the template on that page is a reviewed edit of a page that people own, after the view is live.

## Capabilities

### New Capabilities

- `wiki-progression-graph`: which relations of the clean database the progression graph shows, how a page renders a target's requirements, and how the explorer behaves.

### Modified Capabilities

None.

## Impact

- New: a builder in `src/erenshor/application/wiki_lua/` with unit tests, `Module:Erenshor/Data/Progression` from `wiki generate-lua`, `wiki/modules/Erenshor/Progression.lua` with testcases, `wiki/templates/Progression graph.wiki`, a tracking category page, the gadget sources and registration in `wiki/gadgets/`, node tests for the gadget, and a section of the Game Data guide.
- Changed: the export, code facts, or `barriers.toml` for the five missing facts, and the gate rows that the clean build derives from them. The Adventure Guide keeps its overrides until a separate guide change removes the ones that the clean database then covers.
- Live wiki: the data module, view module, and template deploy with `wiki deploy-repo-pages`, the gadget with `wiki deploy-interface` under the interface account, each after a dry run and approval, with their rollback manifests. The maintainer creates the `Progression Graph` page by hand, and the walkthrough placement is a guarded one-time edit after approval.
