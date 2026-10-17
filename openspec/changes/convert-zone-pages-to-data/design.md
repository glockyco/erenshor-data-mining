# Design

## Context

See `proposal.md` and `adopt-data-backed-wiki/design.md` D1-D3. This is planning only.

Read-only inspection on 2026-10-17 found:

- `ZonePageGenerator.generate_pages` groups `ZoneRepository.get_all_zones()` by `wiki_page_name`, unions `get_zone_connections`, and chooses the first scene present in `zone-positions.json`. `zone.jinja2` emits an empty level, `Dungeon` from `is_dungeon`, otherwise `Zone`, and one `MapLink`. These defaults do not establish the meaning of populated live fields.
- `field_preservation.py:DEFAULT_PRESERVATION_RULES['Zone']` preserves every populated field except title. `Template:Zone` actually renders title, image/caption, type, level, maplink and connects. It adds Zones and, for literal Dungeon, Dungeons. `Template:MapLink` constructs the existing `https://erenshor.compendiums.org/map?sel=zone%3A<scene>` URL without Lua.
- A complete production `embeddedin` query with continuation handling found 43 main-namespace Zone users and 43 top-level roots. Reading all current revisions found exactly the seven legacy fields on every root. Types were 23 Zone, 16 Dungeon and 4 Raid. There were 39 populated level fields, 38 images and 6 captions. The fetched roots agreed with live. These are evidence counts, not fixed acceptance counts.
- The current clean database has 47 zone identities on those 43 pages. Three pages group scenes: Azynthi's Garden has Azynthi/AzynthiClear, Mysterious Portal has DuskenPortal/FernallaPortal/RipperPortal, and Shivering Tomb has ShiveringTomb/ShiveringTomb2. All 47 have map positions. Shivering Tomb's live map field deliberately labels and links both disconnected sections. Mysterious Portal's live field links only one of its three scenes.
- `Template:ZoneData`, `Module:Erenshor/ZoneData` and `Module:Erenshor/Data/Zones` were absent live. `Data/Links` exists. This observation is not permission to change a module's schema if the overview slice publishes it before this change.
- Six live Dungeon pages have `is_dungeon=0`: Mysterious Portal, Rockshade Hold, Lost Cellar, Prielian Cascade, Blooming Sepulcher and Secluded Sanctuary. Native atlas metadata explicitly marks Rockshade, Undercity and PrielPlateau Dungeon. Shipped `ZoneAnnounce` assigns the broad flag to `GameData.InDungeon`, whose only consumer is SimPlayer's task selection, not a public taxonomy renderer. Rockshade's prose calls it a dungeon. Blooming describes its underground areas and progression barriers. Sanctuary describes its ritual portal and multi-stage encounter. Prielian describes entry through a cave. Mysterious Portal describes three ritual-gated scenes. The full mismatch set was supplied to WikiOverviews, which owns the common producer and reasoned mapping. No article-local selector will reproduce that mapping.
- Prison's infobox says Zone while the live Zones overview groups it under Dungeons. Full production revision history resolves the ownership discrepancy: WoWBot created the Zone fallback at revision 39963, and WoWMuch's only later edit, revision 39992, added the map link without changing type. This is not an independently chosen editor infobox classification. The shared zone-type owner retains the reviewed Dungeon designation with that provenance rather than adding a competing article override.
- Bellwain's prose describes an event puzzle zone and its level is `Any`. The current placements are NPCs rather than a fixed hostile level range. Hidden Hills says `5-?`, while actual exported hostile copies include levels 1, 2, 4, 6 and 7 before initialization variance. Reliquary says `16+`, and its Fiend has base level 16. Its entry gate requires the Reliquary Key. The guard's exported `enter` dialog gives that key without a required quest. Shipped `NPCDialogManager.ParseText` and `NPCDialog.GetDialog` have no player-level check for that dialog path. These observations do not prove that `16+` means a recommendation or that its editor intended an access requirement.
- The remaining populated levels are numeric or ranged values, including portal-specific ranges and Blooming's `18-40`. Their pages generally do not define whether Level means enemy range, access or advice. Four blanks are Port Azure, Fernalla's Revival Plains, Underspine Hollow and Prison. Do not relabel all populated values as recommendations.
- Live route text has real editorial corrections. Shivering Step omits raw Island Tomb lines. Reliquary contains initially disabled portal lines whose activation conditions matter. Brax's plane has an empty connects field. Soluna has a disabled unresolved TestScene destination. Old raw line enumeration is not the authoritative usable route set.

