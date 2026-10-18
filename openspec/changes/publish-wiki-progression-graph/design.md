## Context

See `proposal.md` for the motivation. The state on 2026-10-18:

- `derive-progression-requirements` plans the requirement graph in the clean database: nodes with kind, milestone flag, tier, and first way, ways with stable keys, and needs with relations, read through `ProgressionRepository`. A throwaway projection of the current facts found about 3,000 nodes, and 35 to 54 milestones over 25 tiers on the playthrough route of each raid plane.
- The wiki's views follow `publish-wiki-data-views` D1 to D3: a builder in `src/erenshor/application/wiki_lua/`, a declared `DataView` checked at generation, a repository module with `p.render`, and a template. The native identity catalog of `wiki generate-lua` labels identities that have no page of their own, such as character copies that share an article.
- The wiki runs MediaWiki 1.43 with Scribunto, TemplateStyles, and Gadgets, and no Mermaid or graph extension. The repository deploys its gadgets through `wiki deploy-interface`.
- A moodboard of 18 references (attunement and flagging charts, puzzle dependency and lock-and-key graphs, randomizer spheres, tech trees, and the two compendiums) is at `/tmp/erenshor-progression-moodboard/index.html`. It stays untracked, because its images belong to their sources. Its common lesson: lead with meaningful access milestones around one goal, keep the exact requirements one step away, and do not draw every raw requirement.

## Goals / Non-Goals

**Goals:**

- A readable route to any target, built from the shared graph without a second derivation of requirements.
- A text rendering that stands on its own, and an explorer that adds navigation without changing the facts.

**Non-Goals:**

- A checklist of a reader's progress. It needs its own semantics for characters, account state, alternatives, and consumed items, and becomes its own change.
- Computing requirements in Lua or JavaScript. Both only render what the data module holds.

## Decisions

### D1. A wiki view with a drawing gadget

The graph is a view in the sense of `publish-wiki-data-views`: `Module:Erenshor/Data/Progression` (bot-owned), `Module:Erenshor/Progression` and `Template:Progression graph` (repository-owned). A repository gadget draws the graph in the container that the view renders.

Alternatives considered:

- A route of the map site. Rejected: players read the wiki, and the maintainer chose the wiki.
- A window of the Adventure Guide. Rejected: C# interface work, a mod release, and a reader who has to run the game.
- A drawn image or Mermaid text on a page. Rejected: wiki.gg has no Mermaid extension, and a picture goes stale with each build and cannot hold the graph.

### D2. The compact data module

The builder reads `ProgressionRepository` and validates its node, way, and need rows through the declared `DataView` before serializing `Module:Erenshor/Data/Progression`. It retains every node with a way or referenced by a need, including a referenced node without a way. Conditions use the wording table shared with `erenshor progression`, and native identities supply names and optional pages. Generation fails when wording or an identity is missing.

The module uses one table per node with its kind, tier, milestone flag, name, optional page, first-way index, and an array of packed way strings. Each way string is a JSON array of positional needs. JSON escaping preserves every optional value without allocating a Lua table for every need during `mw.loadData`. The generated module's header documents the field order, null handling, page sentinel, and first-way index. `_meta` records the default targets from dedicated planning slots and the source-depth limit. This changes representation, not which way the clean build selected.

The builder reports Lua and JSON bytes and rejects a module above the page budget. Source-row validation remains fail-closed before compaction. The module carries every node's label, so the gadget does not need the full link catalog.

### D3. Levels of detail

- Overview: milestones in the target's first-way closure, ordered by tier. Non-milestones forward their first-way dependencies.
- Detail: all ways of each reached milestone and every need on those ways. Alternatives are labelled "any one of" and the needs of a way "all of".
- Sources: dependencies below overview milestones expand to depth 6, with leaf labels retained at the limit. Sources beyond the first four and gate-free zone entrances appear in counted collapsible groups.

### D4. The view and the template

`{{Progression graph}}` takes `stablekey`. Without it, the view resolves the current page through `Link.pageKeys` for zones, quests, items, and characters, and shows an error with the keys when more than one entity matches. Without an entity on the page, it opens on the four raid planes recorded by the data module's dedicated planning-slot defaults.

The shared `Link.pageKeys` reads `Module:Erenshor/Data/PageKeys`, a small page-to-keys index generated beside `Data/Links`. It preserves the full catalog's page normalization, key order, and every identity variant without loading its image and entity records. Generation checks that every catalog key appears under its own page.

The view loads the compact progression module and decodes a way only when the text needs it. It renders a legend, the first-way overview as an ordered list by tier with each milestone linked, and each milestone's detail as nested lists. A node already shown is referenced, not repeated, and nested sources stop at depth 6. A key without data shows a message and adds `Pages with missing Erenshor progression data`.

The gadget container holds a hidden `pre` with a nowiki JSON payload, serialized through `mw.text.jsonEncode` from plain copies of the compact records touched by the overview and depth-limited detail, including boundary labels. The payload names its targets and nodes. Keeping JSON in text avoids MediaWiki's large-attribute limit. The text remains visible without the gadget.

