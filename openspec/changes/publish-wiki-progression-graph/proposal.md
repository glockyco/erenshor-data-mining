## Why

Players learn what unlocks the raids from the hand-written page [Raid Unlocking Walkthrough](https://erenshor.wiki.gg/wiki/Raid_Unlocking_Walkthrough): 66 numbered steps over seven parts, about 2,800 words. Most of its dependencies are not quest prerequisites. They are keys for doors, runes for planning-table slots, rituals that open portals, items that summon or release a boss, rain that makes a boss vulnerable, and turn-ins whose rewards feed the next step. The page is hard to follow, covers only the first four raids, and nothing checks it against a new game build.

`derive-progression-requirements` gives the clean database one requirement graph with a playthrough tier for every node, and `model-progression-mechanics` completes the mechanisms behind it. The wiki has no view of it.

## What Changes

- A generated wiki view of the requirement graph: bot-owned `Module:Erenshor/Data/Progression` with compact node records and lazily decoded ways, a repository module that renders a target's progression as text, and the template `{{Progression graph}}`.
- One wording table words every way as a plain sentence, such as "Defeat Evadne the Corrupted in Braxonian Desert for Ancient Braxonian Key". The data module carries the sentences, and `erenshor progression show` prints the same ones.
- The view shows the route in the form of the walkthrough: chapters named after the area, gate, or goal that they unlock, each with numbered steps from a new character's start. Each step names one way. Its other ways and the sources of what it needs sit behind one disclosure. Quests are the spine. Keys, runes, gated areas, barriers, bosses that must die, and world states stay visible as steps.
- A repository gadget draws a map of the chapters for one goal at a time. Choosing a chapter shows its steps in the text, and choosing a step draws what it needs and what it unlocks, with the action on each line. Search reaches every step. Without JavaScript the page keeps the text.
- The template renders its own legend and says that the order is one playthrough from a new character, not advice about a save.
- A main-namespace page `Progression Graph`, which people own like every article, places the template without a target and opens the explorer. It is an alternative view of the process that the walkthrough describes, and the two pages link to each other.

Non-goals: a picture of every node at once (search and the step view reach every node), a checklist of a reader's own progress, which becomes its own change once the explorer is in use, level or difficulty advice, and replacing the walkthrough or editing its prose.

Migration boundary: nothing is published while the review of `derive-progression-requirements` lists a wrong step in a raid chain. The walkthrough stays the human-written guide and does not place the template. Its one edit adds a link to `Progression Graph`, which is a reviewed edit of a page that people own.

## Capabilities

### New Capabilities

- `wiki-progression-graph`: how the wiki renders the requirement graph as text and as an explorer.

### Modified Capabilities

None.

## Impact

- New: a builder in `src/erenshor/application/wiki_lua/` with unit tests, sentence wording in `src/erenshor/application/progression_wording.py` shared with `erenshor progression show`, `Module:Erenshor/Data/Progression` from `wiki generate-lua`, `wiki/modules/Erenshor/Progression.lua` with testcases, `wiki/templates/Progression graph.wiki`, a tracking category page, the gadget sources and their registration in `wiki/gadgets/`, node tests for the gadget, and a section of the Game Data guide.
- Shared page inference: a compact `Module:Erenshor/Data/PageKeys` generated from the semantic-link catalog lets every page-inferring view resolve identities without loading the full `Data/Links` records.
- Depends on: `derive-progression-requirements` for the data, and the slices of `model-progression-mechanics` that the raid chains need before publication.
- Live wiki: the data module, view module, and template deploy with `wiki deploy-repo-pages`, the gadget with `wiki deploy-interface` under the interface account, each after a dry run and approval, with their rollback manifests. The maintainer creates the `Progression Graph` page by hand, and the link on the walkthrough is a guarded one-time edit after approval.
