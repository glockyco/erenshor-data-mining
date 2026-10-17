# Design

## Context and Evidence

This is a design-only change. The clean database was queried read-only. No game, database rebuild, local wiki write, or publication was needed.

The current acquisition paths differ in observable structure:

| Executing path | Evidence | Consequence |
|---|---|---|
| `application/processor/writer.py:1501-1555` | `character_fact_sources` selects encountered copies or reviewed dynamic fallback copies. `vendor_offers` retains copy and unlocking quest. | Reuse these rules. Display representatives cannot contribute facts merely by representing a group. |
| `infrastructure/database/repositories/characters.py:528-579,648-731` | Drop rows take a group maximum. Vendor and dialog rows select wiki representatives and turn quest keys into prose. | Distinct copy outcomes and typed gates cannot be recovered by consumers. |
| `infrastructure/database/repositories/items.py:663-698,700-751,890-938` | Obtainability lists eight source families. Craft and item-use queries aggregate slots or mechanisms. Auction selection reduces all routes to one boolean row. | The source lists and the obtainable flag do not have the same domain. |
| `infrastructure/database/repositories/zones.py:106-181` | Mining and fishing source queries require a matching wiki-visible zone. | A factual source can disappear because its location has no wiki page. |
| `application/wiki_lua/items.py:244-288,410-463` | A wiki-specific assembler selects acquisition kinds and emits prose conditions, with no location relation or copy identity. | It is not a reusable acquisition contract. |
| `application/wiki/generators/pages/entities.py:288-370` | Article sources use a second query set and choose only the first rewarding mold's ingredient list. | A nonempty crafting field can hide other recipes. |
| `maps/src/lib/database.base.ts:1251-1638` | Map SQL selects the same families again, aggregates drops, loses vendor quest gates, and adds its own treasure locations and item alias rule. | Presentation visibility and factual selection are coupled. |
| `application/guide/edge_builder.py:496-579,752-802` | Graph sources are reselected. Day and night fishing can become one maximum chance. | Time-specific outcomes can be lost. |
| `application/guide/node_builder.py:177-250` and `mod_writer.py:807-915` | Background sources are selected separately. Ordinary serialized source rows do not copy edge chances or quantities. | Presence checks cannot catch payload fact loss. |
| `application/sheets/queries/drop-chances.sql:4-69` | Sheets reads raw clean source families independently, including every loot copy. | It can disagree with encountered-source selection. |
| `tests/data/test_item_source_rows.py:20-46` | Coverage checks only selected kinds and whether a second query has any rows. | Wrong identities, omitted variants, conditions, probabilities, and quantities still pass. |
| `infrastructure/database/repositories/quests.py:164-183` | Requirement rows take a maximum across quest variants and prefix an already stable quest key. | Preserve variant identity and validate keys. The migration must remove the extra prefix, not preserve it as compatibility. |

Read-only counts from the inspected clean database: 1,537 items, 6,391 loot rows, 586 vendor offers, 2,400 auction routes, 240 furniture placements, 123 possible treasure placements, 438 gate atoms, one conversion, and four fishing bonus records. These are evidence of populated input families, not future fixed acceptance counts. All `src/` paths in the table are relative to `src/erenshor/` except the map path, which is relative to `src/`.

The WaterListener map-key defect and guide chance/time serialization losses are assigned corrective work, not assumptions the future cutover may preserve. `src/Assets/Editor/ExportSystem/AssetScanner/Listener/WaterListener.cs:76-106` synthesizes four map keys and combines the bonus in the raw water rows. The reported clean-data consequence is 184 invalid map-key rows. Integrate the assigned water/mining and guide fixes before freezing provenance fixtures. Preserve native day/night pools, null-slot denominators and actual `GameManager.Maps` identities. Explicitly label native versus final per-catch probability stages so a global replacement roll is not added twice.

Loot host eligibility is another assigned producer correction. `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/LootTable.cs:79-87` returns before any loot rolls if the host is missing, has `DestroyOnDeath`, or is an NPC with `DoNotLeaveCorpse`. The verified affected population is 38 serialized loot rows across four exported hosts. Canonical input completeness must account for these as non-acquirable evidence, not promote every serialized table to player access. Reuse the corrected producer's actual lootable-host predicate for explicit, common-world and special-world roll eligibility. Do not exclude summons as a class. Summoned wolf, warhound and fallen warrior are positive controls with both flags false.

## Goals and Non-Goals

Every acquisition and use fact has one selector, explicit identity and units, and an accountable path to each output. Surface grouping must not erase factual alternatives. This does not introduce a generic cross-surface renderer, a new gameplay gate evaluator, or a wiki query engine.

