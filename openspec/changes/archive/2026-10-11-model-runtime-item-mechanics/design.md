# Design

## Context

The clean build already derives one rule-driven item source this way: `special_world_drops` takes its items from exported `GameManager` pools and its chances from code facts (spec `special-world-drops`). Code facts come in two modes. An `extract` fact writes values into `code_facts`. An `assert` fact pins a statement's shape, so `extract code-facts` fails when a game update changes it. A consumer that relies on an assert carries a `# code-fact: <id>` tag, and `test_code_facts_coverage.py` checks that each assert has one.

What each mechanic needs, from the shipped code:

| Mechanic | Data the game serializes | Rule only in code |
|---|---|---|
| Candlekeeper mold | `Chessboard.Candlekeeper` and `Chessboard.ReplaceStatue` are `Item` fields on a scene component, not exported today | consuming the figurine adds `ReplaceStatue` and spawns the boss |
| Time Stone gate | none; the item ID `2936548` and the scene names are literals | in `ShiveringTomb2` and `StowawayPortal` the stone returns to the inventory |
| Flame Well offering | none; the stone IDs `23431650` (Sivakrux) and `340104` (Offering Stone) and the NPC name are literals | equal stone counts and one equipment piece; success at 40 per stone pair plus 8 per improvement level above Standard (out of 100); Blessed on success, Ascended at a further chance of the improvement bonus plus 5 per stone pair when the piece was improved |
| Fishing maps | `GameManager.Maps`, already exported as the `Maps` pool of `SpecialWorldDropItems` | one catch in 20 is replaced by `Maps[Random.Range(0, 4)]` |

## Goals / Non-Goals

**Goals:**
- The clean database holds each mechanic as rows that `publish-wiki-cargo-data` task 5.4 can map to `ItemSources` and `ItemUses` without reading game code.
- Every item comes from exported data or from an ID that a code fact pins. Every rule constant is pinned by a code fact, so a changed game build fails extraction instead of producing stale rows.

**Non-Goals:**
- Cargo columns, `SourceType` and `UseType` values, query templates, and article text.
- The Chessboard figurines other than the Candlekeeper.
- Modeling the Time Stone's effect elsewhere (resetting respawn timers); only its zone gate is in scope.

## Decisions

**D1. Assert facts with tagged consumer constants, not new extract matchers.** The rules bind to `if` conditions and literal arguments that the existing `node_shape` and `statement_shape` matchers can pin exactly. The processor carries the same literals, tagged with the fact ID, the way `treasure.py` and the Adventure Guide's fishing node already do. A new extract matcher for each shape would add analyzer code with one caller each. Item IDs that appear only as literals (Time Stone, Sivakrux, Offering Stone) are pinned the same way and resolved to stable keys through `items.id`; the build fails if an ID resolves to no item.

**D2. Export the Chessboard's item fields as data.** A new raw table holds one row for each `Item` field of each `Chessboard` component: scene, field name, item stable key. The exporter owns the table. The Candlekeeper conversion reads the `Candlekeeper` and `ReplaceStatue` rows, so a game update that swaps either item needs no code change. The other figurine rows are exported because the listener exports the component's item fields as a whole, and cost nothing.

**D3. One clean table per mechanic shape.** Each table says what the mechanic does, so 5.4 maps it without reinterpretation:
- `item_conversions`: input item, output item, the zone where it happens, and the mechanic name. One row: the Candlekeeper figurine yields its mold at the Chessboard.
- `fishing_bonus_catches`: item and chance per catch in percent. Four rows, one per map piece, each 1/20 × 1/4 = 1.25%. The pieces are the first four entries of the exported `Maps` pool; the build fails if the pool has fewer than four entries.
- `item_zone_restrictions`: item, zone, and outcome. Two rows: the Time Stone returns unused in Shivering Tomb (2) and the Secluded Sanctuary.
- `quality_offerings`: the character that accepts the offering, the two required items, and the rule constants (chance per stone pair, chance per improvement level, the enhancement bonus per stone pair, the result and enhanced qualities). One row per Flame Well character; there are nine, eight of them in the Reliquary, where a well exists only if the player furnished its room.

A single generic "mechanics" table was rejected: its columns would mean different things per row, which moves the interpretation into every consumer.

**D4. Ownership and failure.** The Unity exporter owns the raw Chessboard table. The new processor module owns the four clean tables and runs in the clean build after items, zones, and characters. It raises, naming the fact or item, when a pinned fact is missing from `code_facts`, a pinned ID resolves to no item, the Chessboard export lacks a field, or the `Maps` pool is short. Like every other processor failure, this stops `extract build` with an error, and the clean database must be rebuilt after the fix. A game update that changes any rule fails `extract code-facts` first.

The Flame Well rows join characters on `npc_name` because `TradeWindow` compares the trading NPC's object name, and `NPC.Start` renames each NPC's object to its `NPCName`. The fact `npc.runtime_name_is_npc_name` pins that rename.

## Risks / Trade-offs

- Assert facts duplicate the constants in Python. The coverage contract test keeps the tag, and extraction fails on a change, so the copies cannot drift silently.
- The Reliquary Flame Wells exist only if the player furnished their room. Each row names its character, so a consumer can apply the Reliquary furnishing condition; task 5.4 must show those wells as conditional rather than as unconditional places.
- Rows appear only after a fresh export of the main variant, because the Chessboard table is new. The verification task runs the export.
