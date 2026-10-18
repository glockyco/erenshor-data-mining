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

### D2. The data module

The builder reads `ProgressionRepository` and writes, for each node, one `node` row (`kind`, `tier`, `milestone`, and `label`, a native identity reference) and one `need` row for each need (`way`, `relation`, `need`, and the optional `quantity`, `slot`, `keywords`, `text`, `advisory`, and `unconfirmed`). A `first` field marks the first way. The `DataView` declaration checks types, markup, and identities. The builder words each `condition_key` from one table and fails on a key without wording. Mechanism, barrier, and state nodes take their labels from the same table when no catalog holds them.

The module carries labels so that the gadget does not need the link catalog. The builder reports the module's size and the size of its JSON next to the page budget. A module above the budget is split into shards under a new title (`adopt-data-backed-wiki` D1).

### D3. Levels of detail

- Overview: the milestones of the target's playthrough route, collected through first ways and ordered by tier. Non-milestones on the route contribute their milestone needs, so the overview stays connected.
- Detail: one milestone's ways, each with all of its needs, alternatives labelled "any one of" and the needs of a way "all of".
- Sources: the non-milestone needs of a way, such as the droppers of an item, with sources beyond the first four and gate-free entrances of a zone collapsed into counted groups.

### D4. The view and the template

`{{Progression graph}}` takes `stablekey`. Without it, the view resolves the current page through `Link.pageKeys` for zones, quests, items, and characters, and shows an error with the keys when more than one entity matches. Without any entity on the page, the view opens on the four raid planes, the zones that a dedicated planning-table slot opens.

The view renders a legend, the overview as an ordered list by tier with each milestone linked, each milestone's detail as nested lists below it, and a container with the target's subgraph as JSON (`mw.text.jsonEncode` over plain tables copied from the `mw.loadData` result) for the gadget. A node already shown is referenced, not repeated, and the nested lists stop at a depth of 6. A key without data shows a message and adds `Pages with missing Erenshor progression data`.

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
3. After D6 holds, deploy after a dry run and approval: the data module, the view module, the template, the category page, the guide section, then the gadget.
4. The maintainer creates `Progression Graph`. The walkthrough placement follows the review of `publish-wiki-data-views` D5.

Rollback follows D8.

## Open Questions

- The final title of the explorer page and the pages that place the template. The maintainer decides them at publication. Neither changes the view.
- Which way the overview follows when the first way is one that the designers did not intend. Chazz Pillot drops Mold: A Strange Figurine every time he dies, so killing him is its first way, ahead of the reward of A Note for C. Pillot, and the overview would skip A Hermit's Request. The ways level shows both. Before the overview lands, it needs a rule that comes from the data, such as ranking a way that kills a friendly NPC after the other ways of its node, and the review of task 2.5 of `derive-progression-requirements` names the cases.