Shared source interfaces were inspected in the overview worktree:

- `processor.entities.process_zones` writes `zones.zone_type`. Raid comes from the existing `_load_raid_bosses(raw).scenes`, never `raid_capable`. The shared mapping owns reviewed area designations with reasons. The intended vocabulary is Outdoor, Dungeon, Raid and Event, with no local inference in this slice.
- `ZoneRepository.get_zone_overview_data()` returns zones, eligible spawn candidates, directed lines and gate atoms. It filters actual `c.can_be_damaged` before deduplication and applies `c.level + cs.level_mod`.
- `wiki_lua.zones.ZONES`, `build_zone_rows(data)` and `write_zones_module` declare and serialize per-scene summary/connection/gate rows. Fixed levels use `npc_level_bounds`, including the level-one floor, the below-35 variance and group-encounter rule. The median is over distinct canonical-character/effective-level candidates, not spawn counts. Player-scaled candidates are flagged and excluded from fixed summaries.
- Summary fields are `zoneType`, optional `mapScene`, optional `levelMin`, `levelMedian`, `levelMax`, and `scales`. Connections retain `line` and `destination`. Gate atoms retain `line`, `gate`, `group`, `condition`, `ref` and optional `slot`. All gates on a line are required, groups within a gate are alternatives, and atoms within a group are jointly required. Disabled lines without activation and unsatisfiable gates are omitted by that producer.

The current shared main database does not yet expose `characters.can_be_damaged` or `zones.zone_type`. Conversion depends on the producer integration and rebuilt clean input. Computing a local substitute would bypass that correctness boundary.

## Goals / Non-Goals

Replace only the legacy infobox, preserve every other page byte and all editor content, and make factual updates data-only. Keep one infobox on a grouped scene page. Facts and gates must agree with the overview and other consumers.

Do not add a roster, duplicate a hand-written table, replace existing placed view calls, introduce Lua queries, change game flags, infer Raid from raid persistence, change the public database endpoint, alter companion URLs/protocols, or broaden the guarded deployment engine into a new type-specific implementation.

## Decisions

### 1. Ownership and field dispositions

`Template:ZoneData` invokes `Module:Erenshor/ZoneData`. A call requires an explicit zone stable key. Missing, wrong-kind, unknown or unresolvable group identities produce a concise visible diagnostic and `Category:Zone data calls with invalid identities`. Unknown parameters do not override facts and add `Category:Zone data calls with unsupported parameters` with the unsupported names. Missing required generated rows use `Category:Pages with missing Erenshor zone data`.

| Content | Owner and rule |
|---|---|
| Canonical title, zone type, enemy bounds/median, scaling and usable directed routes/gates | Shared Python/clean database producer. No article override or second selector. |
| Image and imagecaption | Editors. Retain exact value bytes, including full existing file markup and nested PAGENAME. Do not synthesize new screenshot names or replace editor uploads with generated renders. |
| Confirmed level advice | Editors. Only a reviewed value explicitly identified as advice becomes `levelnote`, rendered as a short contextual note, not another competing numeric level row. |
| Map presentation | Editors can retain `maplink` only as presentation of the complete generated map targets. Review the target set and labels before conversion. It cannot redirect an identity to another scene, omit an independently mapped member or invent an unsupported target. Free text not part of a map link is preserved exactly as `mapnote`. |
| Additional access or connection explanation | Editors. `connectionnote` retains exact reviewed notes beside the canonical directed connections. It does not add a fact to the route graph or turn an unusable line into a usable one. |
| Existing level/type/connects/maplink not yet classified | No automatic ownership transfer. Keep the original bytes unchanged in the unconverted article and migration snapshot, and block the batch until each value has an approved disposition. |
| Prose, categories, section headings, images outside the root, navbox, manual rosters and placed view calls | Editors. Never touched by infobox conversion or data refresh. |

