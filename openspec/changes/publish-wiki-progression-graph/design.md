## Context

See `proposal.md` for the motivation. The state on 2026-10-20:

- `derive-progression-requirements` gives the clean database a requirement graph: nodes with kind, milestone flag, tier, and first way, ways with stable keys, and needs with relations, read through `ProgressionRepository`. `UNMET_RELATIONS` names the relations whose target must stay undone. Such a need adds no tier and no step to a route.
- The wiki's views follow `publish-wiki-data-views` D1 to D3: a builder in `src/erenshor/application/wiki_lua/`, a declared `DataView` checked at generation, a repository module with `p.render`, and a template. The native identity catalog of `wiki generate-lua` labels identities that have no page of their own, such as character copies that share an article.
- The wiki runs MediaWiki 1.43 with Scribunto, TemplateStyles, and Gadgets, and no Mermaid or graph extension. The repository deploys its gadgets through `wiki deploy-interface`.
- A moodboard of 18 references (attunement and flagging charts, puzzle dependency and lock-and-key graphs, randomizer spheres, tech trees, and the two compendiums) is at `variants/main/wiki/progression-moodboard/index.html`. It stays in the gitignored variant storage, because its images belong to their sources. Its common lesson: lead with meaningful access milestones around one goal, keep the exact requirements one step away, and do not draw every raw requirement.
- The first explorer drew every milestone of the four raid planes in one graph: 155 cards, 338 line segments, tier columns, and labels such as "All of (first way)". Readers could not follow it. Research on reading graphs and instructions points the same way as the moodboard and the human walkthrough. The claims below come from the papers' abstracts and from the two articles:
  - Overview first, zoom and filter, then details on demand (Shneiderman 1996, doi:10.1109/VL.1996.545307).
  - Node-link diagrams suit path finding, but above about 20 nodes they lost to matrices on most other tasks (Ghoniem, Fekete, and Castagliola 2004, doi:10.1109/INFVIS.2004.1). After the length of a path, line continuity and crossings cost readers most when they follow it (Ware, Purchase, Colpoys, and McGill 2002, doi:10.1057/palgrave.ivs.9500013).
  - Browsing the context of one node of interest serves readers of a large graph better than a global overview (van Ham and Perer 2009, doi:10.1109/TVCG.2009.108). A tree grown from one chosen node beat a traditional graph interface, and more clearly as the data grew denser (Lee, Parr, Plaisant, Bederson, Veksler, Gray, and Kotfila 2006, doi:10.1109/TVCG.2006.106).
  - Flowchart formats beat paragraph instructions in comprehension accuracy and speed (Kammann 1975, doi:10.1177/001872087501700209).
  - Progressive disclosure shows the few most important options first and the rest on request, and designs with more than two levels lose their users (Nielsen 2006, https://www.nngroup.com/articles/progressive-disclosure/).
  - Puzzle dependency charts serve designers, and flowcharts serve players who solve a game. Designers group puzzles into acts that end in a bottleneck (Gilbert 2014, https://grumpygamer.com/puzzle_dependency_charts/).
  - Transitive reduction keeps reachability with the fewest edges (Aho, Garey, and Ullman 1972, doi:10.1137/0201008), and a layered layout reduces crossings by ordering each layer (Sugiyama, Tagawa, and Toda 1981, doi:10.1109/TSMC.1981.4308636).

## Goals / Non-Goals

**Goals:**

- A route that a casual player can follow from a new character's start: chapters, numbered steps in plain sentences, and the exact alternatives one disclosure away.
- A map that shows where a step sits in its goal's route without drawing every requirement.
- One wording for every reader of the graph: the wiki text, the gadget, and `erenshor progression show`.

**Non-Goals:**

- A checklist of a reader's progress. It needs its own semantics for characters, account state, alternatives, and consumed items, and becomes its own change.
- Deciding requirements in Lua or JavaScript. The view groups and orders the persisted first-way route, and the gadget reads the view's chapters.
- Replacing the Raid Unlocking Walkthrough or placing the view in it. The walkthrough stays the human-written guide, and the graph is an alternative view of the same progression on its own page.

## Decisions

### D1. A wiki view with a drawing gadget

The graph is a view in the sense of `publish-wiki-data-views`: `Module:Erenshor/Data/Progression` (bot-owned), `Module:Erenshor/Progression` and `Template:Progression graph` (repository-owned). A repository gadget draws the map in the container that the view renders.

Alternatives considered:

- A route of the map site. Rejected: players read the wiki, and the maintainer chose the wiki.
- A window of the Adventure Guide. Rejected: C# interface work, a mod release, and a reader who has to run the game.
- A drawn image or Mermaid text on a page. Rejected: wiki.gg has no Mermaid extension, and a picture goes stale with each build and cannot hold the graph.

### D2. The compact data module

The builder reads `ProgressionRepository` and validates its node, way, and need rows through the declared `DataView` before serializing `Module:Erenshor/Data/Progression`. It retains every node with a way or referenced by a need, including a referenced node without a way, and a quest without a way whose start has one, because the start's sentence names the quest. It leaves out a way that needs its own node, such as a Loss Stone that the player already holds, because it cannot be how a player gets the node. Sentences and conditions use the wording of D3, and native identities supply names and optional pages. Generation fails when wording or an identity is missing, and when a sentence names a node outside the module.

The module uses one table per node with its kind, tier, milestone flag, name, optional page, first-way index, optional `reward`, and an array of packed way strings. Each way string is a JSON array whose first value is the way's sentence and whose other values are positional needs. JSON escaping preserves every optional value without allocating a Lua table for every need during `mw.loadData`. `reward` names the quest of an item whose first way is that quest's reward and nothing that the reward does not imply, so that the view names the item in the quest's step. The generated module's header documents the field order, null handling, page sentinel, and first-way index. `_meta` holds the default targets from dedicated planning slots, the unmet relations, the action of each relation for the lines of the map, and the title lead of each node kind. This changes representation, not which way the clean build selected.

The builder reports Lua and JSON bytes and rejects a module above the page budget. Source-row validation remains fail-closed before compaction. The module carries every node's label, so the gadget does not need the full link catalog.

### D3. Plain sentences

`progression_wording.py` words each way as one imperative sentence. The sentence names the node, the action, the person, and the place, then the way's conditions, so that it reads alone in a route, in a list of alternatives, and on the command line:

- Each node kind has a pattern led by the way's main relation. An item is defeated for, bought, given, rewarded, crafted, fished, mined, picked up, or found inside another item. A quest is finished by a turn-in, a talk, a read, an entry, a defeat, or an event, after the clause that starts it. A zone is entered from a zone, through a gate, through the planning table, or by a spell. A barrier opens with a key, after a quest, or after defeats. A character is found in its zone. World states, standings, account states, spells, classes, and mechanisms have their own patterns.
- A character, and so a quest giver or a vendor, is placed in the zone of its first way.
- Conditions follow the main clause in a fixed order: gates, quests done, quests to leave undone ("before you finish"), carried and worn items, furnished rooms, states, required levels, and the advisory and unconfirmed marks.
- A need that another need of the same way implies is left out: the turn-in items and the undone quest of a reward way, and the undone quest of a quest's own start.
- A node appears as `{stable key}`, and the renderer replaces it with the node's linked label. Generation fails when a relation has no phrase, when a pattern meets a relation that it cannot word, and when a stable key holds a brace.

The table also gives each relation a short action, such as "defeat" or "open with", which labels a line of the map.

Alternatives considered:

- Wording in Lua and JavaScript. Rejected: two copies of the grammar and none for the command line.
- One sentence per node. Rejected: alternatives need sentences of their own.

### D4. Levels of detail

1. The chapter map of the gadget shows the chapters of one goal and how they depend on each other.
2. The route lists each chapter's steps as numbered sentences. A step is a milestone of the first-way route. An item whose `reward` names a quest of the route is named in that quest's step instead of its own.
3. Each step has one disclosure with its other ways and, for each need that is no step of its own, where to get it. An area that is no step is open, so the disclosure leaves travel there to the area's page. A character whose only way names its zone, and a quest start with one way, add nothing to the step's sentence and get no list. A list of more than four ways collapses after the fourth into a counted group.

This keeps disclosure to two levels below the route.

### D5. Chapters

The view groups the route into chapters, because a long list needs bottlenecks that a reader can hold, like the walkthrough's seven parts:

- Steps are ordered by a depth-first walk from the goals that visits each step's deepest requirement first. A chain is finished before the materials of the next step are gathered, and every step comes after what it needs.
- Areas, gates, and goals anchor chapters. With several goals, so does a step that several goals need when every step that needs it serves fewer goals. Each anchor, in walk order, takes the steps that it needs and that no earlier chapter took.
- A gate's chapter joins the chapter of the area behind it, and a chapter of one step that is no goal joins the chapter after it.
- A chapter of more than twelve steps splits at its quests into parts, each led by its quest. A part of one step joins the next part, and a last part of one step joins the part before it.
- Titles use the leads of the wording table: "Unlock" an area, "Get past" a barrier, "Finish" a quest, "Get" an item, "Find" a character.

Alternatives considered:

- Tier bands. Rejected: tiers are not places, and a band mixes unrelated chains.
- Hand-written chapters. Rejected: they go stale with each build, and the data gives the walkthrough's own parts.

### D6. The view and the template

`{{Progression graph}}` takes `stablekey`. Without it, the view resolves the current page through `Link.pageKeys` for zones, quests, items, and characters, and shows an error with the keys when more than one entity matches. Without an entity on the page, it opens on the four raid planes recorded by the data module's dedicated planning-slot defaults.

The shared `Link.pageKeys` reads `Module:Erenshor/Data/PageKeys`, a small page-to-keys index generated beside `Data/Links`. It preserves the full catalog's page normalization, key order, and every identity variant without loading its image and entity records. Generation checks that every catalog key appears under its own page.

The view loads the compact progression module and decodes a way only when the text needs it. It renders a legend and then each chapter with its heading and an ordered list of steps, and the numbers run on across chapters. A step's list item carries its stable key and an anchor, and the nodes of a sentence link to their pages. A key without data shows a message and adds `Pages with missing Erenshor progression data`.

The gadget container holds a hidden `pre` with a nowiki JSON payload, serialized in one `mw.text.jsonEncode` call: the targets, the chapters with their parts and steps, each step's requirements on the route, the actions of the relations, and the compact records that the rendered sentences name. Keeping JSON in text avoids MediaWiki's large-attribute limit. The text remains visible without the gadget.

### D7. The chapter map

`progression-graph` holds the drawing code and loads through a small default gadget, `progression-graph-loader`, only when the page holds the container.

- One goal at a time. The map opens on the first target, and the reader picks another target or any step of the route. The text hides the steps that the goal does not need and renumbers the rest.
- The map draws the goal's chapters from top to bottom. A line joins two chapters when a step of the lower one needs a step of the upper one, after transitive reduction. Layers follow the longest path, repeated barycenter sweeps order each layer, and a line that spans layers bends through a point in each layer that it crosses, so that no line passes behind a card.
- Choosing a chapter scrolls the text to it and marks it.
- Each step of the text gets a button that draws the step's neighbourhood below it: what its first way needs above it and what needs it below, each line labelled with the action of its relation. Choosing a neighbour that is a step moves there, and any other node becomes the centre of the drawing.
- Search finds every node of the payload by name. A node that is no step leads to the step whose sentence first names it.
- Every card and button is a focusable element with a label. Colours come from the skin's CSS variables, and shapes and labels carry every meaning that colour carries. Every failure is caught and logged, and the text stays visible.

The goal's closure, the chapter graph and its reduction, the layers, the ordering, the bends, the neighbourhood, and search are pure functions apart from the DOM code, with node tests beside `semantic-link-picker-core.test.js`.

Alternatives considered:

- One graph of every milestone, as the first explorer drew it. Rejected: see Context.
- A third-party graph library copied into `MediaWiki:` pages. Rejected: no dependency manager would track the copy, and a chapter graph is small enough for a layered layout of our own.
- A canvas. Rejected: a canvas has no elements for the keyboard or for screen readers.

### D8. When to publish

The data, view, and gadget deploy only after the review of `derive-progression-requirements` (its task 2.5) lists no wrong step in the routes of the four raid planes and Secluded Sanctuary. That needs at least the hierarchy, barrier, and world state slices of `model-progression-mechanics`. Local checks can run earlier against the current facts.

### D9. Owners and write boundaries

| Artifact | Owner | Written by |
|---|---|---|
| `Module:Erenshor/Data/Progression` | bot | `wiki generate-lua` and `wiki deploy-repo-pages --include-generated-data` |
| `Module:Erenshor/Data/PageKeys` | bot | `wiki generate-lua` and `wiki deploy-repo-pages --include-generated-data` |
| `Module:Erenshor/Progression`, its testcases, `Template:Progression graph`, the tracking category page | repository | `wiki deploy-repo-pages` with the dependency, render, and drift checks |
| `MediaWiki:Gadget-progression-graph*` and their definition lines | repository | `wiki deploy-interface` under the interface account |
| The section of `Erenshor Wiki:Game Data` | repository | `wiki deploy-repo-pages` |
| `Progression Graph` and the walkthrough | people | the maintainer creates the first by hand with a link to the second, and a link back on the walkthrough is one guarded `wiki apply-page-edits` edit after approval |

### D10. Failure handling, grouping, and rollback

- Generation fails closed on the checks of D2 and D3, naming the module, node, way, and fact.
- The view shows a message and a tracking category for a missing entity. The gadget never hides the text before it has drawn.
- Commits group by unit: the wording, the data view, the text view, the gadget, and the documentation.
- The data module, the view, and the template roll back through the manifest of their `deploy-repo-pages` run, the gadget through `wiki rollback-interface`, and the walkthrough link through `wiki rollback-repo-pages` with the manifest of its guarded edit. A new page stays after a rollback and needs an administrator to delete it.

## Risks / Trade-offs

- A rare combination of needs could read awkwardly. The builder fails on any relation that it cannot word, and the review reads the sentences of every way signature of the current build.
- Chapters are grouping, not facts. A poor grouping still lists every step in a valid order.
- The sentences make the data module larger. Task 5.5 measures Lua memory and time again against a quarter of the live limits.
- The subgraph JSON could be large on the explorer page. The container holds only the target's route and the records that its sentences name, and generation reports the sizes.
- The layout code is our own. A chapter graph is small, and the code is pure and tested.

## Migration Plan

1. Land the wording, the data view, and the text view, and check them in the local wiki with the real data module.
2. Land the gadget, and check it in a browser in both themes and with the keyboard.
3. After D8 holds, deploy after a dry run and approval: the shared page index before its Link reader, the progression data module, the view module, the template, the category page, the guide section, then the gadget.
4. The maintainer creates `Progression Graph` with a link to the walkthrough. After approval, one guarded edit adds a link to `Progression Graph` on the walkthrough.

Rollback follows D10.

## Open Questions

- The final title of the explorer page and the pages that place the template. The maintainer decides them at publication. Neither changes the view.
- How to rank a first way that the designers did not intend. The route follows the clean build's persisted first way without consumer ranking. Chazz Pillot drops Mold: A Strange Figurine every time he dies, ahead of the reward of A Note for C. Pillot, so that first way skips A Hermit's Request. The step's other ways show both. A reviewed ranking rule belongs in the shared graph, such as ranking a friendly NPC's death after other ways. The review of task 2.5 of `derive-progression-requirements` names the cases. Auction House listings are no way at all, because their stock is random.