## Decisions

### 1. Processor ownership and one database boundary

`application/processor/writer.py` remains the only DDL owner. Add `application/processor/item_provenance.py` as the only acquisition/use selection builder. Run it after items, characters, deduplication, spawns, treasure, quests, code-fact mechanics, and gates have been inserted, before finalization. Validate and publish the complete database atomically using the existing processor staging boundary. The builder reads source tables once and materializes the contract, avoiding repeated per-item selection in every output.

The authoritative relations are:

- `item_acquisitions`: `acquisition_key`, `item_stable_key`, `kind`, `source_stable_key`, `source_group_key`, `source_copy_stable_key`, `variant_key`, `mechanic`, `player_access_state`, `probability_kind`, `probability_min`, `probability_max`, `probability_basis`, `probability_stage`, `quantity_min`, `quantity_max`, `quantity_kind`, `expected_quantity`, `count_distribution`, and `guarantee_scope`. `player_access_state` is `verified_player`, `unconfirmed_player`, `internal_only`, or `non_acquirable`. `probability_stage` separates `native_pool` evidence from `final_acquisition` rates, preventing double counting of replacement mechanisms. Mechanic and UI sources have their own stable source identity. Source keys are nullable only for genuinely global/random mechanisms, never because a link page is absent.
- `item_acquisition_conditions`: acquisition key plus the existing gate/group/atom algebra, typed references and numeric bounds. All gates hold, and within a gate any group holds when all its atoms hold. Add typed day/night, actor-level, quality, zone-use, and route predicates where acquisition facts need them. Do not encode these as English strings. Copy, placement, and route scope remain explicit so alternatives cannot accidentally become conjunctions.
- `item_acquisition_locations`: acquisition key, location key, relation (`fixed`, `spawn`, `possible_treasure`, `interaction`, `mechanic_zone`, or `unlocated`), scene/zone references, placement key, coordinate reference, gate scope, and eligible player-level interval. An unlocated relation carries no fabricated coordinate. Broker interaction locations describe access to an auction route, not guaranteed stock. Possible treasure locations remain per site, not a min/max envelope over unrelated eligibility ranges.
- `item_uses`: `use_key`, input item key, target key, kind, variant key, material slot, quantity bounds, mechanic and outcome identity. Attach typed conditions and locations through equivalent child relations. Crafting recipes and reward slots, quest variants and required slots, item conversion, smithing, quality offerings, and item-use zone restrictions remain separately addressable. Acquisition and use rows share mechanism identity where they are opposite projections of one operation.
- `item_provenance_evidence`: owner key, input relation, and complete input primary key. Multiple evidence rows are allowed for one semantic fact. Common-world summaries retain contributing copy outcomes here, not as individual dropper acquisitions.
- `item_dispositions`: stable item identity, disposition (`current`, `removed`, `unobtainable`, `unused`), reviewed reason/evidence, and current/former page relations. Preserve records for removed identities absent from `items`. Unknown acquisition coverage is a build error or explicit unresolved coverage, never evidence of removal.
- `item_provenance_meta`: schema version, source game build, and input digests including reviewed lifecycle input.

Use deterministic tuple-derived keys from input identities, slots, mechanism and variant identifiers. Names, page titles, display representatives, and probability values are not identities. Exact schema column types and indexes follow writer conventions. Index item keys, source/copy keys, child owner keys, and reverse use targets. Do not materialize full Cartesian products of acquisition rows and locations.

`infrastructure/database/repositories/item_provenance.py` exposes `get_acquisitions(item_key)`, `get_uses(item_key)`, `get_disposition(item_key)`, `get_player_access(item_key)`, `iter_acquisitions()`, and `iter_uses()`. Immutable domain records in `domain/value_objects/item_provenance.py` mirror the typed contract. `get_player_access` distinguishes verified, unconfirmed and no verified path. Existing boolean obtainability callers can return true only for a satisfiable verified-player acquisition, and must not describe false as proven unobtainable. TypeScript reads the same persisted relations. Python and TypeScript codecs validate the same schema version. There is no wiki-provenance service that other surfaces must import.

### 2. Full acquisition and usage domain

The selector covers explicit character loot, common-world substitution, special world pools, vendor stock including quest unlocks, dialog gifts, quest rewards by variant, every recipe reward slot, item-drop pools, spell-created items, scripted item conversions, mining, day/night fishing, fishing bonus replacement, auction routes, placed item bags, starting class inventory, UI grants and non-world mechanic transfers. UI and mechanic sources must not be coerced into vendor or dialog identities. Quality changes and special smithing operations remain typed uses/outcomes, not invented new named items. Input slot or pool distinctions remain even when the same item repeats.