The migration report accounts for every populated legacy field. A fact can be replaced with the shared fact only after its semantic comparison is reviewed. Exact current agreement is evidence, not proof that a person did not own the value. Where old generated publication/checkpoint bytes prove ownership, reuse that proof. Otherwise require the specific field disposition in the reviewed conversion plan. Remove only approved factual spans. Preserve every remaining note and label byte. Do not guess from string shape, strip all wikilinks, or maintain a page-name exception list.

There is no `type` override. A meaningful editor classification goes through the shared typed mapping with a reason and reaches all consumers. If the material meaning remains disputed, conversion waits. Do not show both Outdoor and Dungeon or relabel a preserved range as a recommendation to avoid the decision.

### 2. Shared data, narrow group relation and no replacement schema by default

Read the immutable `Module:Erenshor/Data/Zones` rows and `Data/Links` public identity/link interfaces. Do not serialize a second complete zone dataset. Its producer already owns summary and route semantics. If a required fact is missing, extend the shared producer and publish a narrow relation, or a new version only when an incompatible structure is actually necessary. Existing modules and readers remain available during rollback.

Add `Module:Erenshor/Data/ZonePages` only for the missing page relation. Declare its typed fields through the existing DataView/ViewField mechanism and generated header:

- One record per canonical page-root zone key with an ordered `members` list of zone keys. The first member is the stable root anchor chosen by sorted stable key on initial adoption. Every member must resolve to the same canonical page in Links.
- Optional member display labels and map scene strings come from shared identities/map presentation inputs. They are plain strings, not wikitext. Reuse complete existing fields instead of copying them into this relation. Labels that imply numbered sections require the reviewed scene-to-section correspondence.
- If the shared Zones `mapScene` field already validates against the actual map-position keys, no extra scene list is needed. Otherwise a narrow typed map target relation validates shared scene names against the required `zone-positions.json` input. A missing or invalid input fails generation instead of silently removing every map.

All members resolve the same page record. A call for a non-anchor member resolves the declared record through a generated direct index, not a name search. Duplicate calls for the same page group block migration. Generation validates complete mapped-scene coverage, same-page membership, deterministic order, catalog references, row types, field declarations and module size. No group membership or source facts are discovered by iterating the wiki catalog in Lua.

A single call represents the declared group, so the publishing delta makes that exception explicit. The renderer displays existing per-scene summaries separately inside the one infobox when they differ. It does not average medians, combine them into a new computed median or split the article into multiple infoboxes. Azynthi's alternate scene, all three portal scenes and both Tomb sections remain represented. Scene labels must not claim connectivity between disconnected sections.

### 3. Visitor-facing infobox and routes

Keep the familiar compact infobox surface. Type is the shared designation. Enemy levels are explicitly identified as enemy levels, with the shared median and scaling flag in the same compact surface. Do not show zero or a fabricated range when there are no fixed hostile candidates. Distinguish no fixed hostile enemies from missing export data and player-scaled encounters using the producer's explicit state. Name the build using the existing build-data path, not copied article text.

Use the existing map base URL and the case-sensitive scene names from validated targets. URL-encode the full `zone:<scene>` selector as one query value. Show every independently mapped group member with concise labels. Preserve approved editorial map labels/notes without duplicate automatic and manual rows. Preserve hand-written map images elsewhere in the page. Legacy `MapLink` is untouched.

