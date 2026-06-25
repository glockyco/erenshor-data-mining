---
title: Vithean Arena Round Export Implementation Plan
type: plan
status: implemented
created: 2026-06-17
parent:
---

# Vithean Arena Round Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export scripted Vithean arena round relationships so existing loot-drop data can be joined to the fight that awards each chest.

**Architecture:** Keep loot probability computation in the existing `LootTableListener`/`LootDrops` path. Add a focused Unity component listener for `VithArena` that records each round's input token, reward chest, and spawned enemy prefabs. The Python clean build copies those raw records into normalized clean tables for sheets/wiki/dev queries.

**Tech Stack:** Unity 2021.3 C# editor export scripts, SQLite raw/clean databases, Python clean DB processor, pytest.

---

## Planned commits

1. `feat(export): export scripted arena rounds`
2. `feat(pipeline): build arena round clean tables`
3. `test(pipeline): cover Vithean arena reward joins`

## File structure

- `src/Assets/Editor/Database/ArenaRoundRecord.cs`: raw parent table for each scripted arena round.
- `src/Assets/Editor/Database/ArenaRoundEnemyRecord.cs`: raw child table preserving each enemy slot, including duplicates.
- `src/Assets/Editor/ExportSystem/AssetScanner/Listener/VithArenaListener.cs`: scans `VithArena` components and emits raw records.
- `src/Assets/Editor/StableKeyGenerator.cs`: adds a stable-key helper for arena round rows.
- `src/Assets/Editor/ExportBatch.cs`: registers the listener under `arenarounds`.
- `src/erenshor/application/processor/writer.py`: creates and inserts clean `arena_rounds` / `arena_round_enemies` tables.
- `src/erenshor/application/processor/characters.py`: transfers raw arena round rows after character/item filtering.
- `tests/test_vithean_arena_export.py`: verifies the refreshed playtest data joins rounds to chest loot.

---

### Task 1: Raw Unity export records and listener

**Files:**
- Create: `src/Assets/Editor/Database/ArenaRoundRecord.cs`
- Create: `src/Assets/Editor/Database/ArenaRoundEnemyRecord.cs`
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/VithArenaListener.cs`
- Modify: `src/Assets/Editor/StableKeyGenerator.cs`
- Modify: `src/Assets/Editor/ExportBatch.cs`

- [ ] Step 1: Add raw record classes for `ArenaRounds` and `ArenaRoundEnemies`.
- [ ] Step 2: Add `StableKeyGenerator.ForArenaRound(scene, objectName, roundIndex)` with format `arenaround:{scene}:{object}:{round}`.
- [ ] Step 3: Implement `VithArenaListener` as `IAssetScanListener<VithArena>`.
- [ ] Step 4: Read `Coin1..Coin8`, `Coin1Fight..Coin8Fight`, and `AwardChests` through fixed arrays.
- [ ] Step 5: For each round with a coin, fight list, and matching award chest, emit one parent row and one child row per enemy slot.
- [ ] Step 6: Resolve items with `StableKeyGenerator.ForItem` and characters/chests through `CharacterStableKeyResolver.GetStableKey`.
- [ ] Step 7: Register the listener in `ExportBatch.RegisterListeners` under `arenarounds`.
- [ ] Step 8: Run `uv run erenshor -V playtest extract export` and expect raw `ArenaRounds`/`ArenaRoundEnemies` tables.

### Task 2: Clean DB tables and processor transfer

**Files:**
- Modify: `src/erenshor/application/processor/writer.py`
- Modify: `src/erenshor/application/processor/characters.py`

- [ ] Step 1: Write a failing processor test that creates raw `ArenaRounds`/`ArenaRoundEnemies` rows and asserts clean `arena_rounds`/`arena_round_enemies` contain only rows whose coin/chest/enemy keys survive item/character filtering.
- [ ] Step 2: Add clean schema tables with stable primary keys and snake_case columns.
- [ ] Step 3: Add writer methods `insert_arena_rounds()` and `insert_arena_round_enemies()`.
- [ ] Step 4: In `process_characters()`, load raw arena rows after `all_keys` is known and filter by valid character keys.
- [ ] Step 5: Filter parent rows by valid `CoinItemStableKey` and `AwardChestCharacterStableKey`; filter child rows by retained parent key and valid `EnemyCharacterStableKey`.
- [ ] Step 6: Run the processor test and expect pass.

### Task 3: End-to-end playtest verification query

**Files:**
- Create: `tests/test_vithean_arena_export.py`

- [ ] Step 1: Write a failing integration-style test against `variants/playtest/erenshor-playtest.sqlite` that asserts 8 arena rounds, round 8 enemy `Vitheo the Tactician`, and round 8 chest contains `Wakeweaver`.
- [ ] Step 2: Run the test before rebuilding clean DB with the new schema and expect failure due to missing `arena_rounds` table.
- [ ] Step 3: Run `uv run erenshor -V playtest extract export`, `uv run erenshor -V playtest extract code-facts`, and `uv run erenshor -V playtest extract build`.
- [ ] Step 4: Run `uv run pytest tests/test_vithean_arena_export.py -v` and expect pass.
- [ ] Step 5: Re-run the sendable query joining `arena_rounds -> arena_round_enemies -> characters -> loot_drops -> items` for sanity.