No new probability is inferred. Percent values stay percent. Store basis such as per kill, per catch, per node, per use or listing opportunity. Distinguish exact chance, bounded chance across specified copies, unknown, and not applicable. A guaranteed pool roll does not mean the individual item is guaranteed. Preserve guaranteed-roll count, expected count and count distribution separately. Preserve zero probability as evidence with a non-acquirable disposition instead of promoting it to a source. Unknown quantity is not silently one. Fixed one can be supplied only where the shipped mechanic or input schema establishes it. Conditional formulas remain structured operands, not precomputed unconditional chances.

Player-access evidence is independent from lifecycle. A source used only by a simulated player or seeded in a UI is not automatically obtainable by the player. Preserve unresolved transfer paths as `unconfirmed_player` and proven internal-only use as `internal_only`, without hiding either from the audit. Only verified player paths feed affirmative obtainability and actionable navigation. The page may explain unresolved/internal use with explicit wording. Failure to resolve an optional research question is not permission to fabricate a route or mark an item removed.

Known non-world evidence must be covered by implementation fixtures and export/code-fact work:

- `item:tmog - hideslot` is Transmog - Hide Slot, identified by `Resources/items/TMOG - HIDESLOT.asset:15-16`. `ReplenishTMOGHide.cs:7-14` replenishes `GameData.Misc.TMOGHIDE` in its item icon to quantity one, and `ItemIcon.cs:816-918` handles the cosmetic-slot exception. Model the unlimited CosmeticPanel token as a UI grant with transfer/replenishment semantics, not as stock.
- `item:gen - box of portals` is Box of Portals, identified by `Resources/items/GEN - Box of Portals.asset:15-16`. `PlanningTableUI.cs:35,58-95` exposes and updates the Portal icon. The seeded Portal item and normal ItemIcon transfer path require runtime confirmation before being advertised as a verified player source. Preserve the candidate mechanic source as unconfirmed.
- `item:aura - arcanism` is Stone of Arcanism, identified by `Resources/items/AURA - Arcanism.asset:15-16`. `SimPlayer.cs:3778-3798,5193-5238` carries simulated equipment and its aura slot. Preserve internal equipment-generation evidence separately from the unconfirmed player-transfer question, and require the implementation evidence record to trace the specific item through generation. Do not assert a player source or a reviewed unobtainable lifecycle state.

The game script paths above are under `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/`. Resource paths are under that project's `Assets/`. This design did not run the game. Runtime confirmation belongs to an approved investigation that keeps sound off and shuts the game down normally afterward.

### 3. Identity, copies, locations and conditions

Reuse `character_fact_sources` and `vendor_offers` as the encountered-source rule. Preserve each contributing `source_copy_stable_key`. Select a wiki/map display representative later using existing visibility metadata, and never substitute its loot, stock or dialogs. Reviewed dynamic sources with no known placement stay present and unlocated. A group with encountered copies cannot inherit facts from its unused backup copy.

Item stable keys remain distinct even when pages match. The map may carry hidden variants to exactly one visible page representative, as it does now, but each row retains the originating item key and acquisition key. Multiple visible variants stay separate. No source is merged merely because display names match.

Apply `gate_conditions` and `target_entries` without changing their Boolean or entry semantics. Reliquary furniture sources and completion interactions retain furniture item, room slot, and room-furnished gate per placement. Do not let one unconditional copy erase a gated copy's identity. Treasure retains chest identity, player eligibility, and every possible site's relation. Common-world swap-only rows become one global source per item with its supported range, while rows also bearing own-table flags remain named sources. Retain special-world pool identity even if two pools have equal chances. Auction `direct`, `replacement`, and `gear_surplus` routes retain separate SimPlayer/player bounds and random-stock semantics. Never give them a fixed price or a listing probability absent from input evidence.

### 4. Lifecycle integration without two authorities

Move the neutral loading/validation of `content-lifecycle.json` out of the wiki application boundary into shared input handling when implementing this change. Keep that reviewed file as the human-owned source, not a second editable database authority. Resolve its stable-key records and rename/split relations during the clean build. Page-only notices that cannot be linked to an item remain wiki page records and must not be guessed into an item disposition. Wiki lifecycle rendering and map/guide obtainability read the same resulting item disposition. Existing administrative retired-page writes still use guarded manifests. Missing sources do not imply removed or unused content.