Render outgoing usable lines only. Keep each route's own gate expression. Parallel entrances with different gates remain alternatives rather than forcing a free entrance to inherit another entrance's key. Do not infer return routes, reverse links, current availability or universal access from a destination name. Deduplicate display only when source member, destination and gate expression are equivalent. Group-internal routes are not presented as navigation to another article but remain available in data. Keep initially disabled routes that the shared producer proves can activate and explain their gates briefly. Do not restore inaccessible copied Island Tomb lines or unresolved disabled destinations. Long route expressions may use compact expandable infobox content, not a new view table, and must retain the full condition semantics.

### 4. Reuse native migration and deployment boundaries

The item integration supplies the native guarded edit/deploy/manifest/rollback path plus production comparison and limits. Reuse `GuardedPageEdit`, native guarded deploy and existing manifest rollback. Reuse the integrated comparison/limit services and extract only concrete neutral primitives needed for this zone policy with the integration owner. Do not copy `item_migration.py`, item companion/quality logic, HTTP code or a complete engine into a zone module.

Inventory current generated page membership together with every live legacy/new zone root, including nested and namespace-qualified calls. Persist titles, revisions, hashes, field bytes, matched identities, group members and outside-root hashes. Resolve an unkeyed root only through unique canonical page membership, not display-name guessing. Unexpected roots, duplicate groups, foreign roots, unknown fields, conflicting dispositions and incomplete group coverage block the whole conversion batch. Every page has a converted, already-converted or explicit blocked disposition.

Replace exactly the matched Zone root. Zone has no generated tooltip companions. `Zone Navbox` stays exactly where it is, as do manual rosters, notes, disabled-line comments, tables and existing view calls. No broad regenerated article is a conversion candidate.

Before every write the native path checks the reviewed base revision. A newer, deleted or recreated page conflicts and requires a new fetch/plan/comparison. Save all planned base revisions and original bytes before the first edit, checkpoint successful new revisions, and report partial failures. An incomplete pass must be rolled back or completed before another pass. Rollback restores the exact legacy root and complete original article and refuses later edits.

### 5. Full comparison and actual-host gates

The canary corpus covers every distinct field and group behavior, not only easiest pages: captions and editor image markup, Bellwain with no fixed hostile range, Reliquary's gated portals, Hidden Hills' incomplete level, Mysterious Portal's three scenes, both Tomb maps, Azynthi's alternate scene, a raid, an empty connection set and Shivering Step's excluded raw lines.

Use real generated production-scale modules in local MediaWiki, inspect the new infobox and its complete article in a browser, and capture screenshots before live approval. Check narrow and desktop layouts, image captions, long gated routes, all scene maps and unchanged neighboring prose/tables. A temporary copied article fixture is removed after host verification.

After new data/readers are available on production, parse every current zone article's legacy text and exact candidate with `action=parse`, under the actual title, against the real dependency set. Feature-selected checks and unresolved sandbox dependencies cannot approve conversion. Compare visible text, categories, map hrefs, semantic link targets, images/captions, route gates, per-scene enemy summaries and preserved outside-root text. Record and review every difference, including intentional type and range corrections. Do not normalize away a lost gate, map section or note.

Measure UTF-8 module size, Lua memory/CPU, expanded content, include size and expensive functions using actual host limits/reports, with at least 25 percent headroom under each exposed enforcing limit. Find the heaviest actual zone page by loaded group/route data and page content. Record unavailable metrics honestly. If a limit fails, change data loading or deterministic sharding and compare again, not hide members, gates or editorial text. Production parses must measure the candidate, not infer safety from small fixture results.

### 6. Cutover and deletion gates

New identities get compact ZoneData stubs, with Zone Navbox, only after the approved broad pass and its complete identity-group coverage checkpoint. An existing converted page with unchanged group membership returns its original article bytes on every refresh. Shared facts and new summary values update through data alone. A new member on the same grouped page updates the page relation without an article edit when its existing anchor remains valid. An anchor removal, page split/merge or true article membership change uses guarded template-call/lifecycle reconciliation and preserves all editor bytes. There is no default legacy fallback after zone cutover.