### D5. The explorer gadget

`progression-graph` holds the drawing code and loads through a small default gadget, `progression-graph-loader`, only when the page holds the container.

- Layout: one column per tier, which the data already gives, so the layout needs no layering step. Nodes are ordered within a column by repeated barycenter sweeps. The first-way graph of milestones has no cycles, because each need of a milestone's first way has a lower tier.
- A way with several needs joins at a small labelled junction. Required needs are solid lines. Alternatives appear in the side panel, not as extra edges, so a line never means "one of several".
- Levels of detail follow D3. Expanding a milestone shows its ways and its source groups in place.
- The reader can search every node by name, switch between needs and unlocks (the reversed edges), pan and zoom, and filter to quests or areas. A filtered edge says how many steps it hides on the playthrough route.
- Every node is a focusable element with a label. Enter focuses it, and the arrow keys move to its neighbours.
- Colours come from the skin's CSS variables, so the graph follows the light and dark themes. Shapes and labels carry every meaning that colour carries.
- Every failure is caught and logged, and the text stays visible until the drawing is complete.

The graph model, expansion, filtering, and ordering are pure functions apart from the DOM code, with node tests beside `semantic-link-picker-core.test.js`.

Alternatives considered:

- A third-party graph library copied into `MediaWiki:` pages. Rejected: no dependency manager would track the copy, and the tiers already give the layering that such a library would compute.
- A canvas. Rejected: a canvas has no elements for the keyboard or for screen readers.

### D6. When to publish

The data, view, and gadget deploy only after the review of `derive-progression-requirements` (its task 2.5) lists no wrong step in the routes of the four raid planes and Secluded Sanctuary. That needs at least the hierarchy, barrier, and world state slices of `model-progression-mechanics`. Local checks can run earlier against the current facts.

### D7. Owners and write boundaries

| Artifact | Owner | Written by |
|---|---|---|
| `Module:Erenshor/Data/Progression` | bot | `wiki generate-lua` and `wiki deploy-repo-pages --include-generated-data` |
| `Module:Erenshor/Data/PageKeys` | bot | `wiki generate-lua` and `wiki deploy-repo-pages --include-generated-data` |
| `Module:Erenshor/Progression`, its testcases, `Template:Progression graph`, the tracking category page | repository | `wiki deploy-repo-pages` with the dependency, render, and drift checks |
| `MediaWiki:Gadget-progression-graph*` and their definition lines | repository | `wiki deploy-interface` under the interface account |
| The section of `Erenshor Wiki:Game Data` | repository | `wiki deploy-repo-pages` |
| `Progression Graph` and the walkthrough | people | the maintainer creates the first by hand, and the placement on the second is a guarded one-time edit after the review of `publish-wiki-data-views` D5 |

### D8. Failure handling, grouping, and rollback

- Generation fails closed on the checks of D2, naming the module, node, way, and fact.
- The view shows a message and a tracking category for a missing entity. The gadget never hides the text before it has drawn.
- Commits group by unit: the data view, the text view, the gadget, and the documentation.
- The data module, the view, and the template roll back through the manifest of their `deploy-repo-pages` run, the gadget through `wiki rollback-interface`, and the placement through the guarded-edit manifest. A new page stays after a rollback and needs an administrator to delete it.

## Risks / Trade-offs

- The subgraph JSON could be large on the explorer page. The container holds only the target's subgraph, and generation reports the sizes.
- Rendering a raid's route costs Lua time and memory. Task 1.3 measures the heaviest page against a quarter of the live limits.
- Tiers could read as advice. The legend and every tier label say that a tier is a playthrough order.
- The layout code is our own. Tiers remove the hard part, and the rest is small, pure, and tested.

## Migration Plan

1. Land the data view and the text view, and check them in the local wiki with the real data module.
2. Land the gadget, and check it in a browser in both themes and with the keyboard.
3. After D6 holds, deploy after a dry run and approval: the shared page index before its Link reader, the progression data module, the view module, the template, the category page, the guide section, then the gadget.
4. The maintainer creates `Progression Graph`. The walkthrough placement follows the review of `publish-wiki-data-views` D5.

Rollback follows D8.

## Open Questions

- The final title of the explorer page and the pages that place the template. The maintainer decides them at publication. Neither changes the view.
- How to rank a first way that the designers did not intend. The overview follows the clean build's persisted first way without consumer ranking. Chazz Pillot drops Mold: A Strange Figurine every time he dies, ahead of the reward of A Note for C. Pillot, so that first way skips A Hermit's Request. The ways level shows both. A reviewed ranking rule belongs in the shared graph, such as ranking a friendly NPC's death after other ways. The review of task 2.5 of `derive-progression-requirements` names the cases. The auction-house source of Spell Scroll: Invoke Storm also has tier 0, ahead of Tempestalia, Ring of Storms at tier 6, although Tempestalia is the designed route to Evadne's rain.