### 5. Consumer cutover

| Reader | Required migration |
|---|---|
| `repositories/items.py` | Replace `is_item_obtainable` and spell/skill obtainable-item source predicates with canonical acquisitions and dispositions. Remove old item acquisition/use selectors after all callers migrate. Keep entity/stat queries. |
| `repositories/characters.py`, `zones.py`, `quests.py` | Source/loot/vendor/quest/material row methods become projections of canonical facts or are removed with their callers. Character loot pages, vendor stock views and zone lists use reverse indexes, not raw source selectors. |
| `wiki_lua/items.py`, `wiki_lua/generation.py` | Remove provenance repository protocols and `build_item_sources_by_item`. Serialize canonical typed records and origin IDs to new-version module titles, without condition wording in Python. |
| `wiki_lua` vendor stock/world-drop views | Reuse canonical stock, furniture conditions and pool facts. Keep wiki-specific view grouping. |
| `wiki/generators/pages/entities.py`, `sections/item.py` | Until item conversion, format canonical sources through the legacy parameter renderer. Enumerate every recipe, not the first mold. Transitional text formatting is not another source selector. |
| `maps/src/lib/database.base.ts` | Replace raw acquisition unions in `getItemSources` and character loot projections. Carry origin IDs, typed gates, rates, quantities and location relations through map source row types, provider and popups. Sources without coordinates remain listed and linked. |
| `guide/node_builder.py`, `edge_builder.py`, compiler and `mod_writer.py` | Build acquisition edges/background sources from canonical records. Carry acquisition IDs and variants through edge deduplication, compiled sites and serialized JSON. Preserve day/night chances, quantities, route identities and placement gates. Ranking/navigation may order sources but must not reselect them. |
| `sheets/queries/` | Source/obtainability SQL reads canonical relations. Detailed contributing outcomes may be shown via canonical evidence, without pretending substitution rows are explicit droppers. Keep raw numeric values until formatting. |

The same-cutover search must cover imports of `SourceInfo`, all old source repository methods, raw source table queries, spell/skill obtaining lists, character popup loot, and non-item views. Keep low-level source tables only where they remain producer inputs. Delete obsolete source-selection tables, views and mixed presentation/provenance fields after their maintained callers move. Do not retain schema compatibility solely for unknown consumers. Publishing the database URL is a separate invariant from retaining obsolete schema.

### 6. Coverage is a conservation invariant

Each adapter emits a build-time coverage manifest keyed by acquisition/use ID and originating item. Each fact dimension is either preserved, represented by a reversible grouped row with member IDs, or explicitly not presented for a documented surface reason. A source without a marker is still represented as an unlocated source, not omitted. Visibility can hide an entity from a surface but must record that disposition. Unsupported kinds, unexpected dispositions and lost mandatory dimensions fail generation/build.

Coverage manifests and anti-joins are offline generation/test artifacts, not runtime publication data. Do not add diagnostic coverage rows, instrumentation, allocations or per-frame validation to live C# source ranking, navigation or rendering hot paths. Runtime payloads carry only the identity and factual fields their real consumers require. Contract tests inspect those payloads offline. Publication approval and browser/game acceptance remain separate gates from fact-contract validation.

Independent fixtures and input-to-contract anti-joins establish completeness. Consumer-to-consumer equality alone is insufficient because all consumers could omit the same input. Compare identity sets and typed values before formatting, not rounded strings or row counts alone. Assert positive control counts for every populated source family. Include fixtures for repeated reward slots, same-name different keys, copy-specific loot rates, default classes, missing wiki pages, all auction routes, disjoint treasure intervals, furniture gates, unknown locations, common-world mixed flags, exact/unknown/zero rates, and lifecycle states. Mutation tests remove a condition, quantity, probability, location, source ID or whole kind and require the coverage check to fail.

## Verification and Precise Test Homes

Extend `tests/data/test_item_source_rows.py` from nonempty checks to complete cross-output identity/dimension coverage. Extend `tests/data/repositories/test_items.py`, `tests/data/test_common_world_items.py`, `tests/unit/application/processor/test_item_mechanics.py`, and add isolated provenance-builder and codec fixtures. Extend `tests/unit/application/wiki_lua/test_items_module.py`, guide `test_compiler.py` and `test_mod_writer.py`, map `map/search/item-source-provider.test.ts`, and `tests/contract/test_sheet_queries.py`. Add full clean-data input anti-joins with positive controls. Run narrow tests once after implementation, then `uv run erenshor test ci`. Build/preview the map via its CLI and inspect `/map`, a zone page, conditional and unlocated results in a browser. Coordinate guide payload and in-game gate acceptance with its persistent owner. No Adventure Guide release is in this scope.

