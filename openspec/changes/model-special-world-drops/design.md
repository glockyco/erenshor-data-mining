## Context

See `proposal.md`. The relevant facts:

- `LootTable.InitLootTable` computes `num4 = ServerLootRate + num + LootBlessBonus` and then rolls each special drop independently (`LootTable.cs` lines 148–210). `ServerLootRate` defaults to 1, `LootBlessBonus` to 0, and `num` is 0.5 only for members of the top guild. At the default, `num4 = 1`.
- The mask roll is `Random.value < 0.001f && GM.DropMasks`, unscaled by `num4`, then `Random.Range(0, 100) > 1` picks a random entry of `Misc.Masks` (98 of 100 outcomes), else `Misc.MoloraiMask` (2 of 100).
- Code facts already extract `rate` and `min_level` for Sivak, molds, maps, XP potion, Inert Diamond, Planar Shard, Crystallized Balance, Planar, masks, Molorai Mask, and the demo-only Empty2 through `guarded_member_roll`. The clean `code_facts` table copies them. No consumer reads them. Essence of Amarion (`0.0045454544f`, no gate) has no fact.
- `min_level` is the literal of a strict `Level > N` check.
- `LoadScene.unity` holds the `GameManager` component (Sivak, WorldDropMolds with 11 entries, Maps with 4, XPPot, InertDiamond, PlanarShard, CrystallizedBalance, Planar, Empty2, `DropMasks: 1`, `DemoBuild: 0`) and the `Misc` component (Masks with 15 entries, MoloraiMask, EssenceOfAmarion). `AssetScanner` already opens every build-settings scene.
- Item sources reach consumers through `loot_drops` (character to item) and `item_drops` (item to item). Both carry a character or item as the source. A world drop has neither.

## Goals / Non-Goals

**Goals:** see the spec. Every item, chance, gate, and flag comes from the shipping build.

**Non-Goals:** loot-rate settings and guild or blessing bonuses. Pages state the default and do not model the multiplier. The Adventure Guide, per-character loot tables, and the "A Common World Drop" row are out of scope.

## Decisions

### D1. A scene listener exports the pools

A new listener handles the `GameManager` and `Misc` components in `LoadScene`. It writes one raw row per pool entry: `SpecialWorldDropItems(Pool, Position, ItemStableKey)`, where `Pool` is the serialized field name (`Sivak`, `WorldDropMolds`, `Masks`, `MoloraiMask`, …) and single-item fields have position 0. It writes the two flags to `SpecialWorldDropFlags(Name, Value)`. A null entry is skipped with a warning. The listener fails the export when either component is missing or appears twice, so that a moved component cannot silently empty the pools.

Alternative: hardcode the item stable keys in Python. Rejected. Pools change with game updates, and the project rule is data from the build, not curated lists.

### D2. Code facts carry every rule constant

- Add `loot.world_drop.essence_of_amarion` with `guarded_member_roll`.
- Add a scoped matcher `nested_branch_split` that binds exactly one `if` statement whose condition is a `Random.Range(a, b) > c` comparison and whose then and else branches add the configured members. It returns `range_min`, `range_max`, and `cutoff`. The mask split fact `loot.world_drop.mask_split` uses it with members `Masks` (then) and `MoloraiMask` (else). The scope is the `if` statement, so it does not collide with the `Random.Range(0, 10) > 8` common-item swap that blocked the method-wide `int_comparisons` matcher (the recorded `deferred` entry).
- Add `loot.world_drop.masks_gate` as a `node_shape` assert on the mask condition `Random.value < 0.001f && GameData.GM.DropMasks`. Unscaled masks are a semantic the clean build re-implements, so a change to the condition must fail loudly. The clean-build code carries the `# code-fact:` tags.

### D3. The clean build derives one row per item and roll

`process_special_world_drops` reads the raw pools and flags and the clean `code_facts`, and writes `special_world_drops(item_stable_key, pool, drop_probability, min_level_exclusive)`, with `drop_probability` in percent to match `loot_drops`:

- single-item pool: `rate × 100`;
- list pool: `rate × 100 × entries_of_item / pool_size` (an item listed twice gets twice the share);
- masks: `rate × 100 × (range_max − cutoff − 1) / (range_max − range_min) / pool_size`, and Molorai Mask `rate × 100 × (cutoff − range_min + 1) / (range_max − range_min)`;
- no rows for the Empty2 pool when `DemoBuild` is 0, or for masks when `DropMasks` is 0.

A pool whose code fact is missing, or a fact without a pool, fails the build. That prevents a silent gap when the game renames a field.

### D4. Consumers present a world drop as a sourceless source

- Wiki item pages: the item source assembly gains a world-drop source kind, rendered as "World drop: any enemy above level N (x% per kill)" or "any enemy" without a gate, beside the existing sources. The Lua item data gains a `worlddrops` list, and Cargo refresh registers the `world_drop` source type.
- Drop-chances sheet: a `UNION ALL` branch with source "World drop" and the gate in the level column.
- Map: `getItemSources` gains a `world` source kind without a marker. The item popup and the search result show it as a line, and an item with only world drops is no longer "obtainability unknown".

Chance formatting follows each consumer's existing drop formatting. Very small values (Molorai Mask ≈ 0.002%) keep enough significant digits to stay non-zero.

## Risks / Trade-offs

- [Visitors read the chance as absolute although server loot settings scale it] → Each output says "per kill at the default loot rate".
- [The Molorai Mask share depends on reading `Range(0, 100) > 1` as 98 of 100 outcomes] → The matcher exports the literals, the build computes the share, and a unit test pins the arithmetic for the current literals.
- [A world drop row inflates "obtainable" counts in search and stats] → Intended: these items are obtainable.

## Migration Plan

Export, code facts, and clean build first, with golden review (needs approval). Then consumers one by one: sheets, map, wiki. Deploy maps and sheets after browser and sheet checks. The wiki deploy is a separate decision after Category:Elites exists.

## Open Questions

None.