Remove `ZonePageGenerator`'s legacy fact/connection composition, `zone.jinja2`, Zone-only preservation and legacy semantic-validation expectations, and obsolete zone generator tests only after the full migration, browser/parse gates and exercised canary rollback. Keep useful map validation in its new shared owner. Search all callers before removing any repository method or shared formatter. Keep `Template:Zone`, `Template:MapLink`, `Zone Navbox` and their compatible dependencies. Keep the merge engine, Jinja and full-article paths still needed by unconverted types. The final type conversion, not this slice by assumption, removes remaining obsolete shared machinery. Keep native guarded deploy and rollback permanently.

Update the Game Data guide and ZoneData template documentation in place with compact calls, grouped scene behavior, editor image/caption/map/note inputs, how to report factual corrections, and tracking-category actions. Do not put inventory evidence or benchmarks in permanent guides. Any unused bot data page removal waits for no remaining live readers, a closed rollback window and a separately approved administrator deletion pass.

## Risks / Trade-offs

- The broad dungeon flag conflicts with visitor classifications. Resolve this once in the shared producer, with grounded reasons, rather than rendering inconsistent article overrides.
- Legacy Level is underspecified. Exact preservation and review can block conversion, which is preferable to inventing recommendations or dropping access/strategy information.
- Shared scene pages complicate identity accounting. A declared page relation preserves one infobox without an independent group selector or misleading median.
- Map presentation is editor-owned but map destinations are facts. Validate the full target set and preserve only reviewed presentation, rather than treating arbitrary URL text as canonical data.
- New modules must exist before production comparisons can resolve them. A dependency publication approval is separate from article-conversion approval.

## Migration Plan

1. Integrate the overview's authoritative fields, eligible-copy rules and directed gate semantics, rebuild isolated clean input, and resolve the observed classification conflicts in its shared mapping. Complete the concrete legacy-field disposition report. No ambiguous value is rewritten in this step.
2. Implement the narrow page relation, renderer, validation and native migration adapter. Run changed-path checks and the repository CI gate. Load real generated data into the local host, inspect and obtain screenshot review.
3. Review the complete repository-page dry run and obtain explicit approval. Publish only needed new data, then reader/template/style/category dependencies. Existing Zone users continue working.
4. Run complete production comparisons/limits against all actual pages. Obtain separate canary approval, convert representative pages and verify them, exercise exact manifest rollback, then reapply only through an approved pass.
5. Fetch fresh revisions, regenerate the complete report, resolve every field/identity/parse difference and obtain separate broad approval. Convert, verify complete live group coverage and demonstrate a data-only update leaves article bytes unchanged.
6. Activate compact stubs/membership reconciliation, remove only obsolete zone generation, and update existing contributor documentation. Keep old bytes and dependency pages for rollback until its window closes. Do not push, publish or launch the game as part of this planning assignment.

## Open Questions

These are editorial meaning questions, not permission to bypass shared selectors:

- Reliquary `16+`: the key-giving dialog and entry gate do not establish a level requirement, while the Fiend's nominal level is 16. Does the value express strategy for that one-time encounter, general advice, or a stale range? Preserve it unchanged until that meaning is approved. Do not label it an access gate.
- Bellwain `Any`: the page describes puzzles and exported placements do not establish a fixed hostile range. Is this an explicit all-level participation recommendation that should remain as concise editor advice? Do not turn it into a fabricated numeric enemy range.
- Hidden Hills `5-?`: the export contains lower-level hostile candidates, so this is not a complete current hostile range. Is any intended advice left to retain once the common summary is shown? Do not copy it into a new Recommendation row by default.

Other numeric/ranged fields require the actual shared-summary comparison and the specific approved field disposition before removal. Their absence of explanatory prose is not itself evidence of recommendation ownership. That review is part of the complete conversion report, not a permanent override mechanism.