## Rollout, Failures and Approval

Land schema/selector, complete adapters, and removal as one coherent cutover unit after fixtures are prepared. Temporary comparison code may run in tests during development but cannot remain a production dual-reader fallback. Build into isolated output from a worktree-owned database clone. Refuse unknown schema or unresolved mandatory source references instead of silently reading legacy queries. Publish artifacts generated from the same database/build identity. Keep the last published database and output bundle for rollback. A rollback restores a matching bundle, not mixed old/new readers.

This change does not authorize any live writes. Wiki, Sheets, map publication and guide integration use their owning workflows. Wiki and Sheets writes require a separate complete dry run, review and explicit approval. Item template conversion waits for this change's coverage gate. Keep the published database URL, but remove obsolete schema after the clean cutover. No game is launched by planning. Any future verification that launches one must use regular saved shutdown and leave no game process running. Sound stays off.

## Implementation Handoff and Ownership

Implementation is already approved in intent. Do not stop to reconfirm the backlog. Publication approvals remain separate. Start the apply work in an isolated worktree after `WorktreeIsolation` lands, with worktree-owned APFS database clones. Do not edit the main checkout's active roster/class/quest view paths while those changes own `wiki_lua/generation.py` and repositories.

Use one integration owner for shared files and a frozen interface before adapter work:

| Slice | Exclusive edit ownership | Interface and boundary |
|---|---|---|
| Contract and integration | `processor/writer.py`, new `processor/item_provenance.py`, new domain records and provenance repository, shared lifecycle input, existing repository migrations, `wiki_lua/generation.py` | Own schema/version, immutable record types and builder invocation. Integrate current views first. Deliver a small fixture database and codec records before adapters start. No sibling edits these shared files. |
| Wiki adapters | `wiki_lua/items.py`, view serializers, item article assembly/section formatters and their tests | Accept canonical record/repository inputs only. Return required orchestration/repository edits to the integration owner. Do not add an independent selector or start article conversion. |
| Map adapters | `maps/src/lib/database.base.ts`, source row types/provider/popups and map tests | Read the frozen canonical relations. Preserve origin IDs, typed conditions and final probability stage. Request schema changes through the integration owner. |
| Guide adapter | Existing persistent guide owner's graph/compiler/serializer and real payload consumer paths | Reconcile gates and assigned chance/time fixes with that owner. Consume canonical records while keeping offline diagnostics out of live C# hot paths. No independent guide worktree edit or release. |
| Sheets adapter | Acquisition/obtainability SQL and query contract fixtures | Read canonical relations, preserve numeric values and source stages, and make no live spreadsheet write. |

Exact ordering:

1. Land worktree isolation and integrate active view work plus assigned WaterListener/mining and guide chance/time corrections. Freeze their actual output semantics, not their obsolete pre-fix behavior.
2. In the isolated provenance worktree, the integration owner defines the relations, `probability_stage` (`native_pool` or `final_acquisition`), schema version, domain records and repository signatures listed above. A final chance and its constituent native/global mechanisms cannot be counted as additive alternatives. Provide fixtures for every source family, gate algebra and access state.
3. Implement selector and independent input-to-contract coverage. Freeze keys/codec fields after reviewing positive controls. This work remains unintegrated while readers are incomplete.
4. Run wiki, map and Sheets adapter slices independently against that contract. Coordinate the guide slice through its existing owner. Any newly discovered missing field returns to the integration owner, who updates contract and fixtures once for all adapters.
5. The integration owner applies all shared repository/orchestration changes, removes old selectors and obsolete schema, and searches every callsite. No production dual-read fallback remains. Keep only true producer tables.
6. Run narrow checks once after the slices land, then CI and actual-host checks from the task list. Inspect the coherent final diff and integrate only the complete clean cutover. Offline fact coverage passing does not imply live publication is approved.
7. Start `convert-item-pages-to-data` against the integrated canonical schema. Its versioned-data, local render, production parse, canary rollback and broad conversion gates stay ordered as written. No parallel legacy acquisition selection is reintroduced during that conversion.

## Alternatives

A Python-only shared assembler was rejected because TypeScript and SQL consumers would still select sources independently. A single flattened SQL union was rejected because it cannot retain copy/variant conditions and location alternatives without destructive grouping or row explosion. A shared renderer was rejected because wiki infoboxes, map markers and guide navigation have different presentation responsibilities.
