## 1. Code facts (commit: `feat(code-facts): pin the essence roll and the mask split`)

- [x] 1.1 Add `loot.world_drop.essence_of_amarion` (`guarded_member_roll`) to `src/tools/CodeFacts/specs/erenshor-facts.json`. Verify that `uv run erenshor extract code-facts` extracts `rate=0.0045454544` and `min_level=0`.
- [x] 1.2 Add the `nested_branch_split` matcher to `src/tools/CodeFacts/Matchers.cs` and the `loot.world_drop.mask_split` fact. Verify that it extracts `range_min=0`, `range_max=100`, `cutoff=1`, and that the matcher fails when the configured members are swapped between branches.
- [x] 1.3 Update `tests/data/test_code_facts_real.py` for the new facts. Verify with `uv run pytest tests/data/test_code_facts_real.py`. The `loot.world_drop.masks_gate` assert lands with its consumer in task 3.1, because the coverage test requires a consumer tag for every assert.

## 2. Export (commit: `feat(export): export the special world drop pools`)

- [x] 2.1 Read `skill://unity-export-system`. Add the `SpecialWorldDropItems` and `SpecialWorldDropFlags` records and a listener for the `GameManager` and `Misc` components, as design D1 describes. Verify with `uv run erenshor extract export` that the raw DB has 11 mold rows, 4 map rows, 15 mask rows, one row for each single-item pool, and the flags `DropMasks=1` and `DemoBuild=0`.

## 3. Clean build (commit: `feat(pipeline): derive special world drop chances`)

- [x] 3.1 Add `process_special_world_drops` and the `special_world_drops` clean table, as design D3 describes, with `# code-fact:` tags. Add unit tests for the pool share, a duplicated pool entry, the mask split arithmetic, the disabled-flag cases, and the failure for a pool without a fact. Verify that the clean DB lists Crystallized Balance at 0.05% above level 30.
- [x] 3.2 Run `uv run erenshor golden capture`. Show the golden diff to the user and commit it only after approval.

## 4. Consumers (one commit each)

- [x] 4.1 `feat(sheets): list special world drops`: add the world drop branch to `drop-chances.sql`. Verify the row count against `special_world_drops` with a dry run.
- [x] 4.2 `feat(maps): show special world drops in item search`: add the `world` source kind to `getItemSources`, the fixture, the search provider, and the item popup. Add a unit test for an item whose only source is a world drop. Extend the smoke test with that item. Verify in a browser that the Crystallized Balance search result shows the world drop.
- [x] 4.3 `feat(wiki): show special world drops on item pages`: add the world drop source to the item source assembly, the item section, the Lua item data, and the Cargo source types. Verify with `uv run erenshor wiki generate` that Crystallized Balance and Planar Shard list the world drop, and with the wiki-dev stack that the pages render.

## 5. Release

- [x] 5.1 Update the `code-facts`, `unity-export-system`, and `sheets-queries` skills and `docs/architecture.md` where they describe drop sources. Correct the Molorai Mask share in issue #274.
- [x] 5.2 Run `uv run erenshor test ci`. Deploy sheets, then build, check, and deploy maps. Leave the wiki deploy to a separate user decision.
- [x] 5.3 Close #274 with a summary. Archive the change.
